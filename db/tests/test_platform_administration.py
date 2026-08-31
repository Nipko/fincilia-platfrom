"""Bootstrap, aislamiento y diagnósticos del plano de control en PostgreSQL."""

from __future__ import annotations

import unittest
import uuid
import time

import psycopg
from fastapi.testclient import TestClient

from db.tests.test_api_authorization import (
    AUDIENCE, ISSUER, MIGRATOR_DSN, RUNTIME_DSN, SIGNING_KEY, build_settings,
)
from fincilia_api.main import create_app
from fincilia_platform.tokens import issue


class PlatformAdministrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")

    def setUp(self) -> None:
        marker = uuid.uuid4().hex
        self.admin_id = str(uuid.uuid4())
        self.other_id = str(uuid.uuid4())
        self.admin_ref = f"hmac-sha256:v1:{marker * 2}"
        self.other_ref = f"hmac-sha256:v1:{marker[::-1] * 2}"
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM fincilia.platform_bootstrap_control")
                cursor.execute(
                    "INSERT INTO fincilia.subject (subject_id, subject_kind, display_name) "
                    "VALUES (%s, 'person', 'Admin Plataforma Sintetico'), "
                    "(%s, 'person', 'Persona Sintetica')",
                    (self.admin_id, self.other_id),
                )
                cursor.execute(
                    "INSERT INTO fincilia.identity_binding (subject_id, issuer, "
                    "external_subject_ref, verified_email_ref) VALUES "
                    "(%s, 'https://issuer.example.test', %s, %s), "
                    "(%s, 'https://issuer.example.test', %s, %s)",
                    (self.admin_id, f"hmac-sha256:v1:{'a' * 64}", self.admin_ref,
                     self.other_id, f"hmac-sha256:v1:{'b' * 64}", self.other_ref),
                )
                cursor.execute(
                    "INSERT INTO fincilia.platform_bootstrap_control ("
                    "expected_verified_email_ref, configured_by, configuration_ref) "
                    "VALUES (%s, 'FOUNDER-01', 'TEST-PLATFORM-BOOTSTRAP')",
                    (self.admin_ref,),
                )

    def tearDown(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM fincilia.platform_audit_event "
                    "WHERE actor_subject_id = ANY(%s::uuid[])",
                    ([self.admin_id, self.other_id],),
                )
                cursor.execute(
                    "DELETE FROM fincilia.platform_role_assignment "
                    "WHERE subject_id = ANY(%s::uuid[])",
                    ([self.admin_id, self.other_id],),
                )
                cursor.execute("DELETE FROM fincilia.platform_bootstrap_control")
                cursor.execute(
                    "DELETE FROM fincilia.identity_binding "
                    "WHERE subject_id = ANY(%s::uuid[])",
                    ([self.admin_id, self.other_id],),
                )
                cursor.execute(
                    "DELETE FROM fincilia.subject WHERE subject_id = ANY(%s::uuid[])",
                    ([self.admin_id, self.other_id],),
                )

    def _runtime(self, subject_id: str) -> psycopg.Connection:
        connection = psycopg.connect(RUNTIME_DSN)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('fincilia.subject_id', %s, false)",
                (subject_id,),
            )
        return connection

    def _claim(self) -> None:
        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fincilia.claim_initial_platform_superadmin(%s, %s)",
                    (self.admin_id, self.admin_ref),
                )
                self.assertTrue(cursor.fetchone()[0])

    def _auth(self, subject_id: str) -> dict[str, str]:
        now = int(time.time())
        token = issue(
            subject_id, key=SIGNING_KEY, issuer=ISSUER, audience=AUDIENCE,
            issued_at=now, ttl_seconds=900,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_runtime_has_no_direct_access_to_control_tables(self) -> None:
        with self._runtime(self.other_id) as connection:
            for table in ("platform_role_assignment", "platform_audit_event",
                          "platform_bootstrap_control"):
                with self.subTest(table=table), self.assertRaises(
                        psycopg.errors.InsufficientPrivilege):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(f"SELECT * FROM fincilia.{table}")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.subject SET status = 'suspended' "
                        "WHERE subject_id = %s", (self.admin_id,),
                    )

    def test_only_the_preconfigured_verified_binding_claims_once(self) -> None:
        with self._runtime(self.other_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fincilia.claim_initial_platform_superadmin(%s, %s)",
                    (self.other_id, self.other_ref),
                )
                self.assertFalse(cursor.fetchone()[0])

        self._claim()
        self._claim()  # replay idempotente del mismo sujeto

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.platform_role_assignment "
                    "WHERE platform_role = 'platform_superadmin' AND status = 'active' "
                    "AND subject_id = %s", (self.admin_id,),
                )
                self.assertEqual(1, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT claimed_by::text FROM fincilia.platform_bootstrap_control"
                )
                self.assertEqual(self.admin_id, cursor.fetchone()[0])

    def test_ordinary_subject_is_denied_the_global_overview(self) -> None:
        with self._runtime(self.other_id) as connection:
            for function in (
                    "fincilia.platform_admin_overview()",
                    "fincilia.platform_operational_diagnostics()"):
                with self.subTest(function=function), self.assertRaises(
                        psycopg.errors.InsufficientPrivilege):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(f"SELECT {function}")

    def test_superadmin_gets_metadata_not_financial_payload(self) -> None:
        self._claim()
        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT fincilia.platform_admin_overview()")
                overview = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT platform_role FROM "
                    "fincilia.platform_roles_for_current_subject()"
                )
                roles = [row[0] for row in cursor.fetchall()]
        self.assertEqual(["platform_superadmin"], roles)
        self.assertEqual({"subjects", "firms", "companies", "platform_roles",
                          "bootstrap_claimed"}, set(overview))
        for forbidden in ("amount", "movement", "document", "tax_id", "email"):
            self.assertNotIn(forbidden, str(overview).lower())

    def test_operational_diagnostics_are_aggregate_and_acl_is_closed(self) -> None:
        self._claim()
        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT fincilia.platform_operational_diagnostics()")
                diagnostics = cursor.fetchone()[0]
        self.assertEqual(
            {"jobs", "evidence", "dead_letters", "notifications", "subscriptions"},
            set(diagnostics),
        )
        self.assertEqual(
            {"queued", "running", "failed", "failed_last_24h"},
            set(diagnostics["jobs"]),
        )
        self.assertIsInstance(diagnostics["evidence"]["stored_bytes"], str)
        serialized = str(diagnostics).lower()
        for forbidden in (
                "company_id", "subject_id", "artifact_id", "filename", "amount",
                "balance", "currency", "error_code", "reason_code", "payload"):
            self.assertNotIn(forbidden, serialized)

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_function_privilege('public', "
                    "'fincilia.platform_operational_diagnostics()', 'EXECUTE'), "
                    "has_function_privilege('fincilia_app', "
                    "'fincilia.platform_operational_diagnostics()', 'EXECUTE')"
                )
                public_execute, runtime_execute = cursor.fetchone()
        self.assertFalse(public_execute)
        self.assertTrue(runtime_execute)

    def test_status_change_is_audited_and_self_suspension_is_denied(self) -> None:
        self._claim()
        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM fincilia.platform_admin_set_subject_status("
                    "%s, 'suspended', 'security_review')", (self.other_id,),
                )
                self.assertEqual("suspended", cursor.fetchone()[0])
                cursor.execute(
                    "SELECT action, detail->>'reason_code' "
                    "FROM fincilia.platform_admin_audit(10)"
                )
                audit = cursor.fetchall()
            with self.assertRaises(psycopg.errors.InvalidParameterValue):
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT * FROM fincilia.platform_admin_set_subject_status("
                        "%s, 'suspended', 'self_suspend')", (self.admin_id,),
                    )
        self.assertIn(
            ("platform.subject.status.change", "security_review"), audit,
        )

    def test_superadmin_grants_and_revokes_a_bounded_platform_role(self) -> None:
        self._claim()
        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT platform_role FROM fincilia.platform_admin_grant_role("
                    "%s, 'platform_operator', 'operations_assignment')",
                    (self.other_id,),
                )
                self.assertEqual("platform_operator", cursor.fetchone()[0])

        with self._runtime(self.other_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT platform_role FROM "
                    "fincilia.platform_roles_for_current_subject()"
                )
                self.assertEqual(["platform_operator"],
                                 [row[0] for row in cursor.fetchall()])
                cursor.execute("SELECT fincilia.platform_admin_overview()")
                self.assertTrue(cursor.fetchone()[0]["bootstrap_claimed"])

        with self._runtime(self.admin_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fincilia.platform_admin_revoke_role("
                    "%s, 'platform_operator', 'operations_assignment_ended')",
                    (self.other_id,),
                )
                self.assertTrue(cursor.fetchone()[0])
        with self._runtime(self.other_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT platform_role FROM "
                    "fincilia.platform_roles_for_current_subject()"
                )
                self.assertEqual([], cursor.fetchall())

    def test_http_contract_exposes_roles_and_denies_an_ordinary_subject(self) -> None:
        self._claim()
        with TestClient(create_app(build_settings())) as client:
            denied = client.get(
                "/api/v1/platform/overview", headers=self._auth(self.other_id),
            )
            self.assertEqual(403, denied.status_code)

            me = client.get("/api/v1/me", headers=self._auth(self.admin_id))
            self.assertEqual(200, me.status_code, me.text)
            self.assertEqual(
                ["platform_superadmin"], me.json()["platform_roles"],
            )
            overview = client.get(
                "/api/v1/platform/overview", headers=self._auth(self.admin_id),
            )
            self.assertEqual(200, overview.status_code, overview.text)
            self.assertTrue(overview.json()["bootstrap_claimed"])

            diagnostics = client.get(
                "/api/v1/platform/diagnostics", headers=self._auth(self.admin_id),
            )
            self.assertEqual(200, diagnostics.status_code, diagnostics.text)
            self.assertEqual(
                {"jobs", "evidence", "dead_letters", "notifications", "subscriptions"},
                set(diagnostics.json()["operations"]),
            )

            granted = client.post(
                f"/api/v1/platform/identities/{self.other_id}/roles",
                headers=self._auth(self.admin_id),
                json={"platform_role": "platform_auditor",
                      "reason_code": "http_contract_test"},
            )
            self.assertEqual(200, granted.status_code, granted.text)
            self.assertEqual("platform_auditor", granted.json()["platform_role"])


if __name__ == "__main__":
    unittest.main()
