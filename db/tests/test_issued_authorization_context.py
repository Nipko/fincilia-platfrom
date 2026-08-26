"""Capabilities persistentes contra PostgreSQL real, sin dobles de RLS."""

from __future__ import annotations

import os
import time
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from fincilia_api import repository
from fincilia_api.issued_contexts import (
    IssuedContextError,
    issue_context,
    revalidate_context,
    revoke_context,
)
from fincilia_contracts.tenancy import TenantContext

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
RUNTIME_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
HMAC_KEY = "issued-context-test-key-synthetic-only-32-bytes"

ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
ANA = stable_id("subject", "ana")


def _set_context(connection: psycopg.Connection, company_id: str,
                 subject_id: str = ANA) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                       (company_id,))
        cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                       (subject_id,))


def _tenant(connection: psycopg.Connection, company_id: str) -> TenantContext:
    current = repository.authorize(connection, ANA, company_id)
    if current is None:
        raise AssertionError("synthetic preparer must remain authorized")
    return TenantContext(
        subject_id=ANA, firm_id=current.firm_id, company_id=current.company_id,
        roles=current.roles, authorization_version=current.version,
        engagement_id=current.engagement_id)


class IssuedAuthorizationContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.created_contexts: set[tuple[str, str]] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            for company_id, context_id in sorted(cls.created_contexts):
                with connection.transaction():
                    _set_context(connection, company_id)
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM fincilia.issued_authorization_revocation "
                            "WHERE company_id = %s AND context_id = %s",
                            (company_id, context_id))
                        cursor.execute(
                            "DELETE FROM fincilia.issued_authorization_context "
                            "WHERE company_id = %s AND context_id = %s",
                            (company_id, context_id))

    @contextmanager
    def session(self, company_id: str = ESPIGA):
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with connection.transaction():
                _set_context(connection, company_id)
                yield connection, _tenant(connection, company_id)

    def issue(self, connection: psycopg.Connection, tenant: TenantContext, *,
              key: str | None = None, resource: str | None = None,
              expires_at: datetime | None = None):
        issued = issue_context(
            connection, tenant=tenant, purpose_code="processing_job",
            resource_kind="source_artifact",
            resource_ref=resource or f"artifact:{uuid.uuid4()}",
            idempotency_key=key or f"issued-context-{uuid.uuid4()}",
            expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=1),
            hmac_key=HMAC_KEY)
        type(self).created_contexts.add((tenant.company_id, issued.context_id))
        return issued

    def test_issue_use_and_revoke_are_audited_without_raw_reference(self) -> None:
        raw_reference = f"synthetic-artifact:{uuid.uuid4()}"
        with self.session() as (connection, tenant):
            issued = self.issue(connection, tenant, resource=raw_reference)
            current = revalidate_context(
                connection, tenant=tenant, context_id=issued.context_id,
                purpose_code="processing_job", resource_kind="source_artifact",
                resource_ref=raw_reference, hmac_key=HMAC_KEY)
            self.assertEqual(issued.context_id, current.context_id if current else None)
            self.assertTrue(revoke_context(
                connection, tenant=tenant, context_id=issued.context_id,
                reason_code="resource_retired"))
            self.assertFalse(revoke_context(
                connection, tenant=tenant, context_id=issued.context_id,
                reason_code="resource_retired"))
            self.assertIsNone(revalidate_context(
                connection, tenant=tenant, context_id=issued.context_id,
                purpose_code="processing_job", resource_kind="source_artifact",
                resource_ref=raw_reference, hmac_key=HMAC_KEY))
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT resource_ref_digest, idempotency_key_digest, "
                    "issuance_digest FROM fincilia.issued_authorization_context "
                    "WHERE context_id = %s", (issued.context_id,))
                digests = cursor.fetchone()
                cursor.execute(
                    "SELECT action, detail::text FROM fincilia.audit_event "
                    "WHERE resource_ref = %s ORDER BY occurred_at",
                    (issued.context_id,))
                audit = cursor.fetchall()
            self.assertIsNotNone(digests)
            self.assertTrue(all(len(value) == 64 for value in digests or ()))
            self.assertNotIn(raw_reference, str(digests))
            self.assertNotIn(raw_reference, str(audit))
            self.assertIn("authorization.context.issue", {row[0] for row in audit})
            self.assertIn("authorization.context.use", {row[0] for row in audit})
            self.assertIn("authorization.context.revoke", {row[0] for row in audit})

    def test_idempotent_replay_returns_the_same_context_and_conflict_dies(self) -> None:
        idempotency_key = f"issued-context-{uuid.uuid4()}"
        resource = f"artifact:{uuid.uuid4()}"
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        with self.session() as (connection, tenant):
            first = self.issue(connection, tenant, key=idempotency_key,
                               resource=resource, expires_at=expiry)
            second = self.issue(connection, tenant, key=idempotency_key,
                                resource=resource, expires_at=expiry)
            self.assertEqual(first.context_id, second.context_id)
            with self.assertRaisesRegex(IssuedContextError, "another request"):
                self.issue(connection, tenant, key=idempotency_key,
                           resource=f"artifact:{uuid.uuid4()}", expires_at=expiry)

    def test_an_authorization_version_change_invalidates_the_context(self) -> None:
        with self.session() as (connection, tenant):
            issued = self.issue(connection, tenant)
            resource_digest = None
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT resource_ref_digest FROM "
                    "fincilia.issued_authorization_context WHERE context_id = %s",
                    (issued.context_id,))
                resource_digest = cursor.fetchone()[0]
        # La prueba necesita el valor original para la revalidacion, asi que emite
        # uno estable separado. El digest de arriba confirma que no puede recuperarse.
        resource = f"artifact:{uuid.uuid4()}"
        with self.session() as (connection, tenant):
            issued = self.issue(connection, tenant, resource=resource)
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction():
                _set_context(connection, ESPIGA)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.authorization_version "
                        "SET version = version + 1, updated_at = now() "
                        "WHERE company_id = %s", (ESPIGA,))
        with self.session() as (connection, fresh_tenant):
            self.assertGreater(fresh_tenant.authorization_version,
                               issued.authorization_version)
            self.assertIsNone(revalidate_context(
                connection, tenant=fresh_tenant, context_id=issued.context_id,
                purpose_code="processing_job", resource_kind="source_artifact",
                resource_ref=resource, hmac_key=HMAC_KEY))
        self.assertEqual(64, len(resource_digest))

    def test_a_stale_snapshot_cannot_issue_a_new_context(self) -> None:
        with self.session() as (_connection, stale_tenant):
            pass
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction():
                _set_context(connection, ESPIGA)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.authorization_version "
                        "SET version = version + 1, updated_at = now() "
                        "WHERE company_id = %s", (ESPIGA,))
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with connection.transaction():
                _set_context(connection, ESPIGA)
                with self.assertRaisesRegex(IssuedContextError,
                                            "no longer valid"):
                    self.issue(connection, stale_tenant)

    def test_expiry_and_wrong_resource_fail_closed(self) -> None:
        resource = f"artifact:{uuid.uuid4()}"
        with self.session() as (connection, tenant):
            issued = self.issue(
                connection, tenant, resource=resource,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=1))
        time.sleep(1.05)
        with self.session() as (connection, tenant):
            for candidate in (resource, f"artifact:{uuid.uuid4()}"):
                self.assertIsNone(revalidate_context(
                    connection, tenant=tenant, context_id=issued.context_id,
                    purpose_code="processing_job",
                    resource_kind="source_artifact", resource_ref=candidate,
                    hmac_key=HMAC_KEY))

    def test_rls_hides_another_company_and_runtime_cannot_rewrite_history(self) -> None:
        resource = f"artifact:{uuid.uuid4()}"
        with self.session(ESPIGA) as (connection, tenant):
            issued = self.issue(connection, tenant, resource=resource)
        with self.session(ANDINOS) as (connection, other_tenant):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.issued_authorization_context "
                    "WHERE context_id = %s", (issued.context_id,))
                self.assertEqual(0, cursor.fetchone()[0])
            self.assertIsNone(revalidate_context(
                connection, tenant=other_tenant, context_id=issued.context_id,
                purpose_code="processing_job", resource_kind="source_artifact",
                resource_ref=resource, hmac_key=HMAC_KEY))

        for statement in (
                "UPDATE fincilia.issued_authorization_context "
                "SET purpose_code = 'shared_link' WHERE context_id = %s",
                "DELETE FROM fincilia.issued_authorization_context "
                "WHERE context_id = %s"):
            with self.subTest(statement=statement.split()[0]):
                with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with connection.transaction():
                            _set_context(connection, ESPIGA)
                            with connection.cursor() as cursor:
                                cursor.execute(statement, (issued.context_id,))

    def test_composite_engagement_scope_rejects_a_mixed_company(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction():
                # FORCE RLS tambien aplica al propietario: primero se resuelve el
                # engagement bajo su empresa y solo despues se cambia al alcance
                # donde se intentara insertar la combinacion imposible.
                _set_context(connection, ANDINOS)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT firm_id, engagement_id FROM fincilia.engagement "
                        "WHERE company_id = %s", (ANDINOS,))
                    foreign_firm, foreign_engagement = cursor.fetchone()
                    _set_context(connection, ESPIGA)
                    cursor.execute(
                        "SELECT version FROM fincilia.authorization_version "
                        "WHERE company_id = %s", (ESPIGA,))
                    version = cursor.fetchone()[0]
                    with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                        with connection.transaction():
                            cursor.execute(
                                "INSERT INTO fincilia.issued_authorization_context ("
                                "context_id, company_id, subject_id, firm_id, "
                                "engagement_id, purpose_code, resource_kind, "
                                "resource_ref_digest, authorization_version, "
                                "expires_at, idempotency_key_digest, issuance_digest) "
                                "VALUES (%s, %s, %s, %s, %s, 'processing_job', "
                                "'source_artifact', %s, %s, now() + interval '1 hour', "
                                "%s, %s)",
                                (str(uuid.uuid4()), ESPIGA, ANA, foreign_firm,
                                 foreign_engagement, "a" * 64, version,
                                 "b" * 64, "c" * 64))

    def test_issuance_rejects_unknown_purpose_permission_and_unsafe_expiry(self) -> None:
        with self.session() as (connection, tenant):
            with self.assertRaisesRegex(IssuedContextError, "allowlisted"):
                issue_context(
                    connection, tenant=tenant, purpose_code="close_period",
                    resource_kind="period", resource_ref="period:synthetic",
                    idempotency_key=f"issued-context-{uuid.uuid4()}",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    hmac_key=HMAC_KEY)
            with self.assertRaisesRegex(IssuedContextError, "at most 30 days"):
                self.issue(
                    connection, tenant,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=31))


if __name__ == "__main__":
    unittest.main()
