"""Integridad de la lectura en corriente (FNC-P3.6-R1).

Estas pruebas son adversariales a proposito: cada una construye la entrada que
rompe una garantia concreta, y ninguna pasa por accidente. Son las que faltaban
cuando la corriente se adopto, y por eso hubo que anadirlas despues.

Lo que sostienen, en una linea cada una:

* la codificacion se decide con una muestra, y una muestra no es el fichero;
* un byte que no se entiende **nunca** se sustituye en silencio;
* leer por partes tiene que decir lo mismo que leer entero, o no decir nada;
* el limite se aplica **en** el limite, no una fila antes ni una despues;
* lo que se leyo tiene que ser lo que se subio, y se comprueba;
* la huella del objeto y la de los registros contestan preguntas distintas.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.extraction import (  # noqa: E402
    MAX_EXTRACT_BYTES,
    SNIFF_WINDOW,
    ExtractionError,
    StreamOutcome,
    extract,
    extraction_summary,
    sniff,
    stream_records,
)

HEADER = b"fecha;descripcion;referencia;valor\n"


def ascii_rows(count: int, *, start: int = 1) -> bytes:
    """Filas ASCII puras: obligan a que la muestra elija `utf-8` sin dudar."""
    return b"".join(
        f"{(index % 28) + 1:02d}/02/2026;Pago {index};REF-{index:06d};1.000,00\n"
        .encode("ascii") for index in range(start, start + count))


def padded_to(size: int) -> bytes:
    """Cabecera y filas ASCII hasta pasar `size` bytes."""
    body = b""
    index = 1
    while len(HEADER) + len(body) <= size:
        body += ascii_rows(1, start=index)
        index += 1
    return HEADER + body


def read(payload: bytes, **options):
    preamble, reader = sniff(io.BytesIO(payload))
    outcome = StreamOutcome()
    rows = list(stream_records(reader, preamble, outcome=outcome, **options))
    return preamble, rows, outcome


class ExplodingReader:
    """Un lector que entrega un tramo y despues se rompe.

    Es lo que hace un almacen de objetos cuando la conexion se cae a mitad, y la
    unica forma de comprobar que un fallo del lector deja el desenlace en
    `failed` en vez de en `complete`.
    """

    def __init__(self, payload: bytes, *, fail_after: int) -> None:
        self._payload = payload
        self._fail_after = fail_after
        self._served = 0
        self.closed = False

    def read(self, size: int) -> bytes:
        if self._served >= self._fail_after:
            raise OSError("SYNTHETIC-READER-FAILURE")
        chunk = self._payload[self._served:self._served + size]
        self._served += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


# --------------------------------------------------------------------------- #
# 1. Fidelidad de codificacion
# --------------------------------------------------------------------------- #

class EncodingFidelityTests(unittest.TestCase):
    """La muestra decide, y la muestra puede equivocarse. No puede mentir."""

    def cp1252_beyond_the_window(self) -> bytes:
        """ASCII hasta pasar la ventana, y despues un acento en cp1252.

        Es el caso exacto que el mandato nombra: la muestra ve ASCII puro y
        concluye `utf-8`; el byte `0xE9` que la desmiente esta a sesenta y tantos
        kilobytes, donde la muestra ya no llega.
        """
        head = padded_to(SNIFF_WINDOW + 4096)
        tail = "05/02/2026;Comision café Ltda;REF-999999;-15.900,00\n".encode("cp1252")
        payload = head + tail
        self.assertGreater(len(head), SNIFF_WINDOW,
                           "la parte ASCII tiene que pasar de la ventana")
        self.assertNotIn(b"\xe9", head[:SNIFF_WINDOW],
                         "la muestra no puede contener el byte que la desmiente")
        return payload

    def test_a_cp1252_byte_after_the_window_is_never_replaced(self) -> None:
        """Jamas un U+FFFD en silencio.

        Sustituirlo convierte una evidencia en otra parecida y deja el sistema
        afirmando que leyo lo que no leyo. Entre devolver algo aproximado y no
        devolver nada, la evidencia exige lo segundo.
        """
        payload = self.cp1252_beyond_the_window()
        try:
            _, rows, outcome = read(payload)
        except ExtractionError:
            return  # fallar cerrado tambien vale; lo que no vale es inventar
        rendered = "".join("".join(row.values) for row in rows)
        self.assertNotIn("�", rendered,
                         "un byte que no se entiende se sustituyo en silencio")
        self.assertEqual("complete", outcome.state)

    def test_streaming_agrees_with_the_whole_file_reader(self) -> None:
        """O dice lo mismo que `extract()`, o no dice nada.

        Son dos caminos hacia la misma evidencia. Que discrepen en silencio es
        peor que que uno de los dos falle: el que discrepa gana segun quien
        pregunte.
        """
        payload = self.cp1252_beyond_the_window()
        whole = extract(payload)
        try:
            _, rows, _ = read(payload)
        except ExtractionError:
            return
        self.assertEqual([record.values for record in whole.rows],
                         [row.values for row in rows])

    def test_the_accent_survives_intact(self) -> None:
        """Y cuando no falla, el acento es el que estaba en el fichero."""
        payload = self.cp1252_beyond_the_window()
        try:
            _, rows, _ = read(payload)
        except ExtractionError:
            self.skipTest("esta lectura falla cerrado; lo cubre la prueba de acuerdo")
        self.assertTrue(any("café" in "".join(row.values) for row in rows),
                        "el acento no llego entero al final de la corriente")

    def window_cutting_a_character(self) -> bytes:
        """Un caracter de dos bytes que empieza en el ultimo byte de la ventana.

        La muestra es un corte **por bytes**, y un corte por bytes puede caer
        dentro de un caracter. Cuando cae, `utf-8` falla por el trozo suelto y
        gana `cp1252`, que decodifica cualquier byte sin quejarse: el fichero
        entero se lee mal por culpa de donde cayo el corte, y sin un solo error.
        """
        prefix = padded_to(SNIFF_WINDOW - 300)
        head = "01/02/2026;Cafe "
        pad = SNIFF_WINDOW - len(prefix) - len(head) - 1
        self.assertGreaterEqual(pad, 0)
        row = (head + "x" * pad + "\u00f1;REF-777777;1.000,00\n").encode("utf-8")
        payload = prefix + row + b"02/02/2026;Ultima;REF-888888;2.000,00\n"
        with self.assertRaises(UnicodeDecodeError,
                               msg="el corte tiene que partir el caracter"):
            payload[:SNIFF_WINDOW].decode("utf-8")
        return payload

    def test_a_window_that_cuts_a_character_does_not_pick_the_wrong_codec(self) -> None:
        """El corte no puede decidir la codificacion del fichero.

        Es el fallo mas silencioso de los que habia: no levanta, no trunca, no
        deja rastro. Solo cambia todas las tildes del fichero.
        """
        payload = self.window_cutting_a_character()
        whole = extract(payload)
        preamble, rows, outcome = read(payload)
        self.assertEqual(whole.encoding, preamble.encoding)
        self.assertEqual([record.values for record in whole.rows],
                         [row.values for row in rows])
        self.assertEqual("complete", outcome.state)

    def test_a_nul_beyond_the_sample_is_refused(self) -> None:
        """Un binario con cabecera de texto no se «extrae» en columnas de basura.

        `decode()` mira los primeros kilobytes. Mas alla no lo miraba nadie, y
        `latin-1` decodifica el NUL sin protestar.
        """
        payload = padded_to(SNIFF_WINDOW + 2048) + b"01/02/2026;Bin\x00ario;REF-1;1,00\n"
        with self.assertRaises(ExtractionError):
            read(payload)

    def test_both_readers_split_records_the_same_way(self) -> None:
        """Un avance de pagina dentro de un campo no parte un registro.

        `str.splitlines()` corta por ocho puntos de codigo que no terminan un
        registro CSV. El lector entero lo usaba y el de corriente no, asi que el
        mismo fichero tenia distinto numero de registros segun quien lo leyera.
        """
        payload = (HEADER
                   + "01/02/2026;\"linea uno\x0clinea dos\";REF-1;1.000,00\n".encode("utf-8")
                   + "02/02/2026;Normal;REF-2;2.000,00\n".encode("utf-8"))
        whole = extract(payload)
        _, rows, outcome = read(payload)
        self.assertEqual("complete", outcome.state)
        self.assertEqual([record.values for record in whole.rows],
                         [row.values for row in rows])

    def test_a_pure_ascii_file_needs_no_promotion(self) -> None:
        """Lo normal sigue siendo normal: sin acentos no hay nada que decidir."""
        _, rows, outcome = read(padded_to(2048))
        self.assertEqual("complete", outcome.state)
        self.assertGreater(len(rows), 10)


# --------------------------------------------------------------------------- #
# 2. Limites
# --------------------------------------------------------------------------- #

class LimitTests(unittest.TestCase):
    """Un limite que se aplica una fila antes convierte lo completo en truncado."""

    def test_exactly_the_row_limit_is_complete(self) -> None:
        """Cinco filas con un techo de cinco estan **completas**.

        Marcarlas truncadas bloquearia la publicacion de un fichero que cabe
        entero, y el operador no tendria forma de distinguirlo de uno que no.
        """
        payload = HEADER + ascii_rows(5)
        _, rows, outcome = read(payload, max_rows=5)
        self.assertEqual(5, outcome.data_rows)
        self.assertEqual(5, len([row for row in rows if row.record_ordinal > 1]))
        self.assertEqual("complete", outcome.state, outcome.reason)
        self.assertIsNone(outcome.reason)

    def test_one_row_over_the_limit_truncates_without_emitting_it(self) -> None:
        """Seis filas con un techo de cinco: truncado, y la sexta no sale.

        Las dos mitades importan. Si no truncara, un total cuadraria consigo
        mismo con una fila de menos; si emitiera la sexta, el techo no seria un
        techo.
        """
        payload = HEADER + ascii_rows(6)
        _, rows, outcome = read(payload, max_rows=5)
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("row_limit", outcome.reason)
        self.assertEqual(5, outcome.data_rows)
        emitted = [row for row in rows if row.record_ordinal > 1]
        self.assertEqual(5, len(emitted))
        self.assertNotIn("REF-000006", "".join(
            value for row in emitted for value in row.values))

    def test_whole_and_streaming_limits_agree_after_a_preamble(self) -> None:
        """`max_rows` siempre cuenta datos, no membrete ni cabecera."""
        for data_rows, expected_state in ((5, "complete"), (6, "truncated")):
            with self.subTest(data_rows=data_rows):
                payload = b"ESTADO DE CUENTA SINTETICO\n" + HEADER + ascii_rows(data_rows)
                whole = extract(payload, header_row=2, max_rows=5)
                preamble, reader = sniff(io.BytesIO(payload), header_row=2)
                outcome = StreamOutcome()
                streamed = list(stream_records(reader, preamble, outcome=outcome,
                                               max_rows=5))

                self.assertEqual([row.values for row in whole.rows],
                                 [row.values for row in streamed])
                self.assertEqual(expected_state, outcome.state)
                self.assertEqual(expected_state == "truncated", whole.truncated)
                self.assertEqual(5, len(whole.data_rows()))
                self.assertEqual(5, outcome.data_rows)

    def test_the_byte_limit_is_applied(self) -> None:
        """`MAX_EXTRACT_BYTES` existe para la corriente tambien.

        `extract()` lo comprueba con el fichero en la mano. Leyendo por partes no
        se sabe cuanto ocupa hasta que se acaba, asi que la unica forma de
        aplicarlo es dejar de leer al alcanzarlo y decirlo.
        """
        payload = HEADER + ascii_rows(400)
        _, _, outcome = read(payload, max_bytes=2048)
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("byte_limit", outcome.reason)
        self.assertLessEqual(outcome.bytes_read, 2048 + 262144)

    def test_the_declared_byte_ceiling_is_the_default(self) -> None:
        """Y el techo por defecto es el declarado, no uno inventado aqui."""
        self.assertEqual(64 * 1024 * 1024, MAX_EXTRACT_BYTES)

    def test_the_clock_is_read_even_on_a_small_file(self) -> None:
        """El limite de tiempo existe para todos los ficheros, no para los grandes.

        Se miraba cada quinientas filas de datos, asi que un fichero de tres no
        lo miraba nunca: el limite declarado no existia para el.
        """
        payload = HEADER + ascii_rows(3)
        _, _, outcome = read(payload, max_seconds=-1.0)
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("time_limit", outcome.reason)

    def test_blank_records_do_not_escape_the_limits(self) -> None:
        """Las lineas en blanco se saltaban antes de mirar ningun limite.

        Un fichero hecho de separadores sueltos no estaba acotado por nada: ni
        por filas, porque no cuentan como datos, ni por tiempo, porque el reloj
        colgaba del contador de filas.
        """
        payload = HEADER + ascii_rows(1) + b";;;\n" * 5000
        _, _, outcome = read(payload, max_seconds=-1.0)
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("time_limit", outcome.reason)

    def test_blank_records_do_not_inflate_the_emitted_record_count(self) -> None:
        payload = HEADER + b"\n" + ascii_rows(2)
        _, rows, outcome = read(payload)
        self.assertEqual(len(rows), outcome.records)
        self.assertEqual(3, outcome.records)  # cabecera + dos filas de datos
        self.assertEqual(2, outcome.data_rows)
        self.assertEqual([1, 3, 4], [row.record_ordinal for row in rows])

    def test_consumer_backpressure_does_not_spend_the_extraction_budget(self) -> None:
        """Esperar al consumidor no convierte evidencia completa en truncada.

        El generador se suspende en cada ``yield`` mientras el worker persiste
        un lote. Ese tiempo no es lectura ni parsing y puede variar con la
        latencia de PostgreSQL. La misma evidencia debe tener el mismo desenlace
        aunque el consumidor tarde en pedir el registro siguiente.
        """
        payload = HEADER + ascii_rows(3)
        preamble, reader = sniff(io.BytesIO(payload))
        outcome = StreamOutcome()
        now = [0.0]

        with patch("fincilia_contracts.extraction.time.monotonic",
                   side_effect=lambda: now[0]):
            records = stream_records(reader, preamble, outcome=outcome,
                                     max_seconds=1.0)
            emitted = []
            while True:
                try:
                    emitted.append(next(records))
                except StopIteration:
                    break
                now[0] += 30.0  # trabajo del consumidor, no de la extraccion

        self.assertEqual(4, len(emitted))
        self.assertEqual("complete", outcome.state, outcome.reason)
        self.assertIsNone(outcome.reason)

    def test_a_file_with_only_a_header_fails(self) -> None:
        """Una cabecera sin filas no es un extracto vacio: es un fichero roto.

        Dejarlo pasar como `complete` con cero filas produce un conjunto
        publicable que no dice nada, y nadie mira dos veces un cero.
        """
        with self.assertRaises(ExtractionError):
            read(HEADER)

    def test_a_header_only_file_leaves_the_outcome_failed(self) -> None:
        preamble, reader = sniff(io.BytesIO(HEADER))
        outcome = StreamOutcome()
        with self.assertRaises(ExtractionError):
            list(stream_records(reader, preamble, outcome=outcome))
        self.assertEqual("failed", outcome.state)
        self.assertEqual("no_data_rows", outcome.reason)

    def test_a_reader_that_breaks_leaves_the_outcome_failed(self) -> None:
        """Un almacen que se cae a mitad no deja una lectura `complete`.

        Es la diferencia entre «se leyo entero» y «se dejo de leer»: la primera
        alimenta una publicacion y la segunda tiene que detenerla.
        """
        payload = padded_to(400_000)
        reader = ExplodingReader(payload, fail_after=SNIFF_WINDOW + 262_144)
        preamble, head = sniff(reader)
        outcome = StreamOutcome()
        with self.assertRaises(OSError):
            list(stream_records(head, preamble, outcome=outcome))
        self.assertEqual("failed", outcome.state)
        self.assertEqual("reader_error", outcome.reason)
        self.assertTrue(reader.closed, "la corriente quedo abierta tras el fallo")

    def test_a_record_without_a_byte_span_fails_closed(self) -> None:
        """Un localizador inventado `(0, 0)` no puede llegar a evidencia."""
        payload = HEADER + ascii_rows(1)
        preamble, reader = sniff(io.BytesIO(payload))
        outcome = StreamOutcome()

        with patch("fincilia_contracts.extraction._StreamFeeder.take_span",
                   return_value=None):
            with self.assertRaises(ExtractionError):
                list(stream_records(reader, preamble, outcome=outcome))

        self.assertEqual("failed", outcome.state)
        self.assertEqual("locator_unavailable", outcome.reason)


# --------------------------------------------------------------------------- #
# 3. Integridad del objeto
# --------------------------------------------------------------------------- #

class ObjectIntegrityTests(unittest.TestCase):
    """Dos huellas, dos preguntas. Confundirlas deja una sin contestar."""

    def payload(self) -> bytes:
        return HEADER + ascii_rows(12)

    def test_the_object_digest_is_the_digest_of_the_bytes(self) -> None:
        """La huella del objeto es sha256 de lo que llego, sin interpretar."""
        import hashlib
        payload = self.payload()
        _, _, outcome = read(payload)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), outcome.object_digest)

    def test_the_record_digest_is_not_the_object_digest(self) -> None:
        """Y la de los registros no lo es: resume lo entendido, no lo recibido.

        Son distintas por construccion, y por eso una detecta que el fichero
        cambio y la otra detecta que la lectura cambio.
        """
        _, _, outcome = read(self.payload())
        self.assertNotEqual(outcome.object_digest, outcome.record_digest)
        self.assertEqual(64, len(outcome.record_digest))

    def test_a_declared_digest_that_does_not_match_fails_closed(self) -> None:
        """Si lo leido no es lo que se subio, no hay extraccion que valga."""
        preamble, reader = sniff(io.BytesIO(self.payload()))
        outcome = StreamOutcome()
        with self.assertRaises(ExtractionError):
            list(stream_records(reader, preamble, artifact_sha256="0" * 64,
                                outcome=outcome))
        self.assertEqual("failed", outcome.state)
        self.assertEqual("object_digest_mismatch", outcome.reason)

    def test_a_declared_digest_that_matches_passes(self) -> None:
        import hashlib
        payload = self.payload()
        preamble, reader = sniff(io.BytesIO(payload))
        outcome = StreamOutcome()
        rows = list(stream_records(reader, preamble, outcome=outcome,
                                   artifact_sha256=hashlib.sha256(payload).hexdigest()))
        self.assertEqual("complete", outcome.state)
        self.assertEqual(12, len(rows) - 1)

    def test_a_truncated_read_does_not_claim_the_object_digest(self) -> None:
        """Una lectura a medias no ha visto el objeto entero.

        Comprobar su huella contra la declarada fallaria siempre, y ese fallo
        diria «el fichero cambio» cuando lo que paso es que no se acabo de leer.
        """
        import hashlib
        payload = HEADER + ascii_rows(20)
        preamble, reader = sniff(io.BytesIO(payload))
        outcome = StreamOutcome()
        list(stream_records(reader, preamble, outcome=outcome, max_rows=3,
                            artifact_sha256=hashlib.sha256(payload).hexdigest()))
        self.assertEqual("truncated", outcome.state)
        self.assertEqual("row_limit", outcome.reason)

    def test_the_record_digest_separates_values_that_look_alike(self) -> None:
        """Dos conjuntos distintos de valores no pueden dar la misma huella.

        La version anterior los enmarcaba con `0x1F` y `0x1E` sin escaparlos, y
        esos bytes pueden aparecer dentro de un valor: un campo que llevara el
        separador dentro se resumia igual que dos campos. Con la longitud delante
        de cada valor no puede pasar, porque la huella se puede deshacer.
        """
        one = HEADER + b"01/02/2026;a\x1fb;REF-1;1,00\n"
        two = HEADER + b'01/02/2026;"a";REF-1;1,00\n'
        _, _, first = read(one)
        _, _, second = read(two)
        self.assertNotEqual(first.record_digest, second.record_digest)

    def test_the_summary_reports_both_digests(self) -> None:
        preamble, _, outcome = read(self.payload())
        summary = extraction_summary(preamble, outcome)
        self.assertIn("object_digest", summary)
        self.assertIn("record_digest", summary)
        self.assertNotEqual(summary["object_digest"], summary["record_digest"])

    def test_the_summary_still_carries_no_value_from_the_file(self) -> None:
        preamble, _, outcome = read(self.payload())
        rendered = str(extraction_summary(preamble, outcome))
        for quoted in ("Pago 1", "REF-000001", "1.000,00"):
            self.assertNotIn(quoted, rendered)


if __name__ == "__main__":
    unittest.main()
