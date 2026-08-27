"""Subida de documentos, de extremo a extremo, contra PostgreSQL y MinIO reales.

Lo que se comprueba aqui no se puede comprobar con dobles: que el objeto acabe en
la zona que dice la fila, que la fila sea inmutable de verdad porque el rol no
tiene el privilegio, y que dos empresas no se vean los ficheros. Un doble del
almacen diria que si a todo.
"""

from __future__ import annotations

import io
import unittest
import uuid
import zipfile

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import (ANDINOS, ESPIGA, MIGRATOR_DSN,
                                             RUNTIME_DSN, build_settings)
from fastapi.testclient import TestClient
from fincilia_api.main import create_app
from fincilia_contracts.ingestion import sha256_bytes
from fincilia_platform.probes import ensure_buckets

# Cada ejecucion siembra bytes distintos: la subida es idempotente por contenido,
# asi que reutilizar los mismos bytes haria que la segunda ejecucion lo viera
# entero como «ya presente» y las pruebas de primera entrega dejarian de morder.
RUN = uuid.uuid4().hex[:12]

CLEAN_CSV = (b"fecha,descripcion,valor,moneda\n"
             b"2026-01-02,Pago proveedor,-125000.00,COP\n"
             b"2026-01-03,Cobro cliente,340000.00,COP\n")
CARD_CSV = (b"cliente,medio,valor\n"
            b"Cliente Sintetico,4111111111111111,120000.00\n")


def unique_csv(marker: str) -> bytes:
    return CLEAN_CSV + f"2026-01-04,Ajuste {RUN}-{marker},1.00,COP\n".encode("utf-8")


class DocumentUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        settings = build_settings()
        # Las zonas de evidencia las crea la API al arrancar, pero solo en `local`.
        # Aqui el entorno es `test`, asi que las pruebas se las crean ellas.
        #
        # Si el almacen de objetos no esta arriba, el fallo nativo es una traza de
        # botocore que no dice que falta levantar un servicio. Se traduce a un
        # mensaje que nombra la dependencia: quien lea el log de CI tiene que
        # saber en una linea que arreglar. `tools/local_stack` comprueba ademas,
        # de forma estatica, que ningun paso de CI llegue hasta aqui sin ella.
        try:
            ensure_buckets(settings)
        except Exception as error:  # noqa: BLE001 - el motivo importa mas que el tipo
            raise AssertionError(
                "these tests need the object store: start it with "
                "`docker compose up -d --wait objectstore` "
                f"({type(error).__name__})") from error
        cls.created: set[str] = set()
        cls.created_sources: set[tuple[str, str]] = set()
        cls.client = TestClient(create_app(settings))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        # Las pruebas no dejan documentos en la demo. Los objetos de MinIO se
        # quedan: son inmutables por diseno y borrarlos exigiria un privilegio
        # que el runtime no tiene ni debe tener.
        if not cls.created:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    # El puntero referencia al trabajo: borrar en el otro orden
                    # choca con la clave ajena, y ponerle `ON DELETE CASCADE`
                    # dejaria que borrar un trabajo se llevara por delante estado
                    # de cola sin decirlo.
                    cursor.execute(
                        "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN ("
                        "SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s)))", (list(cls.created),))
                    cursor.execute(
                        "DELETE FROM fincilia.run_attempt WHERE run_id IN ("
                        "SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s)))", (list(cls.created),))
                    cursor.execute(
                        "DELETE FROM fincilia.dead_letter_item WHERE work_id IN ("
                        "SELECT run_id FROM fincilia.processing_run WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s)))", (list(cls.created),))
                    # La extraccion escribe filas que referencian al trabajo.
                    # Aqui no corre el worker, pero el orden tiene que aguantar
                    # que alguien lo haga correr manana.
                    cursor.execute(
                        "DELETE FROM fincilia.raw_record WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s))", (list(cls.created),))
                    cursor.execute(
                        "DELETE FROM fincilia.processing_run WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s))", (list(cls.created),))
                    # La decision de promocion referencia al artefacto: borrar en
                    # el otro orden choca con la clave ajena.
                    cursor.execute(
                        "DELETE FROM fincilia.promotion_decision WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s))", (list(cls.created),))
                    cursor.execute(
                        "DELETE FROM fincilia.source_artifact WHERE content_sha256 = ANY(%s)",
                        (list(cls.created),))
                for company, source_id in cls.created_sources:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,))
                    cursor.execute(
                        "DELETE FROM fincilia.data_source WHERE data_source_id = %s",
                        (source_id,))

    # ---------------------------------------------------------------- helpers #

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def upload(self, username: str, company_id: str, payload: bytes, filename: str,
               *, source_id: str | None = None):
        if payload:
            type(self).created.add(sha256_bytes(payload))
        source_key = "andinos" if company_id == ANDINOS else "espiga"
        return self.client.post(
            f"/api/v1/companies/{company_id}/documents",
            params={"data_source_id": source_id or
                    stable_id("data_source", source_key)},
            headers=self.auth(username),
            files={"file": (filename, io.BytesIO(payload), "application/octet-stream")})

    def create_source(self, company_id: str, *, status: str = "active") -> str:
        source_id = str(uuid.uuid4())
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (company_id,))
                cursor.execute(
                    "INSERT INTO fincilia.data_source (data_source_id, company_id, "
                    "source_family, display_name, status, closed_reason) "
                    "VALUES (%s, %s, 'bank_account', %s, %s, %s)",
                    (source_id, company_id, f"Fuente sintetica {source_id[:8]}",
                     status, "SYNTHETIC-TEST" if status != "active" else None))
        type(self).created_sources.add((company_id, source_id))
        return source_id

    # ------------------------------------------------------------- recorrido #

    def test_a_synthetic_csv_lands_in_quarantine(self) -> None:
        # La subida no promueve nada: eso lo decide el escaneo, despues, y con el
        # contenido leido entero.
        payload = unique_csv("raw")
        response = self.upload("ana@demo.local", ESPIGA, payload, "extracto.csv")
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("quarantine", body["zone"])
        self.assertEqual("quarantined", body["status"])
        self.assertEqual("text/csv", body["media_type"])
        self.assertEqual(sha256_bytes(payload), body["content_sha256"])
        self.assertEqual(len(payload), body["byte_size"])
        self.assertEqual([], body["findings"])
        self.assertEqual(stable_id("data_source", "espiga"),
                         body["data_source_id"])

    def test_a_source_is_required_before_bytes_are_stored(self) -> None:
        from fincilia_platform.objects import S3ObjectStore, object_key
        payload = unique_csv("sin-fuente")
        digest = sha256_bytes(payload)
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents",
            headers=self.auth("ana@demo.local"),
            files={"file": ("sin-fuente.csv", io.BytesIO(payload), "text/csv")})
        self.assertEqual(422, response.status_code, response.text)
        self.assertFalse(S3ObjectStore(build_settings()).exists(
            "quarantine", object_key(ESPIGA, digest)))

    def test_a_source_from_another_company_is_neutral_and_writes_nothing(self) -> None:
        payload = unique_csv("fuente-ajena")
        response = self.upload(
            "ana@demo.local", ESPIGA, payload, "ajena.csv",
            source_id=stable_id("data_source", "andinos"))
        self.assertEqual(403, response.status_code, response.text)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.source_artifact "
                    "WHERE content_sha256 = %s", (sha256_bytes(payload),))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_an_inactive_source_is_rejected_before_storage(self) -> None:
        source_id = self.create_source(ESPIGA, status="suspended")
        response = self.upload(
            "ana@demo.local", ESPIGA, unique_csv("fuente-inactiva"),
            "inactiva.csv", source_id=source_id)
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual("source-inactive", response.json()["type"].rsplit("/", 1)[-1])

    def test_the_same_bytes_twice_are_one_delivery(self) -> None:
        payload = unique_csv("idempotencia")
        first = self.upload("ana@demo.local", ESPIGA, payload, "extracto.csv").json()
        second = self.upload("ana@demo.local", ESPIGA, payload, "otro-nombre.csv").json()
        self.assertEqual(first["artifact_id"], second["artifact_id"])
        self.assertFalse(first["already_present"])
        self.assertTrue(second["already_present"])

    def test_the_same_bytes_from_two_sources_are_two_logical_deliveries(self) -> None:
        payload = unique_csv("dos-fuentes")
        other_source = self.create_source(ESPIGA)
        first = self.upload(
            "ana@demo.local", ESPIGA, payload, "primera.csv").json()
        second = self.upload(
            "ana@demo.local", ESPIGA, payload, "segunda.csv",
            source_id=other_source).json()
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertEqual(other_source, second["data_source_id"])
        self.assertFalse(second["already_present"])

    def test_document_history_is_source_bound_filtered_and_keyset_paginated(self) -> None:
        source_id = stable_id("data_source", "espiga")
        marker = uuid.uuid4().hex[:12]
        created_ids: list[str] = []
        for ordinal in range(3):
            response = self.upload(
                "ana@demo.local", ESPIGA,
                unique_csv(f"historial-{marker}-{ordinal}"),
                f"ciclo-{marker}-{ordinal}.csv", source_id=source_id)
            self.assertEqual(200, response.status_code, response.text)
            created_ids.append(response.json()["artifact_id"])

        headers = self.auth("ana@demo.local")
        first = self.client.get(
            f"/api/v1/companies/{ESPIGA}/document-history",
            params={"limit": 2, "data_source_id": source_id,
                    "filename": marker}, headers=headers)
        self.assertEqual(200, first.status_code, first.text)
        page_one = first.json()
        self.assertEqual(3, page_one["summary"]["total"])
        self.assertEqual(2, len(page_one["items"]))
        self.assertTrue(page_one["has_next"])
        self.assertFalse(page_one["has_previous"])
        self.assertIsNotNone(page_one["next_cursor"])
        for item in page_one["items"]:
            self.assertEqual(source_id, item["data_source_id"])
            self.assertIn(marker, item["filename"])
            self.assertEqual("Extracto bancario (demo)", item["source_name"])
            self.assertNotIn("object_key", item)
            self.assertNotIn("findings", item)
            self.assertNotIn("uploaded_by", item)

        second = self.client.get(
            f"/api/v1/companies/{ESPIGA}/document-history",
            params={"limit": 2, "data_source_id": source_id,
                    "filename": marker, "cursor": page_one["next_cursor"],
                    "direction": "next"}, headers=headers)
        self.assertEqual(200, second.status_code, second.text)
        page_two = second.json()
        self.assertEqual(1, len(page_two["items"]))
        self.assertFalse(page_two["has_next"])
        self.assertTrue(page_two["has_previous"])
        self.assertEqual(set(created_ids), {
            item["artifact_id"] for item in page_one["items"] + page_two["items"]
        })

        previous = self.client.get(
            f"/api/v1/companies/{ESPIGA}/document-history",
            params={"limit": 2, "data_source_id": source_id,
                    "filename": marker,
                    "cursor": page_two["previous_cursor"],
                    "direction": "previous"}, headers=headers)
        self.assertEqual(200, previous.status_code, previous.text)
        self.assertEqual(
            [item["artifact_id"] for item in page_one["items"]],
            [item["artifact_id"] for item in previous.json()["items"]])

    def test_document_history_keeps_legacy_source_unknown(self) -> None:
        digest = sha256_bytes(unique_csv("legacy-historico"))
        type(self).created.add(digest)
        artifact_id = str(uuid.uuid4())
        filename = f"legacy-{uuid.uuid4().hex[:10]}.csv"
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (ESPIGA,))
                cursor.execute(
                    "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                    "filename, byte_size, content_sha256, media_type, zone, "
                    "object_key, status, uploaded_by) VALUES "
                    "(%s, %s, %s, 10, %s, 'text/csv', 'quarantine', %s, "
                    "'quarantined', %s)",
                    (artifact_id, ESPIGA, filename, digest,
                     f"legacy/{artifact_id}", stable_id("subject", "ana")))

        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/document-history",
            params={"filename": filename, "processing_status": "not_started",
                    "zone": "quarantine"},
            headers=self.auth("ana@demo.local"))
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(1, body["summary"]["legacy_unattributed"])
        self.assertEqual(artifact_id, body["items"][0]["artifact_id"])
        self.assertIsNone(body["items"][0]["data_source_id"])
        self.assertEqual("Fuente historica no registrada",
                         body["items"][0]["source_name"])

    def test_document_history_rejects_bad_filters_without_enumeration(self) -> None:
        headers = self.auth("ana@demo.local")
        endpoint = f"/api/v1/companies/{ESPIGA}/document-history"
        for params in (
                {"cursor": "esto-no-es-un-cursor"},
                {"direction": "sideways"},
                {"zone": "object-store"},
                {"processing_status": "cancelled"},
                {"filename": "linea\ninyectada"}):
            with self.subTest(params=params):
                response = self.client.get(endpoint, params=params, headers=headers)
                self.assertEqual(422, response.status_code, response.text)
        foreign = self.client.get(
            endpoint,
            params={"data_source_id": stable_id("data_source", "andinos")},
            headers=headers)
        self.assertEqual(403, foreign.status_code, foreign.text)

    def test_one_changed_byte_is_another_delivery(self) -> None:
        first = self.upload("ana@demo.local", ESPIGA, unique_csv("a"), "e.csv").json()
        second = self.upload("ana@demo.local", ESPIGA, unique_csv("b"), "e.csv").json()
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_a_file_with_a_card_stays_in_quarantine(self) -> None:
        # En la puerta todavia no se ha escaneado nada; lo que se comprueba aqui es
        # que aterriza en cuarentena y que la respuesta no repite el valor. Que el
        # escaneo lo marque como sensible se prueba en
        # `test_quarantine_before_raw`.
        body = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()
        self.assertEqual("quarantine", body["zone"])
        self.assertEqual("quarantined", body["status"])
        self.assertNotIn("4111111111111111", str(body))

    def test_nothing_is_queued_for_profiling_before_it_is_scanned(self) -> None:
        # Lo que se encola en la puerta es el escaneo. Perfilar es leer el fichero
        # entero, y eso no se hace sobre algo que no ha pasado inspeccion.
        body = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{body['artifact_id']}",
            headers=self.auth("ana@demo.local")).json()
        self.assertEqual(["scan"], [run["kind"] for run in detail["runs"]])

    def test_a_clean_file_is_queued_once(self) -> None:
        body = self.upload("ana@demo.local", ESPIGA, unique_csv("cola"), "e.csv").json()
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{body['artifact_id']}",
            headers=self.auth("ana@demo.local")).json()
        # Exactamente un trabajo en la puerta, y de escaneo. En que estado esta
        # depende de si el worker ya lo tomo, y afirmar `queued` haria que la
        # prueba fallara solo porque el worker fue rapido.
        scans = [run for run in detail["runs"] if run["kind"] == "scan"]
        self.assertEqual(1, len(scans))
        self.assertIn(scans[0]["status"], {"queued", "running", "succeeded"})

    def test_a_renamed_executable_is_refused(self) -> None:
        response = self.upload("ana@demo.local", ESPIGA,
                               b"MZ\x90\x00" + b"\x00" * 512, "extracto.csv")
        self.assertEqual(415, response.status_code)
        self.assertEqual("application/problem+json",
                         response.headers["content-type"].split(";")[0])

    def test_a_zip_bomb_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("grande.csv", b"0" * (4 * 1024 * 1024))
        self.assertEqual(415, self.upload("ana@demo.local", ESPIGA, buffer.getvalue(),
                                          "libro.xlsx").status_code)

    def test_an_empty_file_is_refused(self) -> None:
        self.assertEqual(415, self.upload("ana@demo.local", ESPIGA, b"", "v.csv").status_code)

    def test_a_refused_file_is_never_recorded(self) -> None:
        before = self.client.get(f"/api/v1/companies/{ESPIGA}/documents?limit=200",
                                 headers=self.auth("ana@demo.local")).json()
        self.upload("ana@demo.local", ESPIGA, b"\x7fELF\x02" + b"\x00" * 512, "x.csv")
        after = self.client.get(f"/api/v1/companies/{ESPIGA}/documents?limit=200",
                                headers=self.auth("ana@demo.local")).json()
        self.assertEqual(len(before), len(after))

    # ------------------------------------------------------------ permisos #

    def test_uploading_needs_the_upload_permission(self) -> None:
        # Carla es auditora en Andinos: lee, no sube.
        response = self.upload("carla@demo.local", ANDINOS, unique_csv("carla"), "e.csv")
        self.assertEqual(403, response.status_code)

    def test_uploading_into_another_company_is_denied(self) -> None:
        # Beto solo tiene concesion sobre Espiga.
        response = self.upload("beto@demo.local", ANDINOS, unique_csv("beto"), "e.csv")
        self.assertEqual(403, response.status_code)

    def test_documents_are_not_visible_across_companies(self) -> None:
        payload = unique_csv("aislamiento")
        created = self.upload("ana@demo.local", ESPIGA, payload, "solo-espiga.csv").json()
        listed = self.client.get(f"/api/v1/companies/{ANDINOS}/documents?limit=200",
                                 headers=self.auth("ana@demo.local")).json()
        self.assertNotIn(created["artifact_id"],
                         [item["artifact_id"] for item in listed])

    def test_reading_another_companys_document_by_id_is_denied(self) -> None:
        created = self.upload("ana@demo.local", ESPIGA, unique_csv("porid"), "e.csv").json()
        response = self.client.get(
            f"/api/v1/companies/{ANDINOS}/documents/{created['artifact_id']}",
            headers=self.auth("ana@demo.local"))
        self.assertEqual(403, response.status_code)

    def test_a_malformed_document_identifier_is_denied_not_crashed(self) -> None:
        for candidate in ("no-es-uuid", "../../etc/passwd", "0"):
            with self.subTest(candidate=candidate):
                response = self.client.get(
                    f"/api/v1/companies/{ESPIGA}/documents/{candidate}",
                    headers=self.auth("ana@demo.local"))
                self.assertIn(response.status_code, (403, 404))

    def test_the_upload_is_audited(self) -> None:
        created = self.upload("ana@demo.local", ESPIGA, unique_csv("auditoria"),
                              "e.csv").json()
        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=200",
                                 headers=self.auth("sofia@demo.local")).json()
        uploads = [item for item in events
                   if item["action"] == "document.upload"
                   and item["resource_ref"] == created["artifact_id"]]
        self.assertTrue(uploads, "an upload must leave a trace")
        self.assertEqual("allowed", uploads[0]["outcome"])

    # ------------------------------------------------------- inmutabilidad #

    def test_the_runtime_cannot_rewrite_an_artifact(self) -> None:
        created = self.upload("ana@demo.local", ESPIGA, unique_csv("inmutable"),
                              "e.csv").json()
        with psycopg.connect(RUNTIME_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                for statement in (
                        "UPDATE fincilia.source_artifact SET zone = 'raw' "
                        "WHERE artifact_id = %s",
                        "UPDATE fincilia.source_artifact SET data_source_id = NULL "
                        "WHERE artifact_id = %s",
                        "DELETE FROM fincilia.source_artifact WHERE artifact_id = %s"):
                    with self.subTest(statement=statement.split()[0]):
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            cursor.execute(statement, (created["artifact_id"],))
                        connection.rollback()

    def test_source_scoped_idempotency_indexes_replace_company_only_constraint(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'fincilia.source_artifact'::regclass "
                    "AND conname = 'uq_artifact_content'")
                self.assertIsNone(cursor.fetchone())
                cursor.execute(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = 'fincilia' AND tablename = 'source_artifact' "
                    "AND indexname IN ('uq_artifact_source_content', "
                    "'uq_artifact_legacy_content') ORDER BY indexname")
                indexes = dict(cursor.fetchall())
        self.assertEqual(
            {"uq_artifact_legacy_content", "uq_artifact_source_content"},
            set(indexes))
        self.assertIn("data_source_id", indexes["uq_artifact_source_content"])
        self.assertIn("WHERE (data_source_id IS NOT NULL)",
                      indexes["uq_artifact_source_content"])
        self.assertIn("WHERE (data_source_id IS NULL)",
                      indexes["uq_artifact_legacy_content"])

    def test_a_quarantined_artifact_cannot_claim_to_be_stored(self) -> None:
        # El CHECK acopla zona y estado: si pudieran discrepar, «esta en raw»
        # dejaria de significar «paso la admision».
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.CheckViolation):
                    cursor.execute(
                        "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                        "filename, byte_size, content_sha256, media_type, zone, "
                        "object_key, status, uploaded_by) VALUES "
                        "(gen_random_uuid(), %s, 'x.csv', 10, %s, 'text/csv', "
                        "'quarantine', 'k', 'stored', %s)",
                        (ESPIGA, "a" * 64, stable_id("subject", "ana")))

    def test_everything_lands_in_quarantine_and_nothing_in_raw(self) -> None:
        from fincilia_platform.objects import S3ObjectStore, object_key
        store = S3ObjectStore(build_settings())
        clean = self.upload("ana@demo.local", ESPIGA, unique_csv("zona"), "e.csv").json()
        dirty = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()

        for body in (clean, dirty):
            key = object_key(ESPIGA, body["content_sha256"])
            with self.subTest(name=body["filename"]):
                self.assertTrue(store.exists("quarantine", key))
                # Nada llega a la zona de evidencia en la propia subida: si
                # llegara, el escaneo posterior no serviria de nada.
                self.assertFalse(store.exists("raw", key))

    def test_the_stored_bytes_are_the_bytes_that_were_uploaded(self) -> None:
        from fincilia_platform.objects import S3ObjectStore, object_key
        store = S3ObjectStore(build_settings())
        payload = unique_csv("bytes")
        created = self.upload("ana@demo.local", ESPIGA, payload, "e.csv").json()
        self.assertEqual(
            payload,
            store.get("quarantine", object_key(ESPIGA, created["content_sha256"])))


if __name__ == "__main__":
    unittest.main()
