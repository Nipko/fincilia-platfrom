"""FNC-CLS-005 contra API, PostgreSQL real, RLS, SoD y concurrencia."""

from __future__ import annotations

import datetime as dt
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import (
    MIGRATOR_DSN,
    RUNTIME_DSN,
    build_settings,
)
from fincilia_api import close_review
from fincilia_api.main import create_app


ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
ANA_ID = stable_id("subject", "ana")
BETO_ID = stable_id("subject", "beto")
SOFIA_ID = stable_id("subject", "sofia")
WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")


class CloseReviewPacketDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()
        cls.sources: set[str] = set()
        cls.packets: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                if cls.packets:
                    packet_ids = list(cls.packets)
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_command_receipt "
                        "DISABLE TRIGGER close_review_receipt_append_only")
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_decision "
                        "DISABLE TRIGGER close_review_decision_append_only")
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_packet "
                        "DISABLE TRIGGER close_review_packet_append_only")
                    cursor.execute(
                        "DELETE FROM fincilia.close_review_command_receipt "
                        "WHERE result_ref = ANY(%s::uuid[]) OR result_ref IN ("
                        " SELECT decision_id FROM fincilia.close_review_decision "
                        " WHERE packet_id = ANY(%s::uuid[]))",
                        (packet_ids, packet_ids))
                    cursor.execute(
                        "DELETE FROM fincilia.close_review_decision "
                        "WHERE packet_id = ANY(%s::uuid[])", (packet_ids,))
                    cursor.execute(
                        "DELETE FROM fincilia.close_review_packet "
                        "WHERE packet_id = ANY(%s::uuid[])", (packet_ids,))
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_command_receipt "
                        "ENABLE TRIGGER close_review_receipt_append_only")
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_decision "
                        "ENABLE TRIGGER close_review_decision_append_only")
                    cursor.execute(
                        "ALTER TABLE fincilia.close_review_packet "
                        "ENABLE TRIGGER close_review_packet_append_only")
                if cls.sources:
                    source_ids = list(cls.sources)
                    cursor.execute(
                        "DELETE FROM fincilia.source_expectation "
                        "WHERE data_source_id = ANY(%s::uuid[])", (source_ids,))
                    cursor.execute(
                        "DELETE FROM fincilia.source_cycle "
                        "WHERE data_source_id = ANY(%s::uuid[])", (source_ids,))
                    cursor.execute(
                        "DELETE FROM fincilia.data_source "
                        "WHERE data_source_id = ANY(%s::uuid[])", (source_ids,))

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/session",
            json={"username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def period(self, *, anchor: dt.date | None = None) -> tuple[str, str]:
        anchor = anchor or (
            dt.date(2040, 1, 1)
            + dt.timedelta(days=int(uuid.uuid4().hex[:5], 16) % 5000))
        marker = uuid.uuid4().hex[:8]
        source = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources",
            headers=self.auth("sofia@demo.local"), json={
                "source_family": "bank_account",
                "display_name": f"Fuente revision sintetica {marker}",
                "purpose_code": "close_review_test",
                "timezone": "America/Bogota",
            })
        self.assertEqual(201, source.status_code, source.text)
        source_id = source.json()["data_source_id"]
        type(self).sources.add(source_id)
        cycle = self.client.put(
            f"/api/v1/companies/{ESPIGA}/sources/{source_id}/cycle",
            headers=self.auth("sofia@demo.local"), json={
                "periodicity": "custom", "custom_days": 1,
                "due_day_offset": 0, "grace_days": 1,
                "responsible_subject_id": ANA_ID,
                "timezone": "America/Bogota", "anchor_date": anchor.isoformat(),
            })
        self.assertEqual(200, cycle.status_code, cycle.text)
        generated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source_id}/expectations",
            headers=self.auth("sofia@demo.local"), json={"until": anchor.isoformat()})
        self.assertEqual(201, generated.status_code, generated.text)
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT period_start, period_end FROM fincilia.source_expectation "
                    "WHERE data_source_id=%s", (source_id,))
                row = cursor.fetchone()
        return row[0].isoformat(), row[1].isoformat()

    def prepare(self, period: tuple[str, str], *, actor: str = "ana@demo.local",
                reviewer_id: str = BETO_ID, key: str | None = None):
        key = key or f"cls005-prepare-{uuid.uuid4()}"
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/close-review/packets",
            headers={**self.auth(actor), "Idempotency-Key": key},
            json={"period_start": period[0], "period_end": period[1],
                  "assigned_reviewer_id": reviewer_id})
        if response.status_code in (200, 201):
            type(self).packets.add(response.json()["packet_id"])
        return response

    def decide(self, packet_id: str, *, actor: str = "beto@demo.local",
               decision: str = "changes_requested",
               reason: str = "missing_evidence", key: str | None = None):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/close-review/packets/"
            f"{packet_id}/decision",
            headers={**self.auth(actor),
                     "Idempotency-Key": key or f"cls005-decide-{uuid.uuid4()}"},
            json={"decision": decision, "reason_code": reason})

    def test_prepare_replay_manifest_and_narrow_reviewer_list(self) -> None:
        period = self.period()
        reviewers = self.client.get(
            f"/api/v1/companies/{ESPIGA}/close-review/reviewers",
            headers=self.auth("ana@demo.local"))
        self.assertEqual(200, reviewers.status_code, reviewers.text)
        people = reviewers.json()
        self.assertEqual({BETO_ID, SOFIA_ID}, {item["subject_id"] for item in people})
        self.assertNotIn(ANA_ID, {item["subject_id"] for item in people})
        self.assertNotIn("@demo.local", reviewers.text)

        key = f"cls005-replay-{uuid.uuid4()}"
        created = self.prepare(period, key=key)
        self.assertEqual(201, created.status_code, created.text)
        body = created.json()
        self.assertEqual("pending_review", body["status"])
        self.assertEqual("blocked", body["diagnostic_status"])
        self.assertEqual("none", body["financial_effect"])
        self.assertFalse(body["certifies_close"])
        self.assertFalse(body["can_execute_close"])
        self.assertEqual(64, len(body["manifest_digest"]))
        forbidden = {"amount", "currency", "currency_code", "source_name",
                     "account_name", "detail", "value"}

        def keys(value):
            if isinstance(value, dict):
                for name, child in value.items():
                    yield name
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertFalse(forbidden & set(keys(body["manifest"])))
        replay = self.prepare(period, key=key)
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(body["packet_id"], replay.json()["packet_id"])
        self.assertTrue(replay.json()["replayed"])
        conflict = self.prepare(period, reviewer_id=SOFIA_ID, key=key)
        self.assertEqual(409, conflict.status_code, conflict.text)
        self.assertEqual("close-review-idempotency-conflict",
                         conflict.json()["type"].rsplit("/", 1)[-1])

    def test_blocked_positive_sod_and_terminal_decision_fail_closed(self) -> None:
        period = self.period()
        packet = self.prepare(period).json()
        positive = self.decide(
            packet["packet_id"], decision="evidence_reviewed",
            reason="controls_reviewed")
        self.assertEqual(409, positive.status_code, positive.text)
        self.assertEqual("close-review-evidence-blocked",
                         positive.json()["type"].rsplit("/", 1)[-1])
        decided = self.decide(packet["packet_id"])
        self.assertEqual(201, decided.status_code, decided.text)
        self.assertEqual("changes_requested", decided.json()["status"])
        self.assertEqual("none", decided.json()["financial_effect"])
        terminal = self.decide(packet["packet_id"], reason="quality_blocker")
        self.assertEqual(409, terminal.status_code, terminal.text)

        owner_packet = self.prepare(
            self.period(), actor="sofia@demo.local", reviewer_id=BETO_ID).json()
        wrong_reviewer = self.decide(
            owner_packet["packet_id"], actor="sofia@demo.local")
        self.assertEqual(409, wrong_reviewer.status_code, wrong_reviewer.text)
        self.assertEqual("close-review-segregation-of-duties",
                         wrong_reviewer.json()["type"].rsplit("/", 1)[-1])

    def test_material_drift_requires_a_new_packet_version(self) -> None:
        anchor = dt.date(2055, 5, 5)
        period = self.period(anchor=anchor)
        packet = self.prepare(period).json()
        self.period(anchor=anchor)  # una fuente nueva cambia la manifestacion exacta
        stale = self.decide(packet["packet_id"])
        self.assertEqual(409, stale.status_code, stale.text)
        self.assertEqual("close-review-evidence-stale",
                         stale.json()["type"].rsplit("/", 1)[-1])
        replacement = self.prepare(period).json()
        self.assertEqual(packet["version"] + 1, replacement["version"])
        reviewed = self.decide(replacement["packet_id"])
        self.assertEqual(201, reviewed.status_code, reviewed.text)

    def test_rls_append_only_and_worker_denial_are_real(self) -> None:
        packet = self.prepare(self.period()).json()
        packet_id = packet["packet_id"]
        with psycopg.connect(RUNTIME_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ANDINOS,))
                cursor.execute(
                    "SELECT packet_id FROM fincilia.close_review_packet "
                    "WHERE packet_id=%s", (packet_id,))
                self.assertIsNone(cursor.fetchone())
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                for statement in (
                    "UPDATE fincilia.close_review_packet SET version=99 "
                    f"WHERE packet_id='{packet_id}'",
                    "DELETE FROM fincilia.close_review_packet "
                    f"WHERE packet_id='{packet_id}'",
                ):
                    with self.subTest(statement=statement), self.assertRaises(
                            psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement)
        if WORKER_DSN:
            with psycopg.connect(WORKER_DSN, autocommit=True) as worker:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    worker.execute("SELECT * FROM fincilia.close_review_packet")

    def test_database_rejects_manifest_extension_and_ineligible_reviewer(self) -> None:
        packet = self.prepare(self.period()).json()
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                for label, manifest_sql, reviewer in (
                    ("extra financial key", "manifest || '{\"amount\": 1}'::jsonb",
                     BETO_ID),
                    ("preparer role is not reviewer", "manifest", ANA_ID),
                ):
                    with self.subTest(label=label), self.assertRaises(psycopg.Error):
                        cursor.execute(
                            "INSERT INTO fincilia.close_review_packet "
                            "(company_id, period_start, period_end, version, "
                            " manifest_schema_version, manifest, manifest_digest, "
                            " diagnostic_status, prepared_by, assigned_reviewer_id, "
                            " audit_event_id) SELECT company_id, period_start, "
                            "period_end, version + 1000, manifest_schema_version, "
                            f"{manifest_sql}, manifest_digest, diagnostic_status, "
                            "prepared_by, %s, audit_event_id FROM "
                            "fincilia.close_review_packet WHERE packet_id=%s",
                            (reviewer, packet["packet_id"]))

    def test_concurrent_decisions_have_one_winner(self) -> None:
        packet = self.prepare(self.period()).json()

        def attempt() -> str:
            try:
                with psycopg.connect(RUNTIME_DSN) as connection:
                    connection.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    connection.execute(
                        "SELECT set_config('fincilia.subject_id', %s, false)",
                        (BETO_ID,))
                    result = close_review.decide_packet(
                        connection, company_id=ESPIGA, actor_id=BETO_ID,
                        idempotency_key=f"cls005-race-{uuid.uuid4()}",
                        packet_id=packet["packet_id"],
                        decision="changes_requested", reason_code="missing_evidence")
                    connection.commit()
                    return result["status"]
            except close_review.CloseReviewError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _index: attempt(), range(2)))
        self.assertEqual(1, outcomes.count("changes_requested"), outcomes)
        self.assertEqual(1, outcomes.count("close-review-already-decided"), outcomes)


if __name__ == "__main__":
    unittest.main()
