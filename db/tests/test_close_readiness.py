"""FNC-CLS-001 contra API real, PostgreSQL y RLS.

La prueba crea solo calendario sintetico. Deliberadamente no fabrica saldos ni
estados de conciliacion: su ausencia debe mantener el diagnostico bloqueado.
"""

from __future__ import annotations

import datetime as dt
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import (
    MIGRATOR_DSN,
    RUNTIME_DSN,
    build_settings,
)
from fincilia_api.main import create_app


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
ANA = stable_id("subject", "ana")
OWNER = "sofia@demo.local"


class CloseReadinessDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()
        cls.sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if not cls.sources:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company_id in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company_id,))
                    cursor.execute(
                        "DELETE FROM fincilia.source_expectation "
                        "WHERE data_source_id = ANY(%s::uuid[])",
                        (list(cls.sources),))
                    cursor.execute(
                        "DELETE FROM fincilia.source_cycle "
                        "WHERE data_source_id = ANY(%s::uuid[])",
                        (list(cls.sources),))
                    cursor.execute(
                        "DELETE FROM fincilia.data_source "
                        "WHERE data_source_id = ANY(%s::uuid[])",
                        (list(cls.sources),))

    def auth(self) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": OWNER, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def create_expectation(self, company_id: str, marker: str,
                           anchor: dt.date) -> str:
        headers = self.auth()
        source = self.client.post(
            f"/api/v1/companies/{company_id}/sources", headers=headers,
            json={
                "source_family": "bank_account",
                "display_name": f"Fuente cierre sintetica {marker}",
                "purpose_code": "close_diagnostic",
                "timezone": "America/Bogota",
            })
        self.assertEqual(201, source.status_code, source.text)
        source_id = source.json()["data_source_id"]
        type(self).sources.add(source_id)
        cycle = self.client.put(
            f"/api/v1/companies/{company_id}/sources/{source_id}/cycle",
            headers=headers, json={
                "periodicity": "custom",
                "custom_days": 1,
                "due_day_offset": 0,
                "grace_days": 1,
                "responsible_subject_id": ANA,
                "timezone": "America/Bogota",
                "anchor_date": anchor.isoformat(),
            })
        self.assertEqual(200, cycle.status_code, cycle.text)
        generated = self.client.post(
            f"/api/v1/companies/{company_id}/sources/{source_id}/expectations",
            headers=headers, json={"until": anchor.isoformat()})
        self.assertEqual(201, generated.status_code, generated.text)

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)",
                    (company_id,))
                cursor.execute(
                    "SELECT expectation_id FROM fincilia.source_expectation "
                    "WHERE data_source_id = %s", (source_id,))
                return str(cursor.fetchone()[0])

    def test_diagnostic_is_company_scoped_blocked_and_metadata_only(self) -> None:
        anchor = dt.date(2035, 1, 1) + dt.timedelta(
            days=int(uuid.uuid4().hex[:2], 16))
        local_id = self.create_expectation(ESPIGA, uuid.uuid4().hex[:8], anchor)
        foreign_id = self.create_expectation(ANDINOS, uuid.uuid4().hex[:8], anchor)

        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/close-readiness",
            headers=self.auth(), params={"limit": 24})
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("diagnostic_only", body["mode"])
        self.assertFalse(body["close_ready"])
        self.assertFalse(body["can_execute_close"])
        visible = {source["expectation_id"]
                   for period in body["items"] for source in period["sources"]}
        self.assertIn(local_id, visible)
        self.assertNotIn(foreign_id, visible)
        local_period = next(period for period in body["items"]
                            if local_id in {item["expectation_id"]
                                            for item in period["sources"]})
        self.assertEqual("blocked", local_period["status"])
        self.assertFalse(local_period["close_ready"])
        self.assertFalse(local_period["can_execute_close"])
        self.assertIn("account_balances",
                      {item["code"] for item in local_period["blockers"]})
        for source in local_period["sources"]:
            self.assertFalse({"amount", "balance", "currency"} & set(source))

        invalid = self.client.get(
            f"/api/v1/companies/{ESPIGA}/close-readiness",
            headers=self.auth(), params={"limit": 25})
        self.assertEqual(422, invalid.status_code, invalid.text)
        self.assertEqual("close-readiness-limit-invalid",
                         invalid.json()["type"].rsplit("/", 1)[-1])

        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=50",
            headers=self.auth()).json()
        reads = [event for event in events
                 if event["action"] == "close.readiness.read"]
        self.assertTrue(reads)
        self.assertEqual(
            {"limit", "periods_returned", "sources_returned"},
            set(reads[0]["detail"]))

    def test_runtime_rls_does_not_reveal_foreign_expectation(self) -> None:
        anchor = dt.date(2036, 1, 1)
        foreign_id = self.create_expectation(
            ANDINOS, uuid.uuid4().hex[:8], anchor)
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)",
                    (ESPIGA,))
                cursor.execute(
                    "SELECT expectation_id FROM fincilia.source_expectation "
                    "WHERE expectation_id = %s", (foreign_id,))
                self.assertIsNone(cursor.fetchone())


if __name__ == "__main__":
    unittest.main()
