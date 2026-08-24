"""La vertical de P3 completa, contra PostgreSQL y MinIO reales.

Recorre lo mismo que recorre una persona: sube un extracto, deja que el escaneo
lo promueva, mira la vista previa, mapea columnas, resuelve lo ambiguo, prepara
el dataset y **otra persona** lo publica. Despues comprueba que desde un importe
publicado se llega a la celda que lo produjo.

Se ejerce en un proceso, con las credenciales de cada rol: la API con el suyo y
el worker con el suyo. Reclamar trabajo es un privilegio que la API no tiene, y
usar aqui su rol haria que la prueba no probara el recorrido real.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_p3_vertical -v
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient

# El worker no esta en el PYTHONPATH de la imagen a proposito: la API no debe
# poder importarlo. Esta prueba si lo necesita, para ejercer el recorrido entero.
sys.path.insert(0, "/app/worker_src")

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api import datasets
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_contracts.release import digest_of
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ensure_buckets
from fincilia_worker.main import process_one

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
SOURCE = stable_id("data_source", "espiga")
ANDINOS_SOURCE = stable_id("data_source", "andinos")
ACCOUNT = stable_id("account", "espiga")

# Marcados a gritos: una aprobacion sintetica que pareciera humana seria peor
# que no tenerla.
FIXTURE_ACTOR = "SYNTHETIC-TEST-FIXTURE"
FIXTURE_REF = "FIXTURE-NOT-A-HUMAN-APPROVAL"

PREPARER = "ana@demo.local"      # tiene dataset.map, no dataset.publish
REVIEWER = "beto@demo.local"     # tiene dataset.publish, no dataset.map
OWNER = "sofia@demo.local"       # tiene los dos, y aun asi no puede las dos cosas


def statement_csv(marker: str) -> bytes:
    """Extracto con convenios colombianos: fecha dd/mm y decimal con coma.

    El `13/02` de la primera fila no es decorativo: hace que la columna de fecha
    se resuelva sola. Sin ningun dia mayor que doce, el perfilador no puede
    distinguir dd/mm de mm/dd y **bloquea**, que es lo que prueba la otra clase.
    """
    return (
        "fecha;descripcion;referencia;valor\n"
        f"13/02/2026;Pago proveedor {RUN}-{marker};REF-0001;-1.234,56\n"
        "02/03/2026;Consignacion cliente;REF-0002;980.000,00\n"
        "15/03/2026;Comision manejo;;-15.900,00\n"
    ).encode("utf-8")


def ambiguous_csv(marker: str) -> bytes:
    """El mismo extracto sin un solo dia mayor que doce: nadie puede decidir."""
    return (
        "fecha;descripcion;referencia;valor\n"
        f"01/02/2026;Pago proveedor {RUN}-{marker};REF-0101;-1.234,56\n"
        "03/04/2026;Consignacion cliente;REF-0102;980.000,00\n"
    ).encode("utf-8")


PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n"

MAPPING = {
    "columns": {"occurred_on": 0, "description": 1, "reference": 2, "amount": 3},
    "date_format": "dmy",
    "decimal_format": "comma",
    "currency": "COP",
    "direction_mode": "signed_amount",
    "header_row": 1,
    "first_data_row": 2,
    "ignored_columns": [],
}


def register_release(*, state: str = "draft", key: str | None = None,
                     components: list | None = None) -> tuple[str, str]:
    """Registra una version del motor para una prueba. Devuelve `(clave, id)`."""
    release_key = key or f"test-fixture-{uuid.uuid4().hex[:10]}"
    payload = components if components is not None else []
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.engine_release (release_id, release_key, "
                "canonical_schema_version, classification, state, components) "
                "VALUES (gen_random_uuid(), %s, '0.1.0', 'neutral', %s, %s::jsonb) "
                "ON CONFLICT (release_key) DO NOTHING RETURNING release_id",
                (release_key, state, json.dumps(payload)))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "SELECT release_id FROM fincilia.engine_release "
                    "WHERE release_key = %s", (release_key,))
                row = cursor.fetchone()
    return release_key, str(row[0])


def approve_fixture_release(key: str | None = None) -> str:
    """Aprueba una version **de prueba**, marcada como tal sin ambiguedad.

    El actor y la referencia dicen a gritos que esto no es la decision de nadie:
    una aprobacion sintetica que pareciera humana seria peor que no tenerla, y
    ninguna prueba puede mover un gate del programa.
    """
    release_key, release_id = register_release(key=key)
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.release_approval (approval_id, release_id, "
                "action, actor_identity, approval_ref, rationale, components_digest) "
                "VALUES (gen_random_uuid(), %s, 'approved', %s, %s, %s, %s) "
                "ON CONFLICT (release_id, action) DO NOTHING",
                (release_id, FIXTURE_ACTOR, FIXTURE_REF,
                 "aprobacion sintetica de una prueba automatizada; no aprueba nada real",
                 digest_of([])))
            cursor.execute(
                "UPDATE fincilia.engine_release SET state = 'approved', "
                "approval_ref = %s WHERE release_id = %s", (FIXTURE_REF, release_id))
    return release_key


def purge(created: set[str]) -> None:
    """Borra lo que subio una suite, en el orden que fija la clave ajena.

    Ninguna lleva `ON DELETE CASCADE`: que borrar un dataset se llevara por
    delante su evidencia sin decirlo es justo lo que `ON DELETE RESTRICT`
    existe para impedir, y por eso el orden es explicito.
    """
    if not created:
        return
    statements = (
        "DELETE FROM fincilia.lineage_edge WHERE processing_run_id IN ("
        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
        "  SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.lineage_node WHERE entity_ref IN ("
        " SELECT movement_id FROM fincilia.canonical_movement WHERE"
        " dataset_version_id IN (SELECT dataset_version_id"
        "  FROM fincilia.dataset_version WHERE artifact_id IN ("
        "   SELECT artifact_id FROM fincilia.source_artifact"
        "   WHERE content_sha256 = ANY(%s))))",
        "DELETE FROM fincilia.lineage_node WHERE entity_ref IN ("
        " SELECT raw_record_id FROM fincilia.raw_record WHERE artifact_id IN ("
        "  SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.lineage_node WHERE entity_ref IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        # El nodo del dataset y los de decision: cardinalidad uno cada uno, y
        # sin ellos las aristas de arriba dejarian huerfano el grafo.
        "DELETE FROM fincilia.lineage_node WHERE entity_ref IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.lineage_node WHERE entity_ref IN ("
        " SELECT decision_id FROM fincilia.mapping_decision"
        " WHERE mapping_version_id IN ("
        "  SELECT mapping_version_id FROM fincilia.column_mapping_version"
        "  WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "   WHERE content_sha256 = ANY(%s))))",
        # La excepcion por fila referencia al dataset, a la fila y al paso del
        # plan, las tres con `RESTRICT`: se retira antes que ninguna de ellas.
        "DELETE FROM fincilia.lineage_row_override WHERE dataset_version_id IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.movement_evidence_link WHERE movement_id IN ("
        " SELECT movement_id FROM fincilia.canonical_movement"
        " WHERE dataset_version_id IN (SELECT dataset_version_id"
        "  FROM fincilia.dataset_version WHERE artifact_id IN ("
        "   SELECT artifact_id FROM fincilia.source_artifact"
        "   WHERE content_sha256 = ANY(%s))))",
        "DELETE FROM fincilia.canonical_movement WHERE dataset_version_id IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.source_record WHERE dataset_version_id IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.reproducibility_manifest WHERE dataset_version_id IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        # Los puntos de control referencian al dataset, y el plan de linaje
        # tambien: borrar el dataset antes choca con la clave ajena, que es
        # justo lo que `ON DELETE RESTRICT` existe para hacer.
        "DELETE FROM fincilia.dataset_chunk WHERE dataset_version_id IN ("
        " SELECT dataset_version_id FROM fincilia.dataset_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.dataset_version WHERE artifact_id IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        "DELETE FROM fincilia.lineage_transform_step WHERE plan_id IN ("
        " SELECT plan_id FROM fincilia.lineage_transform_plan"
        " WHERE mapping_version_id IN ("
        "  SELECT mapping_version_id FROM fincilia.column_mapping_version"
        "  WHERE artifact_id IN (SELECT artifact_id"
        "   FROM fincilia.source_artifact WHERE content_sha256 = ANY(%s))))",
        "DELETE FROM fincilia.lineage_transform_plan WHERE mapping_version_id IN ("
        " SELECT mapping_version_id FROM fincilia.column_mapping_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.mapping_decision WHERE mapping_version_id IN ("
        " SELECT mapping_version_id FROM fincilia.column_mapping_version"
        " WHERE artifact_id IN (SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.column_mapping_version WHERE artifact_id IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        "DELETE FROM fincilia.column_mapping WHERE mapping_id NOT IN ("
        " SELECT mapping_id FROM fincilia.column_mapping_version)",
        "DELETE FROM fincilia.raw_record WHERE artifact_id IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN ("
        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
        "  SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.run_attempt WHERE run_id IN ("
        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
        "  SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.dead_letter_item WHERE work_id IN ("
        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
        "  SELECT artifact_id FROM fincilia.source_artifact"
        "  WHERE content_sha256 = ANY(%s)))",
        "DELETE FROM fincilia.processing_run WHERE artifact_id IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        "DELETE FROM fincilia.promotion_decision WHERE artifact_id IN ("
        " SELECT artifact_id FROM fincilia.source_artifact"
        " WHERE content_sha256 = ANY(%s))",
        "DELETE FROM fincilia.source_artifact WHERE content_sha256 = ANY(%s)",
    )
    keys = list(created)
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for company in (ESPIGA, ANDINOS):
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (company,))
                for statement in statements:
                    cursor.execute(statement,
                                   () if "%s" not in statement else (keys,))


class VerticalHarness(unittest.TestCase):
    """Montaje compartido: sembrar, arrancar la API y ejercer el worker.

    No lleva pruebas. Las clases que lo heredan traen las suyas y cada una
    limpia lo que subio: `created` es un atributo de clase, no del modulo.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        # Cada suite trabaja contra **su** version del motor. Compartir una haria
        # que aprobar la de una prueba hiciera pasar por aprobada la de la que
        # comprueba que un borrador bloquea.
        cls.release_key = approve_fixture_release()
        settings = build_settings(engine_release_key=cls.release_key)
        try:
            ensure_buckets(settings)
        except Exception as error:  # noqa: BLE001 - el motivo importa mas que el tipo
            raise AssertionError(
                "these tests need the object store: start it with "
                f"`docker compose up -d --wait objectstore` ({type(error).__name__})"
            ) from error
        cls.created: set[str] = set()
        cls.store = S3ObjectStore(cls.worker_settings())
        cls.client = TestClient(create_app(settings))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        purge(cls.created)

    # ---------------------------------------------------------------- helpers #

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
                cache_url="redis://valkey:6379/5",
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
                if not process_one(database, self.store, f"p3-{RUN}"):
                    return
        finally:
            database.close()

    def promoted(self, payload: bytes, filename: str) -> str:
        """Sube un fichero y lo lleva hasta la zona de evidencia, ya extraido."""
        type(self).created.add(sha256_bytes(payload))
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": (filename, io.BytesIO(payload), "application/octet-stream")})
        self.assertEqual(200, response.status_code, response.text)
        artifact_id = response.json()["artifact_id"]
        self.drain()
        return artifact_id

    def create_mapping(self, artifact_id: str, definition: dict | None = None,
                       user: str = PREPARER, *, data_source_id: str = SOURCE,
                       display_name: str | None = None):
        body = dict(definition or MAPPING)
        body.update({"artifact_id": artifact_id,
                     "data_source_id": data_source_id,
                     "display_name": display_name or
                     f"mapeo {uuid.uuid4().hex[:8]}"})
        return self.client.post(f"/api/v1/companies/{ESPIGA}/mappings",
                                headers=self.auth(user), json=body)

    def mapping_row_counts(self, display_name: str) -> tuple[int, int]:
        """Cuenta plantilla y versiones desde PostgreSQL, no desde la respuesta."""
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), coalesce(sum(version_count), 0) FROM ("
                    " SELECT m.mapping_id, count(v.mapping_version_id) version_count"
                    " FROM fincilia.column_mapping m"
                    " LEFT JOIN fincilia.column_mapping_version v"
                    "   ON v.mapping_id = m.mapping_id AND v.company_id = m.company_id"
                    " WHERE m.company_id = %s AND m.display_name = %s"
                    " GROUP BY m.mapping_id) counted",
                    (ESPIGA, display_name))
                row = cursor.fetchone()
        return int(row[0]), int(row[1])

    def mapping_audit_count(self, artifact_id: str) -> int:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.audit_event"
                    " WHERE company_id = %s AND action = 'dataset.map'"
                    " AND detail ->> 'artifact' = %s",
                    (ESPIGA, artifact_id))
                return int(cursor.fetchone()[0])

    def validated_mapping(self, artifact_id: str) -> str:
        created = self.create_mapping(artifact_id)
        self.assertEqual(201, created.status_code, created.text)
        version_id = created.json()["mapping_version_id"]
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, response.status_code, response.text)
        return version_id

    def prepared(self, artifact_id: str, version_id: str, user: str = PREPARER):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(user),
            json={"artifact_id": artifact_id, "mapping_version_id": version_id,
                  "financial_account_id": ACCOUNT})


