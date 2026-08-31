"""FNC-OPS-001 contra PostgreSQL real, autorizacion y RLS.

Los recordatorios son una lectura del calendario persistido. Estas pruebas no
envian mensajes ni cambian el estado de una expectativa.
"""

from __future__ import annotations

import datetime as dt
import unittest
import uuid
from zoneinfo import ZoneInfo

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
SANDBOX_A = stable_id("company", "sandbox_a")
ANA = stable_id("subject", "ana")
OWNER = "sofia@demo.local"
REVIEWER = "beto@demo.local"


class OperationalReminderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()
        cls.sources: set[str] = set()
        cls.expectations: dict[str, set[str]] = {ESPIGA: set(), ANDINOS: set()}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if not cls.sources:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,))
                    cursor.execute(
                        "DELETE FROM fincilia.notification_delivery")
                    cursor.execute(
                        "DELETE FROM fincilia.notification_intent")
                    cursor.execute(
                        "DELETE FROM fincilia.notification_preference")
                    cursor.execute(
                        "DELETE FROM fincilia.source_expectation "
                        "WHERE data_source_id = ANY(%s)", (list(cls.sources),))
                    cursor.execute(
                        "DELETE FROM fincilia.source_cycle "
                        "WHERE data_source_id = ANY(%s)", (list(cls.sources),))
                    cursor.execute(
                        "DELETE FROM fincilia.data_source "
                        "WHERE data_source_id = ANY(%s)", (list(cls.sources),))

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def create_period(self, *, company: str, marker: str,
                      anchor: dt.date, due_offset: int = 0,
                      grace_days: int = 1) -> tuple[str, str]:
        headers = self.auth(OWNER)
        source_response = self.client.post(
            f"/api/v1/companies/{company}/sources", headers=headers,
            json={
                "source_family": "bank_account",
                "display_name": f"Fuente recordatorio sintetico {marker}",
                "purpose_code": "operational",
                "timezone": "America/Bogota",
            })
        self.assertEqual(201, source_response.status_code, source_response.text)
        source_id = source_response.json()["data_source_id"]
        type(self).sources.add(source_id)

        cycle = self.client.put(
            f"/api/v1/companies/{company}/sources/{source_id}/cycle",
            headers=headers,
            json={
                "periodicity": "custom",
                "custom_days": 1,
                "due_day_offset": due_offset,
                "grace_days": grace_days,
                "responsible_subject_id": ANA,
                "timezone": "America/Bogota",
                "anchor_date": anchor.isoformat(),
            })
        self.assertEqual(200, cycle.status_code, cycle.text)
        generated = self.client.post(
            f"/api/v1/companies/{company}/sources/{source_id}/expectations",
            headers=headers, json={"until": anchor.isoformat()})
        self.assertEqual(201, generated.status_code, generated.text)
        self.assertEqual(1, generated.json()["created"])

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (company,))
                cursor.execute(
                    "SELECT expectation_id FROM fincilia.source_expectation "
                    "WHERE data_source_id = %s", (source_id,))
                expectation_id = str(cursor.fetchone()[0])
        type(self).expectations[company].add(expectation_id)
        return source_id, expectation_id

    def test_company_scoped_center_classifies_pages_and_audits_metadata(self) -> None:
        today = dt.datetime.now(ZoneInfo("America/Bogota")).date()
        _, overdue_id = self.create_period(
            company=ESPIGA, marker=f"overdue-{uuid.uuid4().hex[:8]}",
            anchor=today - dt.timedelta(days=10), grace_days=1)
        _, today_id = self.create_period(
            company=ESPIGA, marker=f"today-{uuid.uuid4().hex[:8]}",
            anchor=today)
        _, foreign_id = self.create_period(
            company=ANDINOS, marker=f"foreign-{uuid.uuid4().hex[:8]}",
            anchor=today)

        headers = self.auth(OWNER)
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operations/periods",
            headers=headers, params={"status": "all", "limit": 50})
        self.assertEqual(200, response.status_code, response.text)
        report = response.json()
        indexed = {item["expectation_id"]: item for item in report["items"]}
        self.assertEqual("overdue", indexed[overdue_id]["reminder_state"])
        self.assertEqual("due_today", indexed[today_id]["reminder_state"])
        self.assertTrue(indexed[today_id]["responsible_eligible"])
        self.assertEqual("Ana Preparadora", indexed[today_id]["responsible_name"])
        self.assertNotIn("company_id", indexed[today_id])
        self.assertNotIn(foreign_id, indexed)
        self.assertIn(today.isoformat(), report["local_as_of_dates"])
        self.assertTrue(report["evaluated_at"].endswith("Z"))
        self.assertIn("in_app_projection_only", report["notice"])

        foreign = self.client.get(
            f"/api/v1/companies/{ANDINOS}/operations/periods",
            headers=headers, params={"status": "all", "limit": 50})
        self.assertEqual(200, foreign.status_code, foreign.text)
        foreign_ids = {item["expectation_id"] for item in foreign.json()["items"]}
        self.assertIn(foreign_id, foreign_ids)
        self.assertNotIn(today_id, foreign_ids)

        # Una pagina pequena produce cursor keyset y la siguiente no repite fila.
        first_page = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operations/periods",
            headers=headers, params={"status": "all", "limit": 1}).json()
        self.assertTrue(first_page["has_more"])
        second_page = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operations/periods",
            headers=headers,
            params={"status": "all", "limit": 1,
                    "cursor": first_page["next_cursor"]})
        self.assertEqual(200, second_page.status_code, second_page.text)
        self.assertNotEqual(first_page["items"][0]["expectation_id"],
                            second_page.json()["items"][0]["expectation_id"])

        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=50",
            headers=self.auth(REVIEWER)).json()
        reads = [event for event in events
                 if event["action"] == "operations.periods.read"]
        self.assertTrue(reads)
        self.assertEqual({"filter", "returned", "truncated"},
                         set(reads[0]["detail"]))
        self.assertNotIn("Ana", str(reads[0]))

    def test_permission_cursor_and_rls_fail_closed(self) -> None:
        today = dt.datetime.now(ZoneInfo("America/Bogota")).date()
        _, foreign_id = self.create_period(
            company=ANDINOS, marker=f"rls-{uuid.uuid4().hex[:8]}",
            anchor=today)

        denied = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operations/periods",
            headers=self.auth(REVIEWER))
        self.assertEqual(403, denied.status_code, denied.text)
        invalid = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operations/periods",
            headers=self.auth(OWNER), params={"cursor": "not-a-cursor"})
        self.assertEqual(422, invalid.status_code, invalid.text)
        self.assertEqual(
            "operations-cursor-invalid",
            invalid.json()["type"].rsplit("/", 1)[-1])

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)",
                    (ESPIGA,))
                cursor.execute(
                    "SELECT expectation_id FROM fincilia.source_expectation "
                    "WHERE expectation_id = %s", (foreign_id,))
                self.assertIsNone(cursor.fetchone())

    def test_notification_preferences_sync_and_delivery_states_are_honest(self) -> None:
        today = dt.datetime.now(ZoneInfo("America/Bogota")).date()
        _, expectation_id = self.create_period(
            company=ESPIGA, marker=f"notify-{uuid.uuid4().hex[:8]}", anchor=today)
        ana = self.auth("ana@demo.local")

        default = self.client.get(
            f"/api/v1/companies/{ESPIGA}/notifications/preferences/me",
            headers=ana)
        self.assertEqual(200, default.status_code, default.text)
        self.assertFalse(default.json()["enabled"])
        self.assertEqual("provider_configuration_pending",
                         default.json()["destination_state"])

        enabled = self.client.put(
            f"/api/v1/companies/{ESPIGA}/notifications/preferences/me",
            headers=ana, json={
                "enabled": True, "locale": "es-CO",
                "timezone": "America/Bogota", "quiet_from": "20:00",
                "quiet_until": "07:00"})
        self.assertEqual(200, enabled.status_code, enabled.text)
        self.assertTrue(enabled.json()["enabled"])

        first = self.client.post(
            f"/api/v1/companies/{ESPIGA}/notifications/reminders/sync",
            headers=ana)
        self.assertEqual(200, first.status_code, first.text)
        self.assertGreaterEqual(first.json()["created"], 1)
        self.assertEqual("disabled", first.json()["adapter_state"])
        replay = self.client.post(
            f"/api/v1/companies/{ESPIGA}/notifications/reminders/sync",
            headers=ana)
        self.assertEqual(0, replay.json()["created"])
        self.assertGreaterEqual(replay.json()["replayed"], 1)

        history = self.client.get(
            f"/api/v1/companies/{ESPIGA}/notifications/deliveries/me",
            headers=ana)
        self.assertEqual(200, history.status_code, history.text)
        selected = next(item for item in history.json()
                        if expectation_id in repr(item["context"]) or
                        item["context"]["due_on"] == today.isoformat())
        self.assertEqual("suppressed", selected["status"])
        self.assertEqual("adapter_unconfigured", selected["suppression_reason"])
        rendered = repr(selected).lower()
        for forbidden in ("amount", "balance", "account", "tax_id", "attachment"):
            self.assertNotIn(forbidden, rendered)

        invalid = self.client.put(
            f"/api/v1/companies/{ESPIGA}/notifications/preferences/me",
            headers=ana, json={
                "enabled": True, "locale": "es-CO", "timezone": "Mars/Base",
                "quiet_from": "20:00", "quiet_until": "07:00"})
        self.assertEqual(422, invalid.status_code, invalid.text)

        denied = self.client.get(
            f"/api/v1/companies/{SANDBOX_A}/notifications/preferences/me",
            headers=ana)
        self.assertEqual(403, denied.status_code, denied.text)


if __name__ == "__main__":
    unittest.main()
