"""La puerta de la version del motor, contra PostgreSQL real.

Publicar un movimiento canonico afirma que se puede reproducir. Esa afirmacion
se apoya en una version del motor que alguien miro y aprobo; si nadie la miro, la
afirmacion no vale nada y el sistema no debe hacerla.

Lo que se comprueba aqui es que la puerta este de verdad cerrada: que un borrador
no publique, que una version sustituida no empiece nada nuevo, que lo aprobado
sea lo que corre, y que **ningun rol del runtime** pueda abrirla.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_release_gate -v
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

sys.path.insert(0, "/app/worker_src")

from db.admin.releases import AdminError, datasets_of, list_releases, record, show_release
from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from db.tests.test_p3_vertical import (
    FIXTURE_ACTOR,
    FIXTURE_REF,
    MAPPING,
    approve_fixture_release,
    purge,
    register_release,
    statement_csv,
)
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_contracts.release import digest_of
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ensure_buckets
from fincilia_worker.main import process_one

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
SOURCE = stable_id("data_source", "espiga")
ACCOUNT = stable_id("account", "espiga")
PREPARER = "ana@demo.local"
REVIEWER = "beto@demo.local"

WORKER_ROLE = "fincilia_worker"
APP_ROLE = "fincilia_app"


class ReleaseStateTests(unittest.TestCase):
    """Estados y sus consecuencias, sin pasar por la API."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN:
            raise unittest.SkipTest("migrator DSN is required")

    def connection(self):
        return psycopg.connect(MIGRATOR_DSN, autocommit=True)

    def test_an_approved_release_without_a_reference_is_refused_TST_P35_001(self) -> None:
        # La restriccion es de la base, no del codigo: no hay ruta que la evite.
        with self.connection() as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation) as caught:
                cursor.execute(
                    "INSERT INTO fincilia.engine_release (release_id, release_key, "
                    "canonical_schema_version, classification, state) "
                    "VALUES (gen_random_uuid(), %s, '0.1.0', 'neutral', 'approved')",
                    (f"unattested-{uuid.uuid4().hex[:8]}",))
            self.assertIn("ck_release_approval", str(caught.exception))

    def test_an_approved_release_cannot_be_edited_TST_P35_002(self) -> None:
        # `immutable_after_approval`. Cambiar los componentes despues de la firma
        # seria una firma sobre algo que ya no existe.
        release_key = approve_fixture_release()
        with self.connection() as connection, connection.cursor() as cursor:
            for column, value in (("components", '[{"component_id": "x"}]'),
                                  ("classification", "affects_results"),
                                  ("canonical_schema_version", "9.9.9")):
                with self.subTest(column=column):
                    with self.assertRaises(psycopg.errors.CheckViolation):
                        cursor.execute(
                            f"UPDATE fincilia.engine_release SET {column} = %s "
                            "WHERE release_key = %s", (value, release_key))

    def test_an_approved_release_only_moves_to_superseded_TST_P35_003(self) -> None:
        release_key = approve_fixture_release()
        with self.connection() as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "UPDATE fincilia.engine_release SET state = 'draft' "
                    "WHERE release_key = %s", (release_key,))
            # Sustituirla si se puede: es como se retira una version sin borrar
            # lo que produjo.
            cursor.execute(
                "UPDATE fincilia.engine_release SET state = 'superseded' "
                "WHERE release_key = %s", (release_key,))
            cursor.execute("SELECT state FROM fincilia.engine_release "
                           "WHERE release_key = %s", (release_key,))
            self.assertEqual(cursor.fetchone()[0], "superseded")

    def test_one_signature_per_action_TST_P35_004(self) -> None:
        release_key, release_id = register_release()
        with self.connection() as connection, connection.cursor() as cursor:
            for attempt in range(2):
                cursor.execute(
                    "INSERT INTO fincilia.release_approval (approval_id, release_id, "
                    "action, actor_identity, approval_ref, rationale, "
                    "components_digest) VALUES (gen_random_uuid(), %s, 'approved', "
                    "%s, %s, 'motivo sintetico de prueba', %s) "
                    "ON CONFLICT (release_id, action) DO NOTHING",
                    (release_id, FIXTURE_ACTOR, FIXTURE_REF, digest_of([])))
                self.assertEqual(cursor.rowcount, 1 if attempt == 0 else 0)
        self.assertTrue(release_key)

    def test_no_runtime_role_can_write_a_release_or_its_approval_TST_P35_005(self) -> None:
        # Aprobar es un acto de plataforma. Que la API no pueda hacerlo es una
        # propiedad del motor, no una promesa del codigo.
        with self.connection() as connection, connection.cursor() as cursor:
            for role in (APP_ROLE, WORKER_ROLE):
                for table in ("engine_release", "release_approval"):
                    for verb in ("INSERT", "UPDATE", "DELETE"):
                        with self.subTest(role=role, table=table, verb=verb):
                            cursor.execute(
                                "SELECT has_table_privilege(%s, %s, %s)",
                                (role, f"fincilia.{table}", verb))
                            self.assertFalse(cursor.fetchone()[0])