class VerticalTests(VerticalHarness):
    """El recorrido de una persona, de la subida a la publicacion."""

    # -------------------------------------------------------- vista previa #

    def test_the_preview_shows_the_file_with_its_coordinates_TST_P3_026(self) -> None:
        artifact = self.promoted(statement_csv("preview"), "extracto.csv")
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(PREPARER))
        self.assertEqual(200, response.status_code, response.text)
        page = response.json()
        self.assertEqual(page["header"], ["fecha", "descripcion", "referencia", "valor"])
        # Cuatro registros: la cabecera tambien se leyo y tiene coordenada.
        self.assertEqual(page["total_records"], 4)
        first_data = [row for row in page["rows"] if row["record_ordinal"] == 2][0]
        self.assertEqual(first_data["values"][3], "-1.234,56")
        self.assertEqual(first_data["locator"]["locator_kind"], "tabular_delimited")
        self.assertLess(first_data["locator"]["byte_start"],
                        first_data["locator"]["byte_end"])

    def test_the_preview_carries_the_inferred_type_and_its_confidence_TST_P3_027(self) -> None:
        artifact = self.promoted(statement_csv("types"), "extracto.csv")
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(PREPARER))
        columns = {column["index"]: column for column in response.json()["columns"]}
        self.assertEqual(columns[0]["inferred_type"], "date_dmy")
        self.assertEqual(columns[3]["inferred_type"], "decimal_comma")
        for column in columns.values():
            self.assertIn("type_confidence", column)
            self.assertLessEqual(column["type_confidence"], 1.0)

    def test_the_preview_always_pages_TST_P3_028(self) -> None:
        artifact = self.promoted(statement_csv("paging"), "extracto.csv")
        first = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview?offset=0&limit=2",
            headers=self.auth(PREPARER)).json()
        second = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview?offset=2&limit=2",
            headers=self.auth(PREPARER)).json()
        self.assertEqual(len(first["rows"]), 2)
        self.assertEqual(len(second["rows"]), 2)
        self.assertEqual(first["total_records"], 4)
        self.assertNotEqual([row["record_ordinal"] for row in first["rows"]],
                            [row["record_ordinal"] for row in second["rows"]])

    def test_a_quarantined_document_has_no_preview_TST_P3_029(self) -> None:
        # No se extrae lo que nadie ha inspeccionado. La vista previa lo dice en
        # vez de devolver una pagina vacia que pareceria un fichero sin filas.
        artifact = self.promoted(PDF, "informe.pdf")
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(PREPARER))
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "not-extracted")

    def test_reading_the_preview_needs_more_than_reading_the_document_TST_P3_030(self) -> None:
        # El revisor ve el documento y su perfil; el contenido del fichero pide
        # `dataset.map`, que es de quien prepara.
        artifact = self.promoted(statement_csv("perm"), "extracto.csv")
        document = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, document.status_code, document.text)
        preview = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(REVIEWER))
        self.assertEqual(403, preview.status_code, preview.text)

    def test_the_audit_of_a_preview_counts_rows_and_quotes_none_TST_P3_031(self) -> None:
        artifact = self.promoted(statement_csv("audit"), "extracto.csv")
        self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(PREPARER))
        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=50",
            headers=self.auth(REVIEWER)).json()
        previews = [event for event in events
                    if event["action"] == "document.preview"
                    and event["resource_ref"] == artifact]
        self.assertTrue(previews, "the preview left no audit trail")
        rendered = str(previews[0])
        self.assertIn("rows", rendered)
        for value in ("Pago proveedor", "REF-0001", "1.234,56", "980.000"):
            self.assertNotIn(value, rendered)

    # ------------------------------------------------------------------ mapeo #

    def test_a_cross_company_or_malformed_source_writes_nothing_FNC_API_001_AC_01(
            self) -> None:
        artifact = self.promoted(statement_csv("source-scope"), "extracto.csv")
        cases = (ANDINOS_SOURCE, "not-a-uuid")
        for source_id in cases:
            name = f"scope-{uuid.uuid4().hex}"
            with self.subTest(source_id=source_id):
                response = self.create_mapping(
                    artifact, data_source_id=source_id, display_name=name)
                self.assertEqual(403, response.status_code, response.text)
                self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                                 "forbidden")
                self.assertEqual((0, 0), self.mapping_row_counts(name))

    def test_a_duplicate_name_is_a_stable_conflict_without_a_second_version_FNC_API_001_AC_04(
            self) -> None:
        artifact = self.promoted(statement_csv("duplicate"), "extracto.csv")
        name = f"duplicate-{uuid.uuid4().hex}"

        first = self.create_mapping(artifact, display_name=name)
        second = self.create_mapping(artifact, display_name=name)

        self.assertEqual(201, first.status_code, first.text)
        self.assertEqual(409, second.status_code, second.text)
        self.assertEqual(second.json()["type"].rsplit("/", 1)[-1],
                         "mapping-name-conflict")
        self.assertEqual((1, 1), self.mapping_row_counts(name))
        self.assertEqual(1, self.mapping_audit_count(artifact))

    def test_concurrent_creation_has_one_winner_and_no_orphan_FNC_API_001_AC_03(
            self) -> None:
        artifact = self.promoted(statement_csv("concurrent-map"), "extracto.csv")
        name = f"concurrent-{uuid.uuid4().hex}"
        headers = self.auth(PREPARER)
        body = {**MAPPING, "artifact_id": artifact, "data_source_id": SOURCE,
                "display_name": name}

        def submit():
            return self.client.post(
                f"/api/v1/companies/{ESPIGA}/mappings", headers=headers, json=body)

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: submit(), range(2)))

        self.assertEqual([201, 409], sorted(item.status_code for item in responses),
                         [item.text for item in responses])
        self.assertEqual((1, 1), self.mapping_row_counts(name))
        self.assertEqual(1, self.mapping_audit_count(artifact))

    def test_a_second_insert_failure_rolls_back_the_template_FNC_API_001_AC_03(
            self) -> None:
        name = f"rollback-{uuid.uuid4().hex}"
        unknown_artifact = str(uuid.uuid4())
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with self.assertRaises(datasets.MappingReferenceRefused):
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, true)",
                            (ESPIGA,))
                        cursor.execute(
                            "SELECT set_config('fincilia.subject_id', %s, true)",
                            (stable_id("subject", "ana"),))
                    datasets.create_mapping(
                        connection, company_id=ESPIGA, data_source_id=SOURCE,
                        artifact_id=unknown_artifact, display_name=name,
                        definition=MAPPING, subject_id=stable_id("subject", "ana"),
                        source_schema="0" * 64)

        self.assertEqual((0, 0), self.mapping_row_counts(name))

    def test_an_unexpected_mapping_failure_is_not_reported_as_forbidden_FNC_API_001_AC_05(
            self) -> None:
        artifact = self.promoted(statement_csv("unexpected"), "extracto.csv")
        with patch("fincilia_api.routes.datasets.create_mapping",
                   side_effect=RuntimeError("synthetic unexpected failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic unexpected failure"):
                self.create_mapping(artifact)

    def test_an_ambiguous_date_blocks_validation_until_someone_chooses_TST_P3_032(self) -> None:
        artifact = self.promoted(ambiguous_csv("block"), "ambiguo.csv")
        created = self.create_mapping(artifact)
        self.assertEqual(201, created.status_code, created.text)
        version_id = created.json()["mapping_version_id"]
        blockers = created.json()["blockers"]
        ambiguous = [item for item in blockers if item["code"] == "MAP-AMBIGUOUS-COLUMN"]
        self.assertTrue(ambiguous, f"expected an ambiguity, got {blockers}")
        self.assertEqual(ambiguous[0]["ambiguity_kind"], "date_format")
        self.assertEqual(ambiguous[0]["subject_ref"], "occurred_on")

        refused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(422, refused.status_code, refused.text)

        decided = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/decisions",
            headers=self.auth(PREPARER),
            json={"ambiguity_kind": "date_format", "subject_ref": "occurred_on",
                  "resolved_value": "dmy",
                  "rationale": "el banco emite dd/mm/aaaa en Colombia"})
        self.assertEqual(201, decided.status_code, decided.text)

        accepted = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, accepted.status_code, accepted.text)
        self.assertEqual(accepted.json()["state"], "validated")

    def test_a_decision_that_contradicts_the_mapping_resolves_nothing_TST_P3_033(self) -> None:
        # Decir `mdy` sobre un mapeo que declara `dmy` no resuelve la ambiguedad:
        # deja escrito que la persona quiso una cosa y el sistema hace otra.
        artifact = self.promoted(ambiguous_csv("contra"), "ambiguo.csv")
        created = self.create_mapping(artifact)
        version_id = created.json()["mapping_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/decisions",
            headers=self.auth(PREPARER),
            json={"ambiguity_kind": "date_format", "subject_ref": "occurred_on",
                  "resolved_value": "mdy", "rationale": "eleccion incoherente"})
        refused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(422, refused.status_code, refused.text)

    def test_an_unused_column_is_named_without_blocking_TST_P3_056(self) -> None:
        # Una columna que nadie mapea es normal. Lo que no es normal es no
        # haberla mirado, y esa diferencia importa cuando quien revisa no es
        # quien mapeo.
        artifact = self.promoted(statement_csv("ignorada"), "extracto.csv")
        definition = dict(MAPPING)
        definition["columns"] = {"occurred_on": 0, "description": 1, "amount": 3}
        created = self.create_mapping(artifact, definition)
        self.assertEqual(201, created.status_code, created.text)
        version_id = created.json()["mapping_version_id"]
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}",
            headers=self.auth(PREPARER)).json()
        self.assertEqual([column["index"] for column in detail["unaccounted_columns"]],
                         [2])
        self.assertEqual(detail["blockers"], [])
        # Y declararla ignorada la saca del aviso sin cambiar nada mas.
        declared = dict(definition)
        declared["ignored_columns"] = [2]
        other = self.create_mapping(artifact, declared)
        other_detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/mappings/{other.json()['mapping_version_id']}",
            headers=self.auth(PREPARER)).json()
        self.assertEqual(other_detail["unaccounted_columns"], [])

    def test_a_reviewer_cannot_write_a_mapping_TST_P3_034(self) -> None:
        artifact = self.promoted(statement_csv("revmap"), "extracto.csv")
        response = self.create_mapping(artifact, user=REVIEWER)
        self.assertEqual(403, response.status_code, response.text)

    # ------------------------------------------------------------ preparacion #

    def test_a_draft_mapping_cannot_produce_a_dataset_TST_P3_035(self) -> None:
        artifact = self.promoted(statement_csv("draft"), "extracto.csv")
        created = self.create_mapping(artifact)
        response = self.prepared(artifact, created.json()["mapping_version_id"])
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                         "mapping-not-validated")

    def test_preparing_reads_amounts_directions_and_dates_TST_P3_036(self) -> None:
        artifact = self.promoted(statement_csv("prepare"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        response = self.prepared(artifact, version_id)
        self.assertEqual(201, response.status_code, response.text)
        dataset_id = response.json()["dataset_version_id"]
        self.assertEqual(response.json()["movement_count"], 3)
        self.assertEqual(response.json()["state"], "validated")

        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        by_row = {item["record_ordinal"]: item for item in movements}
        self.assertEqual(Decimal(by_row[2]["amount"]), Decimal("1234.56"))
        self.assertEqual(by_row[2]["direction"], "outflow")
        self.assertEqual(by_row[2]["occurred_on"], "2026-02-13")
        self.assertEqual(Decimal(by_row[3]["amount"]), Decimal("980000.00"))
        self.assertEqual(by_row[3]["direction"], "inflow")
        # El importe es siempre positivo y la direccion lleva el signo.
        for movement in movements:
            self.assertGreater(Decimal(movement["amount"]), 0)
            self.assertIn(movement["direction"], ("inflow", "outflow"))

    def test_preparing_twice_returns_the_same_dataset_TST_P3_037(self) -> None:
        artifact = self.promoted(statement_csv("idem"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        first = self.prepared(artifact, version_id).json()
        second = self.prepared(artifact, version_id).json()
        self.assertEqual(first["dataset_version_id"], second["dataset_version_id"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["movement_count"], first["movement_count"])

    # ------------------------------------------------------------ publicacion #

    def test_the_preparer_cannot_publish_what_the_preparer_prepared_TST_P3_038(self) -> None:
        artifact = self.promoted(statement_csv("sod"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        # Ana no tiene `dataset.publish`: la denegacion es de permiso.
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(PREPARER))
        self.assertEqual(403, response.status_code, response.text)

    def test_an_owner_holding_both_permissions_still_cannot_do_both_TST_P3_039(self) -> None:
        # Sofia tiene `dataset.map` y `dataset.publish`. Lo que no puede es
        # ejercerlos sobre la misma version.
        artifact = self.promoted(statement_csv("owner"), "extracto.csv")
        created = self.create_mapping(artifact, user=OWNER)
        version_id = created.json()["mapping_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(OWNER))
        dataset_id = self.prepared(artifact, version_id, user=OWNER) \
            .json()["dataset_version_id"]
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(OWNER))
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                         "segregation-of-duties")

    def test_a_different_reviewer_publishes_and_it_is_idempotent_TST_P3_040(self) -> None:
        artifact = self.promoted(statement_csv("publish"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        first = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(first.json()["state"], "published")
        second = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, second.status_code, second.text)
        self.assertEqual(second.json()["published_at"], first.json()["published_at"])
        self.assertEqual(second.json()["movement_count"], first.json()["movement_count"])

    def test_a_published_dataset_carries_a_reproducible_manifest_TST_P3_041(self) -> None:
        artifact = self.promoted(statement_csv("manifest"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        dataset = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}",
            headers=self.auth(REVIEWER)).json()
        self.assertEqual(len(dataset["manifest"]["reproduction_key"]), 64)
        self.assertTrue(dataset["manifest"]["reproducible"])
        # Nunca `latest`: la version del motor se nombra.
        self.assertNotIn(dataset["engine_release"].lower(),
                         {"latest", "main", "head", "stable", "current"})

    def test_the_accounting_period_is_never_inferred_TST_P36_001(self) -> None:
        # Cuando ocurrio, cuando se asento y a que periodo contable pertenece son
        # tres hechos distintos. Los dos primeros los trae el fichero; el tercero
        # es una decision de cierre, y rellenarlo con la ocurrencia moveria
        # asientos de mes sin que nada fallara.
        artifact = self.promoted(statement_csv("periodo"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        self.assertTrue(movements)
        for movement in movements:
            with self.subTest(row=movement["record_ordinal"]):
                self.assertIsNone(movement["accounting_date"])
                self.assertIsNotNone(movement["occurred_on"])
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.canonical_movement "
                    "WHERE dataset_version_id = %s AND accounting_date IS NOT NULL",
                    (dataset_id,))
                self.assertEqual(cursor.fetchone()[0], 0)

    def test_no_insert_writes_an_accounting_date_TST_P36_002(self) -> None:
        # Mirar solo el resultado de un caso feliz dejaria pasar una escritura en
        # una rama que esta prueba no recorre. Se leen las sentencias.
        #
        # Leer la columna para devolverla esta bien —la interfaz dice «todavia
        # sin asignar»—. Escribirla es lo que no puede pasar hasta P4.
        import re
        from pathlib import Path

        for module in ("datasets.py", "routes.py", "onboarding.py"):
            with self.subTest(module=module):
                source = Path(f"/app/src/fincilia_api/{module}").read_text(
                    encoding="utf-8")
                code = "\n".join(line for line in source.splitlines()
                                 if not line.lstrip().startswith("#"))
                # Cada lista de columnas de un INSERT, con los saltos de la
                # cadena SQL ya unidos.
                flat = re.sub(r'"\s*\n\s*"', "", code)
                for statement in re.findall(r"INSERT INTO fincilia\.\w+\s*\(([^)]*)\)",
                                            flat):
                    self.assertNotIn("accounting_date", statement)
                for statement in re.findall(r"UPDATE fincilia\.\w+ SET (.{0,400})",
                                            flat):
                    self.assertNotIn("accounting_date", statement)

    def test_the_publish_button_never_lies_about_who_may_press_it_TST_P3_042(self) -> None:
        artifact = self.promoted(statement_csv("button"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        for user, expected in ((REVIEWER, True), (PREPARER, False)):
            with self.subTest(user=user):
                dataset = self.client.get(
                    f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}",
                    headers=self.auth(user)).json()
                self.assertEqual(dataset["can_publish"], expected)
                codes = [item["code"] for item in dataset["publish_blockers"]]
                self.assertEqual(codes, [] if expected else ["permission-denied"])

    # ---------------------------------------------------------------- linaje #

    def test_a_published_amount_leads_back_to_its_cell_TST_P3_043(self) -> None:
        artifact = self.promoted(statement_csv("lineage"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        target = [item for item in movements if item["record_ordinal"] == 2][0]
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{target['movement_id']}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, detail.status_code, detail.text)
        payload = detail.json()
        by_field = {item["field"]: item for item in payload["lineage"]}
        # Cobertura del 100% de los campos publicados, no una media.
        self.assertEqual(set(by_field),
                         {"occurred_on", "description", "reference", "amount"})
        amount = by_field["amount"]
        self.assertEqual(amount["cell"]["record_ordinal"], 2)
        self.assertEqual(amount["cell"]["field_ordinal"], 3)
        self.assertEqual(amount["transform"], "normalise_amount:comma")
        self.assertEqual(len(amount["cell"]["artifact_sha256"]), 64)
        # Y el valor original sigue estando donde estaba.
        self.assertEqual(payload["origin"]["values"][3], "-1.234,56")

    def test_the_lineage_carries_digests_and_never_the_value_TST_P3_044(self) -> None:
        artifact = self.promoted(statement_csv("digest"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{movements[0]['movement_id']}",
            headers=self.auth(REVIEWER)).json()
        for item in detail["lineage"]:
            with self.subTest(field=item["field"]):
                self.assertEqual(len(item["value_digest"]), 64)
                self.assertEqual(item["operation"], "derived_from")

    # ------------------------------------------------------------- aislamiento #

    def test_another_companys_dataset_is_indistinguishable_from_nothing_TST_P3_045(self) -> None:
        artifact = self.promoted(statement_csv("tenant"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        # Ana es preparadora en Andinos tambien, asi que la denegacion no puede
        # venir del permiso: tiene que venir de la politica de la fila.
        response = self.client.get(
            f"/api/v1/companies/{ANDINOS}/datasets/{dataset_id}",
            headers=self.auth(PREPARER))
        self.assertEqual(403, response.status_code, response.text)
        invented = self.client.get(
            f"/api/v1/companies/{ANDINOS}/datasets/{uuid.uuid4()}",
            headers=self.auth(PREPARER))
        self.assertEqual(invented.status_code, response.status_code)
        self.assertEqual(invented.json()["detail"], response.json()["detail"])

    def test_a_movement_of_another_company_is_not_readable_TST_P3_046(self) -> None:
        artifact = self.promoted(statement_csv("movtenant"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        response = self.client.get(
            f"/api/v1/companies/{ANDINOS}/movements/{movements[0]['movement_id']}",
            headers=self.auth(PREPARER))
        self.assertEqual(403, response.status_code, response.text)



class TemplateReuseTests(VerticalHarness):
    """Un mapeo es una plantilla: sirve para el extracto del mes siguiente.

    Lo que no puede cambiar es la forma del fichero. Si cambia, los indices del
    mapeo apuntan a otras columnas y **nada falla**: el importe de la fila sale
    de la columna equivocada y el total sigue cuadrando consigo mismo.
    """

    def test_the_same_mapping_reads_next_months_statement_TST_P3_047(self) -> None:
        first = self.promoted(statement_csv("mes1"), "enero.csv")
        version_id = self.validated_mapping(first)
        second = self.promoted(
            ("fecha;descripcion;referencia;valor\n"
             f"13/03/2026;Pago proveedor {RUN}-mes2;REF-0201;-2.000,00\n"
             "20/03/2026;Consignacion cliente;REF-0202;500.000,00\n").encode("utf-8"),
            "febrero.csv")
        response = self.prepared(second, version_id)
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(response.json()["movement_count"], 2)

    def test_a_file_with_another_shape_is_refused_as_drift_TST_P3_048(self) -> None:
        first = self.promoted(statement_csv("forma1"), "enero.csv")
        version_id = self.validated_mapping(first)
        # Una columna mas, y las cabeceras ya no son las mismas.
        wider = self.promoted(
            ("fecha;descripcion;referencia;moneda;valor\n"
             f"13/03/2026;Pago {RUN}-forma2;REF-0301;COP;-2.000,00\n"
             "20/03/2026;Consignacion;REF-0302;COP;500.000,00\n").encode("utf-8"),
            "otra-forma.csv")
        response = self.prepared(wider, version_id)
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "schema-drift")

    def test_reprocessing_the_same_file_yields_another_version_TST_P3_049(self) -> None:
        # Reprocesar es otra ejecucion de extraccion sobre el mismo artefacto.
        # La version anterior se conserva: lo publicado no se reescribe.
        artifact = self.promoted(statement_csv("reproc"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        first = self.prepared(artifact, version_id).json()["dataset_version_id"]
        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{first}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT fincilia.enqueue_processing_run(%s, %s, 'extract')",
                    (ESPIGA, artifact))
        self.drain()

        second = self.prepared(artifact, version_id)
        self.assertEqual(201, second.status_code, second.text)
        self.assertNotEqual(second.json()["dataset_version_id"], first)
        still = self.client.get(f"/api/v1/companies/{ESPIGA}/datasets/{first}",
                                headers=self.auth(REVIEWER)).json()
        self.assertEqual(still["state"], "published")


class ConcurrencyTests(VerticalHarness):
    """Dos revisores pulsando publicar a la vez.

    Publicar dos veces no puede producir dos publicaciones. La unica que hay es
    la del que llego primero, y el otro se entera en vez de creerse que publico.
    """

    def test_two_simultaneous_publications_seal_the_version_once_TST_P3_050(self) -> None:
        import threading

        artifact = self.promoted(statement_csv("race"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        headers = self.auth(REVIEWER)

        start = threading.Barrier(4)
        outcomes: list[int] = []
        lock = threading.Lock()

        def publish() -> None:
            start.wait(timeout=10)
            response = self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
                headers=headers)
            with lock:
                outcomes.append(response.status_code)

        threads = [threading.Thread(target=publish) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(outcomes), 4, "some publication never answered")
        # Nadie recibe un 500. Publicar dos veces es idempotente y la carrera
        # perdida se dice, no se traga.
        for status in outcomes:
            self.assertIn(status, (200, 409, 422), f"unexpected status {status}")

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT state, published_by, published_at "
                    "FROM fincilia.dataset_version WHERE dataset_version_id = %s",
                    (dataset_id,))
                state, published_by, published_at = cursor.fetchone()
                cursor.execute(
                    "SELECT count(*) FROM fincilia.canonical_movement "
                    "WHERE dataset_version_id = %s", (dataset_id,))
                movements = cursor.fetchone()[0]
        self.assertEqual(state, "published")
        self.assertIsNotNone(published_at)
        self.assertIsNotNone(published_by)
        # Y lo que mas importa: la carrera no duplico un movimiento.
        self.assertEqual(movements, 3)

    def test_two_simultaneous_preparations_do_not_duplicate_TST_P3_051(self) -> None:
        import threading

        artifact = self.promoted(statement_csv("prepare-race"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        start = threading.Barrier(3)
        results: list[tuple[int, str]] = []
        lock = threading.Lock()

        def prepare() -> None:
            start.wait(timeout=10)
            response = self.prepared(artifact, version_id)
            body = response.json() if response.status_code == 201 else {}
            with lock:
                results.append((response.status_code,
                                body.get("dataset_version_id", "")))

        threads = [threading.Thread(target=prepare) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(len(results), 3)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.dataset_version "
                    "WHERE artifact_id = %s", (artifact,))
                datasets = cursor.fetchone()[0]
        # `uq_dataset_reproduction` lo impide en el motor: la misma terna es
        # un solo dataset, y tres peticiones simultaneas no crean tres.
        self.assertEqual(datasets, 1)


class AuditTests(VerticalHarness):
    """Cada decision deja rastro, y el rastro no es una copia de lo decidido."""

    def test_the_whole_chain_is_audited_TST_P3_052(self) -> None:
        artifact = self.promoted(statement_csv("chain"), "extracto.csv")
        self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/preview",
            headers=self.auth(PREPARER))
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))

        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=100",
                                 headers=self.auth(REVIEWER)).json()
        actions = {event["action"] for event in events}
        for expected in ("document.preview", "dataset.map", "dataset.validate",
                         "dataset.prepare", "dataset.publish"):
            with self.subTest(action=expected):
                self.assertIn(expected, actions)

    def test_a_refused_publication_is_audited_as_denied_TST_P3_053(self) -> None:
        artifact = self.promoted(statement_csv("denied"), "extracto.csv")
        created = self.create_mapping(artifact, user=OWNER)
        version_id = created.json()["mapping_version_id"]
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(OWNER))
        dataset_id = self.prepared(artifact, version_id, user=OWNER) \
            .json()["dataset_version_id"]
        refused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(OWNER))
        self.assertEqual(409, refused.status_code, refused.text)

        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=50",
                                 headers=self.auth(REVIEWER)).json()
        denied = [event for event in events
                  if event["action"] == "dataset.publish"
                  and event["resource_ref"] == dataset_id
                  and event["outcome"] == "denied"]
        self.assertTrue(denied, "the refusal left no trail")
        self.assertEqual(denied[0]["detail"].get("reason"), "segregation-of-duties")

    def test_a_rejected_row_is_counted_and_located_TST_P3_054(self) -> None:
        # Publicar a medias sin decir cuanto se quedo fuera es peor que no
        # publicar: el total parece completo y no lo es.
        payload = (
            "fecha;descripcion;referencia;valor\n"
            f"13/02/2026;Pago proveedor {RUN}-mixto;REF-0401;-1.234,56\n"
            "no es una fecha;Fila rota;REF-0402;980.000,00\n"
            "15/03/2026;Comision manejo;;-15.900,00\n"
        ).encode("utf-8")
        artifact = self.promoted(payload, "mixto.csv")
        version_id = self.validated_mapping(artifact)
        response = self.prepared(artifact, version_id)
        self.assertEqual(201, response.status_code, response.text)
        body = response.json()
        self.assertEqual(body["movement_count"], 2)
        self.assertEqual(body["rejected_count"], 1)
        self.assertEqual([item["record_ordinal"] for item in body["rejections"]], [3])
        # El motivo no lleva el valor que fallo.
        self.assertNotIn("no es una fecha", str(body["rejections"]))

        dataset = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{body['dataset_version_id']}",
            headers=self.auth(REVIEWER)).json()
        # Un dataset con filas fuera no se declara completo.
        self.assertEqual(dataset["completeness_state"], "mismatch")

    def test_a_reviewer_can_reject_a_dataset_with_a_reason_TST_P3_055(self) -> None:
        artifact = self.promoted(statement_csv("reject"), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/reject",
            headers=self.auth(REVIEWER),
            json={"reason": "la cuenta no corresponde a este extracto"})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(response.json()["state"], "rejected")
        # Y un conjunto rechazado ya no se publica.
        refused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(422, refused.status_code, refused.text)


if __name__ == "__main__":
    unittest.main()
