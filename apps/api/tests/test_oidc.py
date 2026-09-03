from __future__ import annotations

import base64
import contextlib
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import httpx
from pydantic import ValidationError

from fincilia_api.oidc import ManagedAccount, OidcError, exchange_code
from fincilia_api.routes import OidcExchangeRequest, exchange_managed_identity
from fincilia_api.security import ProblemError
from fincilia_platform.settings import ApiSettings


NOW = 1_788_000_000
SUBJECT = "12345678-1234-4234-8234-123456789abc"
NONCE = "nonce_123456789012345678901234"
VERIFIER = "v" * 64
CODE = "code_123456789012345678901234"


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


def settings() -> ApiSettings:
    with isolated_env():
        return ApiSettings(
            env="pilot",
            secret_source="aws_secrets_manager",
            database_url="postgresql://fincilia_app:synthetic@postgres:5432/fincilia",
            cache_url="rediss://cache.internal:6379/0",
            object_store_endpoint="https://s3.sa-east-1.amazonaws.com",
            object_region="sa-east-1",
            object_credentials_source="aws_workload_identity",
            auth_signing_key="a" * 40,
            identifier_tokenization_key="b" * 40,
            authorization_context_hmac_key="c" * 40,
            oidc_enabled=True,
            oidc_registration_mode="public_google",
            oidc_issuer="https://issuer.example.test/pool",
            oidc_client_id="client-123456",
            oidc_token_endpoint="https://issuer.example.test/oauth2/token",
            oidc_userinfo_endpoint="https://issuer.example.test/oauth2/userInfo",
            oidc_redirect_uri="https://pilot.example.test/api/auth/callback/cognito",
            identity_binding_hmac_key="d" * 40,
            identity_gate_attestation="{}",
            identity_gate_signature="YQ==",
            identity_gate_kms_key_id=(
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "12345678-1234-1234-1234-123456789abc"),
        )


