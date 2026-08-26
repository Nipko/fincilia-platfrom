"""Administracion de roles contra API, PostgreSQL real, RLS y versionado."""

from __future__ import annotations

import unittest
import uuid
import time

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
FIRM = stable_id("firm", "andes")
SOFIA = stable_id("subject", "sofia")
ANA = stable_id("subject", "ana")
CARLA = stable_id("subject", "carla")


class MemberRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.target = str(uuid.uuid4())
        cls.foreign = str(uuid.uuid4())
        cls.foreign_firm = str(uuid.uuid4())
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.subject (subject_id, subject_kind, display_name) "
                    "VALUES (%s, 'person', 'Persona Equipo Sintetica'), "
                    "       (%s, 'person', 'Persona Otra Firma Sintetica')",
                    (cls.target, cls.foreign),
                )
                cursor.execute(
                    "INSERT INTO fincilia.firm (firm_id, legal_name) VALUES (%s, %s)",
                    (cls.foreign_firm, "Firma Aislada Sintetica"),
                )
                cursor.execute(
                    "INSERT INTO fincilia.membership "
                    "(membership_id, subject_id, firm_id, firm_role) VALUES "
                    "(%s, %s, %s, 'member'), (%s, %s, %s, 'member')",
                    (str(uuid.uuid4()), cls.target, FIRM,
                     str(uuid.uuid4()), cls.foreign, cls.foreign_firm),
                )
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.company_grant WHERE subject_id = %s",
                        (cls.target,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.company_grant "
                        "WHERE subject_id = %s AND company_role = 'firm_admin'",
                        (ANA,),
                    )
                cursor.execute(
                    "DELETE FROM fincilia.membership WHERE subject_id IN (%s, %s)",
                    (cls.target, cls.foreign),
                )
                cursor.execute("DELETE FROM fincilia.firm WHERE firm_id = %s",
                               (cls.foreign_firm,))
                cursor.execute(
                    "DELETE FROM fincilia.subject WHERE subject_id IN (%s, %s)",
                    (cls.target, cls.foreign),
                )

    def auth(self, username: str = "sofia@demo.local") -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET},
        )
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def change(self, method: str, subject: str, role: str,
               *, username: str = "sofia@demo.local", company: str = ESPIGA,
               reason: str = "access_required"):
        return self.client.request(
            method,
            f"/api/v1/companies/{company}/members/{subject}/roles",
            headers=self.auth(username),
            json={"role": role, "reason_code": reason},
        )

    def test_owner_lists_firm_members_without_identity_details(self) -> None:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/members", headers=self.auth())
        self.assertEqual(200, response.status_code, response.text)
        by_id = {item["subject_id"]: item for item in response.json()}
        self.assertIn(self.target, by_id)
        self.assertEqual([], by_id[self.target]["company_roles"])
        # Carla pertenece a la firma, pero nunca ha tenido un grant en Espiga.
        # El LEFT JOIN no puede convertir esa ausencia en un rol JSON `null`.
        self.assertEqual([], by_id[CARLA]["company_roles"])
        self.assertNotIn(self.foreign, by_id)
        for item in by_id.values():
            self.assertEqual(
                {"subject_id", "display_name", "firm_role", "company_roles"},
                set(item),
            )
        rendered = response.text.lower()
        for forbidden in ("@demo.local", "credential", "issuer", "external_subject"):
            self.assertNotIn(forbidden, rendered)

    def test_non_managers_cannot_list_or_change_roles(self) -> None:
        for username in ("ana@demo.local", "beto@demo.local", "carla@demo.local"):
            with self.subTest(username=username):
                listed = self.client.get(
                    f"/api/v1/companies/{ESPIGA}/members",
                    headers=self.auth(username),
                )
                self.assertEqual(403, listed.status_code)
                changed = self.change(
                    "POST", self.target, "read_only", username=username)
                self.assertEqual(403, changed.status_code)

    def test_grant_is_idempotent_versioned_and_revocable(self) -> None:
        before = self.client.get(
            f"/api/v1/companies/{ESPIGA}", headers=self.auth()).json()
        granted = self.change("POST", self.target, "preparer")
        self.assertEqual(200, granted.status_code, granted.text)
        self.assertTrue(granted.json()["changed"])
        self.assertGreater(granted.json()["authorization_version"],
                           before["authorization_version"])
        replay = self.change("POST", self.target, "preparer")
        self.assertFalse(replay.json()["changed"])
        self.assertTrue(replay.json()["replayed"])

        members = self.client.get(
            f"/api/v1/companies/{ESPIGA}/members", headers=self.auth()).json()
        target = next(item for item in members if item["subject_id"] == self.target)
        self.assertEqual(["preparer"], target["company_roles"])

        revoked = self.change(
            "DELETE", self.target, "preparer", reason="access_removed")
        self.assertTrue(revoked.json()["changed"])
        replayed = self.change(
            "DELETE", self.target, "preparer", reason="access_removed")
        self.assertTrue(replayed.json()["replayed"])

    def test_one_member_can_hold_multiple_roles(self) -> None:
        for role in ("preparer", "auditor"):
            self.assertEqual(200, self.change("POST", self.target, role).status_code)
        members = self.client.get(
            f"/api/v1/companies/{ESPIGA}/members", headers=self.auth()).json()
        target = next(item for item in members if item["subject_id"] == self.target)
        self.assertEqual(["auditor", "preparer"], target["company_roles"])
        for role in ("preparer", "auditor"):
            self.change("DELETE", self.target, role, reason="access_removed")

    def test_no_one_can_grant_themselves_a_role(self) -> None:
        response = self.change("POST", SOFIA, "reviewer")
        self.assertEqual(409, response.status_code, response.text)
        self.assertTrue(response.json()["type"].endswith("/self-role-change"))

    def test_last_owner_cannot_revoke_their_own_owner_role(self) -> None:
        response = self.change(
            "DELETE", SOFIA, "owner", reason="responsibility_change")
        self.assertEqual(409, response.status_code, response.text)
        self.assertTrue(response.json()["type"].endswith("/last-owner"))

    def test_firm_admin_cannot_escalate_privileged_roles(self) -> None:
        self.assertEqual(200, self.change("POST", ANA, "firm_admin").status_code)
        try:
            normal = self.change(
                "POST", self.target, "read_only", username="ana@demo.local")
            self.assertEqual(200, normal.status_code, normal.text)
            privileged = self.change(
                "POST", self.target, "owner", username="ana@demo.local")
            self.assertEqual(403, privileged.status_code)
        finally:
            self.change("DELETE", self.target, "read_only", reason="access_removed")
            self.change("DELETE", ANA, "firm_admin", reason="access_removed")

    def test_member_from_another_firm_is_rejected(self) -> None:
        for method in ("POST", "DELETE"):
            with self.subTest(method=method):
                response = self.change(method, self.foreign, "read_only")
                self.assertEqual(422, response.status_code, response.text)
                self.assertTrue(
                    response.json()["type"].endswith("/member-not-eligible"))

    def test_permission_change_invalidates_the_preexisting_token(self) -> None:
        stale = self.auth()
        time.sleep(1.05)
        self.assertEqual(200, self.change("POST", self.target, "auditor").status_code)
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}", headers=stale)
        self.assertEqual(401, response.status_code)
        self.change("DELETE", self.target, "auditor", reason="access_removed")

    def test_audit_uses_opaque_subject_and_reason_code(self) -> None:
        self.change("POST", self.target, "read_only")
        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=100",
            headers=self.auth("beto@demo.local"),
        ).json()
        grants = [event for event in events if event["action"] == "member.role.grant"]
        self.assertTrue(grants)
        self.assertEqual(self.target, grants[0]["resource_ref"])
        self.assertEqual("access_required", grants[0]["detail"]["reason_code"])
        self.assertNotIn("Persona Equipo", str(grants[0]))
        self.change("DELETE", self.target, "read_only", reason="access_removed")

    def test_denied_role_change_survives_its_failed_transaction(self) -> None:
        denied = self.change("POST", SOFIA, "reviewer")
        self.assertEqual(409, denied.status_code)
        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=100",
            headers=self.auth("beto@demo.local"),
        ).json()
        attempts = [
            event for event in events
            if event["action"] == "member.role.grant"
            and event["outcome"] == "denied"
            and event["resource_ref"] == SOFIA
        ]
        self.assertTrue(attempts)
        self.assertEqual("self-role-change", attempts[0]["detail"]["reason"])
        self.assertNotIn("display_name", str(attempts[0]))


if __name__ == "__main__":
    unittest.main()
