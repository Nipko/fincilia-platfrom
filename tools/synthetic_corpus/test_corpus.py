from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tools.synthetic_corpus.common import pretty_json_bytes, sha256_bytes, tracked_files
from tools.synthetic_corpus.generator import build_corpus, generate_corpus
from tools.synthetic_corpus.linter import lint_corpus, verify_corpus


class SyntheticCorpusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "corpus"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _generate(self) -> None:
        generate_corpus(self.root)

    def _manifest(self) -> dict:
        return json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def _write_manifest(self, manifest: dict) -> None:
        (self.root / "manifest.json").write_bytes(pretty_json_bytes(manifest))

    def test_same_seed_and_version_produce_identical_bytes(self) -> None:
        first = build_corpus()
        second = build_corpus()
        self.assertEqual(first, second)

    def test_generated_corpus_is_complete_and_reproducible(self) -> None:
        self._generate()
        report = verify_corpus(self.root)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(5, report.checked_files)
        self.assertGreaterEqual(len(report.warnings), 2)

    def test_manifest_contains_hash_and_provenance_for_every_fixture(self) -> None:
        self._generate()
        manifest = self._manifest()
        self.assertTrue(manifest["synthetic"])
        self.assertFalse(manifest["provenance"]["real_data_used"])
        self.assertEqual([], manifest["provenance"]["external_inputs"])
        self.assertEqual(
            set(tracked_files(self.root)) - {"manifest.json"},
            {entry["path"] for entry in manifest["files"]},
        )
        for entry in manifest["files"]:
            content = (self.root / entry["path"]).read_bytes()
            self.assertEqual(entry["sha256"], sha256_bytes(content))
            self.assertEqual(entry["bytes"], len(content))

    def test_settlement_equation_uses_exact_decimal_values(self) -> None:
        self._generate()
        text = (self.root / "files/payments_en_us.csv").read_text(encoding="utf-8")
        row = next(csv.DictReader(io.StringIO(text)))
        self.assertEqual(
            Decimal(row["net"]),
            Decimal(row["gross"]) - Decimal(row["fee"]) - Decimal(row["withholding"]),
        )

    def test_latin1_fixture_is_not_silently_treated_as_utf8(self) -> None:
        self._generate()
        content = (self.root / "files/ambiguous_es_mx_latin1.csv").read_bytes()
        with self.assertRaises(UnicodeDecodeError):
            content.decode("utf-8")
        self.assertIn("Operación sintética", content.decode("latin-1"))

    def test_missing_manifest_is_rejected(self) -> None:
        report = lint_corpus(self.root)
        self.assertIn("DAT-MANIFEST-MISSING", {error["code"] for error in report.errors})

    def test_hash_tampering_is_rejected(self) -> None:
        self._generate()
        target = self.root / "files/payments_en_us.csv"
        target.write_bytes(target.read_bytes() + b"SYN-TAMPER\n")
        report = lint_corpus(self.root)
        codes = {error["code"] for error in report.errors}
        self.assertIn("DAT-HASH-MISMATCH", codes)

    def test_real_or_derived_classification_is_rejected(self) -> None:
        self._generate()
        manifest = self._manifest()
        manifest["classification"] = "authorized_real_sanitized"
        manifest["synthetic"] = False
        manifest["provenance"]["real_data_used"] = True
        self._write_manifest(manifest)
        codes = {error["code"] for error in lint_corpus(self.root).errors}
        self.assertIn("DAT-CLASSIFICATION-DENIED", codes)
        self.assertIn("DAT-NOT-SYNTHETIC", codes)
        self.assertIn("DAT-REAL-DATA-DENIED", codes)

    def test_non_reserved_domain_is_rejected_even_when_hash_is_updated(self) -> None:
        self._generate()
        manifest = self._manifest()
        entry = next(item for item in manifest["files"] if item["path"] == "files/hostile_cells.csv")
        path = self.root / entry["path"]
        non_reserved_domain = b"banco-no-reservado" + b".co"
        content = path.read_bytes().replace(b"example.invalid", non_reserved_domain)
        path.write_bytes(content)
        entry["bytes"] = len(content)
        entry["sha256"] = sha256_bytes(content)
        self._write_manifest(manifest)
        codes = {error["code"] for error in lint_corpus(self.root).errors}
        self.assertIn("DAT-DOMAIN-NOT-RESERVED", codes)

    def test_unlisted_file_is_rejected(self) -> None:
        self._generate()
        (self.root / "files/unlisted.csv").write_text("SYN-UNLISTED\n", encoding="utf-8")
        codes = {error["code"] for error in lint_corpus(self.root).errors}
        self.assertIn("DAT-UNLISTED-FILE", codes)

    def test_unlisted_symlink_is_rejected(self) -> None:
        self._generate()
        os.symlink("missing-synthetic-target", self.root / "files/unlisted-link")
        codes = {error["code"] for error in lint_corpus(self.root).errors}
        self.assertIn("DAT-UNLISTED-FILE", codes)

    def test_external_inputs_are_rejected(self) -> None:
        self._generate()
        manifest = self._manifest()
        manifest["provenance"]["external_inputs"] = ["customer-export.csv"]
        self._write_manifest(manifest)
        codes = {error["code"] for error in lint_corpus(self.root).errors}
        self.assertIn("DAT-EXTERNAL-INPUT-DENIED", codes)


if __name__ == "__main__":
    unittest.main()
