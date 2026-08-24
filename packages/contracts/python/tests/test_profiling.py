"""Contrato del perfilado.

Dos cosas se prueban una y otra vez aqui, porque son las que hacen dano si
fallan: que el perfil **no lleve valores**, y que ante una ambiguedad de dinero o
de fecha **no adivine**.
"""

from __future__ import annotations

import unittest

from fincilia_contracts.profiling import (MAX_COLUMNS, SINGLE_COLUMN, TableProfile,
                                          UnprofilableFile, classify, decode,
                                          looks_like_header, profile, sniff_delimiter)

COP_CSV = (
    "fecha,descripcion,valor,moneda\n"
    "2026-01-02,Pago proveedor,-1250000.00,COP\n"
    "2026-01-03,Cobro cliente,3400000.00,COP\n"
).encode("utf-8")

SEMICOLON_CSV = (
    "Fecha;Detalle;Debito;Credito\n"
    "02/03/2026;Transferencia;1.250.000,00;\n"
    "15/03/2026;Consignacion;;3.400.000,00\n"
).encode("utf-8")


class ClassifyTests(unittest.TestCase):
    def test_integers_and_decimals(self) -> None:
        self.assertEqual("integer", classify("1250"))
        self.assertEqual("integer", classify("-1250"))
        self.assertEqual("decimal_dot", classify("1250.00"))
        self.assertEqual("decimal_dot", classify("1,250.00"))
        self.assertEqual("decimal_comma", classify("1250,00"))
        self.assertEqual("decimal_comma", classify("1.250.000,00"))

    def test_a_thousand_separator_alone_is_ambiguous(self) -> None:
        # `1.234` puede ser mil doscientos treinta y cuatro o uno coma doscientos
        # treinta y cuatro. Elegir en silencio mueve dinero.
        self.assertEqual("ambiguous_numeric", classify("1.234"))
        self.assertEqual("ambiguous_numeric", classify("1,234"))

    def test_iso_dates_are_unambiguous(self) -> None:
        self.assertEqual("date_iso", classify("2026-01-02"))

    def test_a_day_over_twelve_settles_the_order(self) -> None:
        self.assertEqual("date_dmy", classify("15/03/2026"))
        self.assertEqual("date_mdy", classify("03/15/2026"))

    def test_a_date_that_fits_both_orders_is_ambiguous(self) -> None:
        # 02/01/2026 es el 2 de enero o el 1 de febrero. No se decide aqui.
        self.assertEqual("ambiguous_date", classify("02/01/2026"))

    def test_booleans_and_text(self) -> None:
        self.assertEqual("boolean", classify("si"))
        self.assertEqual("boolean", classify("false"))
        self.assertEqual("text", classify("Pago proveedor"))
        # `1` es un entero antes que un booleano: contar filas de unos y ceros
        # como booleanos convertiria un importe en una bandera.
        self.assertEqual("integer", classify("1"))


class DelimiterTests(unittest.TestCase):
    def test_a_comma_file_is_detected(self) -> None:
        self.assertEqual(",", sniff_delimiter(COP_CSV.decode("utf-8")))

    def test_a_semicolon_file_is_detected(self) -> None:
        self.assertEqual(";", sniff_delimiter(SEMICOLON_CSV.decode("utf-8")))

    def test_free_text_full_of_commas_does_not_win_by_frequency(self) -> None:
        # Lo que distingue a un delimitador es aparecer el mismo numero de veces
        # en cada linea, no aparecer mucho.
        sample = ("id|nota\n"
                  "1|uno, dos, tres, cuatro\n"
                  "2|cinco, seis\n")
        self.assertEqual("|", sniff_delimiter(sample))

    def test_a_file_without_a_delimiter_is_one_column(self) -> None:
        # No es un fichero roto: es una columna. Partirlo con un delimitador
        # inventado seria peor que no partirlo.
        self.assertEqual(SINGLE_COLUMN,
                         sniff_delimiter("una linea sin separadores"))

    def test_an_empty_sample_is_refused(self) -> None:
        with self.assertRaises(UnprofilableFile):
            sniff_delimiter("\n\n\n")


class HeaderTests(unittest.TestCase):
    def test_a_row_of_names_is_a_header(self) -> None:
        self.assertTrue(looks_like_header(["fecha", "descripcion", "valor"]))

    def test_a_row_with_a_date_is_data(self) -> None:
        self.assertFalse(looks_like_header(["2026-01-02", "Pago", "100.00"]))

    def test_a_row_with_repeats_is_not_a_header(self) -> None:
        # Dos columnas con el mismo nombre hacen imposible un mapeo sin ambiguedad.
        self.assertFalse(looks_like_header(["valor", "valor"]))

    def test_a_row_with_an_empty_cell_is_not_a_header(self) -> None:
        self.assertFalse(looks_like_header(["fecha", "", "valor"]))


class DecodeTests(unittest.TestCase):
    def test_utf8_with_bom_loses_the_bom(self) -> None:
        text, encoding = decode("fecha,valor\n".encode("utf-8-sig"))
        self.assertTrue(text.startswith("fecha"))
        self.assertEqual("utf-8-sig", encoding)

    def test_latin_text_is_decoded(self) -> None:
        text, _ = decode("descripcion,año\n".encode("cp1252"))
        self.assertIn("a", text)


