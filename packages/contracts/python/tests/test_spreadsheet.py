from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fincilia_contracts.profiling import profile_workbook  # noqa: E402
from fincilia_contracts.spreadsheet import (  # noqa: E402
    SpreadsheetError,
    SpreadsheetOutcome,
    cell_a1,
    inspect_workbook,
    iter_inspection_texts,
    sniff_workbook,
    spreadsheet_summary,
    stream_workbook_rows,
)
from xlsx_factory import build_xlsx  # noqa: E402


ROWS = [
    ["Fecha", "Descripcion", "Importe"],
    ["2026-02-01", "Pago sintetico", -1250],
    ["2026-02-02", "Abono sintetico", 9800],
]


class WorkbookInspectionTests(unittest.TestCase):
    def test_a_single_plain_sheet_is_fully_inspected(self) -> None:
        result = inspect_workbook(build_xlsx(ROWS))
        self.assertTrue(result.supported)
        self.assertEqual(1, len(result.sheets))
        self.assertEqual(0, result.formula_count)

    def test_formulas_are_counted_and_never_executed(self) -> None:
        result = inspect_workbook(build_xlsx(ROWS, formula_at=(2, 3)))
        self.assertEqual(1, result.formula_count)
        with self.assertRaises(SpreadsheetError):
            sniff_workbook(build_xlsx(ROWS, formula_at=(2, 3)))

    def test_multiple_sheets_require_selection(self) -> None:
        payload = build_xlsx(ROWS, second_sheet=[["Otra"], ["fila"]])
        inspection = inspect_workbook(payload)
        self.assertEqual(2, len(inspection.sheets))
        with self.assertRaises(SpreadsheetError):
            sniff_workbook(payload)
        _, preamble = sniff_workbook(
            payload, sheet_identity=inspection.sheets[1].identity)
        self.assertEqual("Otra", preamble.sheet_name)
        self.assertEqual(2, preamble.sheet_ordinal)

    def test_manifest_has_sheet_identity_but_never_cell_values(self) -> None:
        payload = build_xlsx(ROWS, second_sheet=[["Secreto sintetico"], ["fila"]])
        inspection = inspect_workbook(payload)
        manifest = inspection.manifest(hashlib.sha256(payload).hexdigest())
        self.assertEqual(2, manifest["sheet_count"])
        self.assertEqual(["Movimientos", "Otra"],
                         [sheet["name"] for sheet in manifest["sheets"]])
        self.assertNotIn("Secreto sintetico", repr(manifest))

    def test_unknown_sheet_identity_fails_closed(self) -> None:
        payload = build_xlsx(ROWS, second_sheet=[["Otra"], ["fila"]])
        with self.assertRaises(SpreadsheetError):
            sniff_workbook(payload, sheet_identity="0" * 64)

    def test_active_and_external_content_are_visible(self) -> None:
        active = inspect_workbook(build_xlsx(
            ROWS, active_part="xl/embeddings/object1.bin"))
        self.assertEqual(("xl/embeddings/object1.bin",), active.active_parts)
        external = inspect_workbook(build_xlsx(ROWS, external_relationship=True))
        self.assertEqual(1, external.external_relationships)

    def test_unknown_embedded_parts_are_not_silently_ignored(self) -> None:
        result = inspect_workbook(build_xlsx(
            ROWS, active_part="xl/media/synthetic-image.png"))
        self.assertEqual(("xl/media/synthetic-image.png",), result.active_parts)

    def test_macro_enabled_content_type_is_not_plain_xlsx(self) -> None:
        content_types = (
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            b'<Override PartName="/xl/workbook.xml" '
            b'ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/>'
            b'</Types>')
        with self.assertRaises(SpreadsheetError):
            inspect_workbook(build_xlsx(
                ROWS, content_types_override=content_types))

    def test_dtd_is_rejected_before_xml_parsing(self) -> None:
        xml = b'<!DOCTYPE workbook [<!ENTITY x "synthetic">]><workbook>&x;</workbook>'
        with self.assertRaises(SpreadsheetError):
            inspect_workbook(build_xlsx(ROWS, workbook_override=xml))

    def test_inspection_texts_include_cell_text_without_returning_package_bytes(self) -> None:
        texts = list(iter_inspection_texts(build_xlsx(ROWS)))
        self.assertIn("Pago sintetico", [value for _, value in texts])
        self.assertTrue(all(part.endswith((".xml", ".rels")) for part, _ in texts))


