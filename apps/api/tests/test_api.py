"""Pruebas de la API. Se ejecutan **dentro** de la imagen, que es donde viven sus
dependencias:

    docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps \\
        api python -m unittest discover -s /app/tests -t /app/tests

No levantan postgres, valkey ni object storage: las sondas se inyectan. Lo que se
comprueba aqui es la forma del contrato HTTP y la disciplina de la configuracion,
no la integracion, que tiene su propia suite.
"""

from __future__ import annotations

import contextlib
import json
import os
import unittest
from typing import Any

from fastapi.testclient import TestClient
from pydantic import ValidationError

from fincilia_api.main import create_app
from fincilia_platform.probes import ProbeResult
from fincilia_platform.settings import (
    ApiSettings, NotificationWorkerSettings, Settings, WorkerSettings,
)

BASE_ENV: dict[str, str] = {
    "env": "test",
    "database_url": "postgresql://fincilia_app:synthetic@postgres:5432/fincilia_local",
    "cache_url": "redis://valkey:6379/0",
    "object_store_endpoint": "http://objectstore:9000",
    "object_access_key": "fincilia_local_object",
    "object_secret_key": "fincilia_local_object_only",
    "auth_signing_key": "x" * 40,
    # Distinta de la de firma a proposito: la propia clase lo exige, y una
    # prueba que las hiciera iguales dejaria de comprobar nada.
    "identifier_tokenization_key": "y" * 40,
    "authorization_context_hmac_key": "z" * 40,
}