def encoded(value: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def id_token(**overrides) -> str:
    claims = {
        "iss": "https://issuer.example.test/pool",
        "aud": "client-123456",
        "token_use": "id",
        "sub": SUBJECT,
        "exp": NOW + 900,
        "iat": NOW - 10,
        "nonce": NONCE,
    }
    claims.update(overrides)
    return ".".join((encoded({"alg": "RS256", "kid": "synthetic-key"}),
                     encoded(claims), encoded({"proof": "synthetic"})))


class FakeHttp:
    def __init__(self, payload=None, status=200):
        self.payload = payload or {
            "access_token": "access-" + "a" * 40,
            "id_token": id_token(),
            "token_type": "Bearer",
            "expires_in": 900,
            "scope": "openid email profile",
        }
        self.status = status
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return httpx.Response(self.status, json=self.payload)


class FakeCognito:
    def __init__(self, **attributes):
        values = {
            "sub": SUBJECT,
            "email": "Founder@Example.Test",
            "email_verified": "true",
            "name": "Founder Fincilia",
        }
        values.update(attributes)
        self.response = {
            "Username": "Google_opaque",
            "UserAttributes": [
                {"Name": key, "Value": value} for key, value in values.items()
            ],
        }
        self.tokens = []

    def get_user(self, **kwargs):
        self.tokens.append(kwargs["AccessToken"])
        return self.response


class CognitoExchangeTests(unittest.TestCase):
    def exchange(self, *, http=None, cognito=None, nonce=NONCE):
        return exchange_code(
            settings=settings(), code=CODE, verifier=VERIFIER, nonce=nonce,
            http_client=http or FakeHttp(),
            cognito_client=cognito or FakeCognito(), now=NOW)

    def test_code_pkce_is_exchanged_server_side_and_identity_is_tokenised(self):
        http = FakeHttp()
        cognito = FakeCognito()
        identity = self.exchange(http=http, cognito=cognito)
        self.assertEqual("https://issuer.example.test/pool", identity.issuer)
        self.assertRegex(identity.external_subject_ref,
                         r"^hmac-sha256:v1:[0-9a-f]{64}$")
        self.assertRegex(identity.verified_email_ref,
                         r"^hmac-sha256:v1:[0-9a-f]{64}$")
        self.assertNotEqual(identity.external_subject_ref,
                            identity.verified_email_ref)
        self.assertNotIn("@example", repr(identity).casefold())
        self.assertEqual("Founder Fincilia", identity.display_name)
        url, call = http.calls[0]
        self.assertEqual(settings().oidc_token_endpoint, url)
        self.assertEqual(VERIFIER, call["data"]["code_verifier"])
        self.assertEqual(settings().oidc_redirect_uri,
                         call["data"]["redirect_uri"])
        self.assertNotIn("client_secret", call["data"])
        self.assertEqual(["access-" + "a" * 40], cognito.tokens)

    def test_nonce_issuer_audience_expiry_and_cross_token_sub_must_match(self):
        cases = (
            (FakeHttp({**FakeHttp().payload, "id_token": id_token(nonce="wrong")}),
             FakeCognito()),
            (FakeHttp({**FakeHttp().payload, "id_token": id_token(iss="https://evil")}),
             FakeCognito()),
            (FakeHttp({**FakeHttp().payload, "id_token": id_token(aud="other")}),
             FakeCognito()),
            (FakeHttp({**FakeHttp().payload, "id_token": id_token(exp=NOW)}),
             FakeCognito()),
            (FakeHttp(), FakeCognito(sub="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        )
        for http, cognito in cases:
            with self.subTest(payload=http.payload), self.assertRaises(OidcError):
                self.exchange(http=http, cognito=cognito)

    def test_unverified_or_malformed_email_is_rejected(self):
        for cognito in (
            FakeCognito(email_verified="false"),
            FakeCognito(email="not-an-email"),
        ):
            with self.subTest(cognito=cognito.response), self.assertRaises(OidcError):
                self.exchange(cognito=cognito)

    def test_cognito_refresh_token_is_discarded_and_scope_drift_is_rejected(self):
        with_refresh = {
            **FakeHttp().payload,
            "refresh_token": "provider-token-must-never-leave-this-response",
        }
        identity = self.exchange(http=FakeHttp(with_refresh))
        self.assertEqual("Founder Fincilia", identity.display_name)
        self.assertNotIn("provider-token", repr(identity))

        cases = (
            {**FakeHttp().payload, "scope": "openid email aws.cognito.signin.user.admin"},
            {**FakeHttp().payload, "expires_in": 7200},
        )
        for payload in cases:
            with self.subTest(keys=sorted(payload)), self.assertRaises(OidcError):
                self.exchange(http=FakeHttp(payload))
        with self.assertRaises(OidcError):
            self.exchange(http=FakeHttp(status=302))

    def test_malformed_code_verifier_nonce_and_token_are_bounded(self):
        for code, verifier, nonce in (
            ("short", VERIFIER, NONCE),
            (CODE, "short", NONCE),
            (CODE, VERIFIER, "short"),
        ):
            with self.subTest(code=code, nonce=nonce), self.assertRaises(OidcError):
                exchange_code(
                    settings=settings(), code=code, verifier=verifier, nonce=nonce,
                    http_client=FakeHttp(), cognito_client=FakeCognito(), now=NOW)
        with self.assertRaises(OidcError):
            self.exchange(http=FakeHttp({
                **FakeHttp().payload, "id_token": "x" * 20_000}))

    def test_login_and_registration_payloads_cannot_be_confused(self):
        common = {"code": CODE, "verifier": VERIFIER, "nonce": NONCE}
        login = OidcExchangeRequest(**common, mode="login")
        self.assertEqual("login", login.mode)
        registration = OidcExchangeRequest(
            **common, mode="register", firm_name="Firma Fincilia",
            terms_version="terms-2026-09-03-en",
            privacy_version="privacy-2026-09-03-en")
        self.assertEqual("register", registration.mode)
        for payload in (
            {**common, "mode": "login", "firm_name": "No debe entrar"},
            {**common, "mode": "register", "firm_name": "Incompleto"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                OidcExchangeRequest(**payload)

    def test_unknown_login_never_materialises_an_account(self):
        configured = settings()
        throttle = Mock()
        throttle.exhausted.return_value = False
        connection = MagicMock()

        @contextlib.contextmanager
        def session():
            yield connection

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            settings=configured, throttle=throttle,
            database=SimpleNamespace(session=session))))
        body = OidcExchangeRequest(
            code=CODE, verifier=VERIFIER, nonce=NONCE, mode="login")
        with patch("fincilia_api.routes.oidc.exchange_code", return_value=Mock()), \
                patch("fincilia_api.routes.oidc.resolve_account", return_value=None), \
                patch("fincilia_api.routes.oidc.register_account") as register:
            with self.assertRaises(ProblemError) as caught:
                exchange_managed_identity(request, body)
        self.assertTrue(caught.exception.problem.type.endswith(
            "/account-registration-required"))
        register.assert_not_called()
        throttle.record_failure.assert_called_once()

    def test_public_registration_is_the_only_account_creation_path(self):
        configured = settings()
        throttle = Mock()
        throttle.exhausted.return_value = False
        connection = MagicMock()

        @contextlib.contextmanager
        def session():
            yield connection

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            settings=configured, throttle=throttle,
            database=SimpleNamespace(session=session))))
        body = OidcExchangeRequest(
            code=CODE, verifier=VERIFIER, nonce=NONCE, mode="register",
            firm_name="Firma Fincilia", terms_version="terms-2026-09-03-en",
            privacy_version="privacy-2026-09-03-en")
        account = ManagedAccount(SUBJECT, "Founder Fincilia", "active", True)
        with patch("fincilia_api.routes.oidc.exchange_code", return_value=Mock()), \
                patch("fincilia_api.routes.oidc.resolve_account", return_value=None), \
                patch("fincilia_api.routes.oidc.register_account",
                      return_value=account) as register, \
                patch("fincilia_api.routes.repository.record_audit"), \
                patch("fincilia_api.routes.issue", return_value="session-token"):
            response = exchange_managed_identity(request, body)
        self.assertEqual("session-token", response.token)
        register.assert_called_once()
        throttle.clear.assert_called_once()
