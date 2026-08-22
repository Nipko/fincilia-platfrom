"""Toma de trabajos del worker, contra PostgreSQL y MinIO reales.

Aqui no hay dobles porque lo que se prueba es precisamente el comportamiento del
motor: que `FOR UPDATE SKIP LOCKED` impida que dos workers ejecuten el mismo
trabajo, que RLS siga acotando lo que el worker ve una vez fijado el contexto, y
que un puntero reclamado por un proceso muerto vuelva al reparto.

Requiere el esquema migrado y la demo sembrada. Se ejecuta asi:

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from contextlib import contextmanager

import psycopg

sys.path.insert(0, "/app/src")

from fincilia_platform.db import Database  # noqa: E402
from fincilia_platform.objects import S3ObjectStore, object_key  # noqa: E402
from fincilia_platform.settings import WorkerSettings  # noqa: E402
from fincilia_worker import jobs  # noqa: E402
from fincilia_worker.main import process_one  # noqa: E402

RUNTIME_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
# El mismo espacio de nombres que la semilla: si cambia, estas pruebas dejarian
# de apuntar a la empresa de demo y lo dirian en vez de pasar en vacio.
NAMESPACE = uuid.UUID("5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e")
# Empresas de banco de pruebas: existen en la semilla y **nadie** tiene concesion
# sobre ellas. Lo que estas pruebas escriban no lo puede ver ningun usuario, y no
# hace falta borrarlo -- que es justo lo que el rol runtime no puede hacer con un
# artefacto ni con el historial de trabajos, y esta bien que no pueda.
SANDBOX_A = str(uuid.uuid5(NAMESPACE, "company:sandbox_a"))
SANDBOX_B = str(uuid.uuid5(NAMESPACE, "company:sandbox_b"))
ANA = str(uuid.uuid5(NAMESPACE, "subject:ana"))

BANK_CSV = (
    "Fecha;Detalle;Debito;Credito\n"
    "02/03/2026;Transferencia;1.250.000,00;\n"
    "15/03/2026;Consignacion;;3.400.000,00\n"
).encode("utf-8")


@contextmanager
def isolated_env():
    saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def build_settings() -> WorkerSettings:
    with isolated_env():
        return WorkerSettings(
            env="test",
            service_name="fincilia-worker-test",
            database_url=RUNTIME_DSN,
            cache_url="redis://valkey:6379/2",
            object_store_endpoint="http://objectstore:9000",
            object_access_key=os.environ.get("FINCILIA_OBJECT_ACCESS_KEY",
                                             "fincilia_local_object"),
            object_secret_key=os.environ.get("FINCILIA_OBJECT_SECRET_KEY",
                                             "fincilia_local_object_only"),
        )


class WorkerJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUNTIME_DSN:
            raise unittest.SkipTest("a runtime DSN is required")
        cls.settings = build_settings()
        cls.database = Database(cls.settings)
        cls.store = S3ObjectStore(cls.settings)
        cls.artifacts: list[tuple[str, str]] = []

    @classmethod
    def tearDownClass(cls) -> None:
        # Solo se limpian los punteros, que es lo unico que el rol runtime puede
        # borrar. El artefacto y el historial de trabajos se quedan, y es
        # correcto que se queden: son registro, no cache. Por eso las pruebas
        # escriben en empresas que nadie puede ver.
        for company_id, artifact_id in cls.artifacts:
            with cls.database.session(company_id=company_id) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN "
                        "(SELECT run_id FROM fincilia.processing_run "
                        " WHERE artifact_id = %s)", (artifact_id,))
        cls.database.close()

    # ---------------------------------------------------------------- helpers #

    def stage(self, *, company_id: str = SANDBOX_A, payload: bytes = BANK_CSV,
              zone: str = "raw", enqueue: bool = True,
              write_object: bool = True) -> tuple[str, str | None]:
        """Deja un artefacto en su zona y, opcionalmente, un trabajo encolado."""
        digest = uuid.uuid4().hex + uuid.uuid4().hex  # 64 caracteres hexadecimales
        key = object_key(company_id, digest)
        if write_object:
            self.store.put(zone, key, payload, content_type="text/csv")
        artifact_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4()) if enqueue else None
        with self.database.session(company_id=company_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                    "filename, byte_size, content_sha256, media_type, zone, object_key, "
                    "status, uploaded_by) VALUES (%s, %s, 'banco.csv', %s, %s, "
                    "'text/csv', %s, %s, %s, %s)",
                    (artifact_id, company_id, len(payload), digest, zone, key,
                     "stored" if zone == "raw" else "quarantined", ANA))
                if run_id:
                    cursor.execute(
                        "INSERT INTO fincilia.processing_run (run_id, company_id, "
                        "artifact_id, kind) VALUES (%s, %s, %s, 'profile')",
                        (run_id, company_id, artifact_id))
                    cursor.execute(
                        "INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind) "
                        "VALUES (%s, %s, 'profile')", (run_id, company_id))
        type(self).artifacts.append((company_id, artifact_id))
        return artifact_id, run_id

    def run_row(self, company_id: str, run_id: str) -> dict:
        with self.database.session(company_id=company_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, error_code, result FROM fincilia.processing_run "
                    "WHERE run_id = %s", (run_id,))
                row = cursor.fetchone()
        self.assertIsNotNone(row)
        return {"status": row[0], "error_code": row[1], "result": row[2]}

    def drain(self, limit: int = 20) -> int:
        done = 0
        while done < limit and process_one(self.database, self.store, "test-worker"):
            done += 1
        return done

    # ------------------------------------------------------------- recorrido #

    def test_a_queued_job_is_taken_and_profiled(self) -> None:
        _, run_id = self.stage()
        self.assertTrue(self.drain())
        row = self.run_row(SANDBOX_A, run_id)
        self.assertEqual("succeeded", row["status"])
        self.assertIsNone(row["error_code"])
        self.assertEqual(";", row["result"]["delimiter"])
        self.assertEqual(2, row["result"]["row_count"])
        self.assertEqual(4, row["result"]["column_count"])

    def test_the_profile_reports_colombian_formats(self) -> None:
        _, run_id = self.stage()
        self.drain()
        columns = self.run_row(SANDBOX_A, run_id)["result"]["columns"]
        by_header = {column["header"]: column for column in columns}
        self.assertEqual("date_dmy", by_header["Fecha"]["inferred_type"])
        self.assertEqual("decimal_comma", by_header["Debito"]["inferred_type"])

    def test_the_stored_profile_carries_no_values(self) -> None:
        _, run_id = self.stage()
        self.drain()
        rendered = str(self.run_row(SANDBOX_A, run_id)["result"])
        for value in ("Transferencia", "Consignacion", "1.250.000", "3.400.000"):
            self.assertNotIn(value, rendered)

    def test_the_pointer_disappears_when_the_job_ends(self) -> None:
        _, run_id = self.stage()
        self.drain()
        with self.database.session() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.dispatch_pointer "
                           "WHERE run_id = %s", (run_id,))
            self.assertEqual(0, cursor.fetchone()[0])

    def test_a_job_is_never_run_twice(self) -> None:
        _, run_id = self.stage()
        self.drain()
        # Segunda pasada: no queda nada que tomar para ese trabajo.
        self.assertEqual(0, self.drain(limit=1))
        self.assertEqual("succeeded", self.run_row(SANDBOX_A, run_id)["status"])

    def test_a_quarantined_artifact_is_never_profiled(self) -> None:
        # Aunque alguien encole el trabajo a mano, el worker se niega: procesar un
        # fichero en cuarentena seria pasearlo por un proceso mas.
        _, run_id = self.stage(zone="quarantine")
        self.drain()
        row = self.run_row(SANDBOX_A, run_id)
        self.assertEqual("failed", row["status"])
        self.assertEqual("artifact_not_promoted", row["error_code"])

    def test_an_unreadable_file_fails_with_a_reason(self) -> None:
        _, run_id = self.stage(payload=b"\xff\xfe\x00\x01 sin estructura")
        self.drain()
        row = self.run_row(SANDBOX_A, run_id)
        self.assertEqual("failed", row["status"])
        self.assertTrue(row["error_code"])

    def test_a_missing_object_fails_with_a_reason(self) -> None:
        # La fila dice que el objeto esta; el objeto no esta. El trabajo falla
        # diciendo por que, en vez de quedarse en `running` para siempre.
        _, run_id = self.stage(write_object=False)
        self.drain()
        row = self.run_row(SANDBOX_A, run_id)
        self.assertEqual("failed", row["status"])
        self.assertEqual("evidence_unreadable", row["error_code"])

    def test_a_job_never_stays_running(self) -> None:
        for payload in (b"\xff\xfe\x00\x01 binario", b"", BANK_CSV):
            with self.subTest(payload=payload[:6]):
                _, run_id = self.stage(payload=payload or b" ")
                self.drain()
                self.assertIn(self.run_row(SANDBOX_A, run_id)["status"],
                              {"succeeded", "failed"})

    def test_work_from_another_company_is_taken_with_its_own_context(self) -> None:
        _, espiga_run = self.stage(company_id=SANDBOX_A)
        _, andinos_run = self.stage(company_id=SANDBOX_B)
        self.drain()
        self.assertEqual("succeeded", self.run_row(SANDBOX_A, espiga_run)["status"])
        self.assertEqual("succeeded", self.run_row(SANDBOX_B, andinos_run)["status"])
        # Y el trabajo de una empresa no es visible desde el contexto de la otra.
        with self.database.session(company_id=SANDBOX_A) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM fincilia.processing_run "
                               "WHERE run_id = %s", (andinos_run,))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_a_claim_from_a_dead_process_returns_to_the_queue(self) -> None:
        _, run_id = self.stage()
        with self.database.session() as connection:
            with connection.cursor() as cursor:
                # Se simula el proceso que murio despues de reclamar: puntero
                # tomado hace mucho, trabajo todavia en `queued`.
                cursor.execute(
                    "UPDATE fincilia.dispatch_pointer "
                    "SET claimed_at = now() - make_interval(secs => %s), "
                    "    claimed_by = 'proceso-muerto' WHERE run_id = %s",
                    (jobs.STALE_CLAIM_SECONDS + 60, run_id))
        self.drain()
        self.assertEqual("succeeded", self.run_row(SANDBOX_A, run_id)["status"])

    def test_a_fresh_claim_is_left_alone(self) -> None:
        _, run_id = self.stage()
        with self.database.session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE fincilia.dispatch_pointer SET claimed_at = now(), "
                    "claimed_by = 'otro-worker' WHERE run_id = %s", (run_id,))
                released = jobs.release_stale(connection)
        self.assertEqual(0, released)
        self.assertEqual("queued", self.run_row(SANDBOX_A, run_id)["status"])
        # Se libera para que la limpieza de la clase pueda llevarselo.
        with self.database.session() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM fincilia.dispatch_pointer WHERE run_id = %s",
                               (run_id,))

    def test_an_empty_queue_reports_no_work(self) -> None:
        self.drain()
        self.assertFalse(process_one(self.database, self.store, "test-worker"))

    def test_the_worker_role_cannot_rewrite_an_artifact(self) -> None:
        artifact_id, _ = self.stage(enqueue=False)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.database.session(company_id=SANDBOX_A) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE fincilia.source_artifact SET zone = 'quarantine' "
                        "WHERE artifact_id = %s", (artifact_id,))


if __name__ == "__main__":
    unittest.main()
