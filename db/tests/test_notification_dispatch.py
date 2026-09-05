"""FNC-NTF-002 contra PostgreSQL real.

Ejercita el protocolo con su rol LOGIN verdadero. Las filas son sintéticas y
únicas; los estados terminales se conservan como evidencia del intento.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import threading
import unittest
import uuid

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN


WORKER_DSN = os.environ.get("FINCILIA_NOTIFICATION_WORKER_URL", "")
ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
ANA = stable_id("subject", "ana")
KMS_KEY = (
    "arn:aws:kms:sa-east-1:123456789012:key/"
    "12345678-1234-1234-1234-123456789abc"
)

worker_source = "/app/notification_worker_src"
if os.path.isdir(worker_source):
    sys.path.insert(0, worker_source)
else:
    sys.path.insert(0, os.path.abspath("workers/notification/src"))

from fincilia_notification_worker import delivery  # noqa: E402


class NotificationDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN or not WORKER_DSN:
            raise unittest.SkipTest("migrator, app and notification worker DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)

    def _destination(self) -> None:
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                               (ANA,))
                cursor.execute(
                    "SELECT fincilia.upsert_verified_notification_destination("
                    "%s, %s, %s, %s)",
                    (ANA, "hmac-sha256:v1:" + "a" * 64, b"x" * 64, KMS_KEY),
                )

    def _queued(self, *, company: str = ESPIGA, max_attempts: int = 5) -> str:
        self._destination()
        marker = str(uuid.uuid4())
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (company,))
                cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                               (ANA,))
                cursor.execute(
                    "INSERT INTO fincilia.notification_preference "
                    "(company_id, subject_id, channel, purpose_code, enabled, locale) "
                    "VALUES (%s, %s, 'email', 'operational_reminder', true, 'es-CO') "
                    "ON CONFLICT (company_id, subject_id, channel, purpose_code) "
                    "DO UPDATE SET enabled = true, locale = 'es-CO'",
                    (company, ANA),
                )
                cursor.execute(
                    "INSERT INTO fincilia.notification_intent "
                    "(company_id, subject_id, template_code, business_key, render_context) "
                    "VALUES (%s, %s, 'period_due_today', %s, "
                    "jsonb_build_object('period_label', '2026-08 synthetic', "
                    "'due_on', '2026-09-05', 'action_url', "
                    "%s::text)) RETURNING intent_id",
                    (company, ANA, marker, f"/recordatorios?empresa={company}"),
                )
                intent_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO fincilia.notification_delivery "
                    "(company_id, subject_id, intent_id, channel, status, "
                    "idempotency_key, available_at, max_attempts) "
                    "VALUES (%s, %s, %s, 'email', 'queued', %s, "
                    "clock_timestamp() - interval '1 second', %s) "
                    "RETURNING delivery_id::text",
                    (company, ANA, intent_id, uuid.uuid4().hex * 2, max_attempts),
                )
                return str(cursor.fetchone()[0])

    def _claim(self) -> delivery.Claim | None:
        with psycopg.connect(WORKER_DSN) as connection:
            return delivery.claim_next(connection, "synthetic-notification-worker")

    def _finish(self, claim: delivery.Claim, **kwargs) -> str:
        with psycopg.connect(WORKER_DSN) as connection:
            return delivery.finish(connection, claim, **kwargs)

    def _arm(self, claim: delivery.Claim) -> str:
        with psycopg.connect(WORKER_DSN) as connection:
            return delivery.arm(connection, claim)

    def _settle(self, claim: delivery.Claim, **kwargs) -> str:
        with psycopg.connect(WORKER_DSN) as connection:
            return delivery.settle(connection, claim, **kwargs)

    @staticmethod
    def _provider_ref() -> str:
        return "sha256:" + uuid.uuid4().hex * 2

    def test_destination_is_ciphertext_only_and_runtime_cannot_read_it(self) -> None:
        self._destination()
        with psycopg.connect(RUNTIME_DSN) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("SELECT * FROM fincilia.notification_destination")
        with psycopg.connect(MIGRATOR_DSN) as connection:
            row = connection.execute(
                "SELECT address_ref, octet_length(encrypted_address), kms_key_ref "
                "FROM fincilia.notification_destination WHERE subject_id = %s",
                (ANA,),
            ).fetchone()
        self.assertEqual(("hmac-sha256:v1:" + "a" * 64, 64, KMS_KEY), row)
        self.assertNotIn("@", repr(row))

    def test_worker_has_only_the_five_protocol_functions(self) -> None:
        with psycopg.connect(WORKER_DSN) as connection:
            rows = connection.execute(
                "SELECT routine_name FROM information_schema.routine_privileges "
                "WHERE grantee = 'fincilia_notification_worker' "
                "AND routine_schema = 'fincilia' ORDER BY routine_name"
            ).fetchall()
        self.assertEqual([
            ("arm_notification_delivery",),
            ("claim_notification_delivery",),
            ("finish_notification_delivery",),
            ("record_notification_feedback",),
            ("settle_armed_notification_delivery",),
        ], rows)
        with psycopg.connect(WORKER_DSN) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("SELECT * FROM fincilia.subject LIMIT 1")

    def test_two_concurrent_claims_have_exactly_one_winner(self) -> None:
        expected = self._queued()
        barrier = threading.Barrier(2)

        def compete() -> delivery.Claim | None:
            with psycopg.connect(WORKER_DSN) as connection:
                barrier.wait(timeout=5)
                return delivery.claim_next(connection, "synthetic-concurrent-worker")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _index: compete(), range(2)))
        winners = [item for item in claims if item is not None]
        self.assertEqual(1, len(winners))
        self.assertEqual(expected, winners[0].delivery_id)
        self.assertEqual("armed", self._arm(winners[0]))
        self.assertEqual("sent", self._settle(
            winners[0], outcome="sent", provider_message_ref=self._provider_ref()))

    def test_fencing_prevents_a_stale_worker_from_overwriting_success(self) -> None:
        expected = self._queued()
        claim = self._claim()
        self.assertIsNotNone(claim)
        self.assertEqual(expected, claim.delivery_id)
        self.assertEqual("armed", self._arm(claim))
        self.assertEqual("sent", self._settle(
            claim, outcome="sent", provider_message_ref=self._provider_ref()))
        self.assertEqual("stale_lease", self._settle(
            claim, outcome="fatal", reason_code="late_worker"))

    def test_retry_limit_and_unknown_outcome_fail_closed(self) -> None:
        retry_id = self._queued(max_attempts=1)
        retry_claim = self._claim()
        self.assertEqual(retry_id, retry_claim.delivery_id)
        self.assertEqual("armed", self._arm(retry_claim))
        self.assertEqual("failed", self._settle(
            retry_claim, outcome="retryable", reason_code="provider_rate_limited"))

        uncertain_id = self._queued()
        uncertain_claim = self._claim()
        self.assertEqual(uncertain_id, uncertain_claim.delivery_id)
        self.assertEqual("armed", self._arm(uncertain_claim))
        self.assertEqual("uncertain", self._settle(
            uncertain_claim, outcome="uncertain", reason_code="provider_outcome_unknown"))
        self.assertIsNone(self._claim())

    def test_feedback_is_idempotent_and_bounce_suppresses_destination(self) -> None:
        expected = self._queued()
        claim = self._claim()
        self.assertEqual(expected, claim.delivery_id)
        provider_ref = self._provider_ref()
        self.assertEqual("armed", self._arm(claim))
        self.assertEqual("sent", self._settle(
            claim, outcome="sent", provider_message_ref=provider_ref))
        with psycopg.connect(WORKER_DSN) as connection:
            first = delivery.record_feedback(
                connection, event_digest=uuid.uuid4().hex * 2,
                provider_message_ref=provider_ref, event_type="delivered")
        replay_digest = uuid.uuid4().hex * 2
        with psycopg.connect(WORKER_DSN) as connection:
            first_for_replay = delivery.record_feedback(
                connection, event_digest=replay_digest,
                provider_message_ref=provider_ref, event_type="delivered")
            replay = delivery.record_feedback(
                connection, event_digest=replay_digest,
                provider_message_ref=provider_ref, event_type="delivered")
            bounce = delivery.record_feedback(
                connection, event_digest=uuid.uuid4().hex * 2,
                provider_message_ref=provider_ref, event_type="hard_bounce")
        self.assertEqual(("delivered", "delivered", "replayed", "hard_bounce"),
                         (first, first_for_replay, replay, bounce))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            state = connection.execute(
                "SELECT status, suppression_reason FROM fincilia.notification_destination "
                "WHERE subject_id = %s", (ANA,)).fetchone()
        self.assertEqual(("suppressed", "hard_bounce"), state)


if __name__ == "__main__":
    unittest.main()
