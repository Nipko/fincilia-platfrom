from __future__ import annotations

import datetime as dt
import unittest

from botocore.exceptions import ClientError, ReadTimeoutError

from fincilia_platform.email_delivery import (
    AwsKmsDestinationProtector,
    AwsSesAdapter,
    DeliveryError,
    EncryptedDestination,
    render_message,
)
from fincilia_api import notifications


ADDRESS_REF = "hmac-sha256:v1:" + "a" * 64
KEY_ARN = "arn:aws:kms:sa-east-1:123456789012:key/12345678-1234-1234-1234-123456789abc"
CONTEXT = {
    "period_label": "2026-08-01 / 2026-08-31",
    "due_on": "2026-09-05",
    "action_url": "/recordatorios?empresa=12345678-1234-4234-8234-123456789abc",
}


class FakeKms:
    def __init__(self) -> None:
        self.plaintext = b""
        self.calls: list[tuple[str, dict]] = []

    def encrypt(self, **kwargs):
        self.calls.append(("encrypt", kwargs))
        self.plaintext = kwargs["Plaintext"]
        return {"CiphertextBlob": b"ciphertext-" + b"x" * 32}

    def decrypt(self, **kwargs):
        self.calls.append(("decrypt", kwargs))
        return {"Plaintext": self.plaintext}


class FakeSes:
    def __init__(self, result=None, error=None) -> None:
        self.result = result or {"MessageId": "opaque-provider-id"}
        self.error = error
        self.calls: list[dict] = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class TemplateTests(unittest.TestCase):
    def test_templates_are_closed_bilingual_and_value_free(self):
        for locale in ("es-CO", "en-US"):
            message = render_message(
                template_code="period_due_today", locale=locale,
                context=CONTEXT, public_origin="https://fincilia.com")
            self.assertIn("2026-09-05", message.text)
            self.assertIn("https://fincilia.com/recordatorios", message.html)
            for forbidden_value in ("999.99", "0011223344", "tax-123", "cell-a1"):
                self.assertNotIn(forbidden_value, repr(message).casefold())

    def test_extra_context_and_non_https_origins_fail_closed(self):
        with self.assertRaises(DeliveryError):
            render_message(
                template_code="period_due_today", locale="es-CO",
                context={**CONTEXT, "amount": "999"},
                public_origin="https://fincilia.com")
        with self.assertRaises(DeliveryError):
            render_message(
                template_code="period_due_today", locale="es-CO",
                context=CONTEXT, public_origin="http://fincilia.com")


