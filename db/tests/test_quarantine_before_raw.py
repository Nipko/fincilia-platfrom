"""Cuarentena antes que evidencia, de extremo a extremo.

`docs/architecture/dfd-flows.json` declara la subida como
`evidence_quarantine_only` y la promocion como un flujo aparte con control
`C-SCAN` (`content_scan_before_raw`). Estas pruebas comprueban que el codigo dice
lo mismo que el contrato, contra PostgreSQL y MinIO reales.

La regla que se prueba una y otra vez, desde angulos distintos: **nada llega a la
zona de evidencia sin que su contenido se haya inspeccionado entero**. Un formato
que hoy no se sabe inspeccionar se queda donde esta, con el motivo escrito.

Esto cierra la parte automatizable de PAN y credenciales antes de `raw`: el
contenido se recorre completo, el PAN se confirma con Luhn y el hallazgo nunca
incluye el valor. No afirma antivirus. Un formato sin analizador completo
(incluido PDF hoy) permanece en cuarentena; S-01 y TM-005 conservan la revision
humana y el control de malware del entorno objetivo como limites separados.
"""

from __future__ import annotations

import io
import unittest
import uuid
import zipfile

import psycopg
from fastapi.testclient import TestClient

# El worker no esta en el PYTHONPATH de la imagen a proposito: la API no debe
# poder importarlo. Estas pruebas si lo necesitan, para ejercer el recorrido
# entero en un proceso en vez de depender de que el worker de fondo llegue a
# tiempo.
import sys
sys.path.insert(0, "/app/worker_src")
sys.path.insert(0, "/app/packages/contracts/python/tests")

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_platform.objects import S3ObjectStore, object_key
from fincilia_platform.probes import ensure_buckets
from fincilia_worker import jobs
from fincilia_worker.main import process_one
from xlsx_factory import build_xlsx

RUN = uuid.uuid4().hex[:12]
ESPIGA = stable_id("company", "espiga")
SOURCE = stable_id("data_source", "espiga")

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n"


def clean_csv(marker: str) -> bytes:
    return (f"fecha,descripcion,valor,moneda\n"
            f"2026-01-02,Escaneo {RUN}-{marker},-1250.00,COP\n").encode("utf-8")


def card_csv(marker: str) -> bytes:
    return (f"cliente,medio,valor\n"
            f"Cliente {RUN}-{marker},4111111111111111,120000.00\n").encode("utf-8")


def build_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return buffer.getvalue()


class QuarantineBeforeRawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.settings = build_settings()
        ensure_buckets(cls.settings)
        cls.store = S3ObjectStore(cls.settings)
        cls.created: set[str] = set()
        cls.client = TestClient(create_app(cls.settings))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if not cls.created:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                for statement in (
                        "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN ("
                        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                        "  SELECT artifact_id FROM fincilia.source_artifact "
                        "  WHERE content_sha256 = ANY(%s)))",
                        "DELETE FROM fincilia.run_attempt WHERE run_id IN ("
                        " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                        "  SELECT artifact_id FROM fincilia.source_artifact "
                        "  WHERE content_sha256 = ANY(%s)))",
                        # Promover encola tambien la extraccion, asi que
                        # ahora hay filas que referencian al trabajo. El
                        # `ON DELETE RESTRICT` de la clave ajena es lo que
                        # impide que borrar un trabajo se lleve por delante
                        # la evidencia extraida sin decirlo.
                        "DELETE FROM fincilia.raw_record WHERE artifact_id IN ("
                        " SELECT artifact_id FROM fincilia.source_artifact "
                        " WHERE content_sha256 = ANY(%s))",
                        "DELETE FROM fincilia.spreadsheet_selection WHERE artifact_id IN ("
                        " SELECT artifact_id FROM fincilia.source_artifact "
                        " WHERE content_sha256 = ANY(%s))",
                        "DELETE FROM fincilia.processing_run WHERE artifact_id IN ("
                        " SELECT artifact_id FROM fincilia.source_artifact "
                        " WHERE content_sha256 = ANY(%s))",
                        "DELETE FROM fincilia.promotion_decision WHERE artifact_id IN ("
                        " SELECT artifact_id FROM fincilia.source_artifact "
                        " WHERE content_sha256 = ANY(%s))",
                        "DELETE FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s)"):
                    cursor.execute(statement, (list(cls.created),))

    # ---------------------------------------------------------------- helpers #

    def token(self, username: str = "ana@demo.local") -> str:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["token"]

    def upload(self, payload: bytes, filename: str) -> dict:
        type(self).created.add(sha256_bytes(payload))
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents",
            params={"data_source_id": SOURCE},
            headers={"Authorization": f"Bearer {self.token()}"},
            files={"file": (filename, io.BytesIO(payload), "application/octet-stream")})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def drain(self, limit: int = 12) -> None:
        """Ejecuta la cola hasta vaciarla, sin esperar al worker de fondo.

        Con las credenciales del **worker**, no con las de la API: reclamar
        trabajo es un privilegio que la API no tiene, y usar aqui su rol haria que
        la prueba no probara el recorrido real. La primera version lo hizo, y el
        sintoma fue un trabajo que se quedaba en cola para siempre.
        """
        from fincilia_platform.db import Database
        database = Database(self.worker_settings())
        try:
            for _ in range(limit):
                if not process_one(database, self.store, f"test-{RUN}"):
                    return
        finally:
            database.close()

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
                cache_url="redis://valkey:6379/4",
                object_store_endpoint=saved.get("FINCILIA_OBJECT_STORE_ENDPOINT",
                                                "http://objectstore:9000"),
                object_access_key=saved.get("FINCILIA_OBJECT_ACCESS_KEY",
                                            "fincilia_local_object"),
                object_secret_key=saved.get("FINCILIA_OBJECT_SECRET_KEY",
                                            "fincilia_local_object_only"))
        finally:
            os.environ.update(saved)

    def document(self, artifact_id: str) -> dict:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact_id}",
            headers={"Authorization": f"Bearer {self.token()}"})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def settle(self, payload: bytes, filename: str) -> dict:
        created = self.upload(payload, filename)
        self.drain()
        return self.document(created["artifact_id"])

    # ------------------------------------------------------------- la regla #

    def test_an_upload_always_lands_in_quarantine(self) -> None:
        # Antes de que nadie escanee nada, la zona es cuarentena. Sin excepciones
        # por formato: es lo que declara F02.
        created = self.upload(clean_csv("aterriza"), "extracto.csv")
        self.assertEqual("quarantine", created["zone"])
        self.assertEqual("quarantined", created["status"])

    def test_a_clean_csv_is_promoted_only_after_being_read_whole(self) -> None:
        document = self.settle(clean_csv("promovido"), "extracto.csv")
        self.assertEqual("raw", document["zone"])
        self.assertEqual("promoted", document["promotion"]["decision"])
        self.assertEqual("content_inspected", document["promotion"]["reason_code"])
        # Y el objeto esta de verdad en la zona que la decision dice.
        key = object_key(ESPIGA, document["content_sha256"])
        self.assertTrue(self.store.exists("raw", key))
        # El original se conserva en cuarentena: promover copia, no mueve.
        self.assertTrue(self.store.exists("quarantine", key))

    def test_a_pdf_never_reaches_raw(self) -> None:
        # El defecto que motivo esta rebanada: un PDF llegaba a la zona de
        # evidencia sin que nadie hubiera leido su contenido.
        document = self.settle(PDF, "factura.pdf")
        self.assertEqual("quarantine", document["zone"])
        self.assertEqual("quarantined", document["promotion"]["decision"])
        self.assertEqual("no_scanner_for_format", document["promotion"]["reason_code"])
        self.assertFalse(self.store.exists("raw", object_key(ESPIGA,
                                                             document["content_sha256"])))

    def test_a_generic_zip_never_reaches_raw(self) -> None:
        payload = build_zip({f"nota-{RUN}.txt": b"contenido cualquiera"})
        document = self.settle(payload, "cosas.zip")
        self.assertEqual("quarantine", document["zone"])
        self.assertEqual("zip", document["promotion"]["internal_type"])

    def test_a_safe_single_sheet_xlsx_is_scanned_profiled_and_extracted(self) -> None:
        payload = build_xlsx([
            ["Fecha", "Descripcion", "Importe", "Moneda"],
            ["2026-01-02", f"Pago {RUN}", -1250, "COP"],
            ["2026-01-03", f"Abono {RUN}", 3400, "COP"],
        ])
        document = self.settle(payload, "libro.xlsx")
        self.assertEqual("raw", document["zone"])
        self.assertEqual("xlsx", document["promotion"]["internal_type"])
        self.assertEqual("content_inspected", document["promotion"]["reason_code"])
        runs = {run["kind"]: run for run in document["runs"]}
        self.assertEqual("xlsx", runs["profile"]["result"]["technical_format"])
        self.assertEqual("succeeded", runs["extract"]["status"])
        self.assertEqual(3, runs["extract"]["result"]["stored_records"])
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT record_ordinal, origin_locator, raw_values "
                    "FROM fincilia.raw_record WHERE artifact_id = %s "
                    "ORDER BY record_ordinal", (document["artifact_id"],))
                rows = cursor.fetchall()
        self.assertEqual([1, 2, 3], [row[0] for row in rows])
        self.assertEqual("spreadsheet", rows[1][1]["locator_kind"])
        self.assertEqual(2, rows[1][1]["row_number"])
        self.assertEqual(f"Pago {RUN}", rows[1][2][1])

    def test_a_safe_multi_sheet_xlsx_waits_for_and_uses_explicit_selection(self) -> None:
        payload = build_xlsx(
            [["Resumen"], [f"NO-EXTRAER-{RUN}"]],
            second_sheet=[
                ["Fecha", "Descripcion", "Importe", "Moneda"],
                ["2026-02-01", f"SEGUNDA-{RUN}", -2700, "COP"],
            ])
        created = self.upload(payload, "multihoja.xlsx")
        self.drain()
        document = self.document(created["artifact_id"])
        self.assertEqual("raw", document["zone"])
        self.assertEqual("content_inspected_selection_required",
                         document["promotion"]["reason_code"])
        self.assertIsNone(document["spreadsheet"]["selection"])
        self.assertEqual(["scan"], [run["kind"] for run in document["runs"]])

        sheets = document["spreadsheet"]["sheets"]
        unknown = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents/{created['artifact_id']}"
            "/spreadsheet-selection",
            headers={"Authorization": f"Bearer {self.token()}"},
            json={"sheet_identity": "0" * 64})
        self.assertEqual(422, unknown.status_code, unknown.text)
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents/{created['artifact_id']}"
            "/spreadsheet-selection",
            headers={"Authorization": f"Bearer {self.token()}"},
            json={"sheet_identity": sheets[1]["sheet_identity"]})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("Otra", response.json()["sheet_name"])
        self.drain()

        document = self.document(created["artifact_id"])
        self.assertEqual("Otra", document["spreadsheet"]["selection"]["sheet_name"])
        selection_id = document["spreadsheet"]["selection"]["selection_id"]
        runs = {run["kind"]: run for run in document["runs"]}
        self.assertEqual("Otra", runs["profile"]["result"]["sheet_name"])
        self.assertEqual("succeeded", runs["extract"]["status"])
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT raw_values, origin_locator FROM fincilia.raw_record "
                    "WHERE artifact_id = %s ORDER BY record_ordinal",
                    (created["artifact_id"],))
                rows = cursor.fetchall()
        self.assertIn(f"SEGUNDA-{RUN}", repr(rows))
        self.assertNotIn(f"NO-EXTRAER-{RUN}", repr(rows))
        self.assertTrue(all(row[1]["sheet_ordinal"] == 2 for row in rows))

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.spreadsheet_selection SET sheet_ordinal = 1 "
                        "WHERE selection_id = %s", (selection_id,))
            connection.rollback()

        andinos = stable_id("company", "andinos")
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (andinos,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.spreadsheet_selection "
                    "WHERE selection_id = %s", (selection_id,))
                self.assertEqual(0, cursor.fetchone()[0])

        conflict = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents/{created['artifact_id']}"
            "/spreadsheet-selection",
            headers={"Authorization": f"Bearer {self.token()}"},
            json={"sheet_identity": sheets[0]["sheet_identity"]})
        self.assertEqual(409, conflict.status_code, conflict.text)

    def test_a_csv_with_a_card_stays_quarantined(self) -> None:
        document = self.settle(card_csv("tarjeta"), "clientes.csv")
        self.assertEqual("quarantine", document["zone"])
        self.assertEqual("sensitive_content", document["promotion"]["reason_code"])
        # El hallazgo dice donde y de que tipo, nunca el valor.
        self.assertNotIn("4111111111111111", str(document))

    def test_a_quarantined_file_never_feeds_a_profile(self) -> None:
        # Lo que no ha pasado inspeccion no se pasea por otro proceso.
        for payload, name in ((PDF, "factura.pdf"), (card_csv("sin-perfil"), "c.csv")):
            with self.subTest(name=name):
                document = self.settle(payload, name)
                kinds = [run["kind"] for run in document["runs"]]
                self.assertIn("scan", kinds)
                self.assertNotIn("profile", kinds)

    def test_a_promoted_file_is_profiled(self) -> None:
        document = self.settle(clean_csv("perfilado"), "extracto.csv")
        kinds = {run["kind"]: run for run in document["runs"]}
        self.assertIn("scan", kinds)
        self.assertIn("profile", kinds)
        self.assertEqual("succeeded", kinds["profile"]["status"])

    def test_rescanning_the_same_artifact_does_not_change_the_decision(self) -> None:
        # La decision es reproducible: mismo escaner y mismo artefacto, una sola
        # decision. Reintentar un escaneo es inocuo.
        document = self.settle(clean_csv("reescaneo"), "extracto.csv")
        artifact_id = document["artifact_id"]
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute("SELECT count(*) FROM fincilia.promotion_decision "
                               "WHERE artifact_id = %s", (artifact_id,))
                before = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT fincilia.enqueue_processing_run(%s, %s, 'scan')",
                    (ESPIGA, artifact_id))
        self.drain()
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute("SELECT count(*) FROM fincilia.promotion_decision "
                               "WHERE artifact_id = %s", (artifact_id,))
                after = cursor.fetchone()[0]
        self.assertEqual(before, after, "the same scanner produces one decision")

    def test_a_promotion_is_audited(self) -> None:
        document = self.settle(clean_csv("auditada"), "extracto.csv")
        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=200",
            headers={"Authorization": f"Bearer {self.token('sofia@demo.local')}"}).json()
        promotions = [event for event in events
                      if event["action"] == "document.promotion"
                      and event["resource_ref"] == document["artifact_id"]]
        self.assertTrue(promotions, "a promotion is a decision and leaves a trace")
        self.assertEqual("allowed", promotions[0]["outcome"])

    def test_a_refusal_to_promote_is_audited_as_denied(self) -> None:
        document = self.settle(PDF, "factura.pdf")
        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=200",
            headers={"Authorization": f"Bearer {self.token('sofia@demo.local')}"}).json()
        decisions = [event for event in events
                     if event["action"] == "document.promotion"
                     and event["resource_ref"] == document["artifact_id"]]
        self.assertTrue(decisions)
        self.assertEqual("denied", decisions[0]["outcome"])

    # ------------------------------------------------------ coherencia interna #

    def test_the_three_lists_of_work_kinds_agree(self) -> None:
        # La misma lista vive en la restriccion del trabajo, en la del puntero y
        # en la validacion de la funcion. Ampliar una sola produce un fallo que no
        # menciona a las otras dos, y eso ya paso dos veces.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT conrelid::regclass::text, pg_get_constraintdef(oid) "
                    "FROM pg_constraint WHERE conname IN ('ck_run_kind', 'ck_dispatch_kind')")
                definitions = dict(cursor.fetchall())
                cursor.execute(
                    "SELECT prosrc FROM pg_proc p JOIN pg_namespace n "
                    "ON n.oid = p.pronamespace WHERE n.nspname = 'fincilia' "
                    "AND p.proname = 'enqueue_processing_run'")
                source = cursor.fetchone()[0]
        self.assertEqual(2, len(definitions))
        for table, definition in definitions.items():
            with self.subTest(table=table):
                for kind in ("scan", "profile", "extract"):
                    self.assertIn(f"'{kind}'", definition)
        for kind in ("scan", "profile", "extract"):
            self.assertIn(f"'{kind}'", source)

    def test_the_scanner_release_is_part_of_the_decision_identity(self) -> None:
        # Sin la version del escaner en la clave, revisar una decision con un
        # escaner nuevo exigiria borrar la anterior.
        self.assertTrue(jobs.SCANNER_RELEASE)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'uq_promotion_decision'")
                definition = cursor.fetchone()[0]
        self.assertIn("scanner_release", definition)


if __name__ == "__main__":
    unittest.main()
