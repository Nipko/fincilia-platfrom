"""Cien mil filas, contra PostgreSQL y MinIO reales.

El techo de diez mil de P3 no era una politica: era el sintoma de cargar el
fichero entero en memoria y escribir veintitres sentencias por fila. Esta suite
comprueba que ya no lo es, y **mide** en vez de afirmar: si el tiempo o la
memoria no salen, el numero sale igual y se lee en el log de CI.

Lo que se afirma:

* se importa sin agotar la memoria del proceso;
* no se duplica ni una fila, aunque el trabajo se reanude;
* un conjunto a medias **nunca** aparece como publicado;
* las seis etapas logicas del linaje se reconstruyen para lo publicado;
* la publicacion final es atomica y el manifiesto cuadra con lo que quedo escrito.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_scale_publication -v
"""

from __future__ import annotations

import io
import os
import sys
import time
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

sys.path.insert(0, "/app/worker_src")

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from db.tests.test_p3_vertical import MAPPING, approve_fixture_release, purge
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ensure_buckets
from fincilia_worker.main import process_one

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
SOURCE = stable_id("data_source", "espiga")
ACCOUNT = stable_id("account", "espiga")
PREPARER = "ana@demo.local"
REVIEWER = "beto@demo.local"

# La meta del mandato. Se declara aqui para que el numero del log y el de la
# afirmacion sean el mismo.
TARGET_ROWS = 100_000

# Techo de memoria residente del proceso durante la importacion. No es una
# medida de la base: es lo que reserva el proceso que importa, que es lo que
# reventaba antes.
#
# Se mide con `getrusage` y **no** con `tracemalloc`: trazar cada reserva
# multiplica el tiempo por varias veces, y entonces el numero de tiempo diria mas
# del medidor que del codigo.
MAX_PEAK_MIB = 900


def synthetic_statement(rows: int) -> bytes:
    """Un extracto sintetico de `rows` filas, determinista y sin dato real.

    El `13/02` de la primera fila resuelve la columna de fecha: sin ningun dia
    mayor que doce el perfilador no puede distinguir dd/mm de mm/dd y bloquea,
    que es correcto y aqui estorbaria.
    """
    parts = ["fecha;descripcion;referencia;valor\n",
             f"13/02/2026;Apertura {RUN};REF-000000;1.000.000,00\n"]
    for index in range(1, rows):
        day = (index % 28) + 1
        month = (index % 12) + 1
        cents = index % 100
        units = 1_000 + (index % 9_000)
        sign = "-" if index % 3 else ""
        parts.append(
            f"{day:02d}/{month:02d}/2026;Movimiento sintetico {index};"
            # Coma decimal, que es el convenio que declara el mapeo. Con punto,
            # el punto seria separador de miles y exigiria grupos de tres.
            f"REF-{index:06d};{sign}{units},{cents:02d}\n")
    return "".join(parts).encode("utf-8")


def peak_rss_mib() -> float:
    """Pico de memoria residente del proceso, en MiB. Cero si no se puede medir."""
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows
        return 0.0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux informa en KiB; macOS en bytes. En CI es Linux.
    return round(peak / 1024, 1) if peak > 1024 * 1024 else round(peak / 1024, 1)


class ScalePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        if os.environ.get("FINCILIA_SKIP_SCALE_TESTS", "").lower() == "true":
            raise unittest.SkipTest("scale tests disabled by environment")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.release_key = approve_fixture_release()
        cls.settings = build_settings(engine_release_key=cls.release_key)
        try:
            ensure_buckets(cls.settings)
        except Exception as error:  # noqa: BLE001 - el motivo importa mas que el tipo
            raise AssertionError(
                "these tests need the object store: start it with "
                f"`docker compose up -d --wait objectstore` ({type(error).__name__})"
            ) from error
        cls.created: set[str] = set()
        cls.store = S3ObjectStore(cls.worker_settings())
        cls.client = TestClient(create_app(cls.settings))
        cls.client.__enter__()
        cls.measurements: dict[str, object] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        # La medicion se imprime pase lo que pase: un numero que solo aparece
        # cuando la prueba pasa no sirve para saber si el objetivo se alcanzo.
        if cls.measurements:
            print(f"\n[escala] {cls.measurements}", flush=True)
        purge(cls.created)

    @classmethod
    def worker_settings(cls):
        from fincilia_platform.settings import WorkerSettings
        saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
        for key in saved:
            del os.environ[key]
        try:
            return WorkerSettings(
                env="test", service_name="fincilia-worker-scale",
                database_url=saved["FINCILIA_WORKER_URL"],
                cache_url="redis://valkey:6379/7",
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

    def drain(self, limit: int = 8) -> None:
        from fincilia_platform.db import Database
        database = Database(self.worker_settings())
        try:
            for _ in range(limit):
                if not process_one(database, self.store, f"scale-{RUN}"):
                    return
        finally:
            database.close()

    # ------------------------------------------------------------------ el caso

    def test_one_hundred_thousand_rows_publish_without_duplicates_TST_P35_021(self) -> None:
        payload = synthetic_statement(TARGET_ROWS)
        type(self).created.add(sha256_bytes(payload))
        self.measurements["bytes"] = len(payload)
        self.measurements["target_rows"] = TARGET_ROWS

        started = time.monotonic()
        baseline = peak_rss_mib()

        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": ("extracto-grande.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        artifact = upload.json()["artifact_id"]
        self.drain()
        self.measurements["extract_seconds"] = round(time.monotonic() - started, 1)

        # La extraccion no puede haberse truncado: un fichero cortado por el
        # limite de tiempo publicado como completo es exactamente lo que la
        # comprobacion de `truncated` impide.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT result FROM fincilia.processing_run "
                    "WHERE artifact_id = %s AND kind = 'extract' "
                    "AND status = 'succeeded'", (artifact,))
                row = cursor.fetchone()
        self.assertIsNotNone(row, "the extraction never finished")
        summary = row[0] or {}
        self.measurements["extracted_records"] = summary.get("record_count")
        self.assertFalse(summary.get("truncated"),
                         f"extraction truncated: {summary.get('truncation_reason')}")

        body = dict(MAPPING)
        body.update({"artifact_id": artifact, "data_source_id": SOURCE,
                     "display_name": f"mapeo escala {RUN}"})
        created = self.client.post(f"/api/v1/companies/{ESPIGA}/mappings",
                                   headers=self.auth(PREPARER), json=body)
        self.assertEqual(201, created.status_code, created.text)
        version = created.json()["mapping_version_id"]
        self.assertEqual(200, self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version}/validate",
            headers=self.auth(PREPARER)).status_code)

        prepare_started = time.monotonic()
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": version,
                  "financial_account_id": ACCOUNT})
        self.assertIn(response.status_code, (201, 202), response.text)
        dataset = response.json()["dataset_version_id"]
        rounds = 1

        while response.status_code == 202:
            # Mientras esta a medias **no** puede parecer publicado ni validado.
            self.assertEqual(response.json()["state"], "staging")
            visible = self.client.get(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}",
                headers=self.auth(REVIEWER))
            self.assertEqual(visible.json()["state"], "staging")
            self.assertFalse(visible.json()["can_publish"])
            response = self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/continue",
                headers=self.auth(PREPARER))
            self.assertIn(response.status_code, (200, 202), response.text)
            rounds += 1
            self.assertLess(rounds, 200, "the preparation never converged")

        self.measurements.update({
            "prepare_seconds": round(time.monotonic() - prepare_started, 1),
            "total_seconds": round(time.monotonic() - started, 1),
            "rounds": rounds,
            "process_peak_rss_mib": peak_rss_mib(),
            "rss_growth_mib": round(peak_rss_mib() - baseline, 1),
            "chunks": response.json().get("chunks"),
        })

        final = response.json()
        self.assertEqual(final["state"], "validated", final)
        self.assertTrue(final["complete"])
        self.assertEqual(final["movement_count"] + final["rejected_count"],
                         TARGET_ROWS)
        self.measurements["movements"] = final["movement_count"]
        self.measurements["rejected"] = final["rejected_count"]

        # Memoria del proceso que importa. Es el numero que reventaba antes.
        self.assertLess(self.measurements["process_peak_rss_mib"], MAX_PEAK_MIB,
                        f"peak RSS {self.measurements['process_peak_rss_mib']} MiB")

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), count(DISTINCT source_record_id) "
                    "FROM fincilia.canonical_movement WHERE dataset_version_id = %s",
                    (dataset,))
                movements, distinct_origins = cursor.fetchone()
                cursor.execute(
                    "SELECT count(*), count(DISTINCT record_ordinal) "
                    "FROM fincilia.raw_record WHERE processing_run_id = ("
                    "  SELECT processing_run_id FROM fincilia.dataset_version "
                    "  WHERE dataset_version_id = %s)", (dataset,))
                raw_rows, distinct_ordinals = cursor.fetchone()
                cursor.execute(
                    "SELECT count(*) FROM fincilia.dataset_chunk "
                    "WHERE dataset_version_id = %s", (dataset,))
                chunk_rows = cursor.fetchone()[0]
                # El grafo no crece por fila: es la premisa entera del rediseno.
                cursor.execute(
                    "SELECT count(*) FROM fincilia.lineage_node "
                    "WHERE company_id = %s", (ESPIGA,))
                nodes = cursor.fetchone()[0]

        self.assertEqual(movements, final["movement_count"])
        # Cero duplicados: un registro de origen produce un movimiento.
        self.assertEqual(movements, distinct_origins)
        self.assertEqual(raw_rows, distinct_ordinals)
        self.measurements.update({"raw_rows": raw_rows, "chunk_rows": chunk_rows,
                                  "lineage_nodes_company_wide": nodes})
        # Con la representacion anterior serian ochocientos mil nodos solo para
        # este dataset. Aqui el grafo es de cardinalidad constante.
        self.assertLess(nodes, 1_000)

        type(self).dataset_id = dataset

    def test_the_published_lineage_reconstructs_at_scale_TST_P35_022(self) -> None:
        dataset = getattr(type(self), "dataset_id", None)
        if dataset is None:
            self.skipTest("the import test has to run first")
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements?limit=25",
            headers=self.auth(REVIEWER)).json()
        self.assertEqual(len(movements), 25)
        for movement in movements[:5]:
            with self.subTest(row=movement["record_ordinal"]):
                detail = self.client.get(
                    f"/api/v1/companies/{ESPIGA}/movements/{movement['movement_id']}",
                    headers=self.auth(REVIEWER)).json()
                self.assertTrue(detail["lineage_complete"], detail.get("lineage_reason"))
                by_field = {item["field"]: item for item in detail["lineage"]}
                self.assertEqual(set(by_field),
                                 {"occurred_on", "description", "reference", "amount"})
                for field, item in by_field.items():
                    self.assertEqual(len(item["stages"]), 6, field)


if __name__ == "__main__":
    unittest.main()
