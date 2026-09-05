"""FNC-ING-007 contra PostgreSQL real con roles y RLS reales."""

from __future__ import annotations

import json
import os
import unittest
import uuid

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN

WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")
ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")
ANA = stable_id("subject", "ana")


class PdfOcrPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN or not WORKER_DSN:
            raise unittest.SkipTest("migrator, app and worker DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)

    def setUp(self) -> None:
        self.artifact = str(uuid.uuid4())
        self.scan_run = str(uuid.uuid4())
        self.extract_run = str(uuid.uuid4())
        self.source_sha = uuid.uuid4().hex * 2
        self.derived_sha = uuid.uuid4().hex * 2
        self.source_key = (
            f"company/{ESPIGA}/{self.source_sha[:2]}/{self.source_sha}")
        self.release = "tesseract-5.5.1/pdfium-5.13.0/fincilia-ocr-1"
        self.key = (
            f"company/{ESPIGA}/{self.derived_sha[:2]}/{self.derived_sha}.ocr.json")
        with psycopg.connect(MIGRATOR_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            connection.execute(
                "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                "filename, byte_size, content_sha256, media_type, zone, status, "
                "object_key, uploaded_by) VALUES (%s, %s, 'scan-sintetico.pdf', "
                "100, %s, 'application/pdf', 'raw', 'stored', %s, %s)",
                (self.artifact, ESPIGA, self.source_sha, self.source_key, ANA))
            for run_id, kind in ((self.scan_run, "scan"),
                                 (self.extract_run, "extract")):
                connection.execute(
                    "INSERT INTO fincilia.processing_run (run_id, company_id, "
                    "artifact_id, kind, status, started_at, finished_at) "
                    "VALUES (%s, %s, %s, %s, 'succeeded', clock_timestamp(), "
                    "clock_timestamp())",
                    (run_id, ESPIGA, self.artifact, kind))

    def tearDown(self) -> None:
        with psycopg.connect(MIGRATOR_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            connection.execute(
                "DELETE FROM fincilia.raw_record WHERE artifact_id = %s",
                (self.artifact,))
            connection.execute(
                "DELETE FROM fincilia.pdf_ocr_result WHERE artifact_id = %s",
                (self.artifact,))
            connection.execute(
                "DELETE FROM fincilia.processing_run WHERE artifact_id = %s",
                (self.artifact,))
            connection.execute(
                "DELETE FROM fincilia.source_artifact WHERE artifact_id = %s",
                (self.artifact,))

    def _insert_as_worker(self) -> None:
        with psycopg.connect(WORKER_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            connection.execute(
                "INSERT INTO fincilia.pdf_ocr_result (ocr_result_id, company_id, "
                "artifact_id, scan_run_id, source_sha256, derived_object_key, "
                "derived_sha256, ocr_release, language_set, page_count, block_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 2)",
                (str(uuid.uuid4()), ESPIGA, self.artifact, self.scan_run,
                 self.source_sha, self.key, self.derived_sha, self.release,
                 ["spa", "eng"]))

    def test_worker_can_insert_exact_metadata_but_runtime_cannot_read_it(self) -> None:
        self._insert_as_worker()
        with psycopg.connect(WORKER_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            row = connection.execute(
                "SELECT source_sha256, derived_sha256, page_count, block_count, "
                "requires_human_review FROM fincilia.pdf_ocr_result "
                "WHERE artifact_id = %s", (self.artifact,)).fetchone()
        self.assertEqual((self.source_sha, self.derived_sha, 1, 2, True), row)
        with psycopg.connect(RUNTIME_DSN) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("SELECT * FROM fincilia.pdf_ocr_result")

    def test_rls_and_exact_foreign_keys_reject_cross_company_or_wrong_run(self) -> None:
        with psycopg.connect(WORKER_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ANDINOS,))
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute(
                    "INSERT INTO fincilia.pdf_ocr_result (ocr_result_id, company_id, "
                    "artifact_id, scan_run_id, source_sha256, derived_object_key, "
                    "derived_sha256, ocr_release, language_set, page_count, block_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ARRAY['spa'], 1, 1)",
                    (str(uuid.uuid4()), ESPIGA, self.artifact, self.scan_run,
                     self.source_sha, self.key, self.derived_sha, self.release))

        with psycopg.connect(WORKER_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                connection.execute(
                    "INSERT INTO fincilia.pdf_ocr_result (ocr_result_id, company_id, "
                    "artifact_id, scan_run_id, source_sha256, derived_object_key, "
                    "derived_sha256, ocr_release, language_set, page_count, block_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ARRAY['spa'], 1, 1)",
                    (str(uuid.uuid4()), ESPIGA, self.artifact, self.extract_run,
                     self.source_sha, self.key, self.derived_sha, self.release))

    def test_ocr_locator_is_typed_and_requires_release_and_exact_ordinal(self) -> None:
        locator = {
            "locator_kind": "pdf_ocr",
            "artifact_sha256": self.source_sha,
            "record_ordinal": 1,
            "field_count": 1,
            "page_number": 1,
            "block_ordinal": 1,
            "bbox": [0.1, 0.2, 0.8, 0.3],
            "confidence": 0.91,
            "ocr_release": self.release,
        }
        with psycopg.connect(MIGRATOR_DSN) as connection:
            connection.execute(
                "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
            connection.execute(
                "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                "artifact_id, processing_run_id, record_ordinal, origin_locator, "
                "raw_values, values_digest) VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
                (str(uuid.uuid4()), ESPIGA, self.artifact, self.extract_run,
                 json.dumps(locator), json.dumps(["Texto sintetico"]),
                 uuid.uuid4().hex * 2))
            for candidate in (
                    {key: value for key, value in locator.items()
                     if key != "ocr_release"},
                    {**locator, "record_ordinal": 2},
                    {**locator, "page_number": 51}):
                with self.subTest(candidate=candidate):
                    with self.assertRaises(psycopg.errors.CheckViolation):
                        with connection.transaction():
                            connection.execute(
                                "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                                "artifact_id, processing_run_id, record_ordinal, "
                                "origin_locator, raw_values, values_digest) "
                                "VALUES (%s, %s, %s, %s, 3, %s, %s, %s)",
                                (str(uuid.uuid4()), ESPIGA, self.artifact,
                                 self.extract_run, json.dumps(candidate),
                                 json.dumps(["Texto sintetico"]), uuid.uuid4().hex * 2))

    def test_database_metadata_has_no_text_or_payload_column(self) -> None:
        with psycopg.connect(MIGRATOR_DSN) as connection:
            columns = {row[0] for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'fincilia' AND table_name = 'pdf_ocr_result'")}
        self.assertTrue({"derived_object_key", "derived_sha256"} <= columns)
        self.assertFalse({"text", "payload", "raw_values"} & columns)


if __name__ == "__main__":
    unittest.main()
