"""Recorrido de autorizacion de la API contra PostgreSQL real.

Aqui no hay dobles. La aplicacion se levanta con su fabrica, apunta a la base del
stack local con el rol runtime, y cada prueba entra por HTTP como entraria la web.
Es la unica forma de comprobar a la vez las tres capas que tienen que coincidir:
la politica de RLS, la autorizacion del servidor y lo que el endpoint devuelve.

Un doble del repositorio diria que si a todo, que es exactamente lo que estas
pruebas existen para descubrir.
"""

from __future__ import annotations

import os
import time
import unittest
from contextlib import contextmanager

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from fincilia_api.main import create_app
from fincilia_platform.settings import ApiSettings
from fincilia_platform.tokens import issue

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
RUNTIME_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
SIGNING_KEY = "clave-local-sintetica-de-al-menos-32-bytes"
ISSUER = "fincilia-local"
AUDIENCE = "fincilia-api"

ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")


@contextmanager
def isolated_env():
    """Sin `FINCILIA_*` en el entorno.

    `pydantic-settings` lee del entorno aunque se pasen argumentos, y este
    contenedor lleva variables que la API no declara: sin aislar, `extra=forbid`
    haria fallar la construccion por una variable que no es suya.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def build_settings() -> ApiSettings:
    with isolated_env():
        return ApiSettings(
            env="test",
            database_url=RUNTIME_DSN,
            cache_url="redis://valkey:6379/1",
            object_store_endpoint="http://objectstore:9000",
            object_access_key="fincilia_local_object",
            object_secret_key="fincilia_local_object_only",
            auth_signing_key=SIGNING_KEY,
            auth_issuer=ISSUER,
            auth_audience=AUDIENCE,
        )


class ApiAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    # ---------------------------------------------------------------- helpers #

    def sign_in(self, username: str, secret: str = DEFAULT_SECRET):
        return self.client.post("/api/v1/auth/session",
                                json={"username": username, "secret": secret})

    def token_for(self, username: str) -> str:
        response = self.sign_in(username)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["token"]

    def auth(self, username: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_for(username)}"}

    # ------------------------------------------------------------ autenticar #

    def test_a_synthetic_user_signs_in(self) -> None:
        body = self.sign_in("ana@demo.local").json()
        self.assertTrue(body["token"])
        self.assertEqual("Ana Preparadora", body["display_name"])
        self.assertGreater(body["expires_at"], int(time.time()))

    def test_the_response_never_carries_the_stored_hash(self) -> None:
        text = self.sign_in("ana@demo.local").text
        for leaked in ("secret_hash", "salt", "pbkdf2", DEFAULT_SECRET):
            self.assertNotIn(leaked, text)

    def test_a_wrong_secret_is_rejected(self) -> None:
        self.assertEqual(401, self.sign_in("ana@demo.local", "otra").status_code)

    def test_an_unknown_user_is_rejected_the_same_way(self) -> None:
        unknown = self.sign_in("nadie@demo.local")
        wrong = self.sign_in("ana@demo.local", "otra")
        self.assertEqual(401, unknown.status_code)
        # Mismo cuerpo: la respuesta no puede servir para enumerar cuentas.
        self.assertEqual(wrong.json(), unknown.json())

    def test_an_error_is_a_problem_document(self) -> None:
        response = self.sign_in("ana@demo.local", "otra")
        self.assertEqual("application/problem+json",
                         response.headers["content-type"].split(";")[0])
        self.assertEqual({"type", "title", "status", "detail"},
                         set(response.json()))

    def test_an_unknown_field_is_rejected(self) -> None:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": "ana@demo.local",
                                          "secret": DEFAULT_SECRET, "company_id": ESPIGA})
        self.assertEqual(422, response.status_code)

    # --------------------------------------------------------------- sesiones #

    def test_no_token_is_no_access(self) -> None:
        for path in ("/api/v1/me", "/api/v1/companies", f"/api/v1/companies/{ESPIGA}"):
            with self.subTest(path=path):
                self.assertEqual(401, self.client.get(path).status_code)

    def test_a_tampered_token_is_no_access(self) -> None:
        token = self.token_for("ana@demo.local")
        payload, signature = token.split(".")
        forged = payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
        response = self.client.get("/api/v1/me",
                                   headers={"Authorization": f"Bearer {forged}"})
        self.assertEqual(401, response.status_code)

    def test_a_token_signed_with_another_key_is_no_access(self) -> None:
        forged = issue(stable_id("subject", "ana"), key="otra" * 10, issuer=ISSUER,
                       audience=AUDIENCE, issued_at=int(time.time()), ttl_seconds=900)
        response = self.client.get("/api/v1/me",
                                   headers={"Authorization": f"Bearer {forged}"})
        self.assertEqual(401, response.status_code)

    def test_an_expired_token_is_no_access(self) -> None:
        stale = issue(stable_id("subject", "ana"), key=SIGNING_KEY, issuer=ISSUER,
                      audience=AUDIENCE, issued_at=int(time.time()) - 7200,
                      ttl_seconds=900)
        response = self.client.get("/api/v1/me",
                                   headers={"Authorization": f"Bearer {stale}"})
        self.assertEqual(401, response.status_code)

    def test_a_token_for_a_subject_that_does_not_exist_is_no_access(self) -> None:
        ghost = issue("11111111-1111-1111-1111-111111111111", key=SIGNING_KEY,
                      issuer=ISSUER, audience=AUDIENCE, issued_at=int(time.time()),
                      ttl_seconds=900)
        response = self.client.get("/api/v1/me",
                                   headers={"Authorization": f"Bearer {ghost}"})
        self.assertEqual(401, response.status_code)

    # ------------------------------------------------------ firma y empresas #

    def test_the_demo_user_sees_one_firm_and_two_companies(self) -> None:
        body = self.client.get("/api/v1/me", headers=self.auth("ana@demo.local")).json()
        names = sorted(item["legal_name"] for item in body["companies"])
        self.assertEqual(["Panaderia La Espiga SAS", "Transportes Andinos SAS"], names)
        firms = {self.company_detail("ana@demo.local", item["company_id"])["firm_id"]
                 for item in body["companies"]}
        self.assertEqual(1, len(firms))

    def company_detail(self, username: str, company_id: str) -> dict:
        response = self.client.get(f"/api/v1/companies/{company_id}",
                                   headers=self.auth(username))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_a_reviewer_only_sees_the_company_granted_to_them(self) -> None:
        body = self.client.get("/api/v1/companies",
                               headers=self.auth("beto@demo.local")).json()
        self.assertEqual([ESPIGA], [item["company_id"] for item in body])

    def test_reading_another_company_is_denied(self) -> None:
        response = self.client.get(f"/api/v1/companies/{ANDINOS}",
                                   headers=self.auth("beto@demo.local"))
        self.assertEqual(403, response.status_code)
        # El cuerpo no dice si la empresa existe.
        self.assertNotIn(ANDINOS, response.text)

    def test_a_denied_access_is_audited_in_the_target_company(self) -> None:
        self.client.get(f"/api/v1/companies/{ANDINOS}",
                        headers=self.auth("beto@demo.local"))
        events = self.client.get(f"/api/v1/companies/{ANDINOS}/audit",
                                 headers=self.auth("carla@demo.local")).json()
        denied = [item for item in events
                  if item["outcome"] == "denied" and item["action"] == "company.access"]
        self.assertTrue(denied, "a denied access must leave a trace")

    def test_a_malformed_company_identifier_is_denied_not_crashed(self) -> None:
        for candidate in ("no-es-uuid", "../../etc/passwd", "0", "%20"):
            with self.subTest(candidate=candidate):
                response = self.client.get(f"/api/v1/companies/{candidate}",
                                           headers=self.auth("ana@demo.local"))
                self.assertIn(response.status_code, (403, 404))

    # ------------------------------------------------------------- permisos #

    def test_a_preparer_holds_preparation_permissions_and_not_confirmation(self) -> None:
        detail = self.company_detail("ana@demo.local", ESPIGA)
        self.assertEqual(["preparer"], detail["roles"])
        self.assertIn("match.propose", detail["permissions"])
        self.assertNotIn("match.confirm", detail["permissions"])
        self.assertNotIn("close.approve", detail["permissions"])

    def test_a_reviewer_holds_confirmation_and_not_preparation(self) -> None:
        detail = self.company_detail("beto@demo.local", ESPIGA)
        self.assertIn("match.confirm", detail["permissions"])
        self.assertNotIn("match.propose", detail["permissions"])

    def test_segregation_of_duties_holds_across_the_two_demo_users(self) -> None:
        # Nadie propone y confirma: la separacion no es una nota del manual, se ve
        # en los permisos que devuelve el servidor.
        for username in ("ana@demo.local", "beto@demo.local"):
            with self.subTest(username=username):
                permissions = set(self.company_detail(username, ESPIGA)["permissions"])
                self.assertFalse({"match.propose", "match.confirm"} <= permissions)
                self.assertFalse({"close.prepare", "close.approve"} <= permissions)

    def test_reading_the_audit_needs_the_audit_permission(self) -> None:
        denied = self.client.get(f"/api/v1/companies/{ANDINOS}/audit",
                                 headers=self.auth("ana@demo.local"))
        self.assertEqual(403, denied.status_code)
        allowed = self.client.get(f"/api/v1/companies/{ANDINOS}/audit",
                                  headers=self.auth("carla@demo.local"))
        self.assertEqual(200, allowed.status_code)

    def test_the_audit_only_shows_the_company_in_context(self) -> None:
        self.company_detail("ana@demo.local", ESPIGA)
        events = self.client.get(f"/api/v1/companies/{ANDINOS}/audit?limit=200",
                                 headers=self.auth("carla@demo.local")).json()
        self.assertTrue(events)
        for event in events:
            self.assertNotEqual(ESPIGA, event["resource_ref"])
            # Un inicio de sesion es un evento de plataforma, sin empresa. La
            # politica deja verlo al propio sujeto, pero no pertenece al registro
            # de una empresa y no debe aparecer aqui.
            self.assertNotEqual("auth.session.open", event["action"])

    # --------------------------------------------------------- revocacion #

    def test_a_token_older_than_a_permission_change_is_rejected(self) -> None:
        # Se fabrica un token valido de hace cinco segundos: es exactamente lo que
        # tiene en la mano alguien cuyos permisos acaban de cambiar.
        old = issue(stable_id("subject", "ana"), key=SIGNING_KEY, issuer=ISSUER,
                    audience=AUDIENCE, issued_at=int(time.time()) - 5, ttl_seconds=900)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "UPDATE fincilia.authorization_version "
                    "SET version = version + 1, updated_at = now() WHERE company_id = %s",
                    (ESPIGA,))
        response = self.client.get(f"/api/v1/companies/{ESPIGA}",
                                   headers={"Authorization": f"Bearer {old}"})
        self.assertEqual(401, response.status_code)
        # Y un token emitido despues del cambio si vale.
        fresh = self.client.get(f"/api/v1/companies/{ESPIGA}",
                                headers=self.auth("ana@demo.local"))
        self.assertEqual(200, fresh.status_code, fresh.text)

    def test_revoking_the_engagement_removes_access_without_deleting_facts(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ANDINOS,))
                cursor.execute(
                    "UPDATE fincilia.engagement SET status = 'suspended' "
                    "WHERE company_id = %s", (ANDINOS,))
                try:
                    denied = self.client.get(f"/api/v1/companies/{ANDINOS}",
                                             headers=self.auth("ana@demo.local"))
                    self.assertEqual(403, denied.status_code)
                    # La empresa sigue ahi: se corto el acceso, no el hecho.
                    cursor.execute(
                        "SELECT count(*) FROM fincilia.company WHERE company_id = %s",
                        (ANDINOS,))
                    self.assertEqual(1, cursor.fetchone()[0])
                finally:
                    cursor.execute(
                        "UPDATE fincilia.engagement SET status = 'active' "
                        "WHERE company_id = %s", (ANDINOS,))

    # ------------------------------------------------------------- sanidad #

    def test_the_schema_probe_reports_the_applied_head(self) -> None:
        body = self.client.get("/health/ready").json()
        schema = [item for item in body["dependencies"] if item["name"] == "schema"]
        self.assertEqual(1, len(schema))
        self.assertEqual("up", schema[0]["status"], schema[0])
        self.assertRegex(schema[0]["detail"], r"^head V\d{4}$")

    def test_seeding_twice_changes_nothing(self) -> None:
        again = seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        self.assertFalse(again["mutated"], again["created"])


if __name__ == "__main__":
    unittest.main()
