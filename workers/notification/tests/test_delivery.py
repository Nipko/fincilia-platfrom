from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from fincilia_platform.email_delivery import DeliveryError
from fincilia_notification_worker import delivery, main


SECRET_DESTINATION = "synthetic-recipient@example.test"


class FakeDatabase:
    @contextmanager
    def session(self):
        yield Mock()


def claim() -> delivery.Claim:
    return delivery.Claim(
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
        "period_due_today",
        {"period_label": "2026-08-01 / 2026-08-31", "due_on": "2026-09-05",
         "action_url": "/recordatorios?empresa=synthetic"},
        "es-CO", "a" * 64, b"x" * 48, "b" * 64,
        "arn:aws:kms:sa-east-1:123456789012:key/"
        "12345678-1234-1234-1234-123456789abc",
        "44444444-4444-4444-8444-444444444444", 1,
    )


class ProcessTests(unittest.TestCase):
    def test_success_persists_only_the_provider_digest(self) -> None:
        protector = Mock()
        protector.decrypt.return_value = SECRET_DESTINATION
        adapter = Mock()
        adapter.deliver.return_value = "sha256:" + "c" * 64
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "arm", return_value="armed") as arm, \
             patch.object(delivery, "settle", return_value="sent") as settle:
            self.assertTrue(main.process_one(FakeDatabase(), protector, adapter, "worker-1"))
        arm.assert_called_once()
        settle.assert_called_once()
        kwargs = settle.call_args.kwargs
        self.assertEqual("sent", kwargs["outcome"])
        self.assertEqual("sha256:" + "c" * 64, kwargs["provider_message_ref"])
        self.assertNotIn(SECRET_DESTINATION, repr(settle.call_args))

    def test_retryable_failure_is_bounded_by_the_database_protocol(self) -> None:
        protector = Mock()
        protector.decrypt.return_value = SECRET_DESTINATION
        adapter = Mock()
        adapter.deliver.side_effect = DeliveryError("provider_rate_limited", "retryable")
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "arm", return_value="armed"), \
             patch.object(delivery, "settle", return_value="queued") as settle:
            main.process_one(FakeDatabase(), protector, adapter, "worker-1")
        self.assertEqual("retryable", settle.call_args.kwargs["outcome"])
        self.assertEqual("provider_rate_limited", settle.call_args.kwargs["reason_code"])

    def test_uncertain_result_is_never_presented_as_retryable(self) -> None:
        protector = Mock()
        protector.decrypt.return_value = SECRET_DESTINATION
        adapter = Mock()
        adapter.deliver.side_effect = DeliveryError(
            "provider_outcome_unknown", "uncertain")
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "arm", return_value="armed"), \
             patch.object(delivery, "settle", return_value="uncertain") as settle:
            main.process_one(FakeDatabase(), protector, adapter, "worker-1")
        self.assertEqual("uncertain", settle.call_args.kwargs["outcome"])

    def test_decrypted_destination_does_not_enter_logs(self) -> None:
        protector = Mock()
        protector.decrypt.return_value = SECRET_DESTINATION
        adapter = Mock()
        adapter.deliver.side_effect = DeliveryError("provider_rejected", "fatal")
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "arm", return_value="armed"), \
             patch.object(delivery, "settle", return_value="failed"), \
             self.assertLogs("fincilia.notification_worker", level="INFO") as captured:
            main.process_one(FakeDatabase(), protector, adapter, "worker-1")
        self.assertNotIn(SECRET_DESTINATION, "\n".join(captured.output))

    def test_empty_queue_never_calls_provider(self) -> None:
        with patch.object(delivery, "claim_next", return_value=None):
            protector, adapter = Mock(), Mock()
            self.assertFalse(main.process_one(
                FakeDatabase(), protector, adapter, "worker-1"))
        protector.decrypt.assert_not_called()
        adapter.deliver.assert_not_called()

    def test_provider_is_not_called_when_the_durable_arm_fails(self) -> None:
        protector, adapter = Mock(), Mock()
        protector.decrypt.return_value = SECRET_DESTINATION
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "arm", side_effect=RuntimeError("db unavailable")):
            self.assertTrue(main.process_one(FakeDatabase(), protector, adapter, "worker-1"))
        adapter.deliver.assert_not_called()

    def test_decryption_failure_finishes_before_the_provider_boundary(self) -> None:
        protector, adapter = Mock(), Mock()
        protector.decrypt.side_effect = DeliveryError("destination_invalid", "fatal")
        with patch.object(delivery, "claim_next", return_value=claim()), \
             patch.object(delivery, "finish", return_value="failed") as finish, \
             patch.object(delivery, "arm") as arm:
            self.assertTrue(main.process_one(FakeDatabase(), protector, adapter, "worker-1"))
        finish.assert_called_once()
        arm.assert_not_called()
        adapter.deliver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
