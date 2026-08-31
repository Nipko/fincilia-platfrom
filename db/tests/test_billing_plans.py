"""FNC-BIL-001 contra PostgreSQL real, sin proveedor ni cobros."""

from __future__ import annotations

import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api import billing
from fincilia_api.main import create_app


FIRM = stable_id("firm", "andes")
ESPIGA = stable_id("company", "espiga")
SOFIA = stable_id("subject", "sofia")


class BillingPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls._clean()
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        cls._clean()

    @classmethod
    def _clean(cls) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.subject_id', %s, false)",
                               (SOFIA,))
                cursor.execute("DELETE FROM fincilia.firm_usage_event WHERE firm_id = %s",
                               (FIRM,))
                cursor.execute("DELETE FROM fincilia.subscription_event WHERE firm_id = %s",
                               (FIRM,))
                cursor.execute("DELETE FROM fincilia.firm_subscription WHERE firm_id = %s",
                               (FIRM,))
                cursor.execute("DELETE FROM fincilia.billing_account WHERE firm_id = %s",
                               (FIRM,))

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_catalog_evaluation_is_complete_without_prices_or_security_paywall(self) -> None:
        response = self.client.get(
            "/api/v1/billing/plans", headers=self.auth("sofia@demo.local"))
        self.assertEqual(200, response.status_code, response.text)
        plans = response.json()
        self.assertEqual(["starter", "business", "accountant"],
                         [item["plan_code"] for item in plans])
        for plan in plans:
            self.assertEqual("evaluation", plan["catalog_state"])
            self.assertFalse(plan["commercial"]["configured"])
            self.assertIsNone(plan["commercial"]["unit_amount_minor"])
            self.assertTrue(plan["features"]["foundational_security"])
            self.assertTrue(plan["features"]["basic_data_export"])
        self.assertFalse(plans[0]["features"]["multi_company_portfolio"])
        self.assertTrue(plans[2]["features"]["multi_company_portfolio"])

    def test_owner_changes_evaluation_idempotently_and_usage_is_append_only(self) -> None:
        owner = self.auth("sofia@demo.local")
        empty = self.client.get(f"/api/v1/firms/{FIRM}/billing", headers=owner)
        self.assertEqual(200, empty.status_code, empty.text)
        self.assertIsNone(empty.json()["subscription"])
        self.assertEqual("disabled", empty.json()["payments_state"])

        key = str(uuid.uuid4())
        first = self.client.post(
            f"/api/v1/firms/{FIRM}/billing/evaluation", headers=owner,
            json={"plan_code": "accountant", "idempotency_key": key})
        self.assertEqual(200, first.status_code, first.text)
        self.assertFalse(first.json()["replayed"])
        self.assertEqual("accountant", first.json()["subscription"]["plan"]["plan_code"])
        self.assertEqual("evaluation", first.json()["subscription"]["status"])

        replay = self.client.post(
            f"/api/v1/firms/{FIRM}/billing/evaluation", headers=owner,
            json={"plan_code": "accountant", "idempotency_key": key})
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertTrue(replay.json()["replayed"])
        conflict = self.client.post(
            f"/api/v1/firms/{FIRM}/billing/evaluation", headers=owner,
            json={"plan_code": "starter", "idempotency_key": key})
        self.assertEqual(409, conflict.status_code, conflict.text)

        changed = self.client.post(
            f"/api/v1/firms/{FIRM}/billing/evaluation", headers=owner,
            json={"plan_code": "business", "idempotency_key": str(uuid.uuid4())})
        self.assertEqual(200, changed.status_code, changed.text)
        self.assertEqual(2, changed.json()["subscription"]["sequence"])
        self.assertEqual("business", changed.json()["subscription"]["plan"]["plan_code"])
        self.assertEqual(2, len(changed.json()["history"]))

        artifact = str(uuid.uuid4())
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                                   (ESPIGA,))
                    cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                                   (SOFIA,))
                billing.record_usage(
                    connection, firm_id=FIRM, company_id=ESPIGA,
                    subject_id=SOFIA, artifact_id=artifact, byte_size=2048)
                billing.record_usage(
                    connection, firm_id=FIRM, company_id=ESPIGA,
                    subject_id=SOFIA, artifact_id=artifact, byte_size=2048)
        measured = self.client.get(f"/api/v1/firms/{FIRM}/billing", headers=owner)
        self.assertEqual(1, measured.json()["usage"]["documents_uploaded"])
        self.assertEqual(2048, measured.json()["usage"]["storage_bytes"])

        denied = self.client.get(
            f"/api/v1/firms/{FIRM}/billing", headers=self.auth("beto@demo.local"))
        self.assertEqual(403, denied.status_code, denied.text)
        checkout = self.client.post(
            f"/api/v1/firms/{FIRM}/billing/checkout", headers=owner)
        self.assertEqual(503, checkout.status_code, checkout.text)

    def test_runtime_cannot_forge_payment_or_rewrite_subscription(self) -> None:
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute("SELECT set_config('fincilia.subject_id', %s, false)",
                               (SOFIA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "INSERT INTO fincilia.firm_subscription "
                        "(firm_id, plan_version_id, status, source_code, sequence, "
                        "activated_by, idempotency_key, started_at, ended_at) "
                        "VALUES (%s, 'b1000000-0000-4000-8000-000000000001', "
                        "'active', 'payment_provider', 999, %s, %s, now(), now())",
                        (FIRM, SOFIA, str(uuid.uuid4())))
            connection.rollback()

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.subject_id', %s, false)",
                               (SOFIA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.billing_account "
                        "SET configuration_state = 'ready', provider_code = 'fake', "
                        "provider_customer_ref = %s WHERE firm_id = %s",
                        ("sha256:" + "0" * 64, FIRM))
            connection.rollback()


if __name__ == "__main__":
    unittest.main()