@contextlib.contextmanager
def isolated_env():
    """Quita toda `FINCILIA_*` del entorno mientras dura el bloque.

    `pydantic-settings` lee el entorno ademas de los argumentos, asi que sin esto
    una prueba de "falta la credencial" pasaria por accidente cuando se ejecuta
    dentro del contenedor, donde Compose ya la inyecto.
    """
    saved = {key: value for key, value in os.environ.items()
             if key.startswith("FINCILIA_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def api_settings(**overrides: Any) -> ApiSettings:
    payload = {**BASE_ENV, **overrides}
    with isolated_env():
        return ApiSettings(**payload)  # type: ignore[arg-type]


class FakeProbe:
    def __init__(self, name: str, status: str, detail: str = "") -> None:
        self.name = name
        self._result = ProbeResult(name, status, detail, 1)

    def probe(self) -> ProbeResult:
        return self._result


def client(probes) -> TestClient:
    return TestClient(create_app(api_settings(), tuple(probes)))


class SettingsTests(unittest.TestCase):
    def test_a_missing_credential_stops_the_process(self) -> None:
        for required in ("database_url", "cache_url", "object_store_endpoint",
                         "object_access_key", "object_secret_key", "auth_signing_key",
                         "identifier_tokenization_key",
                         "authorization_context_hmac_key"):
            with self.subTest(required=required):
                payload = {key: value for key, value in BASE_ENV.items()
                           if key != required}
                with isolated_env(), self.assertRaises(ValidationError):
                    ApiSettings(**payload)  # type: ignore[arg-type]

    def test_the_tokenization_key_is_not_the_signing_key(self) -> None:
        # Un secreto que sirve para dos cosas tiene el radio de explosion de las
        # dos, y rotar uno obligaria a rotar el otro.
        with self.assertRaises(ValidationError):
            api_settings(identifier_tokenization_key="x" * 40)

    def test_a_short_tokenization_key_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(identifier_tokenization_key="corta")

    def test_the_context_key_is_dedicated_and_bounded(self) -> None:
        for value in ("corta", "x" * 40, "y" * 40):
            with self.subTest(value=value[:5]), self.assertRaises(ValidationError):
                api_settings(authorization_context_hmac_key=value)

    def test_a_floating_engine_release_is_refused(self) -> None:
        # Publicar contra `latest` es publicar contra lo que haya manana.
        for token in ("latest", "LATEST", "main", "head", "stable", "current"):
            with self.subTest(token=token), self.assertRaises(ValidationError):
                api_settings(engine_release_key=token)

    def test_a_named_engine_release_is_accepted(self) -> None:
        settings = api_settings(engine_release_key="fnc-p3-mapping-0.1.0")
        self.assertEqual(settings.engine_release_key, "fnc-p3-mapping-0.1.0")
        self.assertEqual(settings.identifier_key_version, 1)

    def test_build_metadata_is_exact_or_explicitly_local(self) -> None:
        local = api_settings()
        self.assertEqual((local.build_revision, local.release_id),
                         ("development", "unreleased"))
        revision = "a" * 40
        candidate = api_settings(
            build_revision=revision, release_id="fnc-candidate-a1b2c3d4e5f6")
        self.assertEqual(candidate.build_revision, revision)
        for value in ("abc123", "A" * 40, "latest", "main"):
            with self.subTest(revision=value), self.assertRaises(ValidationError):
                api_settings(build_revision=value)
        for value in ("release one", "latest", "FNC-candidate"):
            with self.subTest(release=value), self.assertRaises(ValidationError):
                api_settings(release_id=value)

    def test_production_is_not_an_environment_value(self) -> None:
        for value in ("production", "prod", "staging"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                api_settings(env=value)

    def test_a_gated_capability_cannot_be_enabled_by_a_variable(self) -> None:
        for flag in ("real_data_enabled", "ai_gateway_enabled", "payments_enabled"):
            with self.subTest(flag=flag), self.assertRaises(ValidationError):
                api_settings(**{flag: True})

    def test_stripe_accepts_only_complete_test_mode_gated_configuration(self) -> None:
        stripe = {
            "env": "pilot", "secret_source": "aws_secrets_manager",
            "object_credentials_source": "aws_workload_identity",
            "object_access_key": None, "object_secret_key": None,
            "real_data_enabled": True, "oidc_enabled": True,
            "oidc_registration_mode": "public_google",
            "oidc_issuer": "https://issuer.example.test/pool",
            "oidc_client_id": "client-synthetic",
            "oidc_token_endpoint": "https://issuer.example.test/oauth2/token",
            "oidc_userinfo_endpoint": "https://issuer.example.test/oauth2/userInfo",
            "oidc_redirect_uri": "https://fincilia.com/api/auth/callback/cognito",
            "identity_binding_hmac_key": "d" * 40,
            "identity_gate_attestation": "{}", "identity_gate_signature": "YQ==",
            "identity_gate_kms_key_id": "kms-identity-synthetic",
            "data_gate_attestation": "{}", "data_gate_signature": "YQ==",
            "data_gate_kms_key_id": "kms-data-synthetic",
            "payments_enabled": True, "payment_provider": "stripe",
            "stripe_secret_key": "sk_test_synthetic1234567890",
            "stripe_webhook_secret": "whsec_synthetic1234567890",
            "stripe_public_origin": "https://fincilia.com",
        }
        configured = api_settings(**stripe)
        self.assertEqual("stripe", configured.payment_provider)
        self.assertEqual("2026-08-26.dahlia", configured.stripe_api_version)
        with self.assertRaises(ValidationError):
            api_settings(**{**stripe,
                            "stripe_secret_key": "sk_live_synthetic1234567890"})
        with self.assertRaises(ValidationError):
            api_settings(**{**stripe, "oidc_enabled": False})

    def test_disabled_payments_reject_partial_stripe_secrets(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(stripe_webhook_secret="whsec_synthetic1234567890")

    def test_notifications_are_disabled_without_provider_configuration(self) -> None:
        configured = api_settings()
        self.assertEqual("disabled", configured.notification_provider)
        values = (
            configured.notification_region,
            configured.notification_from_address,
            configured.notification_reply_to_address,
            configured.notification_destination_kms_key_id,
            configured.notification_configuration_set,
            configured.notification_public_origin,
        )
        self.assertEqual(("disabled",) * 6, values)
        with self.assertRaises(ValidationError):
            api_settings(notification_region="sa-east-1")

    def test_ses_requires_the_complete_gated_pilot_configuration(self) -> None:
        configured = {
            **BASE_ENV,
            "env": "pilot",
            "secret_source": "aws_secrets_manager",
            "object_credentials_source": "aws_workload_identity",
            "object_access_key": None,
            "object_secret_key": None,
            "real_data_enabled": True,
            "oidc_enabled": True,
            "oidc_registration_mode": "public_google",
            "oidc_issuer": "https://issuer.example.test/pool",
            "oidc_client_id": "client-123456",
            "oidc_token_endpoint": "https://issuer.example.test/oauth2/token",
            "oidc_userinfo_endpoint": "https://issuer.example.test/oauth2/userInfo",
            "oidc_redirect_uri": "https://fincilia.com/api/auth/callback/cognito",
            "identity_binding_hmac_key": "d" * 40,
            "identity_gate_attestation": "{}",
            "identity_gate_signature": "YQ==",
            "identity_gate_kms_key_id": (
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "12345678-1234-1234-1234-123456789abc"),
            "data_gate_attestation": "{}",
            "data_gate_signature": "YQ==",
            "data_gate_kms_key_id": (
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "22345678-1234-1234-1234-123456789abc"),
            "notification_provider": "aws_ses",
            "notification_region": "sa-east-1",
            "notification_from_address": "notifications@fincilia.com",
            "notification_reply_to_address": "support@fincilia.com",
            "notification_destination_kms_key_id": (
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "32345678-1234-1234-1234-123456789abc"),
            "notification_configuration_set": "fincilia-uat",
            "notification_public_origin": "https://fincilia.com",
        }
        with isolated_env():
            result = ApiSettings(**configured)  # type: ignore[arg-type]
        self.assertEqual("aws_ses", result.notification_provider)
        for removed in (
            "real_data_enabled", "oidc_enabled", "notification_from_address",
            "notification_destination_kms_key_id", "notification_public_origin",
        ):
            with self.subTest(removed=removed), isolated_env(), \
                    self.assertRaises(ValidationError):
                changed = dict(configured)
                changed.pop(removed)
                ApiSettings(**changed)  # type: ignore[arg-type]

    def test_an_undeclared_variable_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(mystery_switch="on")

    def test_a_non_redis_cache_url_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(cache_url="http://valkey:6379")

    def test_a_non_http_object_endpoint_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(object_store_endpoint="s3://objectstore")

    def test_pool_bounds_are_coherent(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(database_pool_min=8, database_pool_max=2)

    def test_a_short_signing_key_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            api_settings(auth_signing_key="too-short")

    def test_the_worker_refuses_secrets_it_never_uses(self) -> None:
        # El worker no emite tokens y no da de alta cuentas. Recibir cualquiera
        # de los dos secretos ampliaria su radio de explosion sin ninguna
        # ganancia, asi que se rechazan en vez de ignorarse.
        forbidden = ("auth_signing_key", "identifier_tokenization_key",
                     "authorization_context_hmac_key")
        payload = {key: value for key, value in BASE_ENV.items()
                   if key not in forbidden}
        with isolated_env():
            worker = WorkerSettings(**payload)  # type: ignore[arg-type]
            self.assertIsNone(worker.auth_signing_key)
            self.assertIsNone(worker.identifier_tokenization_key)
            self.assertIsNone(worker.authorization_context_hmac_key)
            for secret in forbidden:
                with self.subTest(secret=secret):
                    with self.assertRaises(ValidationError):
                        WorkerSettings(**{**payload, secret: BASE_ENV[secret]})  # type: ignore[arg-type]

    def test_notification_worker_refuses_application_secrets(self) -> None:
        forbidden = ("auth_signing_key", "identifier_tokenization_key",
                     "authorization_context_hmac_key", "cache_url",
                     "object_store_endpoint", "object_access_key",
                     "object_secret_key")
        payload = {
            "env": "test",
            "database_url": BASE_ENV["database_url"],
        }
        with isolated_env():
            worker = NotificationWorkerSettings(**payload)  # type: ignore[arg-type]
            self.assertEqual("disabled", worker.notification_provider)
            for secret in forbidden:
                with self.subTest(secret=secret), self.assertRaises(ValidationError):
                    NotificationWorkerSettings(
                        **{**payload, secret: BASE_ENV.get(secret, "synthetic")})  # type: ignore[arg-type]

    def test_notification_worker_requires_the_complete_gated_provider(self) -> None:
        payload = {
            "env": "pilot",
            "secret_source": "aws_secrets_manager",
            "database_url": BASE_ENV["database_url"],
            "real_data_enabled": True,
            "oidc_enabled": True,
            "data_gate_attestation": "{}",
            "data_gate_signature": "YQ==",
            "data_gate_kms_key_id": (
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "22345678-1234-1234-1234-123456789abc"),
            "notification_provider": "aws_ses",
            "notification_region": "sa-east-1",
            "notification_from_address": "notifications@fincilia.com",
            "notification_reply_to_address": "support@fincilia.com",
            "notification_destination_kms_key_id": (
                "arn:aws:kms:sa-east-1:123456789012:key/"
                "32345678-1234-1234-1234-123456789abc"),
            "notification_configuration_set": "fincilia-uat",
            "notification_public_origin": "https://fincilia.com",
        }
        with isolated_env():
            configured = NotificationWorkerSettings(**payload)  # type: ignore[arg-type]
        self.assertEqual("aws_ses", configured.notification_provider)
        for removed in ("real_data_enabled", "oidc_enabled", "data_gate_signature",
                        "notification_reply_to_address"):
            changed = dict(payload)
            changed.pop(removed)
            with self.subTest(removed=removed), isolated_env(), \
                    self.assertRaises(ValidationError):
                NotificationWorkerSettings(**changed)  # type: ignore[arg-type]

    def test_the_base_settings_do_not_require_a_signing_key(self) -> None:
        payload = {key: value for key, value in BASE_ENV.items()
                   if key != "auth_signing_key"}
        with isolated_env():
            self.assertIsNone(Settings(**payload).auth_signing_key)  # type: ignore[arg-type]

    def test_the_four_evidence_zones_are_declared(self) -> None:
        self.assertEqual(len(api_settings().buckets), 4)
        self.assertEqual(len(set(api_settings().buckets)), 4)


class HealthTests(unittest.TestCase):
    def all_up(self):
        return [FakeProbe("postgresql", "up", "fincilia_app@17.11"),
                FakeProbe("valkey", "up", "pong"),
                FakeProbe("object_storage", "up", "4 buckets")]

    def test_live_never_touches_a_dependency(self) -> None:
        class Exploding:
            name = "postgresql"

            def probe(self):
                raise AssertionError("live must not probe dependencies")

        response = client([Exploding()]).get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")

    def test_request_id_is_returned_and_invalid_input_is_replaced(self) -> None:
        accepted = client(self.all_up()).get(
            "/health/live", headers={"X-Request-ID": "request-12345678"})
        self.assertEqual(accepted.headers["X-Request-ID"], "request-12345678")
        for supplied in ("short", "bad\nvalue", "x" * 65):
            with self.subTest(supplied=supplied):
                # HTTP clients reject CR/LF before the application. A tab reaches
                # the middleware and exercises the same invalid-character path.
                transmitted = supplied.replace("\n", "\t")
                response = client(self.all_up()).get(
                    "/health/live", headers={"X-Request-ID": transmitted})
                generated = response.headers["X-Request-ID"]
                self.assertRegex(generated, r"^[0-9a-f]{32}$")
                self.assertNotEqual(generated, transmitted)

    def test_security_headers_cover_success_and_controlled_errors(self) -> None:
        expected = {
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
            "cross-origin-resource-policy": "same-site",
        }
        api = client(self.all_up())
        for path, status in (("/health/live", 200), ("/does-not-exist", 404)):
            with self.subTest(path=path):
                response = api.get(path)
                self.assertEqual(status, response.status_code)
                for header, value in expected.items():
                    self.assertEqual(value, response.headers.get(header))
                # TLS termina en el edge. Una API HTTP local no debe afirmar HSTS.
                self.assertNotIn("strict-transport-security", response.headers)

    def test_health_exposes_non_secret_build_identity(self) -> None:
        settings = api_settings(
            build_revision="b" * 40, release_id="fnc-candidate-bbbbbbbbbbbb")
        app = TestClient(create_app(settings, tuple(self.all_up())))
        for path in ("/health/live", "/health/ready", "/health/config"):
            with self.subTest(path=path):
                body = app.get(path).json()
                self.assertEqual(body["release_id"], "fnc-candidate-bbbbbbbbbbbb")
                self.assertEqual(body["revision"], "b" * 40)

    def test_ready_is_200_when_every_dependency_answers(self) -> None:
        response = client(self.all_up()).get("/health/ready")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ready")
        self.assertEqual(len(body["dependencies"]), 3)

    def test_ready_is_503_when_one_dependency_is_down(self) -> None:
        for index in range(3):
            with self.subTest(down=index):
                probes = self.all_up()
                probes[index] = FakeProbe(probes[index].name, "down", "ConnectionError")
                response = client(probes).get("/health/ready")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["status"], "degraded")

    def test_ready_names_which_dependency_failed(self) -> None:
        probes = self.all_up()
        probes[1] = FakeProbe("valkey", "down", "TimeoutError")
        body = client(probes).get("/health/ready").json()
        failed = [row for row in body["dependencies"] if row["status"] == "down"]
        self.assertEqual([row["name"] for row in failed], ["valkey"])

    def test_no_health_response_leaks_a_credential(self) -> None:
        settings = api_settings()
        for path in ("/health/live", "/health/ready", "/health/config"):
            with self.subTest(path=path):
                body = json.dumps(client(self.all_up()).get(path).json())
                self.assertNotIn(settings.auth_signing_key, body)
                self.assertNotIn(settings.object_secret_key, body)
                self.assertNotIn("postgresql://", body)
                self.assertNotIn("password", body.lower())

    def test_config_reports_every_gated_capability_as_off(self) -> None:
        body = client(self.all_up()).get("/health/config").json()
        self.assertEqual(body["data_ceiling"], "synthetic_only")
        self.assertEqual(set(body["capabilities"].values()), {False})

    def test_docs_are_absent_outside_local(self) -> None:
        self.assertEqual(client(self.all_up()).get("/docs").status_code, 404)

    def test_docs_are_present_in_local(self) -> None:
        local = TestClient(create_app(api_settings(env="local"),
                                      tuple(self.all_up())))
        self.assertEqual(local.get("/docs").status_code, 200)

    def test_an_unknown_route_is_a_clean_404(self) -> None:
        response = client(self.all_up()).get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Traceback", response.text)

    def test_the_openapi_document_is_served_and_versioned(self) -> None:
        body = client(self.all_up()).get("/openapi.json").json()
        self.assertEqual(body["info"]["title"], "Fincilia API")
        self.assertIn("/health/ready", body["paths"])

    def test_company_provisioning_response_cannot_expose_protected_identifiers(
            self) -> None:
        body = client(self.all_up()).get("/openapi.json").json()
        schema = body["components"]["schemas"]["CompanyProvisionResponse"]
        properties = set(schema["properties"])

        self.assertIn("refreshed_session", properties)
        self.assertIn("permissions", properties)
        self.assertIn("account_id", properties)
        self.assertNotIn("tax_identifier", properties)
        self.assertNotIn("account_identifier", properties)
        post = body["paths"]["/api/v1/companies"]["post"]
        response_schema = post["responses"]["200"]["content"][
            "application/json"]["schema"]
        self.assertEqual(
            "#/components/schemas/CompanyProvisionResponse",
            response_schema["$ref"],
        )


if __name__ == "__main__":
    unittest.main()
