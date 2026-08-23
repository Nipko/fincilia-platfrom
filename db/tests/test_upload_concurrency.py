"""Idempotencia de la subida bajo concurrencia real.

No se simula la concurrencia con turnos: se lanzan hilos que suben **los mismos
bytes a la vez** contra la misma base. Una comprobacion previa del tipo «¿ya
existe?» pasa cualquier prueba secuencial y falla exactamente aqui, que es donde
importa: dos peticiones simultaneas o crean dos filas o una responde 500.

Tambien se comprueba lo que pasa cuando una de las dos escrituras falla. Una
subida toca dos sistemas, y entre ellos hay una ventana; lo que no puede pasar es
que el resultado se declare correcto cuando no lo es.
"""

from __future__ import annotations

import io
import threading
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_platform.objects import S3ObjectStore, object_key
from fincilia_platform.probes import ensure_buckets

RUN = uuid.uuid4().hex[:12]
SANDBOX_A = stable_id("company", "sandbox_a")
SANDBOX_B = stable_id("company", "sandbox_b")
ESPIGA = stable_id("company", "espiga")

CONCURRENT_UPLOADS = 16


def csv_for(marker: str) -> bytes:
    return (f"fecha,descripcion,valor,moneda\n"
            f"2026-01-02,Concurrencia {RUN}-{marker},-1250.00,COP\n").encode("utf-8")


