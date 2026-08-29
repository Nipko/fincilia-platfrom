from __future__ import annotations

import base64
import contextlib
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from fincilia_platform.gates import (
    GateVerificationError,
    canonical_payload,
    parse_attestation,
    verify_kms_attestation,
)
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ObjectStoreProbe
from fincilia_platform.settings import ApiSettings, WorkerSettings


NOW = dt.datetime(2026, 8, 28, 18, 0, tzinfo=dt.UTC)
KMS_ARN = "arn:aws:kms:sa-east-1:123456789012:key/12345678-1234-1234-1234-123456789abc"


@contextlib.contextmanager
def isolated_env():
    saved = {key: value for key, value in os.environ.items()
             if key.startswith("FINCILIA_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def attestation(**overrides):
    value = {
        "schema_version": "1.0.0",
        "gate": "DRG-01",
        "environment": "private-pilot",
        "status": "met",
        "authorized": True,
        "pilot_id": "fnc-pilot-founder",
        "issued_at": "2026-08-28T17:00:00Z",
        "expires_at": "2026-09-27T17:00:00Z",
        "evidence_digest": "a" * 64,
        "approver_ids": ["FOUNDER-01", "SECURITY-02"],
    }
    value.update(overrides)
    return json.dumps(value)


class FakeKms:
    def __init__(self, valid=True):
        self.valid = valid
        self.calls = []

    def verify(self, **kwargs):
        self.calls.append(kwargs)
        return {"SignatureValid": self.valid}


class GateAttestationTests(unittest.TestCase):
    def test_exact_canonical_payload_is_verified_by_kms(self):
        kms = FakeKms()
        result = verify_kms_attestation(
            raw=attestation(),
            signature_b64=base64.b64encode(b"signed-proof").decode(),
            key_id=KMS_ARN,
            required_gate="DRG-01",
            kms_client=kms,
            now=NOW,
        )
        self.assertEqual(result.gate, "DRG-01")
        self.assertEqual(kms.calls[0]["MessageType"], "RAW")
        self.assertEqual(kms.calls[0]["SigningAlgorithm"], "RSASSA_PSS_SHA_256")
        self.assertEqual(
            kms.calls[0]["Message"],
            canonical_payload(json.loads(attestation())),
        )

    def test_invalid_kms_signature_fails_closed(self):
        with self.assertRaises(GateVerificationError):
            verify_kms_attestation(
                raw=attestation(), signature_b64=base64.b64encode(b"bad").decode(),
                key_id=KMS_ARN, required_gate="DRG-01",
                kms_client=FakeKms(False), now=NOW,
            )

    def test_gate_cannot_be_substituted(self):
        with self.assertRaises(GateVerificationError):
            parse_attestation(attestation(gate="DRG-00"),
                              required_gate="DRG-01", now=NOW)

    def test_unknown_or_extra_fields_fail_closed(self):
        with self.assertRaises(GateVerificationError):
            parse_attestation(attestation(comment="looks safe"),
                              required_gate="DRG-01", now=NOW)

    def test_expired_future_and_overlong_attestations_fail(self):
        cases = (
            {"expires_at": "2026-08-28T17:59:59Z"},
            {"issued_at": "2026-08-28T18:06:00Z"},
            {"expires_at": "2026-12-01T17:00:00Z"},
            {"issued_at": "2026-09-01T00:00:00Z", "expires_at": "2026-08-30T00:00:00Z"},
        )
        for override in cases:
            with self.subTest(override=override), self.assertRaises(GateVerificationError):
                parse_attestation(attestation(**override),
                                  required_gate="DRG-01", now=NOW)

    def test_two_distinct_human_identifiers_are_required(self):
        for approvers in (["FOUNDER-01"], ["FOUNDER-01", "FOUNDER-01"]):
            with self.subTest(approvers=approvers), self.assertRaises(GateVerificationError):
                parse_attestation(attestation(approver_ids=approvers),
                                  required_gate="DRG-01", now=NOW)

    def test_host_key_alias_and_oversized_inputs_are_rejected(self):
        for key_id in ("alias/fincilia", "key/1234", "arn:aws:kms:sa-east-1:bad:key/x"):
            with self.subTest(key_id=key_id), self.assertRaises(GateVerificationError):
                verify_kms_attestation(
                    raw=attestation(), signature_b64="YQ==", key_id=key_id,
                    required_gate="DRG-01", kms_client=FakeKms(), now=NOW)
        with self.assertRaises(GateVerificationError):
            parse_attestation(" " * 16_385, required_gate="DRG-01", now=NOW)


class PilotSettingsTests(unittest.TestCase):
    BASE = {
        "env": "pilot",
        "secret_source": "aws_secrets_manager",
        "database_url": "postgresql://fincilia_app:synthetic@postgres:5432/fincilia",
        "cache_url": "rediss://cache.internal:6379/0",
        "object_store_endpoint": "https://s3.sa-east-1.amazonaws.com",
        "object_region": "sa-east-1",
        "object_credentials_source": "aws_workload_identity",
        "auth_signing_key": "a" * 40,
        "identifier_tokenization_key": "b" * 40,
        "authorization_context_hmac_key": "c" * 40,
    }

    def test_pilot_uses_workload_identity_without_static_aws_keys(self):
        with isolated_env():
            settings = ApiSettings(**self.BASE)
        self.assertIsNone(settings.object_access_key)
        self.assertIsNone(settings.object_secret_key)
        for target, factory in (
            ("fincilia_platform.objects.boto3.client", S3ObjectStore),
            ("fincilia_platform.probes.boto3.client",
             lambda value: ObjectStoreProbe(value).client()),
        ):
            with self.subTest(target=target), patch(target) as client:
                factory(settings)
                kwargs = client.call_args.kwargs
                self.assertNotIn("aws_access_key_id", kwargs)
                self.assertNotIn("aws_secret_access_key", kwargs)

    def test_pilot_rejects_local_secrets_and_static_aws_keys(self):
        bad = (
            {"secret_source": "local_env"},
            {"object_credentials_source": "local_static",
             "object_access_key": "access", "object_secret_key": "secret-secret"},
            {"object_access_key": "access"},
        )
        for override in bad:
            with self.subTest(override=override), self.assertRaises(ValidationError):
                with isolated_env():
                    ApiSettings(**{**self.BASE, **override})

    def test_real_data_flag_needs_the_kms_attestation_configuration(self):
        with self.assertRaises(ValidationError):
            with isolated_env():
                ApiSettings(**{**self.BASE, "real_data_enabled": True})
        with isolated_env():
            configured = ApiSettings(**{
                **self._oidc_config(),
                "real_data_enabled": True,
                "data_gate_attestation": attestation(),
                "data_gate_signature": "YQ==",
                "data_gate_kms_key_id": KMS_ARN,
            })
        self.assertTrue(configured.real_data_enabled)

    def test_real_data_worker_needs_drg01_but_not_identity_secrets(self):
        worker_payload = {
            key: value for key, value in self.BASE.items()
            if key not in {
                "auth_signing_key", "identifier_tokenization_key",
                "authorization_context_hmac_key",
            }
        }
        with isolated_env():
            settings = WorkerSettings(**{
                **worker_payload,
                "real_data_enabled": True,
                "data_gate_attestation": attestation(),
                "data_gate_signature": "YQ==",
                "data_gate_kms_key_id": KMS_ARN,
            })
        self.assertTrue(settings.real_data_enabled)
        self.assertFalse(settings.oidc_enabled)
        self.assertIsNone(settings.identity_binding_hmac_key)

    def _oidc_config(self):
        return {
            **self.BASE,
            "oidc_enabled": True,
            "oidc_registration_mode": "public_google",
            "oidc_issuer": "https://issuer.example.test/pool",
            "oidc_client_id": "client-123456",
            "oidc_token_endpoint": "https://issuer.example.test/oauth2/token",
            "oidc_userinfo_endpoint": "https://issuer.example.test/oauth2/userInfo",
            "oidc_redirect_uri": "https://pilot.example.test/api/auth/callback/cognito",
            "identity_binding_hmac_key": "d" * 40,
            "identity_gate_attestation": attestation(gate="DRG-00"),
            "identity_gate_signature": "YQ==",
            "identity_gate_kms_key_id": KMS_ARN,
        }

    def test_oidc_needs_https_public_registration_and_a_dedicated_key(self):
        common = self._oidc_config()
        with isolated_env():
            self.assertTrue(ApiSettings(**common).oidc_enabled)
        for override in (
            {"oidc_token_endpoint": "http://issuer.example.test/token"},
            {"identity_binding_hmac_key": "a" * 40},
        ):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                with isolated_env():
                    ApiSettings(**{**common, **override})

    def test_public_google_registration_cannot_run_without_oidc(self):
        with self.assertRaises(ValidationError):
            with isolated_env():
                ApiSettings(**{
                    **self.BASE,
                    "oidc_registration_mode": "public_google",
                })