class AdminToolTests(unittest.TestCase):
    """La herramienta con la que una persona aprueba. No aprueba ella."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN:
            raise unittest.SkipTest("migrator DSN is required")

    def connection(self):
        return psycopg.connect(MIGRATOR_DSN, autocommit=True)

    def test_approving_needs_an_actor_a_reference_and_a_reason_TST_P35_006(self) -> None:
        release_key, _ = register_release()
        with self.connection() as connection:
            for missing in ("actor", "approval_ref", "rationale"):
                payload = {"actor": FIXTURE_ACTOR, "approval_ref": FIXTURE_REF,
                           "rationale": "motivo sintetico de prueba"}
                payload[missing] = ""
                with self.subTest(missing=missing):
                    with self.assertRaises(AdminError) as caught:
                        record(connection, release_key=release_key,
                               action="approved", **payload)
                    self.assertIn(missing.split("_")[0], str(caught.exception))

    def test_a_floating_release_is_refused_TST_P35_007(self) -> None:
        with self.connection() as connection:
            for token in ("latest", "LATEST", "main", "head", "stable", "current"):
                with self.subTest(token=token):
                    with self.assertRaises(AdminError) as caught:
                        record(connection, release_key=token, action="approved",
                               actor=FIXTURE_ACTOR, approval_ref=FIXTURE_REF,
                               rationale="motivo sintetico de prueba")
                    self.assertIn("floating", str(caught.exception))

    def test_approving_writes_state_and_signature_together_TST_P35_008(self) -> None:
        release_key, release_id = register_release()
        with self.connection() as connection:
            outcome = record(connection, release_key=release_key, action="approved",
                             actor=FIXTURE_ACTOR, approval_ref=FIXTURE_REF,
                             rationale="motivo sintetico de prueba")
        self.assertEqual(outcome["state"], "approved")
        self.assertEqual(outcome["components_digest"], digest_of([]))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT state, approval_ref FROM fincilia.engine_release "
                           "WHERE release_id = %s", (release_id,))
            self.assertEqual(cursor.fetchone(), ("approved", FIXTURE_REF))
            cursor.execute("SELECT actor_identity FROM fincilia.release_approval "
                           "WHERE release_id = %s AND action = 'approved'",
                           (release_id,))
            self.assertEqual(cursor.fetchone()[0], FIXTURE_ACTOR)

    def test_approving_twice_is_refused_TST_P35_009(self) -> None:
        release_key = approve_fixture_release()
        with self.connection() as connection:
            with self.assertRaises(AdminError) as caught:
                record(connection, release_key=release_key, action="approved",
                       actor=FIXTURE_ACTOR, approval_ref=FIXTURE_REF,
                       rationale="motivo sintetico de prueba")
            self.assertIn("already", str(caught.exception))

    def test_a_superseded_release_starts_nothing_new_TST_P35_010(self) -> None:
        release_key = approve_fixture_release()
        with self.connection() as connection:
            record(connection, release_key=release_key, action="superseded",
                   actor=FIXTURE_ACTOR, approval_ref=FIXTURE_REF,
                   rationale="sustituida en una prueba")
            with self.assertRaises(AdminError) as caught:
                record(connection, release_key=release_key, action="approved",
                       actor=FIXTURE_ACTOR, approval_ref=FIXTURE_REF,
                       rationale="motivo sintetico de prueba")
            self.assertIn("superseded", str(caught.exception))

    def test_showing_a_release_reveals_what_would_be_approved_TST_P35_011(self) -> None:
        components = [{"component_id": "csv-extractor", "component_kind": "parser",
                       "version": "0.1.0", "digest": "a" * 64}]
        release_key, _ = register_release(components=components)
        with self.connection() as connection:
            detail = show_release(connection, release_key)
        self.assertEqual(detail["state"], "draft")
        self.assertEqual(detail["components"], components)
        self.assertEqual(detail["components_digest"], digest_of(components))
        self.assertEqual(detail["history"], [])

    def test_the_tool_reports_what_a_release_produced_TST_P35_012(self) -> None:
        release_key = approve_fixture_release()
        with self.connection() as connection:
            produced = datasets_of(connection, release_key)
            listed = list_releases(connection)
        self.assertEqual(produced, [])
        keys = {item["release_key"] for item in listed}
        self.assertIn(release_key, keys)

    def test_an_unknown_release_is_a_clear_refusal_TST_P35_013(self) -> None:
        with self.connection() as connection:
            with self.assertRaises(AdminError):
                show_release(connection, f"no-existe-{uuid.uuid4().hex[:8]}")


class ReleaseGateApiTests(unittest.TestCase):
    """Lo mismo, pero desde la API: es donde importa que la puerta este cerrada."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.created: set[str] = set()
        cls.store = S3ObjectStore(cls.worker_settings())
        try:
            ensure_buckets(build_settings())
        except Exception as error:  # noqa: BLE001 - el motivo importa mas que el tipo
            raise AssertionError(
                "these tests need the object store: start it with "
                f"`docker compose up -d --wait objectstore` ({type(error).__name__})"
            ) from error

    def setUp(self) -> None:
        # Una release por prueba. Compartirla acopla el resultado al orden
        # alfabetico de los metodos, que es la clase de dependencia que hace que
        # una suite pase sola y falle entera.
        self.release_key, self.release_id = register_release()
        self.settings = build_settings(engine_release_key=self.release_key)
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    @classmethod
    def tearDownClass(cls) -> None:
        purge(cls.created)

    @classmethod
    def worker_settings(cls):
        import os
        from fincilia_platform.settings import WorkerSettings
        saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
        for key in saved:
            del os.environ[key]
        try:
            return WorkerSettings(
                env="test", service_name="fincilia-worker-test",
                database_url=saved["FINCILIA_WORKER_URL"],
                cache_url="redis://valkey:6379/6",
                object_store_endpoint=saved.get("FINCILIA_OBJECT_STORE_ENDPOINT",
                                                "http://objectstore:9000"),
                object_access_key=saved.get("FINCILIA_OBJECT_ACCESS_KEY",
                                            "fincilia_local_object"),
                object_secret_key=saved.get("FINCILIA_OBJECT_SECRET_KEY",
                                            "fincilia_local_object_only"))
        finally:
            os.environ.update(saved)

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def drain(self, limit: int = 16) -> None:
        from fincilia_platform.db import Database
        database = Database(self.worker_settings())
        try:
            for _ in range(limit):
                if not process_one(database, self.store, f"gate-{RUN}"):
                    return
        finally:
            database.close()

    def validated_mapping(self, marker: str) -> tuple[str, str]:
        payload = statement_csv(f"gate-{marker}")
        type(self).created.add(sha256_bytes(payload))
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": ("extracto.csv", io.BytesIO(payload),
                            "application/octet-stream")})
        self.assertEqual(200, response.status_code, response.text)
        artifact = response.json()["artifact_id"]
        self.drain()
        body = dict(MAPPING)
        body.update({"artifact_id": artifact, "data_source_id": SOURCE,
                     "display_name": f"mapeo {uuid.uuid4().hex[:8]}"})
        created = self.client.post(f"/api/v1/companies/{ESPIGA}/mappings",
                                   headers=self.auth(PREPARER), json=body)
        self.assertEqual(201, created.status_code, created.text)
        version = created.json()["mapping_version_id"]
        validated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, validated.status_code, validated.text)
        return artifact, version

    def prepare(self, artifact: str, version: str):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": version,
                  "financial_account_id": ACCOUNT})

    def approve_ours(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.release_approval (approval_id, release_id, "
                    "action, actor_identity, approval_ref, rationale, "
                    "components_digest) VALUES (gen_random_uuid(), %s, 'approved', "
                    "%s, %s, 'aprobacion sintetica de prueba', %s) "
                    "ON CONFLICT (release_id, action) DO NOTHING",
                    (self.release_id, FIXTURE_ACTOR, FIXTURE_REF, digest_of([])))
                cursor.execute(
                    "UPDATE fincilia.engine_release SET state = 'approved', "
                    "approval_ref = %s WHERE release_id = %s",
                    (FIXTURE_REF, self.release_id))

    # ------------------------------------------------------------------ pruebas

    def test_a_draft_release_cannot_prepare_a_dataset_TST_P35_014(self) -> None:
        artifact, version = self.validated_mapping("draft")
        response = self.prepare(artifact, version)
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                         "engine-release-not-approved")
        # Y el motivo dice quien tiene que decidir, no solo que no se puede.
        self.assertIn("human decision", response.json()["detail"])

    def test_a_draft_release_produces_no_movement_at_all_TST_P35_015(self) -> None:
        artifact, version = self.validated_mapping("nomov")
        self.prepare(artifact, version)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.dataset_version "
                    "WHERE artifact_id = %s", (artifact,))
                self.assertEqual(cursor.fetchone()[0], 0)

    def test_no_endpoint_changes_the_state_of_a_release_TST_P35_016(self) -> None:
        # Recorrer la superficie publica: ninguna ruta nombra `release`.
        paths = [route.path for route in self.client.app.routes]
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn("release", path.lower())

    def test_once_approved_the_same_request_succeeds_TST_P35_017(self) -> None:
        artifact, version = self.validated_mapping("approved")
        blocked = self.prepare(artifact, version)
        self.assertEqual(422, blocked.status_code, blocked.text)
        self.approve_ours()
        allowed = self.prepare(artifact, version)
        self.assertEqual(201, allowed.status_code, allowed.text)
        self.assertEqual(allowed.json()["movement_count"], 3)

    def test_a_release_superseded_after_preparing_blocks_publication_TST_P35_018(self) -> None:
        self.approve_ours()
        artifact, version = self.validated_mapping("superseded")
        prepared = self.prepare(artifact, version)
        self.assertEqual(201, prepared.status_code, prepared.text)
        dataset = prepared.json()["dataset_version_id"]

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE fincilia.engine_release SET state = 'superseded' "
                    "WHERE release_id = %s", (self.release_id,))
        try:
            response = self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
                headers=self.auth(REVIEWER))
            self.assertEqual(409, response.status_code, response.text)
            self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                             "engine-release-not-approved")
            # Y lo que se preparo con ella sigue siendo consultable: reproducir
            # historicos es justo lo que `superseded` conserva.
            still = self.client.get(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}",
                headers=self.auth(REVIEWER))
            self.assertEqual(200, still.status_code, still.text)
            self.assertEqual(still.json()["engine_release"], self.release_key)
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.engine_release SET state = 'approved' "
                        "WHERE release_id = %s", (self.release_id,))

    def test_changing_the_components_after_approval_stops_publication_TST_P35_019(self) -> None:
        # El disparador impide el cambio; esto comprueba la segunda linea, la que
        # mira la API al leer. Se fuerza el desajuste escribiendo la constancia
        # con otro digest, que es la unica via que queda.
        self.approve_ours()
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE fincilia.release_approval SET components_digest = %s "
                    "WHERE release_id = %s AND action = 'approved'",
                    ("b" * 64, self.release_id))
        try:
            artifact, version = self.validated_mapping("tampered")
            response = self.prepare(artifact, version)
            self.assertEqual(422, response.status_code, response.text)
            self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                             "engine-release-tampered")
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.release_approval SET components_digest = %s "
                        "WHERE release_id = %s AND action = 'approved'",
                        (digest_of([]), self.release_id))

    def test_an_approval_without_a_signature_row_is_refused_TST_P35_020(self) -> None:
        # Estado aprobado y ninguna constancia: la base lo permite si alguien
        # escribe solo el estado, y la API se niega a publicar con eso.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM fincilia.release_approval WHERE release_id = %s",
                    (self.release_id,))
                cursor.execute(
                    "UPDATE fincilia.engine_release SET state = 'approved', "
                    "approval_ref = %s WHERE release_id = %s",
                    (FIXTURE_REF, self.release_id))
        try:
            artifact, version = self.validated_mapping("unattested")
            response = self.prepare(artifact, version)
            self.assertEqual(422, response.status_code, response.text)
            self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                             "engine-release-unattested")
        finally:
            self.approve_ours()


if __name__ == "__main__":
    unittest.main()
