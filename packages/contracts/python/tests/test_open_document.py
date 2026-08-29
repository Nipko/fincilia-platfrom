from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fincilia_contracts.open_document import (  # noqa: E402
    OpenDocumentError,
    OpenDocumentOutcome,
    inspect_open_document,
    iter_open_document_texts,
    open_document_summary,
    sniff_open_document,
    stream_open_document_rows,
)
from fincilia_contracts.profiling import profile_open_document  # noqa: E402
from ods_factory import build_ods  # noqa: E402


ROWS = [
    ["Fecha", "Descripcion", "Importe"],
    ["2026-08-01", "Pago sintetico", -1250],
    ["2026-08-02", "Abono sintetico", 3400],
]


class OpenDocumentInspectionTests(unittest.TestCase):
    def test_a_plain_ods_is_fully_inspected(self) -> None:
        result = inspect_open_document(build_ods(ROWS))
        self.assertTrue(result.supported)
        self.assertEqual("Movimientos", result.sheets[0].name)

    def test_a_multi_sheet_manifest_never_contains_cell_values(self) -> None:
        payload = build_ods(ROWS, second_sheet=[["Referencia"], ["SECRETO-SINTETICO"]])
        result = inspect_open_document(payload)
        manifest = result.manifest(hashlib.sha256(payload).hexdigest())
        self.assertEqual(2, manifest["sheet_count"])
        self.assertNotIn("SECRETO-SINTETICO", repr(manifest))

    def test_formulas_external_links_scripts_and_encryption_are_not_safe(self) -> None:
        formula = inspect_open_document(build_ods(ROWS, formula_at=(2, 3)))
        external = inspect_open_document(build_ods(ROWS, external_link=True))
        scripted = inspect_open_document(build_ods(ROWS, scripts=True))
        self.assertEqual(1, formula.formula_count)
        self.assertEqual(1, external.external_relationships)
        self.assertTrue(scripted.active_parts)
        with self.assertRaises(OpenDocumentError):
            inspect_open_document(build_ods(ROWS, encrypted=True))

    def test_dtd_entities_are_rejected_before_xml_parsing(self) -> None:
        content = b'<!DOCTYPE x [<!ENTITY leak "synthetic">]><x>&leak;</x>'
        with self.assertRaises(OpenDocumentError):
            inspect_open_document(build_ods(ROWS, content_override=content))

    def test_logical_text_is_available_for_secret_scanning(self) -> None:
        texts = dict(iter_open_document_texts(build_ods(ROWS)))
        self.assertEqual("Pago sintetico", texts["Movimientos!R2C2"])


class OpenDocumentExtractionTests(unittest.TestCase):
    def test_rows_are_deterministic_and_carry_spreadsheet_coordinates(self) -> None:
        payload = build_ods(ROWS)
        _, preamble = sniff_open_document(payload)
        outcome = OpenDocumentOutcome()
        rows = list(stream_open_document_rows(
            payload, preamble, artifact_sha256=hashlib.sha256(payload).hexdigest(),
            outcome=outcome))
        self.assertEqual("complete", outcome.state)
        self.assertEqual(2, outcome.data_rows)
        self.assertEqual(("2026-08-01", "Pago sintetico", "-1250"), rows[1].values)
        locator = rows[1].locator(hashlib.sha256(payload).hexdigest())
        self.assertEqual("spreadsheet", locator["locator_kind"])
        self.assertEqual(2, locator["row_number"])

    def test_multi_sheet_requires_the_exact_visible_identity(self) -> None:
        payload = build_ods(ROWS, second_sheet=[["Referencia"], ["SEGUNDA"]])
        inspection = inspect_open_document(payload)
        with self.assertRaises(OpenDocumentError):
            sniff_open_document(payload)
        _, preamble = sniff_open_document(
            payload, sheet_identity=inspection.sheets[1].identity)
        rows = list(stream_open_document_rows(payload, preamble))
        self.assertEqual("SEGUNDA", rows[1].values[0])

    def test_profile_and_summary_do_not_copy_values(self) -> None:
        payload = build_ods(ROWS)
        profile = profile_open_document(payload).as_dict()
        _, preamble = sniff_open_document(payload)
        outcome = OpenDocumentOutcome()
        list(stream_open_document_rows(payload, preamble, outcome=outcome))
        summary = open_document_summary(preamble, outcome)
        self.assertEqual("ods", profile["technical_format"])
        self.assertEqual(2, profile["row_count"])
        self.assertNotIn("Pago sintetico", repr(profile))
        self.assertNotIn("Pago sintetico", repr(summary))

    def test_digest_drift_and_hidden_selection_fail_closed(self) -> None:
        payload = build_ods(ROWS)
        _, preamble = sniff_open_document(payload)
        with self.assertRaises(OpenDocumentError):
            list(stream_open_document_rows(
                payload, preamble, artifact_sha256="0" * 64))
        hidden = build_ods(ROWS, hidden_first=True)
        with self.assertRaises(OpenDocumentError):
            sniff_open_document(hidden)


if __name__ == "__main__":
    unittest.main()