class QuietHoursTests(unittest.TestCase):
    def test_overnight_quiet_hours_defer_to_the_local_end(self):
        preference = {
            "timezone": "America/Bogota", "quiet_from": "20:00",
            "quiet_until": "07:00",
        }
        inside = dt.datetime(2026, 9, 5, 2, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(
            dt.datetime(2026, 9, 5, 12, 0, tzinfo=dt.timezone.utc),
            notifications._available_at(inside, preference),
        )
        outside = dt.datetime(2026, 9, 5, 15, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(outside, notifications._available_at(outside, preference))

    def test_naive_time_is_never_assumed_to_be_utc(self):
        with self.assertRaises(notifications.NotificationError):
            notifications._available_at(dt.datetime(2026, 9, 5, 2, 30), {
                "timezone": "America/Bogota", "quiet_from": "20:00",
                "quiet_until": "07:00",
            })


class DestinationProtectionTests(unittest.TestCase):
    def test_email_is_canonicalised_and_only_ciphertext_is_serialised(self):
        kms = FakeKms()
        protector = AwsKmsDestinationProtector(kms, key_id=KEY_ARN)
        encrypted = protector.encrypt(" Founder@Example.Test ", address_ref=ADDRESS_REF)
        encoded = protector.encode(encrypted)
        self.assertEqual("founder@example.test", kms.plaintext.decode())
        self.assertNotIn("@", encoded)
        restored = protector.decode(
            encoded, address_ref=ADDRESS_REF, key_ref=KEY_ARN)
        self.assertEqual("founder@example.test", protector.decrypt(restored))
        self.assertEqual({
            "purpose": "fincilia-notification-destination-v1",
            "address_ref": ADDRESS_REF,
        }, kms.calls[0][1]["EncryptionContext"])

    def test_ciphertext_is_bound_to_its_hmac_reference(self):
        kms = FakeKms()
        protector = AwsKmsDestinationProtector(kms, key_id=KEY_ARN)
        encrypted = protector.encrypt("founder@example.test", address_ref=ADDRESS_REF)
        changed_ref = "hmac-sha256:v1:" + "b" * 64
        protector.decrypt(EncryptedDestination(
            encrypted.ciphertext, changed_ref, KEY_ARN))
        self.assertEqual(changed_ref,
                         kms.calls[-1][1]["EncryptionContext"]["address_ref"])

    def test_wrong_key_or_malformed_ciphertext_fails_without_address(self):
        protector = AwsKmsDestinationProtector(FakeKms(), key_id=KEY_ARN)
        with self.assertRaises(DeliveryError) as caught:
            protector.decrypt(EncryptedDestination(b"x" * 40, ADDRESS_REF, "other"))
        self.assertNotIn("@", str(caught.exception))
        with self.assertRaises(DeliveryError):
            protector.decode("not base64", address_ref=ADDRESS_REF, key_ref=KEY_ARN)
        with self.assertRaises(DeliveryError):
            protector.encrypt("founder@example.test", address_ref="founder@example.test")


class SesAdapterTests(unittest.TestCase):
    def adapter(self, client):
        return AwsSesAdapter(
            client, from_address="notifications@fincilia.com",
            reply_to="support@fincilia.com", configuration_set="fincilia-uat",
            public_origin="https://fincilia.com")

    def test_send_is_minimised_and_returns_only_a_provider_digest(self):
        ses = FakeSes()
        provider_ref = self.adapter(ses).deliver(
            recipient="user@example.test", template_code="period_due_soon",
            locale="es-CO", context=CONTEXT, idempotency_key="b" * 64)
        self.assertRegex(provider_ref, r"^sha256:[0-9a-f]{64}$")
        rendered = repr(ses.calls[0])
        self.assertIn("user@example.test", rendered)
        self.assertNotIn("opaque-provider-id", provider_ref)
        self.assertNotIn("attachment", rendered.casefold())
        self.assertEqual("b" * 64, ses.calls[0]["EmailTags"][0]["Value"])

    def test_timeout_is_uncertain_and_never_classified_as_retryable(self):
        error = ReadTimeoutError(endpoint_url="https://email.sa-east-1.amazonaws.com")
        with self.assertRaises(DeliveryError) as caught:
            self.adapter(FakeSes(error=error)).deliver(
                recipient="user@example.test", template_code="period_due_soon",
                locale="es-CO", context=CONTEXT, idempotency_key="b" * 64)
        self.assertEqual(("provider_outcome_unknown", "uncertain"),
                         (caught.exception.code, caught.exception.failure_class))

    def test_provider_errors_are_reduced_to_allowlisted_codes(self):
        for provider_code, expected in (
            ("TooManyRequestsException", ("provider_rate_limited", "retryable")),
            ("MessageRejected", ("provider_rejected", "fatal")),
        ):
            error = ClientError(
                {"Error": {"Code": provider_code, "Message": "contains address"}},
                "SendEmail")
            with self.subTest(provider_code=provider_code), \
                    self.assertRaises(DeliveryError) as caught:
                self.adapter(FakeSes(error=error)).deliver(
                    recipient="user@example.test", template_code="period_due_soon",
                    locale="en-US", context=CONTEXT, idempotency_key="c" * 64)
            self.assertEqual(expected,
                             (caught.exception.code, caught.exception.failure_class))
            self.assertNotIn("address", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
