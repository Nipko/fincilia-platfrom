"""Reanudar una extraccion que fallo entre dos lotes (FNC-P3.6).

La extraccion en corriente escribe por tandas, y una tanda es una transaccion.
Eso deja una pregunta que la version que cargaba el fichero entero no tenia: si
el proceso cae despues de confirmar la segunda tanda y antes de la tercera,
?que pasa al reintentar?

La respuesta tiene que ser «nada visible»: el mismo recuento, el mismo digest y
ni una fila repetida. `uq_raw_record_ordinal` sobre
`(processing_run_id, record_ordinal)` con `ON CONFLICT DO NOTHING` es lo que lo
hace cierto por construccion, y esto lo comprueba en vez de suponerlo.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_extraction_resume -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

sys.path.insert(0, "/app/worker_src")

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from db.tests.test_p3_vertical import approve_fixture_release, purge
from db.tests.test_scale_publication import synthetic_statement
from fincilia_api.main import create_app
from fincilia_contracts.extraction import StreamOutcome, sniff, stream_records
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_contracts.release import digest_of
from fincilia_platform.db import Database
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.probes import ensure_buckets
from fincilia_worker import jobs
from fincilia_worker import main as worker_main
from fincilia_worker.main import process_one

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
PREPARER = "ana@demo.local"

# Suficientes filas para que haya varias tandas y el fallo caiga de verdad entre
# dos, sin convertir esta prueba en una de escala.
ROWS = 4_000
BATCH = 500


class ExtractionResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.settings = build_settings(engine_release_key=approve_fixture_release())
        ensure_buckets(cls.settings)
        cls.created: set[str] = set()
        cls.store = S3ObjectStore(cls.worker_settings())
        cls.client = TestClient(create_app(cls.settings))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        purge(cls.created)

    @classmethod
    def worker_settings(cls):
        from fincilia_platform.settings import WorkerSettings
        saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
        for key in saved:
            del os.environ[key]
        try:
            return WorkerSettings(
                env="test", service_name="fincilia-worker-resume",
                database_url=saved["FINCILIA_WORKER_URL"],
                cache_url="redis://valkey:6379/9",
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

    def drain(self, limit: int = 12) -> None:
        from fincilia_platform.db import Database
        database = Database(self.worker_settings())
        try:
            for _ in range(limit):
                if not process_one(database, self.store, f"resume-{RUN}"):
                    return
        finally:
            database.close()

    def available_now(self, run_id: str) -> None:
        """Adelanta la espera del reintento.

        Esta prueba no mide el `backoff` —eso lo decide `finish_run` y ya tiene
        su propia prueba—, mide que reanudar no duplica.
        """
        # `dispatch_pointer` esta en `rls_exemptions`: no lleva politica de
        # empresa, asi que el migrador la ve entera sin poner contexto.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE fincilia.dispatch_pointer "
                               "SET available_at = now() "
                               "WHERE run_id = %s AND available_at > now()",
                               (run_id,))

    def reference(self, payload: bytes) -> tuple[int, str]:
        """Lo que una lectura entera y sin sobresaltos produce.

        La huella que se compara es la **de registros**, no la del objeto: lo que
        esta prueba afirma es que reanudar ve lo mismo que leer de un tiron, y
        eso lo contesta el resumen de lo entendido. Que los bytes sean los
        mismos lo contesta `object_digest`, y lo comprueba el worker contra
        `source_artifact.content_sha256`.
        """
        outcome = StreamOutcome()
        preamble, reader = sniff(io.BytesIO(payload))
        rows = sum(1 for _ in stream_records(reader, preamble, outcome=outcome))
        return rows, outcome.record_digest

    def extraction_of(self, artifact_id: str) -> dict:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT run_id, status, attempt, result, error_code, "
                    "       failure_class, lease_token::text "
                    "FROM fincilia.processing_run "
                    "WHERE artifact_id = %s AND kind = 'extract'", (artifact_id,))
                rows = cursor.fetchall()
        self.assertEqual(1, len(rows), "there should be exactly one extract run")
        (run_id, status, attempt, result, error_code, failure_class,
         lease_token) = rows[0]
        return {"run_id": str(run_id), "status": status, "attempt": attempt,
                "result": result or {}, "error_code": error_code,
                "failure_class": failure_class, "lease_token": lease_token}

    def stored(self, run_id: str) -> tuple[int, int]:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), count(DISTINCT record_ordinal) "
                    "FROM fincilia.raw_record WHERE processing_run_id = %s",
                    (run_id,))
                return cursor.fetchone()

    def ordinals(self, run_id: str) -> list[int]:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT record_ordinal FROM fincilia.raw_record "
                    "WHERE processing_run_id = %s ORDER BY record_ordinal", (run_id,))
                return [int(row[0]) for row in cursor]

    def attempts(self, run_id: str) -> list[tuple]:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT attempt_number, outcome, failure_class, reason_code "
                    "FROM fincilia.run_attempt WHERE run_id = %s "
                    "ORDER BY attempt_number", (run_id,))
                return cursor.fetchall()

    def pointer_count(self, run_id: str) -> int:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.dispatch_pointer WHERE run_id = %s",
                    (run_id,))
                return int(cursor.fetchone()[0])

    def extraction_audit_count(self, run_id: str) -> int:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.audit_event "
                    "WHERE action = 'document.extraction' "
                    "AND detail ->> 'run' = %s", (run_id,))
                return int(cursor.fetchone()[0])

    def settlement_failure_is_recoverable(self, helper_name: str) -> None:
        payload = ("fecha;descripcion;referencia;valor\n"
                   f"01/02/2026;Fallo {helper_name};SETTLE-{RUN};1,00\n").encode()
        type(self).created.add(sha256_bytes(payload))
        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": (f"settle-{helper_name}-{RUN}.csv", io.BytesIO(payload),
                            "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        artifact_id = upload.json()["artifact_id"]

        original = getattr(worker_main, helper_name)

        def failing(*args, **kwargs):
            claim = args[1]
            if str(claim.artifact_id) == artifact_id:
                raise RuntimeError(f"SYNTHETIC-{helper_name}-FAILURE")
            return original(*args, **kwargs)

        setattr(worker_main, helper_name, failing)
        try:
            self.drain()
        finally:
            setattr(worker_main, helper_name, original)

        pending = self.extraction_of(artifact_id)
        self.assertEqual("queued", pending["status"], pending)
        self.assertEqual(2, pending["attempt"])
        self.assertIsNone(pending["error_code"])
        self.assertEqual(1, self.pointer_count(pending["run_id"]))
        self.assertEqual([(1, "failed", "unknown", "extraction_error")],
                         self.attempts(pending["run_id"]))
        self.assertEqual(0, self.extraction_audit_count(pending["run_id"]))

        self.available_now(pending["run_id"])
        self.drain()
        settled = self.extraction_of(artifact_id)
        self.assertEqual("succeeded", settled["status"], settled)
        self.assertEqual(1, self.extraction_audit_count(settled["run_id"]))

    # ------------------------------------------------------------------ el caso

    def test_a_failure_between_two_batches_resumes_clean_TST_P36_033(self) -> None:
        payload = synthetic_statement(ROWS)
        type(self).created.add(sha256_bytes(payload))
        expected_rows, expected_digest = self.reference(payload)

        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": (f"resume-{RUN}.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        artifact = upload.json()["artifact_id"]

        original_flush = worker_main._flush
        original_batch = worker_main.STORE_BATCH
        calls: list[int] = []
        partial: dict[str, int] = {}

        def failing_flush(database, claim, batch):
            calls.append(len(batch))
            if len(calls) == 3:
                # Dos tandas ya confirmadas y la tercera sin empezar: el hueco
                # exacto que el mandato pide ejercer.
                partial["run_id"] = str(claim.run_id)
                partial["rows"] = self.stored(claim.run_id)[0]
                raise RuntimeError("SYNTHETIC-FAILURE between two batches")
            return original_flush(database, claim, batch)

        worker_main._flush = failing_flush
        worker_main.STORE_BATCH = BATCH
        try:
            self.drain()
            self.assertGreaterEqual(len(calls), 3, "the failure never happened")
            self.assertEqual(2 * BATCH, partial.get("rows"),
                             "two batches should already be durable")

            failed = self.extraction_of(artifact)
            self.assertNotEqual("succeeded", failed["status"])
            self.assertEqual(partial["run_id"], failed["run_id"],
                             "resuming keeps the same run")

            # Y ahora se reanuda, con el mismo trabajo y el mismo identificador.
            worker_main._flush = original_flush
            self.available_now(partial["run_id"])
            self.drain()
        finally:
            worker_main._flush = original_flush
            worker_main.STORE_BATCH = original_batch

        settled = self.extraction_of(artifact)
        self.assertEqual("succeeded", settled["status"], settled)
        self.assertEqual(partial["run_id"], settled["run_id"])
        self.assertGreaterEqual(settled["attempt"], 2, "it should have retried")

        # Recuento y digest, identicos a los de una lectura entera.
        self.assertEqual(expected_rows, settled["result"].get("record_count"))
        self.assertEqual(expected_digest, settled["result"].get("record_digest"))
        # Y la del objeto es la del fichero que se subio, no la de los registros.
        self.assertEqual(sha256_bytes(payload),
                         settled["result"].get("object_digest"))
        self.assertNotEqual(settled["result"].get("object_digest"),
                            settled["result"].get("record_digest"))
        self.assertEqual("complete", settled["result"].get("state"))
        self.assertFalse(settled["result"].get("truncated"))

        # Cero duplicados: tantas filas como ordinales distintos.
        rows, ordinals = self.stored(settled["run_id"])
        self.assertEqual(expected_rows, rows)
        self.assertEqual(rows, ordinals)
        # El conflicto identico de las dos primeras tandas fue una reanudacion,
        # no un error. PostgreSQL las ignoro y el intento final solo cuenta lo
        # que realmente inserto; `stored_records` cuenta el estado durable.
        self.assertEqual(rows, settled["result"].get("stored_records"))
        self.assertEqual(expected_rows - 2 * BATCH,
                         settled["result"].get("inserted_records"))
        self.assertLess(settled["result"]["inserted_records"],
                        settled["result"]["stored_records"])

    def test_a_divergent_conflict_aborts_the_whole_batch(self) -> None:
        """Una segunda lectura distinta falla fatal y no deja media tanda."""
        payload = synthetic_statement(1_200).replace(
            b"Movimiento sintetico 1", b"Movimiento sintetico D1", 1)
        type(self).created.add(sha256_bytes(payload))
        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": (f"divergent-{RUN}.csv", io.BytesIO(payload),
                            "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        artifact_id = upload.json()["artifact_id"]

        original_flush = worker_main._flush
        original_batch = worker_main.STORE_BATCH
        injected: dict[str, object] = {}

        def divergent_flush(database, claim, batch):
            if not injected and str(claim.artifact_id) == artifact_id:
                poisoned = list(batch[len(batch) // 2])
                values = json.loads(poisoned[5])
                values[-1] = "SYNTHETIC-DIVERGENT-READING"
                poisoned[5] = jobs.dumps(values)
                poisoned[6] = digest_of(values)
                with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, false)",
                            (claim.company_id,))
                        cursor.execute(
                            "INSERT INTO fincilia.raw_record (raw_record_id, "
                            "company_id, artifact_id, processing_run_id, "
                            "record_ordinal, origin_locator, raw_values, "
                            "values_digest) VALUES (gen_random_uuid(), %s, %s, "
                            "%s, %s, %s::jsonb, %s::jsonb, %s)", tuple(poisoned))
                injected["run_id"] = str(claim.run_id)
                injected["ordinal"] = poisoned[3]
            return original_flush(database, claim, batch)

        worker_main._flush = divergent_flush
        worker_main.STORE_BATCH = BATCH
        try:
            self.drain()
        finally:
            worker_main._flush = original_flush
            worker_main.STORE_BATCH = original_batch

        self.assertTrue(injected, "the divergent row was never injected")
        settled = self.extraction_of(artifact_id)
        self.assertEqual("failed", settled["status"], settled)
        self.assertEqual(1, settled["attempt"])
        self.assertEqual("raw_record_conflict", settled["error_code"])
        self.assertEqual("fatal", settled["failure_class"])
        self.assertEqual({}, settled["result"])

        rows, ordinals = self.stored(str(injected["run_id"]))
        self.assertEqual(1, rows,
                         "the insert before conflict detection was not rolled back")
        self.assertEqual(1, ordinals)
        self.assertEqual([int(injected["ordinal"])],
                         self.ordinals(str(injected["run_id"])))
        self.assertEqual([(1, "failed", "fatal", "raw_record_conflict")],
                         self.attempts(str(injected["run_id"])))
        self.assertEqual(0, self.pointer_count(str(injected["run_id"])))

    def test_a_stale_lease_cannot_flush_even_one_record(self) -> None:
        """El vallado ocurre dentro de la transaccion que escribiria el lote."""
        artifact_id = str(uuid.uuid4())
        content_digest = uuid.uuid4().hex + uuid.uuid4().hex
        type(self).created.add(content_digest)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "INSERT INTO fincilia.source_artifact (artifact_id, "
                    "company_id, filename, byte_size, content_sha256, media_type, "
                    "zone, object_key, status, uploaded_by) VALUES (%s, %s, "
                    "'stale-synthetic.csv', 10, %s, 'text/csv', 'raw', %s, "
                    "'stored', %s)",
                    (artifact_id, ESPIGA, content_digest,
                     f"synthetic/{content_digest}", stable_id("subject", "ana")))

        with psycopg.connect(RUNTIME_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT fincilia.enqueue_processing_run(%s, %s, 'extract')",
                    (ESPIGA, artifact_id))
                run_id = str(cursor.fetchone()[0])

        database = Database(self.worker_settings())
        old_claim = None
        fresh_claim = None
        try:
            with database.session() as connection:
                old_claim = jobs.claim_next(connection, f"stale-old-{RUN}")
            self.assertIsNotNone(old_claim)
            self.assertEqual(run_id, old_claim.run_id,
                             "another queued job made the fencing test ambiguous")

            values = ["fecha", "descripcion"]
            locator = {"locator_kind": "tabular_delimited",
                       "artifact_sha256": content_digest,
                       "record_ordinal": 1, "byte_start": 1, "byte_end": 9,
                       "field_count": 2}
            batch = [(ESPIGA, artifact_id, run_id, 1, jobs.dumps(locator),
                      jobs.dumps(values), digest_of(values))]

            # El primer worker deja vencer el arriendo. El puntero vuelve a
            # quedar disponible y otro worker recupera exactamente el mismo
            # run con un token nuevo.
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    cursor.execute(
                        "UPDATE fincilia.processing_run SET lease_expires_at = "
                        "clock_timestamp() - interval '1 second' "
                        "WHERE run_id = %s AND lease_token = %s",
                        (run_id, old_claim.lease_token))
                    self.assertEqual(1, cursor.rowcount)
                    cursor.execute(
                        "UPDATE fincilia.dispatch_pointer SET available_at = "
                        "clock_timestamp() - interval '1 second' WHERE run_id = %s",
                        (run_id,))
                    self.assertEqual(1, cursor.rowcount)

            with self.assertRaises(jobs.StaleLease):
                worker_main._flush(database, old_claim, batch)
            self.assertEqual((0, 0), self.stored(run_id))

            with database.session() as connection:
                fresh_claim = jobs.claim_next(connection, f"stale-fresh-{RUN}")
            self.assertIsNotNone(fresh_claim)
            self.assertEqual(run_id, fresh_claim.run_id)
            self.assertNotEqual(old_claim.lease_token, fresh_claim.lease_token)

            with self.assertRaises(jobs.StaleLease):
                worker_main._flush(database, old_claim, batch)
            self.assertEqual((0, 0), self.stored(run_id))

            current = self.extraction_of(artifact_id)
            self.assertEqual("running", current["status"])
            self.assertEqual(2, current["attempt"])
            self.assertEqual(fresh_claim.lease_token, current["lease_token"])
            self.assertIsNone(current["error_code"])
            self.assertIsNone(current["failure_class"])
            self.assertEqual(1, self.pointer_count(run_id))
            self.assertEqual(
                [(1, "abandoned", "unknown", "lease_expired"),
                 (2, "running", None, None)], self.attempts(run_id))
        finally:
            if fresh_claim is not None and fresh_claim.run_id == run_id:
                with database.session(company_id=ESPIGA) as connection:
                    jobs.finish(connection, fresh_claim,
                                error_code="synthetic_test_abort",
                                failure_class=jobs.FATAL)
            database.close()

    def test_a_count_failure_cannot_finish_the_extraction(self) -> None:
        self.settlement_failure_is_recoverable("_stored_records")

    def test_an_audit_failure_rolls_back_the_successful_finish(self) -> None:
        self.settlement_failure_is_recoverable("_audit_extraction")

    def test_the_partial_extraction_never_looked_complete_TST_P36_034(self) -> None:
        """Mientras estuvo a medias, nadie pudo tomarla por terminada.

        Se comprueba sobre el rastro que queda: el intento que fallo esta
        marcado como fallido y con su clase, y el que la cerro es otro.
        """
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT a.outcome, a.failure_class, a.reason_code "
                    "FROM fincilia.run_attempt a "
                    "JOIN fincilia.processing_run r ON r.run_id = a.run_id "
                    "WHERE r.kind = 'extract' AND a.outcome = 'failed' "
                    "  AND a.reason_code = 'extraction_error' "
                    "ORDER BY a.finished_at DESC LIMIT 1")
                row = cursor.fetchone()
        self.assertIsNotNone(row, "the failed attempt should be recorded")
        self.assertEqual("failed", row[0])
        self.assertEqual("unknown", row[1])
        # Y el motivo no transcribe el mensaje de la excepcion ni un valor.
        self.assertEqual("extraction_error", row[2])

    def test_the_extraction_audit_counts_and_quotes_nothing_TST_P36_041(self) -> None:
        """El rastro dice cuanto se leyo y como acabo. Ni un valor.

        Quien tiene `audit.read` no es necesariamente quien puede ver el
        contenido del documento, asi que un rastro que transcribiera importes
        seria una copia parcial del extracto viviendo bajo otras reglas de
        acceso.
        """
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT detail FROM fincilia.audit_event "
                    "WHERE action = 'document.extraction' "
                    "ORDER BY occurred_at DESC LIMIT 5")
                rows = [row[0] for row in cursor]
        self.assertTrue(rows, "the extraction should be audited")
        for detail in rows:
            with self.subTest(detail=sorted(detail)):
                # Las claves son exactamente estas: nada de valores, columnas ni
                # nombres de fichero. `stored` y las dos huellas se anadieron en
                # R1, y la lista sigue siendo cerrada a proposito: es lo que
                # impide que un dia entre aqui un valor del extracto.
                self.assertLessEqual(
                    set(detail), {"records", "stored", "state", "reason",
                                  "object_digest", "record_digest", "run"})
                rendered = json.dumps(detail, ensure_ascii=False)
                for quoted in ("Movimiento sintetico", "1.000.000,00", "REF-",
                               "Apertura"):
                    self.assertNotIn(quoted, rendered)

    def test_a_value_with_tabs_and_backslashes_survives_the_copy_TST_P36_043(self) -> None:
        """La tanda entra por `COPY`, y `COPY` tiene formato de texto propio.

        Una tabulacion, una barra invertida o un salto de linea dentro de un
        campo entrecomillado son exactamente lo que ese formato escapa, y una
        diferencia de escapado corromperia la evidencia sin que nada lo dijera:
        el digest se calcula antes de escribir, asi que no delataria el cambio.
        """
        awkward = "con\ttabulador y \\barra"
        multiline = "primera linea\nsegunda linea"
        payload = (
            "fecha;descripcion;referencia;valor\r\n"
            f'13/02/2026;"{awkward}";REF-000001;1.000,00\r\n'
            f'14/03/2026;"{multiline}";REF-000002;-2.000,00\r\n'
        ).encode("utf-8")
        type(self).created.add(sha256_bytes(payload))

        upload = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents", headers=self.auth(PREPARER),
            files={"file": (f"raro-{RUN}.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(200, upload.status_code, upload.text)
        self.drain()

        settled = self.extraction_of(upload.json()["artifact_id"])
        self.assertEqual("succeeded", settled["status"], settled)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT record_ordinal, raw_values FROM fincilia.raw_record "
                    "WHERE processing_run_id = %s ORDER BY record_ordinal",
                    (settled["run_id"],))
                stored = {row[0]: row[1] for row in cursor}

        # Los bytes que se leyeron son los que quedaron guardados, tabulador,
        # barra y salto de linea incluidos.
        self.assertEqual(awkward, stored[2][1])
        self.assertEqual(multiline, stored[3][1])


if __name__ == "__main__":
    unittest.main()
