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
# asi que reutilizar los mismos bytes haria que la segunda ejecucion viera todo
# como «ya presente» y las pruebas de primera entrega dejarian de morder.
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
        ensure_buckets(settings)
        cls.created: set[str] = set()
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
                    cursor.execute(
                        "DELETE FROM fincilia.processing_run WHERE artifact_id IN ("
                        "SELECT artifact_id FROM fincilia.source_artifact "
                        "WHERE content_sha256 = ANY(%s))", (list(cls.created),))
                    cursor.execute(
                        "DELETE FROM fincilia.source_artifact WHERE content_sha256 = ANY(%s)",
                        (list(cls.created),))

    # ---------------------------------------------------------------- helpers #

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def upload(self, username: str, company_id: str, payload: bytes, filename: str):
        if payload:
            type(self).created.add(sha256_bytes(payload))
        return self.client.post(
            f"/api/v1/companies/{company_id}/documents",
            headers=self.auth(username),
            files={"file": (filename, io.BytesIO(payload), "application/octet-stream")})

    # ------------------------------------------------------------- recorrido #

    def test_a_synthetic_csv_lands_in_raw(self) -> None:
        payload = unique_csv("raw")
        response = self.upload("ana@demo.local", ESPIGA, payload, "extracto.csv")
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("raw", body["zone"])
        self.assertEqual("stored", body["status"])
        self.assertEqual("text/csv", body["media_type"])
        self.assertEqual(sha256_bytes(payload), body["content_sha256"])
        self.assertEqual(len(payload), body["byte_size"])
        self.assertEqual([], body["findings"])

    def test_the_same_bytes_twice_are_one_delivery(self) -> None:
        payload = unique_csv("idempotencia")
        first = self.upload("ana@demo.local", ESPIGA, payload, "extracto.csv").json()
        second = self.upload("ana@demo.local", ESPIGA, payload, "otro-nombre.csv").json()
        self.assertEqual(first["artifact_id"], second["artifact_id"])
        self.assertFalse(first["already_present"])
        self.assertTrue(second["already_present"])

    def test_one_changed_byte_is_another_delivery(self) -> None:
        first = self.upload("ana@demo.local", ESPIGA, unique_csv("a"), "e.csv").json()
        second = self.upload("ana@demo.local", ESPIGA, unique_csv("b"), "e.csv").json()
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_a_file_with_a_card_stays_in_quarantine(self) -> None:
        body = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()
        self.assertEqual("quarantine", body["zone"])
        self.assertEqual("quarantined", body["status"])
        self.assertIn("payment_card_number", [item["kind"] for item in body["findings"]])
        # El hallazgo dice donde, nunca que.
        self.assertNotIn("4111111111111111", str(body))

    def test_a_quarantined_file_is_not_queued_for_processing(self) -> None:
        body = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{body['artifact_id']}",
            headers=self.auth("ana@demo.local")).json()
        self.assertEqual([], detail["runs"])

    def test_a_clean_file_is_queued_once(self) -> None:
        body = self.upload("ana@demo.local", ESPIGA, unique_csv("cola"), "e.csv").json()
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{body['artifact_id']}",
            headers=self.auth("ana@demo.local")).json()
        self.assertEqual(1, len(detail["runs"]))
        self.assertEqual("queued", detail["runs"][0]["status"])
        self.assertEqual("profile", detail["runs"][0]["kind"])

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
                        "DELETE FROM fincilia.source_artifact WHERE artifact_id = %s"):
                    with self.subTest(statement=statement.split()[0]):
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            cursor.execute(statement, (created["artifact_id"],))
                        connection.rollback()

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

    def test_the_object_really_is_in_the_zone_the_row_claims(self) -> None:
        from fincilia_platform.objects import S3ObjectStore, object_key
        store = S3ObjectStore(build_settings())
        clean = self.upload("ana@demo.local", ESPIGA, unique_csv("zona"), "e.csv").json()
        dirty = self.upload("ana@demo.local", ESPIGA, CARD_CSV, "clientes.csv").json()

        clean_key = object_key(ESPIGA, clean["content_sha256"])
        dirty_key = object_key(ESPIGA, dirty["content_sha256"])
        self.assertTrue(store.exists("raw", clean_key))
        self.assertFalse(store.exists("quarantine", clean_key))
        self.assertTrue(store.exists("quarantine", dirty_key))
        # Lo que quedo en cuarentena **no** esta en raw: si estuviera, el escaner
        # habria servido para nada.
        self.assertFalse(store.exists("raw", dirty_key))

    def test_the_stored_bytes_are_the_bytes_that_were_uploaded(self) -> None:
        from fincilia_platform.objects import S3ObjectStore, object_key
        store = S3ObjectStore(build_settings())
        payload = unique_csv("bytes")
        created = self.upload("ana@demo.local", ESPIGA, payload, "e.csv").json()
        self.assertEqual(payload,
                         store.get("raw", object_key(ESPIGA, created["content_sha256"])))


if __name__ == "__main__":
    unittest.main()
