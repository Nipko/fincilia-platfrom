"""Lectura incremental: los mismos registros, sin sostener el fichero.

La prueba que sostiene a todas: **el resultado tiene que ser identico** al de la
version que materializaba el fichero entero. Un rediseno de rendimiento que
cambiara una sola coordenada seria un rediseno de significado disfrazado.

Y la segunda: que no acumule. Se comprueba contando objetos vivos, no leyendo el
codigo, porque la forma de romperlo es guardar algo «solo por si acaso».
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.extraction import (  # noqa: E402
    MAX_CELL_LENGTH,
    ExtractionError,
    StreamOutcome,
    extract,
    extraction_summary,
    sniff,
    slice_of,
    stream_records,
)

BANK = (
    "fecha;descripcion;referencia;valor\n"
    "01/02/2026;Pago proveedor Ltda;REF-0001;-1.234,56\n"
    "02/02/2026;Consignacion cliente;REF-0002;980.000,00\n"
    "03/02/2026;Comision manejo;;-15.900,00\n"
).encode("utf-8")


def read(payload: bytes, **options):
    """Lee del principio al final y devuelve `(preambulo, filas, resultado)`."""
    preamble, reader = sniff(io.BytesIO(payload),
                             header_row=options.pop("header_row", 1),
                             delimiter=options.pop("delimiter", None))
    outcome = StreamOutcome()
    rows = list(stream_records(reader, preamble, outcome=outcome, **options))
    return preamble, rows, outcome


class EquivalenceTests(unittest.TestCase):
    """Lo que sale en corriente es lo que salia entero. Nada mas y nada menos."""

    def test_the_records_match_the_materialising_reader(self) -> None:
        _, streamed, _ = read(BANK)
        whole = extract(BANK)
        self.assertEqual([row.record_ordinal for row in streamed],
                         [row.record_ordinal for row in whole.rows])
        self.assertEqual([row.values for row in streamed],
                         [row.values for row in whole.rows])

    def test_the_byte_spans_match_exactly(self) -> None:
        # Un tramo distinto es un localizador distinto, y un localizador que ya
        # se publico no puede cambiar de significado por un cambio de motor.
        _, streamed, _ = read(BANK)
        whole = extract(BANK)
        self.assertEqual([(row.byte_start, row.byte_end) for row in streamed],
                         [(row.byte_start, row.byte_end) for row in whole.rows])

    def test_the_span_still_recovers_the_row_from_the_bytes(self) -> None:
        _, rows, _ = read(BANK)
        for row in rows:
            with self.subTest(record=row.record_ordinal):
                recovered = slice_of(BANK, row).decode("utf-8")
                self.assertEqual(recovered.splitlines()[0].split(";"), list(row.values))

    def test_a_quoted_field_spanning_lines_keeps_its_span(self) -> None:
        payload = (
            'fecha,descripcion,importe\n'
            '2026-02-01,"linea uno\nlinea dos",10.00\n'
            '2026-02-02,siguiente,20.00\n'
        ).encode("utf-8")
        _, rows, _ = read(payload)
        multiline = [row for row in rows if row.record_ordinal == 2][0]
        self.assertEqual(multiline.values[1], "linea uno\nlinea dos")
        self.assertEqual(slice_of(payload, multiline).decode("utf-8"),
                         '2026-02-01,"linea uno\nlinea dos",10.00\n')

    def test_a_byte_order_mark_does_not_shift_the_spans(self) -> None:
        payload = bytes.fromhex("efbbbf") + BANK
        preamble, rows, _ = read(payload)
        self.assertEqual(preamble.encoding, "utf-8-sig")
        header = rows[0]
        self.assertEqual(header.byte_start, 3)
        self.assertTrue(slice_of(payload, header).startswith(b"fecha;"))

    def test_a_file_without_a_final_newline_still_yields_its_last_row(self) -> None:
        payload = BANK.rstrip(b"\n")
        _, rows, _ = read(payload)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1].values[0], "03/02/2026")


class MemoryTests(unittest.TestCase):
    """No acumular es la propiedad, y se comprueba contando."""

    def test_it_is_a_generator_and_not_a_list(self) -> None:
        preamble, reader = sniff(io.BytesIO(BANK))
        produced = stream_records(reader, preamble)
        self.assertTrue(hasattr(produced, "__next__"))
        self.assertTrue(hasattr(produced, "send"))

    def test_consuming_one_row_does_not_read_the_whole_file(self) -> None:
        # Si leyera el fichero entero para dar la primera fila, el contador de
        # bytes ya estaria al final.
        big = BANK + b"".join(b"04/02/2026;Relleno %d;;1,00\n" % i for i in range(5_000))
        preamble, reader = sniff(io.BytesIO(big))
        outcome = StreamOutcome()
        produced = stream_records(reader, preamble, outcome=outcome)
        next(produced)
        self.assertLess(outcome.bytes_read, len(big) // 2)
        produced.close()

    def test_nothing_holds_the_rows_after_they_are_yielded(self) -> None:
        import gc
        big = BANK + b"".join(b"04/02/2026;Relleno %d;;1,00\n" % i for i in range(20_000))
        preamble, reader = sniff(io.BytesIO(big))
        seen = 0
        for _ in stream_records(reader, preamble):
            seen += 1
        gc.collect()
        from fincilia_contracts.extraction import ExtractedRow
        alive = sum(1 for item in gc.get_objects() if isinstance(item, ExtractedRow))
        self.assertGreater(seen, 20_000)
        # Alguna puede seguir viva por el marco de la prueba; lo que no puede es
        # que sigan vivas todas.
        self.assertLess(alive, 100, f"{alive} rows are still alive after streaming")


class OutcomeTests(unittest.TestCase):
    def test_a_complete_read_says_complete(self) -> None:
        _, _, outcome = read(BANK)
        self.assertEqual(outcome.state, "complete")
        self.assertIsNone(outcome.reason)
        self.assertEqual(outcome.records, 4)
        self.assertEqual(outcome.data_rows, 3)
        self.assertEqual(outcome.bytes_read, len(BANK))

    def test_reaching_the_row_limit_says_truncated(self) -> None:
        # `truncated` es un estado y no un fallo, pero **no** es `complete`, y
        # eso es lo que impide publicarlo.
        _, rows, outcome = read(BANK, max_rows=2)
        self.assertEqual(outcome.state, "truncated")
        self.assertEqual(outcome.reason, "row_limit")
        self.assertEqual(len(rows), 3)

    def test_an_unterminated_quote_swallows_the_rest_and_says_so(self) -> None:
        # `csv` no considera esto un error: se come el resto del fichero dentro
        # del campo abierto. Impedirlo exigiria otro analizador, asi que lo que
        # se comprueba es que el recuento **no mienta**: sale un registro, no
        # tres, y el tramo de bytes abarca cuanto se trago.
        payload = b'a,b\n"sin cerrar,2\n3,4\n5,6\n'
        _, rows, outcome = read(payload)
        data = [row for row in rows if row.record_ordinal >= 2]
        self.assertEqual(len(data), 1)
        self.assertEqual(outcome.data_rows, 1)
        self.assertEqual(data[0].byte_end, len(payload))

    def test_an_oversized_cell_fails_instead_of_being_trimmed(self) -> None:
        payload = b"a,b\n1," + b"x" * (MAX_CELL_LENGTH + 1) + b"\n"
        outcome = StreamOutcome()
        preamble, reader = sniff(io.BytesIO(payload))
        with self.assertRaises(ExtractionError):
            list(stream_records(reader, preamble, outcome=outcome))
        self.assertEqual(outcome.state, "failed")
        self.assertEqual(outcome.reason, "cell_too_long")

    def test_the_digest_is_the_same_for_the_same_content(self) -> None:
        _, _, first = read(BANK)
        _, _, second = read(BANK)
        self.assertEqual(first.content_digest, second.content_digest)
        self.assertEqual(len(first.content_digest), 64)

    def test_the_digest_changes_when_a_row_changes(self) -> None:
        # Es lo que permite decir si dos lecturas vieron lo mismo sin guardar el
        # fichero para compararlo.
        _, _, original = read(BANK)
        _, _, altered = read(BANK.replace(b"980.000,00", b"980.000,01"))
        self.assertNotEqual(original.content_digest, altered.content_digest)

    def test_a_partial_read_has_a_different_digest_than_the_whole(self) -> None:
        _, _, whole = read(BANK)
        _, _, partial = read(BANK, max_rows=2)
        self.assertNotEqual(whole.content_digest, partial.content_digest)

    def test_the_summary_carries_no_value_from_the_file(self) -> None:
        preamble, _, outcome = read(BANK)
        rendered = repr(extraction_summary(preamble, outcome))
        for value in ("Pago proveedor Ltda", "REF-0001", "980.000"):
            self.assertNotIn(value, rendered)


class PreambleTests(unittest.TestCase):
    def test_the_sample_is_bounded_and_still_finds_the_header(self) -> None:
        preamble, _ = sniff(io.BytesIO(BANK))
        self.assertEqual(preamble.header,
                         ("fecha", "descripcion", "referencia", "valor"))
        self.assertEqual(preamble.delimiter, ";")
        self.assertEqual(preamble.first_data_row, 2)

    def test_a_preamble_is_skipped_by_declaring_the_header_row(self) -> None:
        payload = (b"Banco Sintetico SA\nExtracto de cuenta\n" + BANK)
        preamble, rows, _ = read(payload, header_row=3)
        self.assertEqual(preamble.header,
                         ("fecha", "descripcion", "referencia", "valor"))
        self.assertEqual([row.record_ordinal for row in rows][:1], [1])
        data = [row for row in rows if row.record_ordinal >= preamble.first_data_row]
        self.assertEqual(len(data), 3)

    def test_a_header_beyond_the_sample_is_refused(self) -> None:
        # Una cabecera a sesenta kilobytes del principio no es una cabecera, y
        # decirlo es mejor que leer el fichero entero para descubrirlo.
        with self.assertRaises(ExtractionError):
            sniff(io.BytesIO(BANK), header_row=9_999)

    def test_an_empty_artifact_is_refused(self) -> None:
        for payload in (b"", b"   \n  \n"):
            with self.subTest(payload=payload):
                with self.assertRaises(ExtractionError):
                    sniff(io.BytesIO(payload))

    def test_the_reader_is_closed_even_when_the_read_fails(self) -> None:
        class Watcher(io.BytesIO):
            closed_by_us = False

            def close(self) -> None:
                type(self).closed_by_us = True
                super().close()

        payload = b"a,b\n1," + b"x" * (MAX_CELL_LENGTH + 1) + b"\n"
        preamble, reader = sniff(Watcher(payload))
        with self.assertRaises(ExtractionError):
            list(stream_records(reader, preamble))
        self.assertTrue(Watcher.closed_by_us,
                        "an exception must not leave the object stream open")


if __name__ == "__main__":
    unittest.main()
