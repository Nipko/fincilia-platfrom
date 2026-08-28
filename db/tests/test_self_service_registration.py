"""Registro web sintetico, privilegios y primer espacio contra PostgreSQL real."""

from __future__ import annotations

import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app


SECRET = "Registro-Demo-2026!"


class SelfServiceRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex
        self.username = f"registro.{self.marker}@demo.local"
        self.display_name = f"Persona Registro {self.marker[:8]}"
        self.firm_name = f"Firma Registro Sintetica {self.marker[:8]}"
        self.subject_ids: set[str] = set()
        self.company_ids: set[str] = set()

    def tearDown(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                # Los recibos de aprovisionamiento y la auditoria de plataforma
                # tienen RLS por sujeto incluso para el migrador. La prueba conoce
                # el sujeto que acaba de crear y fija ese contexto antes de borrar
                # sus filas; sin el contexto el DELETE no falla, simplemente no ve
                # nada y deja referencias que hacen fallar la limpieza posterior.
                if self.subject_ids:
                    cursor.execute(
                        "SELECT set_config('fincilia.subject_id', %s, false)",
                        (next(iter(self.subject_ids)),),
                    )
                for company_id in self.company_ids:
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
                        "WHERE company_id = %s", (company_id,))
                    cursor.execute(
                        "DELETE FROM fincilia.company WHERE company_id = %s",
                        (company_id,),
                    )
                for subject_id in self.subject_ids:
                    cursor.execute(
                        "SELECT set_config('fincilia.subject_id', %s, false)",
                        (subject_id,),
                    )
                    cursor.execute(
                        "SELECT firm_id FROM fincilia.membership WHERE subject_id = %s",
                        (subject_id,),
                    )
                    firm_ids = [row[0] for row in cursor.fetchall()]
                    cursor.execute(
                        "DELETE FROM fincilia.audit_event WHERE subject_id = %s",
                        (subject_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.membership WHERE subject_id = %s",
                        (subject_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.local_credential WHERE subject_id = %s",
                        (subject_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.identity_binding WHERE subject_id = %s",
                        (subject_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.subject WHERE subject_id = %s",
                        (subject_id,),
                    )
                    for firm_id in firm_ids:
                        cursor.execute(
                            "DELETE FROM fincilia.firm WHERE firm_id = %s",
                            (firm_id,),
                        )

    def payload(self, **overrides) -> dict:
        value = {
            "username": self.username,
            "secret": SECRET,
            "display_name": self.display_name,
            "firm_name": self.firm_name,
        }
        value.update(overrides)
        return value

    def register(self, **overrides):
        response = self.client.post(
            "/api/v1/auth/registration", json=self.payload(**overrides))
        if response.status_code == 201:
            self.subject_ids.add(response.json()["subject_id"])
        return response

    @staticmethod
    def bearer(response) -> dict[str, str]:
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_registration_is_atomic_navigable_and_redacted(self) -> None:
        response = self.register()
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(
            {"token", "expires_at", "subject_id", "display_name"},
            set(response.json()),
        )
        self.assertNotIn(self.username, response.text)
        self.assertNotIn(SECRET, response.text)

        firms = self.client.get(
            "/api/v1/firms/manageable", headers=self.bearer(response))
        self.assertEqual(200, firms.status_code, firms.text)
        self.assertEqual(1, len(firms.json()))
        self.assertEqual(self.firm_name, firms.json()[0]["legal_name"])
        self.assertEqual("owner", firms.json()[0]["firm_role"])
        companies = self.client.get(
            "/api/v1/companies", headers=self.bearer(response))
        self.assertEqual([], companies.json())

        login = self.client.post(
            "/api/v1/auth/session",
            json={"username": self.username.upper(), "secret": SECRET},
        )
        # El login no normaliza silenciosamente una identidad distinta.
        self.assertEqual(401, login.status_code)
        login = self.client.post(
            "/api/v1/auth/session",
            json={"username": self.username, "secret": SECRET},
        )
        self.assertEqual(200, login.status_code, login.text)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.algorithm, c.iterations, c.salt, c.secret_hash, "
                    "       b.external_subject_ref "
                    "FROM fincilia.local_credential c "
                    "JOIN fincilia.identity_binding b USING (subject_id) "
                    "WHERE c.username = %s", (self.username,))
                credential = cursor.fetchone()
        self.assertEqual("pbkdf2_sha256", credential[0])
        self.assertEqual(240000, credential[1])
        self.assertRegex(credential[2], r"^[0-9a-f]{32}$")
        self.assertRegex(credential[3], r"^[0-9a-f]{64}$")
        self.assertRegex(credential[4], r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(SECRET, credential[3])

    def test_duplicate_rolls_back_every_row_from_the_losing_attempt(self) -> None:
        first = self.register()
        self.assertEqual(201, first.status_code, first.text)
        second = self.register(display_name="Otra Persona Sintetica")
        self.assertEqual(409, second.status_code, second.text)
        self.assertNotIn(self.username, second.text)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*), count(DISTINCT s.subject_id), "
                    "       count(DISTINCT m.firm_id) "
                    "FROM fincilia.local_credential c "
                    "JOIN fincilia.subject s USING (subject_id) "
                    "JOIN fincilia.membership m USING (subject_id) "
                    "WHERE c.username = %s", (self.username,))
                self.assertEqual((1, 1, 1), cursor.fetchone())

    def test_invalid_inputs_and_extra_fields_fail_closed(self) -> None:
        cases = (
            ({"username": f"registro.{self.marker}@example.com"}, 422),
            ({"secret": "password-debil"}, 422),
            ({"display_name": "X"}, 422),
            ({"extra": "not-allowed"}, 422),
        )
        for overrides, status in cases:
            with self.subTest(overrides=overrides):
                response = self.register(**overrides)
                self.assertEqual(status, response.status_code, response.text)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.local_credential "
                    "WHERE username = %s", (self.username,))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_new_account_completes_the_existing_company_onboarding(self) -> None:
        registered = self.register()
        self.assertEqual(201, registered.status_code, registered.text)
        headers = self.bearer(registered)
        firm = self.client.get(
            "/api/v1/firms/manageable", headers=headers).json()[0]
        payload = {
            "firm_id": firm["firm_id"],
            "legal_name": f"Empresa Nueva Sintetica {self.marker[:8]}",
            "country_code": "CO",
            "tax_identifier": f"NIT-SYN-{self.marker}",
            "setup": {
                "account_family": "bank_account",
                "account_name": "Cuenta inicial sintetica",
                "account_identifier": f"CTA-SYN-{self.marker}",
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
        created = self.client.post(
            "/api/v1/companies", json=payload,
            headers={**headers, "Idempotency-Key": f"fnc-reg-{self.marker}"},
        )
        self.assertEqual(201, created.status_code, created.text)
        self.company_ids.add(created.json()["company_id"])
        for field in ("account_id", "source_id", "link_id", "cycle_id"):
            self.assertIsNotNone(created.json()[field])
        refreshed = created.json()["refreshed_session"]
        detail = self.client.get(
            f"/api/v1/companies/{created.json()['company_id']}",
            headers={"Authorization": f"Bearer {refreshed['token']}"},
        )
        self.assertEqual(200, detail.status_code, detail.text)
        self.assertEqual(["owner"], detail.json()["roles"])

    def test_privileges_expose_only_the_bounded_function(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    "has_function_privilege('public', "
                    "'fincilia.register_local_account(uuid,uuid,uuid,text,text,text,text,text,integer,text,text)', 'EXECUTE'), "
                    "has_function_privilege('fincilia_app', "
                    "'fincilia.register_local_account(uuid,uuid,uuid,text,text,text,text,text,integer,text,text)', 'EXECUTE'), "
                    "has_schema_privilege('fincilia_identity', 'fincilia', 'CREATE'), "
                    "(SELECT rolcanlogin FROM pg_roles WHERE rolname='fincilia_identity')")
                self.assertEqual((False, True, False, False), cursor.fetchone())

        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO fincilia.local_credential "
                        "(subject_id, username, algorithm, iterations, salt, secret_hash) "
                        "VALUES (%s, %s, 'pbkdf2_sha256', 240000, %s, %s)",
                        (str(uuid.uuid4()), self.username, "0" * 32, "0" * 64),
                    )


if __name__ == "__main__":
    unittest.main()
