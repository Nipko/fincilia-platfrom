"""Extraccion fiel y localizadores que se pueden comprobar.

La prueba que sostiene a todas las demas es `slice_of`: si los bytes que dice el
localizador no son la fila, el localizador miente, y un localizador que miente
sostiene una auditoria que no se sostiene.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.extraction import (  # noqa: E402
    MAX_CELL_LENGTH,
    ExtractedRow,
    ExtractionError,
    extract,
    preview_page,
    slice_of,
)

SIMPLE = (
    "fecha,descripcion,importe\r\n"
    "2026-02-01,Pago proveedor,1.234,56\r\n"
).encode("utf-8")

# Con punto y coma para que el importe con coma decimal no parta la fila.
BANK = (
    "fecha;descripcion;referencia;importe\n"
    "01/02/2026;Pago proveedor Ltda;REF-0001;-1.234,56\n"
    "02/02/2026;Consignacion cliente;REF-0002;980.000,00\n"
    "03/02/2026;Comision manejo;;-15.900,00\n"
).encode("utf-8")


class FaithfulExtractionTests(unittest.TestCase):
    def test_a_value_is_returned_exactly_as_it_was_read(self) -> None:
        # Sin recortar y sin normalizar: interpretar es trabajo del mapeo, y
        # mezclarlos haria imposible contestar «que decia el fichero».
        payload = b"a,b\n  espacio  ,  0012  \n"
        result = extract(payload)
        self.assertEqual(result.data_rows()[0].values, ("  espacio  ", "  0012  "))

    def test_the_byte_span_of_a_row_is_exactly_that_row(self) -> None:
        result = extract(BANK)
        # Tambien la cabecera: su tramo tiene que cuadrar igual que el de un dato.
        for row in result.rows:
            with self.subTest(record=row.record_ordinal):
                recovered = slice_of(BANK, row).decode("utf-8")
                self.assertEqual(recovered.rstrip("\r\n").split(";"),
                                 list(row.values))

    def test_a_quoted_field_may_span_lines_without_shifting_the_span(self) -> None:
        payload = (
            'fecha,descripcion,importe\n'
            '2026-02-01,"linea uno\nlinea dos",10.00\n'
            '2026-02-02,siguiente,20.00\n'
        ).encode("utf-8")
        result = extract(payload)
        self.assertEqual(len(result.data_rows()), 2)
        multiline, following = result.data_rows()
        self.assertEqual(multiline.values[1], "linea uno\nlinea dos")
        self.assertEqual(slice_of(payload, multiline).decode("utf-8"),
                         '2026-02-01,"linea uno\nlinea dos",10.00\n')
        self.assertEqual(slice_of(payload, following).decode("utf-8"),
                         '2026-02-02,siguiente,20.00\n')

    def test_the_ordinal_counts_records_and_not_lines(self) -> None:
        # Un campo entrecomillado con salto de linea desplazaria cada
        # referencia posterior si se contaran lineas en vez de registros.
        payload = (
            'a,b\n'
            '1,"dos\nlineas"\n'
            '2,siguiente\n'
        ).encode("utf-8")
        result = extract(payload)
        self.assertEqual([row.record_ordinal for row in result.data_rows()], [2, 3])

    def test_a_byte_order_mark_does_not_shift_the_spans(self) -> None:
        payload = b"\xef\xbb\xbf" + SIMPLE
        result = extract(payload)
        self.assertEqual(result.encoding, "utf-8-sig")
        row = result.data_rows()[0]
        # Tres bytes de marca al principio del fichero desplazarian todos los
        # tramos si el decodificador se los comiera sin que nadie los contara.
        self.assertTrue(slice_of(payload, row).startswith(b"2026-02-01"))
        self.assertEqual(row.byte_start, len(b"fecha,descripcion,importe") + 5)

    def test_an_empty_line_is_skipped_without_consuming_an_ordinal_of_data(self) -> None:
        payload = b"a,b\n1,2\n\n3,4\n"
        result = extract(payload)
        self.assertEqual([row.values for row in result.data_rows()],
                         [("1", "2"), ("3", "4")])
        self.assertEqual([row.record_ordinal for row in result.data_rows()], [2, 4])


class RangeSelectionTests(unittest.TestCase):
    def test_a_preamble_is_skipped_by_declaring_the_header_row(self) -> None:
        # Adivinar el membrete seria decidir por el preparador.
        payload = (
            "Banco Sintetico SA\n"
            "Extracto de cuenta\n"
            "fecha,descripcion,importe\n"
            "2026-02-01,Pago,10.00\n"
        ).encode("utf-8")
        result = extract(payload, header_row=3)
        self.assertEqual(result.header, ("fecha", "descripcion", "importe"))
        self.assertEqual(result.data_rows()[0].record_ordinal, 4)
        # El membrete no desaparece: se leyo, tiene coordenada, y no es un dato.
        self.assertEqual([row.record_ordinal for row in result.rows], [1, 2, 3, 4])

    def test_rows_between_the_header_and_the_first_data_row_are_skipped(self) -> None:
        payload = (
            "fecha,descripcion,importe\n"
            "---,---,---\n"
            "2026-02-01,Pago,10.00\n"
        ).encode("utf-8")
        result = extract(payload, header_row=1, first_data_row=3)
        self.assertEqual(len(result.data_rows()), 1)
        self.assertEqual(result.data_rows()[0].record_ordinal, 3)

    def test_a_first_data_row_before_the_header_is_refused(self) -> None:
        with self.assertRaises(ExtractionError):
            extract(SIMPLE, header_row=3, first_data_row=2)

    def test_a_header_row_that_does_not_exist_is_refused(self) -> None:
        with self.assertRaises(ExtractionError):
            extract(SIMPLE, header_row=99)

    def test_a_header_is_named_when_the_file_leaves_it_blank(self) -> None:
        result = extract(b"fecha,,importe\n2026-02-01,x,10\n")
        self.assertEqual(result.header, ("fecha", "columna_2", "importe"))


class LocatorTests(unittest.TestCase):
    def test_a_cell_locator_carries_file_row_and_column(self) -> None:
        result = extract(BANK)
        locator = result.data_rows()[0].cell_locator("a" * 64, 3)
        self.assertEqual(locator["artifact_sha256"], "a" * 64)
        self.assertEqual(locator["record_ordinal"], 2)
        self.assertEqual(locator["field_ordinal"], 3)
        self.assertEqual(locator["locator_kind"], "tabular_delimited")

    def test_a_field_ordinal_outside_the_record_is_invalid_not_a_gap(self) -> None:
        # `out_of_bounds_outcome: invalid` en el contrato de localizadores.
        result = extract(BANK)
        with self.assertRaises(ExtractionError):
            result.data_rows()[0].cell_locator("a" * 64, 9)
        with self.assertRaises(ExtractionError):
            result.data_rows()[0].cell_locator("a" * 64, -1)

    def test_a_row_locator_declares_the_span_and_the_field_count(self) -> None:
        row = ExtractedRow(record_ordinal=7, byte_start=10, byte_end=42,
                           values=("a", "b"))
        locator = row.locator("b" * 64)
        self.assertEqual(locator["byte_start"], 10)
        self.assertEqual(locator["byte_end"], 42)
        self.assertEqual(locator["field_count"], 2)


class LimitTests(unittest.TestCase):
    def test_reaching_the_row_limit_is_declared_and_not_silent(self) -> None:
        payload = b"a,b\n" + b"".join(b"%d,x\n" % index for index in range(50))
        result = extract(payload, max_rows=10)
        self.assertEqual(len(result.rows), 10)
        self.assertEqual(len(result.data_rows()), 9)
        self.assertTrue(result.truncated)
        self.assertEqual(result.truncation_reason, "row_limit")

    def test_a_complete_read_is_not_marked_truncated(self) -> None:
        result = extract(BANK)
        self.assertFalse(result.truncated)
        self.assertIsNone(result.truncation_reason)

    def test_an_oversized_cell_is_refused_rather_than_trimmed(self) -> None:
        # Recortar convertiria un fichero roto en uno que parece bueno.
        payload = b"a,b\n1," + b"x" * (MAX_CELL_LENGTH + 1) + b"\n"
        with self.assertRaises(ExtractionError):
            extract(payload)

    def test_a_file_without_data_rows_is_refused(self) -> None:
        with self.assertRaises(ExtractionError):
            extract(b"fecha,descripcion,importe\n")

    def test_an_empty_artifact_is_refused(self) -> None:
        with self.assertRaises(ExtractionError):
            extract(b"   \n  \n")


class ShapeTests(unittest.TestCase):
    def test_a_ragged_row_is_counted_and_kept(self) -> None:
        # Se cuenta y se conserva: descartarla seria perder una fila del
        # extracto sin decirlo.
        payload = b"a,b,c\n1,2,3\n4,5\n"
        result = extract(payload)
        self.assertEqual(result.ragged_rows, 1)
        self.assertEqual(len(result.data_rows()), 2)

    def test_the_summary_carries_no_value_from_the_file(self) -> None:
        # El resultado de la ejecucion lo lee cualquiera que vea el documento;
        # los valores viven en `raw_record`, que exige contexto de empresa.
        result = extract(BANK)
        summary = result.as_dict()
        flattened = repr(summary)
        self.assertNotIn("Pago proveedor Ltda", flattened)
        self.assertNotIn("REF-0001", flattened)
        self.assertEqual(summary["row_count"], 3)
        self.assertEqual(summary["record_count"], 4)
        self.assertEqual(summary["column_count"], 4)

    def test_the_delimiter_is_sniffed_and_can_be_overridden(self) -> None:
        self.assertEqual(extract(BANK).delimiter, ";")
        with self.assertRaises(ExtractionError):
            extract(BANK, delimiter="!")


class SelectionTests(unittest.TestCase):
    def test_moving_the_header_reselects_without_reading_the_file_again(self) -> None:
        # Cambiar de opinion sobre donde empieza la tabla no toca la evidencia:
        # los registros ya estan leidos y solo cambia cual se considera dato.
        result = extract(BANK)
        self.assertEqual(len(result.data_rows()), 3)
        self.assertEqual(len(result.data_rows(first_data_row=3)), 2)
        self.assertEqual(len(result.data_rows(first_data_row=1)), 4)

    def test_every_record_including_the_header_carries_a_locator(self) -> None:
        result = extract(BANK)
        self.assertEqual(len(result.rows), 4)
        for row in result.rows:
            with self.subTest(record=row.record_ordinal):
                self.assertLess(row.byte_start, row.byte_end)
                self.assertEqual(row.locator("c" * 64)["record_ordinal"],
                                 row.record_ordinal)


class PreviewTests(unittest.TestCase):
    def test_a_preview_is_always_a_page(self) -> None:
        result = extract(BANK)
        self.assertEqual(len(preview_page(result, offset=0, limit=2)), 2)
        self.assertEqual(len(preview_page(result, offset=2, limit=2)), 2)
        self.assertEqual(preview_page(result, offset=9, limit=2), ())

    def test_a_page_beyond_the_end_is_empty_and_not_an_error(self) -> None:
        result = extract(BANK)
        self.assertEqual(preview_page(result, offset=100), ())

    def test_a_negative_page_is_refused(self) -> None:
        result = extract(BANK)
        with self.assertRaises(ExtractionError):
            preview_page(result, offset=-1)
        with self.assertRaises(ExtractionError):
            preview_page(result, limit=0)


if __name__ == "__main__":
    unittest.main()
