"""FNC-SMB-006 contra PostgreSQL real: cadencia de carga y recordatorio en la app.

V0071. La cadencia es un historial append-only que solo el owner activo cambia,
aislado por RLS. El recordatorio usa `notification_intent` y nace con la entrega
externa suprimida (`in_app_only`): ningun mensaje sale de Fincilia (ADR-037).

Trabaja sobre ANDINOS. Las filas de historial que deja son la traza correcta de
lo que ocurrio; los recordatorios sinteticos se limpian al terminar, como en la
suite de recordatorios operativos. Solo datos sinteticos.
"""

from __future__ import annotations

import datetime as dt
import json
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api import upload_schedule
from fincilia_api.main import create_app


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
SOFIA = stable_id("subject", "sofia")
ANA = stable_id("subject", "ana")
OWNER = "sofia@demo.local"
PREPARER = "ana@demo.local"
AUDITOR = "carla@demo.local"


def slug(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


def purge_upload_reminders() -> None:
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (ANDINOS,))
            cursor.execute("SELECT set_config('fincilia.subject_id', %s, false)",
                           (SOFIA,))
            cursor.execute(
                "DELETE FROM fincilia.notification_delivery d "
                "USING fincilia.notification_intent i "
                "WHERE i.intent_id = d.intent_id AND i.company_id = d.company_id "
                "  AND i.company_id = %s AND i.template_code = 'statement_upload_due'",
                (ANDINOS,))
            cursor.execute(
                "DELETE FROM fincilia.notification_intent "
                "WHERE company_id = %s AND template_code = 'statement_upload_due'",
                (ANDINOS,))


class UploadScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        purge_upload_reminders()
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        purge_upload_reminders()

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def url(self, company: str = ANDINOS) -> str:
        return f"/api/v1/companies/{company}/upload-schedule"

    def current(self) -> str | None:
        return self.client.get(self.url(), headers=self.auth(OWNER)).json()["cadence"]

    def other_cadence(self) -> str:
        return "weekly" if self.current() != "weekly" else "monthly"

    # ------------------------------------------------------------------ API #

    def test_owner_changes_the_cadence_and_others_only_read(self) -> None:
        read = self.client.get(self.url(), headers=self.auth(PREPARER))
        self.assertEqual(200, read.status_code, read.text)
        self.assertFalse(read.json()["can_change"])
        self.assertEqual([], read.json()["channels"]["external"])
        self.assertIn("in_app_only", read.json()["notice"])

        target = self.other_cadence()
        refused = self.client.put(self.url(), headers=self.auth(PREPARER),
                                  json={"cadence": target})
        self.assertEqual(403, refused.status_code, refused.text)
        self.assertEqual("upload-schedule-owner-required", slug(refused))
        invalid = self.client.put(self.url(), headers=self.auth(OWNER),
                                  json={"cadence": "daily"})
        self.assertEqual(422, invalid.status_code, invalid.text)

        changed = self.client.put(self.url(), headers=self.auth(OWNER),
                                  json={"cadence": target})
        self.assertEqual(200, changed.status_code, changed.text)
        body = changed.json()
        self.assertTrue(body["changed"])
        self.assertTrue(body["can_change"])
        self.assertEqual(target, body["cadence"])
        self.assertEqual(target, body["history"][0]["cadence"])
        self.assertEqual(SOFIA, body["history"][0]["changed_by"])
        period = body["current_period"]
        self.assertIn(period["reminder_state"], {"received", "upcoming", "due_soon"})
        self.assertLessEqual(period["period_start"], period["period_end"])

        again = self.client.put(self.url(), headers=self.auth(OWNER),
                                json={"cadence": target})
        self.assertEqual(200, again.status_code, again.text)
        self.assertFalse(again.json()["changed"])
        self.assertEqual(body["history"][0]["version"],
                         again.json()["history"][0]["version"])

        # Otra empresa no se convierte en un formulario vacio.
        foreign = self.client.get(self.url(ESPIGA), headers=self.auth(AUDITOR))
        self.assertEqual(403, foreign.status_code, foreign.text)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ANDINOS,))
                cursor.execute(
                    "SELECT outcome, detail FROM fincilia.audit_event "
                    "WHERE action = 'company.upload_schedule.change' "
                    "ORDER BY occurred_at DESC LIMIT 2")
                audited = cursor.fetchall()
        self.assertEqual({"allowed", "denied"}, {row[0] for row in audited})

    def test_sync_endpoint_never_reports_an_external_message(self) -> None:
        response = self.client.post(
            f"/api/v1/companies/{ANDINOS}/notifications/reminders/sync",
            headers=self.auth(OWNER))
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("disabled", response.json()["adapter_state"])
        self.assertEqual("no external message was sent", response.json()["notice"])

    # ------------------------------------------------------------- database #

    def _runtime(self, company: str, subject: str | None = None):
        connection = psycopg.connect(RUNTIME_DSN)
        cursor = connection.cursor()
        cursor.execute("SELECT set_config('fincilia.company_id', %s, false)", (company,))
        if subject:
            cursor.execute("SELECT set_config('fincilia.subject_id', %s, false)",
                           (subject,))
        return connection, cursor

    def _audit(self, cursor, company: str, subject: str) -> str:
        audit_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO fincilia.audit_event (audit_event_id, company_id, subject_id, "
            "action, resource_kind, resource_ref, outcome) VALUES "
            "(%s, %s, %s, 'company.upload_schedule.change', 'company', %s, 'allowed')",
            (audit_id, company, subject, company))
        return audit_id

    def test_database_enforces_owner_version_append_only_and_rls(self) -> None:
        connection, cursor = self._runtime(ANDINOS)
        try:
            cursor.execute(
                "SELECT COALESCE(max(version), 0) + 1 "
                "FROM fincilia.company_upload_schedule_change")
            version = int(cursor.fetchone()[0])
            cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (ANDINOS,))
            current = cursor.fetchone()[0]
            target = "biweekly" if current != "biweekly" else "weekly"

            def insert(changed_by: str, *, at_version: int = version,
                       cadence: str = target, company: str = ANDINOS) -> None:
                audit_id = self._audit(cursor, company, changed_by)
                cursor.execute(
                    "INSERT INTO fincilia.company_upload_schedule_change "
                    "(company_id, version, cadence, changed_by, audit_event_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (company, at_version, cadence, changed_by, audit_id))

            with self.assertRaises(psycopg.errors.InsufficientPrivilege) as raised:
                with connection.transaction():
                    insert(ANA)
            self.assertEqual("ck_upload_schedule_change_owner",
                             raised.exception.diag.constraint_name)
            with self.assertRaises(psycopg.errors.CheckViolation):
                with connection.transaction():
                    insert(SOFIA, at_version=version + 5)
            if current is not None:
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        insert(SOFIA, cadence=current)
            # Una fila de otra empresa no entra bajo este alcance (RLS).
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    cursor.execute(
                        "INSERT INTO fincilia.company_upload_schedule_change "
                        "(company_id, version, cadence, changed_by, audit_event_id) "
                        "VALUES (%s, 1, 'weekly', %s, %s)",
                        (ESPIGA, SOFIA, str(uuid.uuid4())))
            with connection.transaction():
                insert(SOFIA)
            cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (ANDINOS,))
            self.assertEqual(target, cursor.fetchone()[0])
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    cursor.execute(
                        "UPDATE fincilia.company_upload_schedule_change "
                        "SET cadence = 'monthly' WHERE company_id = %s", (ANDINOS,))
            connection.commit()
        finally:
            connection.close()

        # Otra empresa no ve el historial ni la cadencia.
        connection, cursor = self._runtime(ESPIGA)
        try:
            cursor.execute(
                "SELECT count(*) FROM fincilia.company_upload_schedule_change "
                "WHERE company_id = %s", (ANDINOS,))
            self.assertEqual(0, cursor.fetchone()[0])
            cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (ANDINOS,))
            self.assertIsNone(cursor.fetchone()[0])
        finally:
            connection.close()

        # Ni el migrador reescribe la historia: el disparador append-only manda.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ANDINOS,))
                with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                    cursor.execute(
                        "DELETE FROM fincilia.company_upload_schedule_change "
                        "WHERE company_id = %s", (ANDINOS,))
            connection.rollback()

    def test_reminder_is_in_app_only_once_per_period(self) -> None:
        # Garantiza una cadencia mensual por la via legal (owner + API).
        if self.current() != "monthly":
            response = self.client.put(self.url(), headers=self.auth(OWNER),
                                       json={"cadence": "monthly"})
            self.assertEqual(200, response.status_code, response.text)
        # Un mes historico sin cargas, dentro de la ventana de aviso.
        local_now = dt.datetime(2020, 3, 28, 9, 0)
        connection, cursor = self._runtime(ANDINOS, SOFIA)
        try:
            first = upload_schedule.sync_upload_reminder(
                connection, company_id=ANDINOS, subject_id=SOFIA, local_now=local_now)
            second = upload_schedule.sync_upload_reminder(
                connection, company_id=ANDINOS, subject_id=SOFIA, local_now=local_now)
            early = upload_schedule.sync_upload_reminder(
                connection, company_id=ANDINOS, subject_id=SOFIA,
                local_now=dt.datetime(2020, 4, 2, 9, 0))
            self.assertEqual({"created": 1, "replayed": 0, "suppressed": 1}, first)
            self.assertEqual({"created": 0, "replayed": 1, "suppressed": 0}, second)
            self.assertEqual({"created": 0, "replayed": 0, "suppressed": 0}, early)
            cursor.execute(
                "SELECT d.status, d.suppression_reason, d.in_app_only, d.channel, "
                "       i.render_context "
                "FROM fincilia.notification_delivery d "
                "JOIN fincilia.notification_intent i ON i.intent_id = d.intent_id "
                "WHERE i.template_code = 'statement_upload_due' "
                "  AND i.business_key LIKE 'upload:monthly:2020-03-01:%%'")
            rows = cursor.fetchall()
            self.assertEqual(1, len(rows))
            status, reason, in_app, channel, context = rows[0]
            self.assertEqual(("suppressed", "in_app_only", True, "email"),
                             (status, reason, in_app, channel))
            self.assertEqual({"period_label", "due_on", "action_url"}, set(context))

            # Ninguna entrega de esta plantilla puede nacer encolada.
            cursor.execute(
                "INSERT INTO fincilia.notification_intent (company_id, subject_id, "
                "template_code, business_key, render_context) VALUES "
                "(%s, %s, 'statement_upload_due', %s, %s::jsonb) RETURNING intent_id",
                (ANDINOS, SOFIA, f"upload:monthly:2020-05-01:{ANDINOS}",
                 json.dumps({"period_label": "2020-05-01 / 2020-05-31",
                             "due_on": "2020-05-31",
                             "action_url": f"/recordatorios?empresa={ANDINOS}"})))
            intent_id = str(cursor.fetchone()[0])
            with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                with connection.transaction():
                    cursor.execute(
                        "INSERT INTO fincilia.notification_delivery (company_id, "
                        "subject_id, intent_id, channel, status, idempotency_key) "
                        "VALUES (%s, %s, %s, 'email', 'queued', %s)",
                        (ANDINOS, SOFIA, intent_id, "f" * 64))
            self.assertEqual("ck_notification_delivery_in_app_only",
                             raised.exception.diag.constraint_name)
            connection.commit()
        finally:
            connection.close()

        listed = self.client.get(
            f"/api/v1/companies/{ANDINOS}/notifications/deliveries/me",
            headers=self.auth(OWNER))
        self.assertEqual(200, listed.status_code, listed.text)
        ours = [item for item in listed.json()
                if item["template_code"] == "statement_upload_due"]
        self.assertTrue(ours)
        self.assertTrue(all(item["status"] == "suppressed" for item in ours))


if __name__ == "__main__":
    unittest.main()
