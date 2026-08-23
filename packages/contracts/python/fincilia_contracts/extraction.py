"""Extraccion fiel de un CSV, con la coordenada exacta de cada celda.

El perfilador cuenta y mide sin transcribir nada. Esto es lo contrario: aqui si
salen los valores, y por eso todo lo que produce arrastra su procedencia.

Lo que hace que esta extraccion sea *fiel* son tres cosas:

* **el valor se devuelve tal cual se leyo.** Sin recortar, sin normalizar, sin
  interpretar. Interpretar es trabajo del mapeo, y mezclarlos haria imposible
  contestar «que decia el fichero» sin volver a descargarlo;
* **cada fila lleva su tramo de bytes** dentro del artefacto, y cada celda su
  ordinal de campo. El contrato de linaje prohibe el localizador opaco
  universal: una coordenada que no permite volver al fichero y comprobar no es
  una coordenada, es una promesa;
* **los limites se declaran y se dicen.** Un fichero que excede el limite sale
  marcado `truncated`, nunca recortado en silencio.

Nada de esto decide nada economico. `direction`, importes y fechas son cosa de
`mapping`, que trabaja sobre lo que aqui sale.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from typing import Final, Iterator

from .profiling import (
    CANDIDATE_DELIMITERS,
    MAX_COLUMNS,
    SNIFF_BYTES,
    UnprofilableFile,
    clean_header,
    decode,
    sniff_delimiter,
)

# Limites declarados. El primero que se alcance detiene la lectura y lo dice.
MAX_EXTRACT_ROWS: Final[int] = 200_000
MAX_EXTRACT_BYTES: Final[int] = 64 * 1024 * 1024
MAX_CELL_LENGTH: Final[int] = 4_096
MAX_EXTRACT_SECONDS: Final[float] = 60.0
# Cada cuantas filas se mira el reloj. Mirarlo en cada fila cuesta mas que leer.
DEADLINE_EVERY: Final[int] = 500

LOCATOR_KIND: Final[str] = "tabular_delimited"

# Motivos por los que una lectura se detuvo antes de acabar. Son estados, no
# fallos: el trabajo termina bien y la interfaz dice lo que falta.
TRUNCATION_REASONS: Final[tuple[str, ...]] = ("row_limit", "byte_limit", "time_limit")


class ExtractionError(ValueError):
    """El fichero no se puede leer como tabla delimitada."""


@dataclass(frozen=True)
class ExtractedRow:
    """Una fila del fichero y donde estaba.

    `record_ordinal` cuenta registros del fichero empezando en 1, incluida la
    cabecera. No cuenta lineas: un campo entrecomillado puede llevar saltos de
    linea dentro, y contar lineas desplazaria la referencia de todo lo que viene
    despues.
    """

    record_ordinal: int
    byte_start: int
    byte_end: int
    values: tuple[str, ...]

    def locator(self, artifact_sha256: str) -> dict[str, object]:
        """Coordenada de la fila dentro de la version del artefacto."""
        return {
            "locator_kind": LOCATOR_KIND,
            "artifact_sha256": artifact_sha256,
            "record_ordinal": self.record_ordinal,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "field_count": len(self.values),
        }

    def cell_locator(self, artifact_sha256: str, field_ordinal: int) -> dict[str, object]:
        """Coordenada de una celda: fichero, fila y columna.

        Un ordinal fuera de las columnas declaradas es invalido, no un hueco:
        `out_of_bounds_outcome: invalid` en el contrato de localizadores.
        """
        if not 0 <= field_ordinal < len(self.values):
            raise ExtractionError(
                f"field ordinal {field_ordinal} is outside the {len(self.values)} "
                "columns of this record")
        locator = self.locator(artifact_sha256)
        locator["field_ordinal"] = field_ordinal
        return locator


@dataclass(frozen=True)
class Extraction:
    """El resultado de leer un fichero: cabecera, filas y que se dejo fuera."""

    encoding: str
    delimiter: str
    header: tuple[str, ...]
    header_row: int
    first_data_row: int
    rows: tuple[ExtractedRow, ...]
    truncated: bool
    truncation_reason: str | None
    ragged_rows: int

    @property
    def column_count(self) -> int:
        return len(self.header)

    def data_rows(self, first_data_row: int | None = None) -> tuple[ExtractedRow, ...]:
        """Los registros que el preparador declaro como datos.

        Es una seleccion sobre lo ya leido, no otra lectura: mover la cabecera
        no vuelve a tocar la evidencia.
        """
        start = self.first_data_row if first_data_row is None else first_data_row
        return tuple(row for row in self.rows if row.record_ordinal >= start)

    def as_dict(self) -> dict[str, object]:
        """Resumen sin valores: es lo que se guarda en el resultado del trabajo.

        El resultado de una ejecucion lo lee cualquiera que pueda ver el
        documento. Las filas van a `raw_record`, que exige contexto de empresa.
        """
        return {
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "header": list(self.header),
            "header_row": self.header_row,
            "first_data_row": self.first_data_row,
            "column_count": self.column_count,
            "record_count": len(self.rows),
            "row_count": len(self.data_rows()),
            "ragged_rows": self.ragged_rows,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
        }


class _LineFeeder:
    """Alimenta al lector CSV linea a linea y recuerda cuantas consumio.

    Es la unica forma de saber que tramo de bytes ocupa un registro cuando un
    campo entrecomillado puede abarcar varias lineas. `csv.reader` consume del
    iterador solo lo que necesita, asi que contar consumos da el tramo exacto.
    """

    def __init__(self, text: str, wire_encoding: str, byte_prefix: int) -> None:
        self._lines = text.splitlines(keepends=True)
        self._spans: list[tuple[int, int]] = []
        offset = byte_prefix
        for line in self._lines:
            size = len(line.encode(wire_encoding, errors="replace"))
            self._spans.append((offset, offset + size))
            offset += size
        self.consumed = 0
        self.total_bytes = offset

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        if self.consumed >= len(self._lines):
            raise StopIteration
        line = self._lines[self.consumed]
        self.consumed += 1
        return line

    def span(self, first_line: int) -> tuple[int, int]:
        """Tramo de bytes de las lineas consumidas desde `first_line`."""
        if first_line >= len(self._spans):
            return (self.total_bytes, self.total_bytes)
        last = min(self.consumed, len(self._spans)) - 1
        last = max(last, first_line)
        return (self._spans[first_line][0], self._spans[last][1])


UTF8_BOM: Final[bytes] = bytes.fromhex("efbbbf")


def _wire_encoding(encoding: str, payload: bytes) -> tuple[str, int]:
    """Como volver a bytes, y cuantos bytes se comio el decodificador.

    Dos trampas, y las dos desplazan todos los tramos si se pasan por alto:

    * `utf-8-sig` quita la marca de orden al decodificar y la **anade** al
      codificar. Medir lineas con el insertaria tres bytes en cada una;
    * decodificar con `utf-8-sig` funciona igual de bien sobre un fichero **sin**
      marca, asi que el nombre del codec no dice si habia marca. Lo dice el
      fichero, y por eso se mira.
    """
    if encoding == "utf-8-sig":
        return "utf-8", len(UTF8_BOM) if payload.startswith(UTF8_BOM) else 0
    return encoding, 0


def extract(payload: bytes, *, header_row: int = 1, first_data_row: int | None = None,
            max_rows: int = MAX_EXTRACT_ROWS,
            max_seconds: float = MAX_EXTRACT_SECONDS,
            delimiter: str | None = None) -> Extraction:
    """Lee un CSV entero devolviendo **cada registro** con su coordenada.

    Salen tambien el membrete y la cabecera. Extraer es leer el fichero; decidir
    que filas son datos es interpretar, y eso es del mapeo. Separarlo asi tiene
    una consecuencia practica: cambiar de opinion sobre donde empieza la tabla no
    obliga a volver a descargar y releer la evidencia.

    `header_row` y `first_data_row` cuentan registros desde 1 y aqui solo sirven
    para nombrar las columnas y para olfatear el separador; quien los aplica de
    verdad es `ColumnMapping`.
    """
    if len(payload) > MAX_EXTRACT_BYTES:
        raise ExtractionError(
            f"artifact exceeds the declared extraction limit of {MAX_EXTRACT_BYTES} bytes")
    if header_row < 1:
        raise ExtractionError("header_row is 1-based")
    if first_data_row is None:
        first_data_row = header_row + 1
    if first_data_row <= header_row:
        raise ExtractionError("first_data_row must come after header_row")

    try:
        text, encoding = decode(payload)
    except UnprofilableFile as error:
        raise ExtractionError(str(error)) from error
    if not text.strip():
        raise ExtractionError("the artifact has no readable content")

    # El olfateo empieza en la cabecera declarada, no en el principio del
    # fichero. Un membrete de tres lineas sin separadores decidiria que la tabla
    # tiene una sola columna, y el preparador ya dijo donde empieza la tabla.
    #
    # Contar lineas para posicionarse es una aproximacion: un campo
    # entrecomillado con salto de linea la descuadra. Por eso, si la cuenta se
    # sale del fichero, se olfatea el fichero entero y ya esta; quien decide de
    # verdad si la cabecera existe es el bucle de abajo, que cuenta registros.
    sample_from = 0
    for _ in range(header_row - 1):
        newline = text.find("\n", sample_from)
        if newline < 0:
            sample_from = 0
            break
        sample_from = newline + 1
    try:
        chosen = delimiter or sniff_delimiter(text[sample_from:sample_from + SNIFF_BYTES])
    except UnprofilableFile as error:
        raise ExtractionError(str(error)) from error
    if chosen not in CANDIDATE_DELIMITERS:
        raise ExtractionError(
            "no delimiter found from the declared header row onward; a single-column "
            f"file is not a statement (got {chosen!r})")

    wire, prefix = _wire_encoding(encoding, payload)
    feeder = _LineFeeder(text, wire, prefix)
    reader = csv.reader(feeder, delimiter=chosen)

    header: tuple[str, ...] = ()
    rows: list[ExtractedRow] = []
    ragged = 0
    truncated = False
    reason: str | None = None
    ordinal = 0
    started = time.monotonic()

    while True:
        first_line = feeder.consumed
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            raise ExtractionError(f"malformed delimited file: {error}") from error
        ordinal += 1
        if len(values) > MAX_COLUMNS:
            raise ExtractionError(
                f"record {ordinal} declares {len(values)} columns, over the "
                f"limit of {MAX_COLUMNS}")
        # Una celda desmesurada no se recorta: recortarla convertiria un fichero
        # roto en uno que parece bueno.
        for value in values:
            if len(value) > MAX_CELL_LENGTH:
                raise ExtractionError(
                    f"a cell in record {ordinal} exceeds {MAX_CELL_LENGTH} characters")

        if ordinal == header_row:
            header = tuple(clean_header(value, f"columna_{index + 1}")
                           for index, value in enumerate(values))
        if not any(value.strip() for value in values):
            # Una linea en blanco no es un registro. El ordinal sigue avanzando:
            # la fila 7 del fichero se llama 7 en la pantalla y en el localizador.
            continue

        if header and ordinal >= first_data_row and len(values) != len(header):
            ragged += 1
        start, end = feeder.span(first_line)
        rows.append(ExtractedRow(record_ordinal=ordinal, byte_start=start,
                                 byte_end=end, values=tuple(values)))

        if len(rows) >= max_rows:
            truncated, reason = True, "row_limit"
            break
        if len(rows) % DEADLINE_EVERY == 0 and time.monotonic() - started > max_seconds:
            truncated, reason = True, "time_limit"
            break

    if not header:
        raise ExtractionError(f"record {header_row} declared as header does not exist")
    result = Extraction(encoding=encoding, delimiter=chosen, header=header,
                        header_row=header_row, first_data_row=first_data_row,
                        rows=tuple(rows), truncated=truncated,
                        truncation_reason=reason, ragged_rows=ragged)
    if not result.data_rows() and not truncated:
        raise ExtractionError("the artifact has a header but no data rows")
    return result


def slice_of(payload: bytes, row: ExtractedRow) -> bytes:
    """Los bytes exactos que ocupa una fila. Sirve para comprobar el localizador.

    Si esto no devuelve la fila, el localizador miente, y un localizador que
    miente es peor que no tenerlo: sostiene una auditoria que no se sostiene.
    """
    return payload[row.byte_start:row.byte_end]


def preview_page(extraction: Extraction, *, offset: int = 0,
                 limit: int = 50) -> tuple[ExtractedRow, ...]:
    """Una pagina de filas. La vista previa **siempre** pagina.

    Devolver el fichero entero por una peticion convertiria la vista previa en
    una descarga de la evidencia con otro nombre.
    """
    if offset < 0 or limit < 1:
        raise ExtractionError("offset must be zero or more and limit at least one")
    return extraction.rows[offset:offset + limit]
