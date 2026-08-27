"""Carril de rendimiento: limite productivo, fuera de cada corrida por push.

La corrida bloqueante prueba cien mil filas porque ese es el numero del mandato y
porque cabe en el presupuesto de tiempo de CI. El limite productivo completo no
cabe en cada empuje, y meterlo convertiria cada commit en una espera larga: el coste no
lo paga quien escribe la prueba, lo paga cada persona que empuja un cambio.

Asi que vive aparte y **no corre por defecto**. Se enciende con
`FINCILIA_PERF_LANE=true`, y el flujo de CI la lanza solo en `workflow_dispatch`.
Que no bloquee no la hace decorativa: mide, imprime y falla si el importe se
degrada mas alla del presupuesto.

    FINCILIA_PERF_LANE=true \\
      docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_perf_lane -v
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
from db.spikes.staging_benchmark import run as staging_run
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from db.tests.test_p3_vertical import MAPPING, approve_fixture_release, purge
from db.tests.test_scale_publication import peak_rss_mib, synthetic_statement
from fincilia_api.main import create_app
from fincilia_contracts.extraction import MAX_EXTRACT_ROWS
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ensure_buckets
from fincilia_worker.main import process_one

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
SOURCE = stable_id("data_source", "espiga")
ACCOUNT = stable_id("account", "espiga")
PREPARER = "ana@demo.local"
REVIEWER = "beto@demo.local"

# El carril mide **el limite productivo**, y por eso el numero sale de la
# constante y no de un deseo. Antes decia 250.000 mientras `MAX_EXTRACT_ROWS`
# decia 200.000: el carril habria medido una lectura truncada creyendo medir una
# entera, que es la peor clase de medida —sale un numero, y el numero no
# corresponde a lo que se dice haber medido—.
#
# Reconciliar hacia arriba habria sido subir el techo del producto para que
# cuadrara una prueba. Se reconcilia hacia el contrato.
TARGET_ROWS = MAX_EXTRACT_ROWS

# Dos veces el volumen de la corrida bloqueante, con el mismo margen proporcional
# sobre sus presupuestos. Si el importe fuera lineal, 94,2 s se convertirian en
# unos 188; se deja hasta 600 porque el carril corre en una maquina que no se
# reserva para el.
MAX_TOTAL_SECONDS = 600
MAX_PEAK_MIB = 600
MAX_GROWTH_MIB = 200


def enabled() -> bool:
    return os.environ.get("FINCILIA_PERF_LANE", "").lower() == "true"


class PerformanceLaneTests(unittest.TestCase):
    """No bloquea, pero tampoco afirma sin medir."""

    @classmethod
    def setUpClass(cls) -> None:
        if not enabled():
            raise unittest.SkipTest(
                "the performance lane runs on demand: set FINCILIA_PERF_LANE=true")
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.settings = build_settings(engine_release_key=approve_fixture_release())
        ensure_buckets(cls.settings)
        cls.created: set[str] = set()
        cls.store = S3ObjectStore(cls.worker_settings())
        cls.client = TestClient(create_app(cls.settings))
        cls.client.__enter__()
        cls.measurements: dict[str, object] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if cls.measurements:
            print(f"\n[carril] {cls.measurements}", flush=True)
        purge(cls.created)

    @classmethod
    def worker_settings(cls):
        from fincilia_platform.settings import WorkerSettings
        saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
        for key in saved:
            del os.environ[key]
        try:
            return WorkerSettings(
                env="test", service_name="fincilia-worker-perf",
                database_url=saved["FINCILIA_WORKER_URL"],
                cache_url="redis://valkey:6379/11",
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
                if not process_one(database, self.store, f"perf-{RUN}"):
                    return
        finally:
            database.close()

    def extraction_of(self, artifact_id: str) -> dict:
        """El resultado de la extraccion, tal y como quedo guardado."""
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT result FROM fincilia.processing_run "
                    "WHERE artifact_id = %s AND kind = 'extract' "
                    "AND status = 'succeeded'", (artifact_id,))
                row = cursor.fetchone()
        return (row[0] if row else {}) or {}

    # ------------------------------------------------------------------ el caso

    def test_the_productive_ceiling_imports_within_budget_TST_P36_039(self) -> None:
        """El fichero mas grande que el producto acepta, entero y medido."""
        payload = synthetic_statement(TARGET_ROWS)
        type(self).created.add(sha256_bytes(payload))
        self.measurements.update({"target_rows": TARGET_ROWS,
                                  "bytes": len(payload)})

        started = time.monotonic()
        baseline = peak_rss_mib()
        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            params={"data_source_id": SOURCE},
            files={"file": (f"perf-{RUN}.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        artifact = upload.json()["artifact_id"]
        self.drain()
        self.measurements["extract_seconds"] = round(time.monotonic() - started, 1)

        body = dict(MAPPING)
        body.update({"artifact_id": artifact, "data_source_id": SOURCE,
                     "display_name": f"mapeo carril {RUN}"})
        created = self.client.post(f"/api/v1/companies/{ESPIGA}/mappings",
                                   headers=self.auth(PREPARER), json=body)
        self.assertEqual(201, created.status_code, created.text)
        version = created.json()["mapping_version_id"]
        self.assertEqual(200, self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version}/validate",
            headers=self.auth(PREPARER)).status_code)

        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": version,
                  "financial_account_id": ACCOUNT})
        self.assertIn(response.status_code, (201, 202), response.text)
        dataset = response.json()["dataset_version_id"]
        rounds = 1
        while response.status_code == 202:
            self.assertEqual(response.json()["state"], "staging")
            response = self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/continue",
                headers=self.auth(PREPARER))
            self.assertIn(response.status_code, (200, 202), response.text)
            rounds += 1
            self.assertLess(rounds, 400, "the preparation never converged")

        final = response.json()
        self.measurements.update({
            "total_seconds": round(time.monotonic() - started, 1),
            "rounds": rounds,
            "process_peak_rss_mib": peak_rss_mib(),
            "rss_growth_mib": round(peak_rss_mib() - baseline, 1),
            "chunks": final.get("chunks"),
            "movements": final.get("movement_count"),
            "rejected": final.get("rejected_count"),
        })

        self.assertEqual("validated", final["state"], final)
        self.assertEqual(TARGET_ROWS,
                         final["movement_count"] + final["rejected_count"])
        # Y estaba **entera**: el limite es el techo, no una fila menos.
        self.assertIs(False, self.extraction_of(artifact).get("truncated"),
                      "la lectura del limite exacto no puede salir truncada")

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), count(DISTINCT source_record_id) "
                    "FROM fincilia.canonical_movement WHERE dataset_version_id = %s",
                    (dataset,))
                movements, origins = cursor.fetchone()
        # Cero duplicados tambien a este volumen.
        self.assertEqual(movements, origins)

        self.assertLess(self.measurements["total_seconds"], MAX_TOTAL_SECONDS,
                        f"the import took {self.measurements['total_seconds']} s")
        self.assertLess(self.measurements["process_peak_rss_mib"], MAX_PEAK_MIB)
        self.assertLess(self.measurements["rss_growth_mib"], MAX_GROWTH_MIB)

    def test_one_row_over_the_ceiling_truncates_at_scale_TST_P36_044(self) -> None:
        """Y una fila mas se trunca, a tamano real.

        La prueba pura lo comprueba con cinco filas y un techo de cinco, que es
        donde vive la logica. Esta lo comprueba donde vive el riesgo: con el
        techo de verdad, sobre PostgreSQL y el almacen de objetos, porque un
        limite que se aplica bien en una prueba de mesa y mal a escala no es un
        limite.
        """
        payload = synthetic_statement(TARGET_ROWS + 1)
        type(self).created.add(sha256_bytes(payload))
        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            params={"data_source_id": SOURCE},
            files={"file": (f"techo-{RUN}.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        self.drain()

        result = self.extraction_of(upload.json()["artifact_id"])
        self.measurements["over_the_ceiling"] = {
            "row_count": result.get("row_count"),
            "truncated": result.get("truncated"),
            "reason": result.get("truncation_reason"),
            "stored": result.get("stored_records"),
        }
        self.assertIs(True, result.get("truncated"))
        self.assertEqual("row_limit", result.get("truncation_reason"))
        self.assertEqual(TARGET_ROWS, result.get("row_count"))
        # La fila que sobra no se persiste: el techo no es orientativo.
        self.assertEqual(TARGET_ROWS + 1, result.get("stored_records"),
                         "se guardan el membrete y las filas del techo, ni una mas")

    def test_the_staging_spike_at_scale_TST_P36_040(self) -> None:
        """La comparacion INSERT/COPY con el volumen que la hace significativa."""
        result = staging_run(TARGET_ROWS,
                             app_dsn=os.environ["FINCILIA_WORKER_URL"],
                             migrator_dsn=MIGRATOR_DSN, company_id=ESPIGA,
                             other_company_id=ANDINOS)
        self.measurements["staging_spike"] = result
        for label in ("insert_multirow_500", "copy_through_temp_500",
                      "copy_through_temp_5000"):
            self.assertEqual(TARGET_ROWS, result[label]["stored"], label)
        self.assertIs(True, result["security_clean"], result["security"])


if __name__ == "__main__":
    unittest.main()