class ProfileTests(unittest.TestCase):
    def test_a_clean_ledger_is_profiled(self) -> None:
        result = profile(COP_CSV)
        self.assertTrue(result.has_header)
        self.assertEqual(",", result.delimiter)
        self.assertEqual(2, result.row_count)
        self.assertEqual(4, result.column_count)
        self.assertEqual(["fecha", "descripcion", "valor", "moneda"],
                         [column.header for column in result.columns])
        self.assertEqual("date_iso", result.columns[0].inferred_type)
        self.assertEqual("text", result.columns[1].inferred_type)
        self.assertEqual("decimal_dot", result.columns[2].inferred_type)

    def test_a_colombian_bank_export_is_profiled(self) -> None:
        result = profile(SEMICOLON_CSV)
        self.assertEqual(";", result.delimiter)
        self.assertEqual(2, result.row_count)
        self.assertEqual("date_dmy", result.columns[0].inferred_type)
        self.assertEqual("decimal_comma", result.columns[2].inferred_type)
        # Cada fila tiene un lado vacio: eso son huecos, no filas irregulares.
        self.assertEqual(0, result.ragged_rows)
        self.assertEqual(1, result.columns[2].empty)

    def test_the_profile_never_carries_a_value(self) -> None:
        rendered = str(profile(COP_CSV).as_dict())
        for value in ("Pago proveedor", "Cobro cliente", "1250000", "3400000"):
            self.assertNotIn(value, rendered)

    def test_an_ambiguous_amount_column_is_flagged_for_a_person(self) -> None:
        payload = b"fecha,valor\n2026-01-02,1.234\n2026-01-03,5.678\n"
        result = profile(payload)
        self.assertEqual("ambiguous_numeric", result.columns[1].inferred_type)
        self.assertTrue(result.columns[1].ambiguous)
        self.assertIn("valor", result.needs_decision)

    def test_an_ambiguous_date_column_is_flagged_for_a_person(self) -> None:
        payload = b"fecha,valor\n02/01/2026,10.00\n03/04/2026,20.00\n"
        result = profile(payload)
        self.assertEqual("ambiguous_date", result.columns[0].inferred_type)
        self.assertIn("fecha", result.needs_decision)

    def test_one_unambiguous_row_settles_the_whole_date_column(self) -> None:
        payload = b"fecha,valor\n02/01/2026,10.00\n15/03/2026,20.00\n"
        result = profile(payload)
        self.assertEqual("date_dmy", result.columns[0].inferred_type)
        self.assertEqual((), result.needs_decision)

    def test_a_file_without_a_header_keeps_all_its_rows(self) -> None:
        payload = b"2026-01-02,Pago,100.00\n2026-01-03,Cobro,200.00\n"
        result = profile(payload)
        self.assertFalse(result.has_header)
        self.assertEqual(2, result.row_count)
        self.assertEqual(["columna_1", "columna_2", "columna_3"],
                         [column.header for column in result.columns])

    def test_ragged_rows_are_counted_not_hidden(self) -> None:
        payload = b"a,b,c\n1,2,3\n4,5\n6,7,8,9\n"
        result = profile(payload)
        self.assertEqual(2, result.ragged_rows)

    def test_confidence_reports_how_much_of_the_column_fits(self) -> None:
        payload = b"valor,nota\n10.00,a\n20.00,b\n30.00,c\npendiente,d\n"
        column = profile(payload).columns[0]
        self.assertEqual("decimal_dot", column.inferred_type)
        self.assertEqual(0.75, column.type_confidence)

    def test_a_single_column_file_is_profiled_as_one_column(self) -> None:
        payload = b"referencia\nFAC-2026-000123\nFAC-2026-000124\n"
        result = profile(payload)
        self.assertEqual("", result.delimiter)
        self.assertEqual(1, result.column_count)
        self.assertEqual(2, result.row_count)

    def test_blank_lines_are_not_rows(self) -> None:
        payload = b"a,b\n1,2\n\n\n3,4\n"
        self.assertEqual(2, profile(payload).row_count)

    def test_row_limit_is_reported_as_truncated(self) -> None:
        payload = b"a,b\n" + b"1,2\n" * 50
        result = profile(payload, max_rows=10)
        self.assertTrue(result.truncated)
        self.assertEqual(10, result.row_count)

    def test_too_many_columns_is_refused(self) -> None:
        payload = (",".join(f"c{index}" for index in range(MAX_COLUMNS + 1))).encode()
        with self.assertRaises(UnprofilableFile):
            profile(payload)

    def test_an_empty_file_is_refused(self) -> None:
        with self.assertRaises(UnprofilableFile):
            profile(b"")

    def test_the_profile_is_serialisable(self) -> None:
        payload = profile(COP_CSV).as_dict()
        self.assertIsInstance(payload["columns"], list)
        self.assertEqual(4, len(payload["columns"]))

    def test_the_result_type_is_the_declared_one(self) -> None:
        self.assertIsInstance(profile(COP_CSV), TableProfile)


if __name__ == "__main__":
    unittest.main()
