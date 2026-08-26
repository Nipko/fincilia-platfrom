"""Trabajo durable y capability contra PostgreSQL real.

Estas pruebas usan los tres roles efectivos. Comprueban que la API solo encola
con una capability viva, que el despachador vuelve a evaluarla y que el worker
no puede seguir escribiendo ni cerrar con exito tras una revocacion.
"""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from fincilia_api import repository
from fincilia_api.issued_contexts import issue_context, revoke_context
from fincilia_contracts.tenancy import TenantContext

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
APP_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")
HMAC_KEY = "processing-context-test-key-synthetic-only-32"

COMPANY = stable_id("company", "espiga")
OTHER_COMPANY = stable_id("company", "andinos")
SUBJECT = stable_id("subject", "ana")


def set_context(connection: psycopg.Connection, company_id: str,
                subject_id: str = SUBJECT) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                       (company_id,))
        cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                       (subject_id,))


class ProcessingAuthorizationContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (MIGRATOR_DSN and APP_DSN and WORKER_DSN):
            raise unittest.SkipTest("migrator, app and worker DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.created: list[tuple[str, str, str]] = []

    @classmethod
    def tearDownClass(cls) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            for artifact_id, run_id, context_id in reversed(cls.created):
                with connection.transaction():
                    set_context(connection, COMPANY)
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM fincilia.dispatch_pointer WHERE run_id = %s",
                                       (run_id,))
                        cursor.execute("DELETE FROM fincilia.run_attempt WHERE run_id = %s",
                                       (run_id,))
                        cursor.execute("DELETE FROM fincilia.dead_letter_item WHERE work_id = %s",
                                       (run_id,))
                        cursor.execute("DELETE FROM fincilia.processing_run WHERE run_id = %s",
                                       (run_id,))
                        cursor.execute(
                            "DELETE FROM fincilia.issued_authorization_revocation "
                            "WHERE context_id = %s", (context_id,))
                        cursor.execute(
                            "DELETE FROM fincilia.issued_authorization_context "
                            "WHERE context_id = %s", (context_id,))
                        cursor.execute("DELETE FROM fincilia.source_artifact WHERE artifact_id = %s",
                                       (artifact_id,))

    def create_work(self) -> tuple[str, str, str, TenantContext]:
        artifact_id = str(uuid.uuid4())
        digest = uuid.uuid4().hex + uuid.uuid4().hex
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                        "filename, byte_size, content_sha256, media_type, zone, object_key, "
                        "status, uploaded_by) VALUES (%s, %s, 'synthetic.csv', 12, %s, "
                        "'text/csv', 'raw', %s, 'stored', %s)",
                        (artifact_id, COMPANY, digest, f"synthetic/{digest}", SUBJECT))

        with psycopg.connect(APP_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                authorized = repository.authorize(connection, SUBJECT, COMPANY)
                self.assertIsNotNone(authorized)
                tenant = TenantContext(
                    subject_id=SUBJECT, firm_id=authorized.firm_id,
                    company_id=authorized.company_id, roles=authorized.roles,
                    authorization_version=authorized.version,
                    engagement_id=authorized.engagement_id)
                issued = issue_context(
                    connection, tenant=tenant, purpose_code="processing_job",
                    resource_kind="source_artifact", resource_ref=artifact_id,
                    idempotency_key=f"processing-test:{artifact_id}",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    hmac_key=HMAC_KEY)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT fincilia.enqueue_processing_run(%s, %s, 'profile', %s)::text",
                        (COMPANY, artifact_id, issued.context_id))
                    run_id = cursor.fetchone()[0]
        type(self).created.append((artifact_id, run_id, issued.context_id))
        return artifact_id, run_id, issued.context_id, tenant

    def claim(self, expected_run_id: str):
        # El stack de desarrollo puede tener trabajos legitimos de la sesion web.
        # Se aparcan durante esta reclamacion y se restaura su disponibilidad
        # exacta despues; la prueba no consume ni reordena trabajo ajeno.
        parked: list[tuple[str, datetime]] = []
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT run_id::text, available_at FROM fincilia.dispatch_pointer "
                    "WHERE run_id <> %s", (expected_run_id,))
                parked = cursor.fetchall()
                cursor.execute(
                    "UPDATE fincilia.dispatch_pointer "
                    "SET available_at = now() + interval '1 day' WHERE run_id <> %s",
                    (expected_run_id,))
        try:
            with psycopg.connect(WORKER_DSN, autocommit=False) as connection:
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT run_id::text, company_id::text, lease_token::text "
                        "FROM fincilia.claim_next_run('context-test-worker', 60)")
                    return cursor.fetchone()
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    for run_id, available_at in parked:
                        cursor.execute(
                            "UPDATE fincilia.dispatch_pointer SET available_at = %s "
                            "WHERE run_id = %s", (available_at, run_id))

    def run_state(self, run_id: str) -> tuple:
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT status, error_code, failure_class, issued_context_id::text "
                        "FROM fincilia.processing_run WHERE run_id = %s", (run_id,))
                    return cursor.fetchone()

    def revoke(self, context_id: str, tenant: TenantContext) -> None:
        with psycopg.connect(APP_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                self.assertTrue(revoke_context(
                    connection, tenant=tenant, context_id=context_id,
                    reason_code="access_removed"))

    def test_context_is_persisted_and_live_work_can_complete(self) -> None:
        _artifact, run_id, context_id, _tenant = self.create_work()
        self.assertEqual(context_id, self.run_state(run_id)[3])
        claimed = self.claim(run_id)
        self.assertEqual(run_id, claimed[0])
        with psycopg.connect(WORKER_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT fincilia.hold_processing_lease(%s, %s)",
                                   (run_id, claimed[2]))
                    self.assertTrue(cursor.fetchone()[0])
                    cursor.execute(
                        "SELECT fincilia.finish_run(%s, %s, '{}'::jsonb, NULL, NULL)",
                        (run_id, claimed[2]))
                    self.assertEqual("succeeded", cursor.fetchone()[0])

    def test_revoked_context_is_rejected_before_claim(self) -> None:
        _artifact, run_id, context_id, tenant = self.create_work()
        self.revoke(context_id, tenant)
        self.assertIsNone(self.claim(run_id))
        self.assertEqual(
            ("failed", "authorization_context_invalid", "requires_human", context_id),
            self.run_state(run_id))

    def test_revocation_after_claim_blocks_batches_and_success(self) -> None:
        _artifact, run_id, context_id, tenant = self.create_work()
        claimed = self.claim(run_id)
        self.assertEqual(run_id, claimed[0])
        self.revoke(context_id, tenant)
        with psycopg.connect(WORKER_DSN, autocommit=False) as connection:
            with connection.transaction():
                set_context(connection, COMPANY)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT fincilia.hold_processing_lease(%s, %s)",
                                   (run_id, claimed[2]))
                    self.assertFalse(cursor.fetchone()[0])
                    cursor.execute(
                        "SELECT fincilia.finish_run(%s, %s, '{}'::jsonb, NULL, NULL)",
                        (run_id, claimed[2]))
                    self.assertEqual("authorization_context_invalid",
                                     cursor.fetchone()[0])
        self.assertEqual("failed", self.run_state(run_id)[0])

    def test_context_from_another_company_cannot_be_attached(self) -> None:
        artifact_id, _run_id, context_id, _tenant = self.create_work()
        with psycopg.connect(APP_DSN, autocommit=False) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    set_context(connection, OTHER_COMPANY)
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT fincilia.enqueue_processing_run(%s, %s, 'extract', %s)",
                            (OTHER_COMPANY, artifact_id, context_id))

    def test_runtime_cannot_rebind_a_run_to_another_context(self) -> None:
        _artifact, run_id, _context_id, _tenant = self.create_work()
        with psycopg.connect(APP_DSN, autocommit=False) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    set_context(connection, COMPANY)
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "UPDATE fincilia.processing_run SET issued_context_id = NULL "
                            "WHERE run_id = %s", (run_id,))


if __name__ == "__main__":
    unittest.main()
