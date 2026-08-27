"""Clasificacion de fallos del worker.

Lo que se prueba aqui es la decision que el worker toma sobre un fallo, porque de
ella depende si un trabajo se reintenta, muere, o acaba delante de una persona.
Es logica pura y no necesita base de datos.

El protocolo de despacho -- arriendos, recuperacion, reintentos y carta muerta --
se prueba contra PostgreSQL real y con las credenciales de cada rol en
`db/tests/test_dispatch_protocol.py`. Ahi es donde tiene sentido: son propiedades
del motor y de los privilegios, no del codigo que las invoca.
"""

from __future__ import annotations

import io
import re
import sys
import unittest

sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/packages/contracts/python/tests")

from fincilia_contracts.extraction import (  # noqa: E402
    ExtractionError,
    StreamOutcome,
    extraction_summary,
    sniff,
    stream_records,
)
from fincilia_platform.objects import ObjectStoreError  # noqa: E402
from fincilia_worker import jobs  # noqa: E402
from xlsx_factory import build_xlsx  # noqa: E402

CLEAN_CSV = (
    "Fecha;Detalle;Debito;Credito\n"
    "02/03/2026;Transferencia;1.250.000,00;\n"
    "15/03/2026;Consignacion;;3.400.000,00\n"
).encode("utf-8")

BINARY = bytes([0xFF, 0xFE, 0x00, 0x01]) + b" binario"
REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,79}$")


class FailureClassificationTests(unittest.TestCase):
    def test_a_readable_file_is_profiled_without_failure(self) -> None:
        result, error, failure = jobs.run_profile(CLEAN_CSV)
        self.assertIsNone(error)
        self.assertIsNone(failure)
        self.assertEqual(";", result["delimiter"])
        self.assertEqual(2, result["row_count"])

    def test_the_profile_carries_no_value_from_the_file(self) -> None:
        result, _, _ = jobs.run_profile(CLEAN_CSV)
        rendered = str(result)
        for value in ("Transferencia", "Consignacion", "1.250.000", "3.400.000"):
            self.assertNotIn(value, rendered)

    def test_a_safe_xlsx_uses_the_spreadsheet_profiler(self) -> None:
        payload = build_xlsx([
            ["Fecha", "Descripcion", "Importe"],
            ["2026-02-01", "Pago sintetico", -1250],
        ])
        result, error, failure = jobs.run_profile(payload, internal_type="xlsx")
        self.assertIsNone(error)
        self.assertIsNone(failure)
        self.assertEqual("xlsx", result["technical_format"])
        self.assertEqual(1, result["row_count"])
        self.assertNotIn("Pago sintetico", repr(result))

    def test_an_unreadable_file_is_fatal_not_retryable(self) -> None:
        # El fichero es el que es. Reintentarlo tres veces daria lo mismo tres
        # veces y solo retrasaria el unico desenlace posible.
        result, error, failure = jobs.run_profile(BINARY)
        self.assertIsNone(result)
        self.assertEqual("unprofilable", error)
        self.assertEqual(jobs.FATAL, failure)

    def test_an_empty_file_is_fatal(self) -> None:
        _, error, failure = jobs.run_profile(b"")
        self.assertEqual("unprofilable", error)
        self.assertEqual(jobs.FATAL, failure)

    def test_every_reason_code_fits_the_bounded_vocabulary(self) -> None:
        # La base rechaza cualquier codigo que no encaje. El contrato prohibe el
        # error crudo, y un codigo libre acabaria llevandolo dentro.
        for payload in (b"", BINARY, b"sin delimitador ninguno"):
            with self.subTest(payload=payload[:8]):
                _, error, _ = jobs.run_profile(payload)
                if error is not None:
                    self.assertRegex(error, REASON_CODE)

    def test_the_failure_classes_are_the_declared_ones(self) -> None:
        declared = {"retryable", "rate_limited", "fatal", "requires_human", "unknown"}
        for value in (jobs.RETRYABLE, jobs.FATAL, jobs.UNKNOWN):
            self.assertIn(value, declared)

    def test_the_lease_outlasts_any_reasonable_profile(self) -> None:
        # Un arriendo mas corto que el trabajo haria que cada perfilado normal se
        # recuperase a mitad y se ejecutara dos veces.
        self.assertGreaterEqual(jobs.LEASE_SECONDS, 60)
        self.assertLessEqual(jobs.LEASE_SECONDS, 3600)

    def test_the_worker_has_no_way_to_release_a_pointer_by_itself(self) -> None:
        # Las dos funciones que borraban el puntero sin comprobar nada eran las
        # que dejaban trabajos invisibles para siempre. Ya no existen, y que no
        # vuelvan es parte del contrato de este modulo.
        for gone in ("drop_pointer", "release_stale", "take_pointer", "start_run"):
            self.assertFalse(hasattr(jobs, gone),
                             f"{gone} writes the queue without checking the lease")

def stream(payload: bytes, **options):
    """Lee unos bytes en corriente, como lo hace el worker."""
    preamble, reader = sniff(io.BytesIO(payload), **options)
    outcome = StreamOutcome()
    rows = list(stream_records(reader, preamble, outcome=outcome))
    return preamble, rows, outcome


