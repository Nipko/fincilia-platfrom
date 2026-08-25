"""Alta de empresa y perfil fundador contra PostgreSQL real.

Este primer bloque fija que el entorno local usa el mismo RBAC acumulable que el
producto. No existe un ``test_admin`` ni un bypass de autorizacion.
"""

from __future__ import annotations

import unittest

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, PEOPLE, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, build_settings
from fincilia_api.main import create_app
from fincilia_contracts.tenancy import ROLES


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
SOFIA = stable_id("subject", "sofia")
PROVISIONER = stable_id("subject", "provisioner")


class FounderRoleSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN:
            raise unittest.SkipTest("migrator DSN is required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def auth(self) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": "sofia@demo.local", "secret": DEFAULT_SECRET},
        )
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_founder_profile_declares_every_product_role(self) -> None:
        founder = next(person for person in PEOPLE if person["key"] == "sofia")
        for company in ("espiga", "andinos"):
            self.assertEqual(set(ROLES), set(founder["grants"][company]))

    def test_founder_has_real_accumulated_grants_in_each_company(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company_id in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company_id,),
                    )
                    cursor.execute(
                        "SELECT company_role, granted_by FROM fincilia.company_grant "
                        "WHERE company_id = %s AND subject_id = %s "
                        "  AND revoked_at IS NULL",
                        (company_id, SOFIA),
                    )
                    grants = cursor.fetchall()
                    self.assertEqual(set(ROLES), {row[0] for row in grants})
                    self.assertEqual({PROVISIONER}, {str(row[1]) for row in grants})

    def test_one_login_receives_the_union_without_a_special_mode(self) -> None:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}", headers=self.auth())
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(set(ROLES), set(body["roles"]))
        self.assertIn("dataset.map", body["permissions"])
        self.assertIn("dataset.publish", body["permissions"])
        self.assertIn("member.manage", body["permissions"])
        self.assertNotIn("test_admin", body)
        self.assertNotIn("bypass", body)


if __name__ == "__main__":
    unittest.main()