class ConcurrentUploadTests(unittest.TestCase):
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
                for company in (ESPIGA, SANDBOX_A, SANDBOX_B):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    for statement in (
                            "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN ("
                            " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                            "  SELECT artifact_id FROM fincilia.source_artifact "
                            "  WHERE content_sha256 = ANY(%s)))",
                            "DELETE FROM fincilia.run_attempt WHERE run_id IN ("
                            " SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                            "  SELECT artifact_id FROM fincilia.source_artifact "
                            "  WHERE content_sha256 = ANY(%s)))",
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
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["token"]

    def upload(self, payload: bytes, filename: str = "e.csv",
               company: str = ESPIGA, token: str | None = None):
        type(self).created.add(sha256_bytes(payload))
        return self.client.post(
            f"/api/v1/companies/{company}/documents",
            headers={"Authorization": f"Bearer {token or self.token()}"},
            files={"file": (filename, io.BytesIO(payload), "application/octet-stream")})

    def artifact_count(self, digest: str, company: str = ESPIGA) -> int:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (company,))
                cursor.execute("SELECT count(*) FROM fincilia.source_artifact "
                               "WHERE content_sha256 = %s", (digest,))
                return cursor.fetchone()[0]

    def run_count(self, digest: str, company: str = ESPIGA) -> int:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (company,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.processing_run r "
                    "JOIN fincilia.source_artifact a ON a.artifact_id = r.artifact_id "
                    "WHERE a.content_sha256 = %s", (digest,))
                return cursor.fetchone()[0]

    # ------------------------------------------------------------ concurrencia #

    def test_sixteen_simultaneous_uploads_are_one_delivery(self) -> None:
        payload = csv_for("simultaneas")
        token = self.token()
        results: list = []
        barrier = threading.Barrier(CONCURRENT_UPLOADS)
        lock = threading.Lock()

        def attempt() -> None:
            # La barrera es lo que hace la prueba: sin ella los hilos se
            # serializan solos y no se prueba nada.
            barrier.wait()
            response = self.upload(payload, token=token)
            with lock:
                results.append((response.status_code, response.json()))

        threads = [threading.Thread(target=attempt) for _ in range(CONCURRENT_UPLOADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(CONCURRENT_UPLOADS, len(results))
        codes = {code for code, _ in results}
        self.assertEqual({200}, codes, f"every upload must answer 200, saw {codes}")

        identifiers = {body["artifact_id"] for _, body in results}
        self.assertEqual(1, len(identifiers), "the same bytes are one artifact")

        digest = sha256_bytes(payload)
        self.assertEqual(1, self.artifact_count(digest), "exactly one row")
        self.assertEqual(1, self.run_count(digest), "exactly one processing run")

        firsts = [body for _, body in results if not body["already_present"]]
        self.assertEqual(1, len(firsts), "exactly one upload is the first delivery")

    def test_the_object_is_written_once_and_matches_the_bytes(self) -> None:
        payload = csv_for("objeto")
        body = self.upload(payload).json()
        key = object_key(ESPIGA, body["content_sha256"])
        self.assertTrue(self.store.exists(body["zone"], key))
        self.assertEqual(payload, self.store.get(body["zone"], key))
        # Reescribir la misma clave con los mismos bytes es inocuo: la clave sale
        # del contenido, asi que una subida concurrente no puede pisar otra cosa.
        again = self.upload(payload).json()
        self.assertTrue(again["already_present"])
        self.assertEqual(payload, self.store.get(body["zone"], key))

    def test_the_same_bytes_in_two_companies_are_two_artifacts(self) -> None:
        payload = csv_for("dos-empresas")
        # Ana tiene concesion sobre las dos empresas de demo.
        first = self.upload(payload, company=ESPIGA).json()
        andinos = stable_id("company", "andinos")
        second = self.upload(payload, company=andinos).json()
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertEqual(1, self.artifact_count(first["content_sha256"], ESPIGA))
        self.assertEqual(1, self.artifact_count(first["content_sha256"], andinos))

    def test_one_changed_byte_is_a_different_artifact(self) -> None:
        first = self.upload(csv_for("byte-a")).json()
        second = self.upload(csv_for("byte-b")).json()
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_a_duplicate_is_audited_as_a_duplicate(self) -> None:
        payload = csv_for("auditoria")
        created = self.upload(payload).json()
        self.upload(payload)
        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=200",
                                 headers={"Authorization": f"Bearer {self.token('sofia@demo.local')}"}).json()
        results = [event["detail"].get("result") for event in events
                   if event["action"] == "document.upload"
                   and event["resource_ref"] == created["artifact_id"]]
        # Contar una entrega repetida igual que una nueva haria imposible saber si
        # alguien reintenta o si algo se esta duplicando.
        self.assertIn("created", results)
        self.assertIn("duplicate", results)

    def test_a_failing_object_store_publishes_nothing(self) -> None:
        # Si el almacen falla no hay evidencia que procesar. Lo que no puede pasar
        # es que la fila exista igualmente y el trabajo se encole.
        payload = csv_for("almacen-caido")
        digest = sha256_bytes(payload)

        class Broken:
            def put(self, *args, **kwargs):
                from fincilia_platform.objects import ObjectStoreError
                raise ObjectStoreError("simulated outage")

        original = self.client.app.state.object_store
        self.client.app.state.object_store = Broken()
        try:
            response = self.upload(payload)
        finally:
            self.client.app.state.object_store = original
        self.assertEqual(503, response.status_code)
        self.assertEqual(0, self.artifact_count(digest))
        self.assertEqual(0, self.run_count(digest))

    def test_the_upload_recovers_after_the_store_comes_back(self) -> None:
        payload = csv_for("reintento")

        class Broken:
            def put(self, *args, **kwargs):
                from fincilia_platform.objects import ObjectStoreError
                raise ObjectStoreError("simulated outage")

        original = self.client.app.state.object_store
        self.client.app.state.object_store = Broken()
        try:
            self.assertEqual(503, self.upload(payload).status_code)
        finally:
            self.client.app.state.object_store = original
        # El mismo fichero, sin cambiar nada: la subida se completa.
        body = self.upload(payload).json()
        self.assertFalse(body["already_present"])
        self.assertEqual(1, self.artifact_count(body["content_sha256"]))


    # ------------------------------------------------------------ reconciliar #

    def test_the_reconciler_finds_a_row_whose_object_is_missing(self) -> None:
        from db.reconcile.objects import reconcile
        # Lo que deja una caida entre escribir el objeto y registrar la fila,
        # visto del otro lado: la fila existe y el objeto no.
        artifact_id = str(uuid.uuid4())
        digest = uuid.uuid4().hex + uuid.uuid4().hex
        type(self).created.add(digest)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (SANDBOX_A,))
                cursor.execute(
                    "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                    "filename, byte_size, content_sha256, media_type, zone, object_key, "
                    "status, uploaded_by) VALUES (%s, %s, 'perdido.csv', 10, %s, "
                    "'text/csv', 'raw', %s, 'stored', %s)",
                    (artifact_id, SANDBOX_A, digest, f"company/{SANDBOX_A}/zz/{digest}",
                     stable_id("subject", "ana")))

        report = reconcile(MIGRATOR_DSN, self.settings, scope=[SANDBOX_A])
        missing = [item["artifact_id"] for item in report["rows_without_objects"]]
        self.assertIn(artifact_id, missing)
        # Una fila sin su evidencia no es un estado correcto, y no se declara asi.
        self.assertFalse(report["ok"])

    def test_the_reconciler_never_reports_ok_without_looking(self) -> None:
        from db.reconcile.objects import reconcile
        # Un informe vacio en verde diria que esta bien tras no mirar nada.
        report = reconcile(MIGRATOR_DSN, self.settings, scope=[])
        if not report["companies"]:
            self.assertFalse(report["ok"])
            self.assertIn("scope", report["error"])

    def test_the_reconciler_is_idempotent(self) -> None:
        from db.reconcile.objects import reconcile
        first = reconcile(MIGRATOR_DSN, self.settings, scope=[ESPIGA])
        second = reconcile(MIGRATOR_DSN, self.settings, scope=[ESPIGA])
        self.assertEqual(first["rows_without_objects"], second["rows_without_objects"])
        self.assertEqual(first["repaired"], second["repaired"])

    def test_the_reconciler_requeues_an_artifact_left_without_work(self) -> None:
        from db.reconcile.objects import reconcile
        payload = csv_for("sin-trabajo")
        body = self.upload(payload).json()
        # Se borra el trabajo, dejando el artefacto promovido y sin cola: el
        # residuo de una caida entre registrar y encolar.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN "
                    "(SELECT run_id FROM fincilia.processing_run WHERE artifact_id = %s)",
                    (body["artifact_id"],))
                cursor.execute(
                    "DELETE FROM fincilia.run_attempt WHERE run_id IN "
                    "(SELECT run_id FROM fincilia.processing_run WHERE artifact_id = %s)",
                    (body["artifact_id"],))
                cursor.execute("DELETE FROM fincilia.processing_run WHERE artifact_id = %s",
                               (body["artifact_id"],))
        report = reconcile(MIGRATOR_DSN, self.settings, scope=[ESPIGA], do_repair=True)
        repaired = [item["artifact_id"] for item in report["repaired"]]
        self.assertIn(body["artifact_id"], repaired)
        self.assertEqual(1, self.run_count(body["content_sha256"]))
        self.assertEqual(["scan"], [item["kind"] for item in report["repaired"]
                                    if item["artifact_id"] == body["artifact_id"]])


if __name__ == "__main__":
    unittest.main()
