"""FNC-SMB-002: filas canonizables de factura DIAN y MT940, con linaje por campo.

Solo fixtures sinteticos de `structured_factory`.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

from fincilia_contracts import structured_rows as rows
from fincilia_contracts.mapping import apply

sys.path.insert(0, str(Path(__file__).resolve().parent))

from structured_factory import (attached_document, invoice,  # noqa: E402
                                invoice_xml, mt940)

SHA = "a" * 64


def mapping_from(definition: dict):
    from fincilia_contracts.mapping import ColumnMapping
    return ColumnMapping(
        columns=dict(definition["columns"]), date_format=definition["date_format"],
        decimal_format=definition["decimal_format"], currency=definition["currency"],
        direction_mode=definition["direction_mode"],
        header_row=definition["header_row"],
        first_data_row=definition["first_data_row"])


class InvoiceRowsTests(unittest.TestCase):
    def test_invoice_becomes_header_and_one_row_with_field_lineage(self) -> None:
        stream, summary = rows.stream_invoice_rows(invoice(), artifact_sha256=SHA)
        records = list(stream)
        self.assertEqual(2, len(records))
        header, data = records
        self.assertTrue(header.origin["synthetic_header"])
        self.assertEqual(rows.DIAN_HEADER, header.values)
        locator = data.locator(SHA)
        self.assertEqual("xml_element", locator["locator_kind"])
        self.assertEqual(len(data.values), locator["field_count"])
        self.assertEqual(len(data.values), len(locator["field_paths"]))
        self.assertEqual("/Invoice/cbc:ID[1]", locator["field_paths"][0])
        self.assertTrue(locator["field_paths"][6].endswith("cbc:PayableAmount[1]"))
        # La descripcion compuesta enumera sus tres elementos de origen.
        self.assertEqual(3, len(locator["field_paths"][8]))
        self.assertIn("NIT FNC-SYN-NIT-0002", data.values[8])
        self.assertEqual("complete", summary["source_status"])
        self.assertEqual("COP", summary["currency"])

    def test_proposed_definition_maps_the_invoice_without_rejections(self) -> None:
        stream, summary = rows.stream_invoice_rows(invoice(), artifact_sha256=SHA)
        records = list(stream)
        definition = rows.proposed_definition(summary)
        self.assertIsNotNone(definition)
        result = apply(mapping_from(definition), [list(records[1].values)])
        self.assertEqual((), result.rejections)
        movement = result.movements[0]
        self.assertEqual(Decimal("119000"), movement.amount)
        self.assertEqual("inflow", movement.direction)
        self.assertEqual("2026-03-02", movement.occurred_on)
        self.assertEqual("SYN-FE-0001", movement.reference)

    def test_partial_invoice_is_declared_partial_and_cannot_map(self) -> None:
        payload = invoice_xml(payable="12,5").encode("utf-8")
        stream, summary = rows.stream_invoice_rows(payload, artifact_sha256=SHA)
        records = list(stream)
        self.assertEqual("partial", summary["source_status"])
        self.assertEqual("", records[1].values[6])
        definition = rows.proposed_definition(summary)
        result = apply(mapping_from(definition), [list(records[1].values)])
        self.assertEqual(1, len(result.rejections))

    def test_attached_document_keeps_the_container(self) -> None:
        payload = attached_document(invoice_xml(declaration=False))
        stream, _ = rows.stream_invoice_rows(payload, artifact_sha256=SHA)
        data = list(stream)[1]
        self.assertIn("container", data.origin)
        self.assertTrue(data.origin["container"].startswith("/AttachedDocument"))

    def test_profile_carries_shape_and_never_values(self) -> None:
        profile = rows.profile_invoice(invoice())
        self.assertEqual(len(rows.DIAN_HEADER), profile["column_count"])
        serialised = repr(profile)
        self.assertNotIn("119000", serialised)
        self.assertNotIn("FNC-SYN-NIT-0002", serialised)
        self.assertFalse(any(column["ambiguous"] for column in profile["columns"]))


class Mt940RowsTests(unittest.TestCase):
    def test_each_statement_line_is_a_movement_row(self) -> None:
        stream, summary = rows.stream_mt940_rows(mt940(), artifact_sha256=SHA)
        records = list(stream)
        self.assertEqual(4, len(records))
        self.assertEqual("balanced", summary["balance_check"])
        self.assertEqual("complete", summary["source_status"])
        first = records[1]
        locator = first.locator(SHA)
        self.assertEqual("mt940_tag", locator["locator_kind"])
        self.assertEqual("61", locator["tag"])
        self.assertEqual([7], locator["information_lines"])
        self.assertEqual(len(first.values), len(locator["field_tags"]))
        self.assertEqual("inflow", first.values[2])
        self.assertEqual("outflow", records[3].values[2])  # RC: reverso de credito

    def test_proposed_definition_maps_every_line_exactly(self) -> None:
        stream, summary = rows.stream_mt940_rows(mt940(), artifact_sha256=SHA)
        records = list(stream)
        definition = rows.proposed_definition(summary)
        result = apply(mapping_from(definition),
                       [list(record.values) for record in records[1:]])
        self.assertEqual((), result.rejections)
        self.assertEqual([Decimal("150000"), Decimal("50000"), Decimal("20000")],
                         [movement.amount for movement in result.movements])
        for movement in result.movements:
            self.assertIsInstance(movement.amount, Decimal)

    def test_unbalanced_statement_is_extracted_but_not_complete(self) -> None:
        _, summary = rows.stream_mt940_rows(
            mt940(closing="C260331COP1080001,00"), artifact_sha256=SHA)
        self.assertEqual("mismatch", summary["balance_check"])
        self.assertEqual("partial", summary["source_status"])


if __name__ == "__main__":
    unittest.main()
