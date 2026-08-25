"""Alta de empresa y perfil fundador contra PostgreSQL real.

Este primer bloque fija que el entorno local usa el mismo RBAC acumulable que el
producto. No existe un ``test_admin`` ni un bypass de autorizacion.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, PEOPLE, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app
from fincilia_contracts.tenancy import ROLES


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
SOFIA = stable_id("subject", "sofia")
PROVISIONER = stable_id("subject", "provisioner")


class CompanyProvisioningTests(unittest.TestCase):
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

    def setUp(self) -> None:
        self.created_companies: list[str] = []

    def tearDown(self) -> None:
        # Solo filas sinteticas creadas por esta prueba, en orden inverso a sus
        # referencias. No se toca la demo que esta usando el navegador local.
        if not self.created_companies:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.subject_id', %s, false)",
                    (SOFIA,),
                )
                for company_id in self.created_companies:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company_id,),
                    )
                    for table in (
                        "source_expectation", "source_cycle", "data_source_account",
                        "data_source", "financial_account", "audit_event",
                        "company_grant", "engagement", "authorization_version",
                    ):
                        cursor.execute(
                            f"DELETE FROM fincilia.{table} WHERE company_id = %s",
                            (company_id,),
                        )
                    cursor.execute(
                        "DELETE FROM fincilia.company_provisioning_command "
                        "WHERE company_id = %s",
                        (company_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.company WHERE company_id = %s",
                        (company_id,),
                    )

    def auth(self, username: str = "sofia@demo.local") -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET},
        )
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def payload(self, *, suffix: str | None = None,
                account_family: str = "bank_account") -> dict:
        marker = suffix or uuid.uuid4().hex
        return {
            "firm_id": stable_id("firm", "andes"),
            "legal_name": f"Empresa Alta Sintetica {marker[:12]}",
            "country_code": "CO",
            "tax_identifier": f"NIT-{marker}",
            "setup": {
                "account_family": account_family,
                "account_name": "Cuenta inicial sintetica",
                "account_identifier": f"CTA-{marker}",
                "currency_code": "COP",
                "source_family": "bank_account",
                "source_name": "Extracto inicial sintetico",
                "purpose_code": "operational",
                "timezone": "America/Bogota",
                "anchor_date": "2026-08-01",
                "due_day_offset": 0,
                "grace_days": 3,
            },
        }

    def create(self, payload: dict, key: str, *,
               username: str = "sofia@demo.local"):
        response = self.client.post(
            "/api/v1/companies", json=payload,
            headers={**self.auth(username), "Idempotency-Key": key},
        )
        if response.status_code in (200, 201):
            company_id = response.json()["company_id"]
            if company_id not in self.created_companies:
                self.created_companies.append(company_id)
        return response

    def test_owner_sees_only_the_firm_they_can_manage(self) -> None:
        owner = self.client.get("/api/v1/firms/manageable", headers=self.auth())
        self.assertEqual(200, owner.status_code, owner.text)
        self.assertEqual([stable_id("firm", "andes")],
                         [item["firm_id"] for item in owner.json()])
        member = self.client.get(
            "/api/v1/firms/manageable", headers=self.auth("ana@demo.local"))
        self.assertEqual([], member.json())

    def test_full_setup_is_atomic_navigable_and_redacted(self) -> None:
        payload = self.payload()
        response = self.create(payload, f"fnc-onb-{uuid.uuid4().hex}")
        self.assertEqual(201, response.status_code, response.text)
        body = response.json()
        self.assertEqual(
            {
                "company_id", "legal_name", "country_code", "status", "roles",
                "firm_id", "engagement_id", "authorization_version", "permissions",
                "account_id", "source_id", "link_id", "cycle_id",
                "expectations_created", "replayed", "refreshed_session",
            },
            set(body),
        )
        for field in ("company_id", "engagement_id", "account_id", "source_id",
                      "link_id", "cycle_id"):
            self.assertTrue(body[field], field)
        self.assertIn("company.read", body["permissions"])
        self.assertNotIn("tax_identifier", body)
        self.assertNotIn("account_identifier", body)
        rendered = response.text
        self.assertNotIn(payload["tax_identifier"], rendered)
        self.assertNotIn(payload["setup"]["account_identifier"], rendered)

        detail = self.client.get(
            f"/api/v1/companies/{body['company_id']}", headers=self.auth())
        self.assertEqual(200, detail.status_code, detail.text)
        self.assertEqual(["owner"], detail.json()["roles"])
        accounts = self.client.get(
            f"/api/v1/companies/{body['company_id']}/accounts",
            headers=self.auth()).json()
        sources = self.client.get(
            f"/api/v1/companies/{body['company_id']}/sources",
            headers=self.auth()).json()
        self.assertEqual(1, len(accounts))
        self.assertEqual(1, len(sources))
        self.assertNotIn(payload["setup"]["account_identifier"], str(accounts))

        events = self.client.get(
            f"/api/v1/companies/{body['company_id']}/audit?limit=20",
            headers=self.auth()).json()
        self.assertTrue(any(item["action"] == "company.provision" for item in events))
        self.assertNotIn(payload["tax_identifier"], str(events))
        self.assertNotIn(payload["setup"]["account_identifier"], str(events))

    def test_company_can_start_without_optional_operational_masters(self) -> None:
        payload = self.payload()
        payload["setup"] = None
        response = self.create(payload, f"fnc-onb-{uuid.uuid4().hex}")

        self.assertEqual(201, response.status_code, response.text)
        body = response.json()
        for field in ("account_id", "source_id", "link_id", "cycle_id"):
            self.assertIsNone(body[field])
        self.assertEqual(0, body["expectations_created"])
        detail = self.client.get(
            f"/api/v1/companies/{body['company_id']}", headers=self.auth())
        self.assertEqual(200, detail.status_code, detail.text)

    def test_invalid_protected_values_are_never_reflected_by_validation(self) -> None:
        payload = self.payload()
        payload["tax_identifier"] = {"secret": "SYN-TAX-NEVER-ECHO"}
        payload["setup"]["account_identifier"] = {
            "secret": "SYN-ACCOUNT-NEVER-ECHO",
        }

        response = self.create(payload, f"fnc-onb-{uuid.uuid4().hex}")

        self.assertEqual(422, response.status_code, response.text)
        self.assertNotIn("SYN-TAX-NEVER-ECHO", response.text)
        self.assertNotIn("SYN-ACCOUNT-NEVER-ECHO", response.text)

        oversized = self.payload()
        oversized["tax_identifier"] = "SYN-PRIVATE-" + "X" * 200
        too_long = self.create(oversized, f"fnc-onb-{uuid.uuid4().hex}")
        self.assertEqual(422, too_long.status_code, too_long.text)
        self.assertNotIn(oversized["tax_identifier"], too_long.text)

    def test_same_key_replays_and_changed_request_conflicts(self) -> None:
        payload = self.payload()
        key = f"fnc-onb-{uuid.uuid4().hex}"
        first = self.create(payload, key)
        replay = self.create(payload, key)
        self.assertEqual(201, first.status_code, first.text)
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(first.json()["company_id"], replay.json()["company_id"])
        self.assertTrue(replay.json()["replayed"])
        changed = {**payload, "legal_name": payload["legal_name"] + " cambio"}
        conflict = self.create(changed, key)
        self.assertEqual(409, conflict.status_code, conflict.text)
        self.assertTrue(conflict.json()["type"].endswith("/idempotency-conflict"))

    def test_concurrent_retries_create_one_company_and_return_one_receipt(self) -> None:
        payload = self.payload()
        key = f"fnc-onb-{uuid.uuid4().hex}"
        headers = {**self.auth(), "Idempotency-Key": key}

        def submit(_attempt: int):
            return self.client.post(
                "/api/v1/companies", json=payload, headers=headers)

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(submit, range(2)))

        self.assertEqual([200, 201], sorted(item.status_code for item in responses),
                         [item.text for item in responses])
        company_ids = {item.json()["company_id"] for item in responses}
        self.assertEqual(1, len(company_ids))
        self.assertEqual([False, True],
                         sorted(item.json()["replayed"] for item in responses))
        self.created_companies.extend(company_ids)

    def test_runtime_firm_read_is_subject_scoped_and_remains_read_only(self) -> None:
        self.assertTrue(RUNTIME_DSN)
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.subject_id', %s, true)", (SOFIA,))
                cursor.execute("SELECT firm_id::text FROM fincilia.firm ORDER BY 1")
                self.assertEqual([(stable_id("firm", "andes"),)], cursor.fetchall())

            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.subject_id', %s, true)",
                    (str(uuid.uuid4()),),
                )
                cursor.execute("SELECT count(*) FROM fincilia.firm")
                self.assertEqual(0, cursor.fetchone()[0])

            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.subject_id', %s, true)",
                        (SOFIA,),
                    )
                    cursor.execute(
                        "UPDATE fincilia.firm SET legal_name = legal_name "
                        "WHERE firm_id = %s",
                        (stable_id("firm", "andes"),),
                    )

    def test_member_cannot_provision_and_foreign_firm_is_indistinguishable(self) -> None:
        payload = self.payload()
        denied = self.create(
            payload, f"fnc-onb-{uuid.uuid4().hex}", username="ana@demo.local")
        self.assertEqual(403, denied.status_code, denied.text)
        foreign = {**payload, "firm_id": str(uuid.uuid4())}
        denied_foreign = self.create(
            foreign, f"fnc-onb-{uuid.uuid4().hex}")
        self.assertEqual(403, denied_foreign.status_code, denied_foreign.text)
        self.assertEqual(denied.json()["detail"], denied_foreign.json()["detail"])

    def test_invalid_initial_setup_rolls_back_the_company_and_key(self) -> None:
        marker = uuid.uuid4().hex
        invalid = self.payload(suffix=marker, account_family="unsupported")
        failed = self.create(invalid, f"fnc-onb-{uuid.uuid4().hex}")
        self.assertEqual(422, failed.status_code, failed.text)

        # El mismo NIT puede usarse enseguida en una solicitud valida. Si la
        # company o el recibo hubieran sobrevivido al error, responderia 409.
        valid = self.payload(suffix=marker)
        recovered = self.create(valid, f"fnc-onb-{uuid.uuid4().hex}")
        self.assertEqual(201, recovered.status_code, recovered.text)

    def test_provisioning_authority_has_no_login_or_product_access(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    "  EXISTS(SELECT 1 FROM fincilia.identity_binding WHERE subject_id=%s),"
                    "  EXISTS(SELECT 1 FROM fincilia.local_credential WHERE subject_id=%s),"
                    "  EXISTS(SELECT 1 FROM fincilia.membership WHERE subject_id=%s)",
                    (PROVISIONER, PROVISIONER, PROVISIONER),
                )
                self.assertEqual((False, False, False), cursor.fetchone())


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
