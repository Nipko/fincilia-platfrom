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
from fincilia_platform.settings import ApiSettings, Settings, WorkerSettings

BASE_ENV: dict[str, str] = {
    "env": "test",
    "database_url": "postgresql://fincilia_app:synthetic@postgres:5432/fincilia_local",
    "cache_url": "redis://valkey:6379/0",
    "object_store_endpoint": "http://objectstore:9000",
    "object_access_key": "fincilia_local_object",
    "object_secret_key": "fincilia_local_object_only",
    "auth_signing_key": "x" * 40,
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
                         "object_access_key", "object_secret_key", "auth_signing_key"):
            with self.subTest(required=required):
                payload = {key: value for key, value in BASE_ENV.items()
                           if key != required}
                with isolated_env(), self.assertRaises(ValidationError):
                    ApiSettings(**payload)  # type: ignore[arg-type]

    def test_production_is_not_an_environment_value(self) -> None:
        for value in ("production", "prod", "staging"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                api_settings(env=value)

    def test_a_gated_capability_cannot_be_enabled_by_a_variable(self) -> None:
        for flag in ("real_data_enabled", "ai_gateway_enabled", "payments_enabled"):
            with self.subTest(flag=flag), self.assertRaises(ValidationError):
                api_settings(**{flag: True})

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

    def test_the_worker_refuses_a_signing_key_it_never_uses(self) -> None:
        payload = {key: value for key, value in BASE_ENV.items()
                   if key != "auth_signing_key"}
        with isolated_env():
            worker = WorkerSettings(**payload)  # type: ignore[arg-type]
            self.assertIsNone(worker.auth_signing_key)
            with self.assertRaises(ValidationError):
                WorkerSettings(**BASE_ENV)  # type: ignore[arg-type]

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


if __name__ == "__main__":
    unittest.main()