class ExtractionTests(unittest.TestCase):
    """Extraer transcribe; perfilar no. La diferencia es la que decide donde va
    cada cosa: la forma al resultado de la ejecucion, los valores a `raw_record`.

    El worker **no** materializa el fichero: consume un generador por tandas.
    Estas pruebas usan la misma via, no una comoda que ya no existe en produccion.
    """

    def test_a_readable_file_is_read_without_failure(self) -> None:
        preamble, rows, outcome = stream(CLEAN_CSV)
        self.assertEqual(";", preamble.delimiter)
        self.assertEqual(2, outcome.data_rows)
        self.assertEqual(3, len(rows))
        self.assertEqual("complete", outcome.state)

    def test_the_extraction_summary_carries_no_value_from_the_file(self) -> None:
        # El resultado de la ejecucion lo lee cualquiera que vea el documento.
        preamble, _, outcome = stream(CLEAN_CSV)
        rendered = str(extraction_summary(preamble, outcome))
        for value in ("Transferencia", "Consignacion", "1.250.000", "3.400.000"):
            self.assertNotIn(value, rendered)

    def test_every_extracted_record_carries_its_coordinate(self) -> None:
        _, rows, _ = stream(CLEAN_CSV)
        for row in rows:
            with self.subTest(record=row.record_ordinal):
                locator = row.locator("a" * 64)
                self.assertEqual(locator["locator_kind"], "tabular_delimited")
                self.assertLess(locator["byte_start"], locator["byte_end"])
                recovered = CLEAN_CSV[row.byte_start:row.byte_end].decode("utf-8")
                self.assertEqual(recovered.splitlines()[0].split(";"),
                                 list(row.values))

    def test_reading_is_a_generator_and_not_a_list(self) -> None:
        # Es la propiedad entera del rediseno: si esto devolviera una lista,
        # cien mil filas volverian a vivir en memoria a la vez.
        preamble, reader = sniff(io.BytesIO(CLEAN_CSV))
        produced = stream_records(reader, preamble)
        self.assertTrue(hasattr(produced, "__next__"))
        produced.close()


class FailureClassificationOfExtractionTests(unittest.TestCase):
    """De esta clasificacion depende si un trabajo se reintenta, muere o espera."""

    def test_an_unreadable_file_is_fatal_not_retryable(self) -> None:
        # El fichero es el que es. Reintentarlo tres veces daria lo mismo tres
        # veces y solo retrasaria el unico desenlace posible.
        error, failure = jobs.classify_extraction(ExtractionError("no se puede leer"))
        self.assertEqual("unextractable", error)
        self.assertEqual(jobs.FATAL, failure)

    def test_an_unreachable_object_is_retryable(self) -> None:
        # Puede ser el almacen y no la evidencia.
        error, failure = jobs.classify_extraction(ObjectStoreError("EndpointError"))
        self.assertEqual("evidence_unreadable", error)
        self.assertEqual(jobs.RETRYABLE, failure)

    def test_anything_else_waits_for_a_person(self) -> None:
        error, failure = jobs.classify_extraction(ValueError("algo raro"))
        self.assertEqual("extraction_error", error)
        self.assertEqual(jobs.UNKNOWN, failure)

    def test_every_reason_code_fits_the_bounded_vocabulary(self) -> None:
        # La base rechaza cualquier codigo que no encaje.
        for error in (ExtractionError("x"), ObjectStoreError("y"), ValueError("z")):
            with self.subTest(error=type(error).__name__):
                code, _ = jobs.classify_extraction(error)
                self.assertRegex(code, REASON_CODE)

    def test_an_unreadable_stream_is_classified_as_unextractable(self) -> None:
        """El camino real: leer basura levanta y el worker lo clasifica.

        La version anterior envolvia esto en un `try/except` sin `else` y sin
        `self.fail`, asi que el dia que `stream()` dejara de levantar la prueba
        habria seguido pasando en verde sin comprobar nada. Ahora la ausencia de
        excepcion es un fallo, que es lo que tenia que haber sido.
        """
        for payload in (b"", BINARY, b"solo cabecera"):
            with self.subTest(payload=payload[:8]):
                with self.assertRaises(ExtractionError) as caught:
                    stream(payload)
                code, failure = jobs.classify_extraction(caught.exception)
                self.assertEqual("unextractable", code)
                self.assertEqual(jobs.FATAL, failure)

    def test_a_divergent_conflict_is_fatal_and_not_retried(self) -> None:
        """Dos lecturas del mismo tramo que no coinciden no se reintentan.

        Reintentar leeria lo mismo y volveria a chocar. Lo que hace falta es que
        alguien mire por que no coinciden, y por eso es `fatal` y no reintentable.
        """
        code, failure = jobs.classify_extraction(
            jobs.RawRecordConflict("records 3, 4 already exist with other content"))
        self.assertEqual("raw_record_conflict", code)
        self.assertEqual(jobs.FATAL, failure)


if __name__ == "__main__":
    unittest.main()