class WorkbookExtractionTests(unittest.TestCase):
    def test_rows_keep_sheet_row_and_exact_values(self) -> None:
        payload = build_xlsx(ROWS)
        _, preamble = sniff_workbook(payload)
        outcome = SpreadsheetOutcome()
        rows = list(stream_workbook_rows(
            payload, preamble, artifact_sha256=hashlib.sha256(payload).hexdigest(),
            outcome=outcome))
        self.assertEqual(("Fecha", "Descripcion", "Importe"), rows[0].values)
        self.assertEqual(("2026-02-01", "Pago sintetico", "-1250"), rows[1].values)
        locator = rows[1].locator(hashlib.sha256(payload).hexdigest())
        self.assertEqual("spreadsheet", locator["locator_kind"])
        self.assertEqual(2, locator["row_number"])
        self.assertEqual(1, locator["sheet_ordinal"])
        self.assertEqual(3, locator["field_count"])
        self.assertEqual("C2", cell_a1(2, 3))
        self.assertEqual("complete", outcome.state)
        self.assertEqual(2, outcome.data_rows)

    def test_selected_second_sheet_is_the_only_one_extracted(self) -> None:
        payload = build_xlsx(ROWS, second_sheet=[
            ["Referencia", "Importe"], ["SEGUNDA", 27]])
        inspection = inspect_workbook(payload)
        _, preamble = sniff_workbook(
            payload, sheet_identity=inspection.sheets[1].identity)
        rows = list(stream_workbook_rows(payload, preamble))
        self.assertEqual(("Referencia", "Importe"), rows[0].values)
        self.assertEqual(("SEGUNDA", "27"), rows[1].values)
        self.assertEqual(2, rows[1].locator("a" * 64)["sheet_ordinal"])

    def test_excel_serial_with_date_style_is_rendered_as_iso(self) -> None:
        payload = build_xlsx(
            [["Fecha", "Importe"], [45292, 10]], date_at={(2, 1)})
        _, preamble = sniff_workbook(payload)
        rows = list(stream_workbook_rows(payload, preamble))
        self.assertEqual("2024-01-01", rows[1].values[0])

    def test_digest_mismatch_fails_closed(self) -> None:
        payload = build_xlsx(ROWS)
        _, preamble = sniff_workbook(payload)
        with self.assertRaises(SpreadsheetError):
            list(stream_workbook_rows(payload, preamble, artifact_sha256="0" * 64))

    def test_row_limit_is_declared(self) -> None:
        payload = build_xlsx(ROWS)
        _, preamble = sniff_workbook(payload)
        outcome = SpreadsheetOutcome()
        rows = list(stream_workbook_rows(payload, preamble, max_rows=1,
                                         outcome=outcome))
        self.assertEqual(2, len(rows))  # cabecera + una fila de datos
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("row_limit", outcome.reason)

    def test_summary_never_contains_cell_values(self) -> None:
        payload = build_xlsx(ROWS)
        _, preamble = sniff_workbook(payload)
        outcome = SpreadsheetOutcome()
        list(stream_workbook_rows(payload, preamble, outcome=outcome))
        rendered = repr(spreadsheet_summary(preamble, outcome))
        self.assertNotIn("Pago sintetico", rendered)
        self.assertNotIn("9800", rendered)


class WorkbookProfileTests(unittest.TestCase):
    def test_profile_detects_types_without_examples(self) -> None:
        profile = profile_workbook(build_xlsx(ROWS)).as_dict()
        self.assertEqual("xlsx", profile["technical_format"])
        self.assertEqual("date_iso", profile["columns"][0]["inferred_type"])
        self.assertEqual("integer", profile["columns"][2]["inferred_type"])
        self.assertEqual(2, profile["row_count"])
        self.assertNotIn("Pago sintetico", repr(profile))

    def test_profile_uses_the_selected_sheet(self) -> None:
        payload = build_xlsx(ROWS, second_sheet=[
            ["Referencia", "Importe"], ["SEGUNDA", 27]])
        inspection = inspect_workbook(payload)
        profile = profile_workbook(
            payload, sheet_identity=inspection.sheets[1].identity).as_dict()
        self.assertEqual("Otra", profile["sheet_name"])
        self.assertEqual(["Referencia", "Importe"],
                         [column["header"] for column in profile["columns"]])
        self.assertNotIn("SEGUNDA", repr(profile))


if __name__ == "__main__":
    unittest.main()
