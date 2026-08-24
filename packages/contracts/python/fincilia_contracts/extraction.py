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
import hashlib
import io
import time
from dataclasses import dataclass
from typing import Final, Iterator

from .profiling import (
    CANDIDATE_DELIMITERS,
    ENCODINGS,
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

# Y por que puede no terminar. Un truncamiento acaba bien y no publica; un fallo
# no acaba. Mezclarlos dejaria «se dejo de leer» indistinguible de «se leyo
# entero», que es justo la diferencia que importa.
FAILURE_REASONS: Final[tuple[str, ...]] = (
    "malformed_delimited_file", "too_many_columns", "cell_too_long",
    "encoding_mismatch", "no_data_rows", "object_digest_mismatch", "reader_error",
)

# Las codificaciones admitidas, en el orden en que `decode()` las prueba y sin la
# marca de orden, que no es un codec distinto sino el mismo con tres bytes
# delante. Es la lista que usa la promocion, y tiene que ser esta y no otra: si
# la corriente probara otro orden, elegiria un codec distinto del que elige
# `extract()` sobre el mismo fichero.
WIRE_ENCODINGS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys("utf-8" if name == "utf-8-sig" else name for name in ENCODINGS))


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


def _lf_lines(text: str) -> list[str]:
    """Corta solo por `\n`, conservando el salto. Igual que la corriente.

    `str.splitlines()` corta ademas por ocho puntos de codigo que no terminan un
    registro CSV: tabulacion vertical, avance de pagina, los separadores de
    fichero, grupo y registro, y los de linea y parrafo de Unicode. Usarlo aqui
    hacia que el lector entero y el de corriente partieran el mismo fichero en
    registros distintos, y entonces «el mismo fichero» dejaba de ser el mismo
    segun quien lo leyera. Un campo entrecomillado con un avance de pagina dentro
    era un registro para uno y dos para el otro.
    """
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


class _LineFeeder:
    """Alimenta al lector CSV linea a linea y recuerda cuantas consumio.

    Es la unica forma de saber que tramo de bytes ocupa un registro cuando un
    campo entrecomillado puede abarcar varias lineas. `csv.reader` consume del
    iterador solo lo que necesita, asi que contar consumos da el tramo exacto.
    """

    def __init__(self, text: str, wire_encoding: str, byte_prefix: int) -> None:
        self._lines = _lf_lines(text)
        self._spans: list[tuple[int, int]] = []
        offset = byte_prefix
        for line in self._lines:
            # Sin `errors`: el texto salio de decodificar estos mismos bytes con
            # este mismo codec, asi que volver a codificarlo es exacto. Un
            # `replace` aqui solo podria tapar un fallo que hay que ver.
            size = len(line.encode(wire_encoding))
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
    emitted = 0
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

        is_data = ordinal >= first_data_row
        # `max_rows` significa filas de datos en las dos rutas. Hay que mirar
        # si existe una fila adicional antes de declarar truncamiento: un
        # fichero con exactamente el limite esta completo, no cortado.
        if is_data and emitted >= max_rows:
            truncated, reason = True, "row_limit"
            break
        if header and is_data and len(values) != len(header):
            ragged += 1
        start, end = feeder.span(first_line)
        rows.append(ExtractedRow(record_ordinal=ordinal, byte_start=start,
                                 byte_end=end, values=tuple(values)))
        if is_data:
            emitted += 1
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


# --------------------------------------------------------------------------- #
# Lectura incremental (FNC-P3.6)
# --------------------------------------------------------------------------- #

# Cuanto se lee de golpe del almacen. Ni tan poco que cada fila cueste un viaje,
# ni tanto que el buffer sea el fichero otra vez.
READ_CHUNK: Final[int] = 256 * 1024

# Cuanto hace falta ver para decidir codificacion, separador y cabecera. Es una
# muestra acotada a proposito: si hiciera falta el fichero entero para saber como
# leerlo, no habria forma de leerlo por partes.
SNIFF_WINDOW: Final[int] = 64 * 1024

@dataclass(frozen=True)
class Preamble:
    """Lo que hay que saber **antes** de leer una fila.

    Sale de una muestra acotada del principio del fichero. Todo lo demas se lee
    en corriente, sin volver atras y sin guardar lo que ya paso.
    """

    encoding: str
    wire_encoding: str
    delimiter: str
    header: tuple[str, ...]
    header_row: int
    first_data_row: int
    byte_prefix: int

    @property
    def column_count(self) -> int:
        return len(self.header)


@dataclass
class StreamOutcome:
    """Como acabo una lectura. Se rellena mientras se lee, no al final.

    `state` es lo que decide si esto puede publicarse: `complete` si, y
    `truncated` o `failed` no. Una lectura a medias que dijera `complete` haria
    que un total cuadrara consigo mismo con filas de menos.
    """

    state: str = "complete"
    reason: str | None = None
    records: int = 0
    data_rows: int = 0
    ragged_rows: int = 0
    bytes_read: int = 0
    # Dos huellas, dos preguntas. `object_digest` es sha256 de los bytes tal y
    # como salieron del almacen —contesta «esto es lo que se subio»— y
    # `record_digest` resume los registros ya entendidos —contesta «esta lectura
    # vio lo mismo que aquella»—. La version anterior tenia una sola, llamada
    # `content_digest`, que no era la del contenido y por tanto no contestaba la
    # primera.
    object_digest: str = ""
    record_digest: str = ""
    # Con que codec se acabo leyendo. Puede no ser el que eligio la muestra.
    effective_encoding: str = ""

    def as_dict(self) -> dict[str, object]:
        return {"state": self.state, "truncation_reason": self.reason,
                "truncated": self.state == "truncated",
                "failed": self.state == "failed",
                "record_count": self.records, "row_count": self.data_rows,
                "ragged_rows": self.ragged_rows, "bytes_read": self.bytes_read,
                "object_digest": self.object_digest,
                "record_digest": self.record_digest,
                "effective_encoding": self.effective_encoding}


class _HeadReader:
    """Un lector que ya leyo el principio y lo devuelve antes que el resto.

    Olfatear exige mirar el principio; leer en corriente exige no volver atras.
    Guardar esa muestra y anteponerla resuelve las dos cosas sin pedirle al
    almacen un segundo `GET` del mismo objeto.
    """

    def __init__(self, head: bytes, rest) -> None:
        self._head = head
        self._rest = rest
        self._offset = 0

    def read(self, size: int) -> bytes:
        if self._offset < len(self._head):
            chunk = self._head[self._offset:self._offset + size]
            self._offset += len(chunk)
            return chunk
        if self._rest is None:
            return b""
        return self._rest.read(size)

    def close(self) -> None:
        closer = getattr(self._rest, "close", None)
        if closer is not None:
            closer()


class _RawTap:
    """Cuenta y resume los bytes **antes** de entenderlos.

    La huella se toma sobre lo que sale del almacen, sin decodificar y sin quitar
    la marca de orden: es la del objeto, no la de lo que se entendio de el.
    Compararla con `source_artifact.content_sha256` contesta una pregunta que
    ninguna otra comprobacion contesta —si lo leido es lo subido— y que hasta
    ahora nadie hacia.
    """

    def __init__(self, reader) -> None:
        self._reader = reader
        self._digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size: int) -> bytes:
        chunk = self._reader.read(size)
        if chunk:
            self._digest.update(chunk)
            self.bytes_read += len(chunk)
        return chunk

    @property
    def object_digest(self) -> str:
        return self._digest.hexdigest()


def _byte_lines(reader, *, chunk_size: int = READ_CHUNK):
    """Lineas crudas con su desplazamiento exacto, sin sostener el fichero.

    Se parte por bytes y **no** por texto decodificado. Las codificaciones que
    este producto admite —utf-8 y las de un byte— nunca usan `0x0A` dentro de un
    caracter, asi que cortar por el salto de linea no puede partir uno por la
    mitad. Y trabajar en bytes hace que el desplazamiento sea exacto por
    construccion, en vez de una conversion que hay que acertar.
    """
    offset = 0
    buffer = b""
    while True:
        chunk = reader.read(chunk_size)
        if not chunk:
            break
        buffer += chunk
        while True:
            index = buffer.find(b"\n")
            if index < 0:
                break
            line = buffer[:index + 1]
            yield offset, line
            offset += len(line)
            buffer = buffer[index + 1:]
    if buffer:
        yield offset, buffer


class _StreamFeeder:
    """Alimenta al lector CSV y recuerda **solo** el tramo del registro en curso.

    La version anterior guardaba el tramo de todas las lineas del fichero para
    poder contestar por cualquiera. Esta contesta por la que se esta leyendo, que
    es la unica por la que alguien pregunta, y por eso no crece.
    """

    def __init__(self, lines, preamble: Preamble) -> None:
        self._lines = lines
        self._encoding = preamble.wire_encoding
        self._prefix = preamble.byte_prefix
        self._spans: list[tuple[int, int]] = []
        self._first = True
        # Mientras cuanto se ha leido sea ASCII, cambiar de codec no reinterpreta
        # ni una linea anterior: las cuatro codificaciones admitidas coinciden en
        # ASCII byte a byte. En cuanto se decodifica un caracter que no lo es, el
        # codec ha afirmado algo sobre esos bytes y ya no se puede cambiar de
        # opinion sin cambiar filas que ya salieron.
        self._ascii_so_far = True
        self.promoted_from: str | None = None
        self.bytes_read = 0

    @property
    def encoding(self) -> str:
        return self._encoding

    def __iter__(self):
        return self

    def __next__(self) -> str:
        offset, raw = next(self._lines)
        start = offset
        if self._first:
            self._first = False
            if self._prefix and raw.startswith(UTF8_BOM):
                # La marca de orden se come tres bytes y no es contenido. El
                # registro empieza despues de ella.
                raw = raw[len(UTF8_BOM):]
                start += len(UTF8_BOM)
        self._spans.append((start, offset + len(raw) + (start - offset)))
        self.bytes_read = offset + len(raw) + (start - offset)
        return self._decode(raw)

    def _decode(self, raw: bytes) -> str:
        """Decodifica sin red. Un byte que no se entiende no se sustituye.

        La version anterior pasaba `errors="replace"`, y eso convertia
        `Comision cafe` en `Comision caf` con un caracter de reemplazo dentro,
        dejando el desenlace en `complete`. Una evidencia parecida a la real es
        peor que ninguna: se publica, cuadra, y nadie mira dos veces.
        """
        if b"\x00" in raw:
            # `decode()` mira los primeros kilobytes; mas alla no lo miraba
            # nadie, y `latin-1` decodifica el NUL sin protestar. Un binario con
            # cabecera de texto se «extraia» en columnas de basura.
            raise ExtractionError(
                "the artifact contains control bytes and is not text")
        try:
            text = raw.decode(self._encoding)
        except UnicodeDecodeError as error:
            text = self._promote(raw, error)
        if self._ascii_so_far and not raw.isascii():
            self._ascii_so_far = False
        return text

    def _promote(self, raw: bytes, error: UnicodeDecodeError) -> str:
        """Vuelve a decidir la codificacion, y solo cuando es demostrable.

        La muestra que eligio el codec puede ser ASCII entera y el primer byte
        acentuado aparecer mucho mas alla de ella. Ese fichero es legitimo y
        `extract()` lo lee bien, porque decodifica el fichero entero. Rechazarlo
        aqui seria perder una capacidad que el producto ya tiene.

        Asi que se promociona, pero solo mientras todo lo leido haya sido ASCII,
        que es cuando cambiar de codec no toca ni una fila anterior. Si ya se
        habia decodificado algo que no era ASCII, se levanta: el fichero no es
        consistentemente decodificable, y seguir seria elegir en silencio cual de
        las dos lecturas vale.
        """
        if not self._ascii_so_far:
            raise ExtractionError(
                "the file stops being decodable as "
                f"{self._encoding!r} after a non-ASCII character was already "
                "read; two different encodings cannot both be right")
        for candidate in WIRE_ENCODINGS:
            if candidate == self._encoding:
                continue
            try:
                text = raw.decode(candidate)
            except UnicodeDecodeError:
                continue
            self.promoted_from = self._encoding
            self._encoding = candidate
            return text
        raise ExtractionError(
            "the file is not decodable as text in any supported encoding "
            f"(failed at byte {error.start} of a record)")

    def take_span(self) -> tuple[int, int] | None:
        """El tramo de las lineas consumidas desde la ultima llamada."""
        if not self._spans:
            return None
        span = (self._spans[0][0], self._spans[-1][1])
        self._spans.clear()
        return span


def sniff(reader, *, header_row: int = 1,
          delimiter: str | None = None) -> tuple[Preamble, _HeadReader]:
    """Decide codificacion, separador y cabecera con una muestra acotada.

    Devuelve el preambulo y un lector que vuelve a entregar esa muestra antes que
    el resto: asi se olfatea sin pedir el objeto dos veces y sin poder volver
    atras despues.
    """
    if header_row < 1:
        raise ExtractionError("header_row is 1-based")
    # Un `read` puede devolver menos de lo pedido sin que se haya acabado el
    # objeto —un cuerpo HTTP lo hace a menudo— y decidir la codificacion sobre
    # media muestra es decidirla sobre otra cosa.
    head = b""
    while len(head) < SNIFF_WINDOW:
        chunk = reader.read(SNIFF_WINDOW - len(head))
        if not chunk:
            break
        head += chunk
    if not head:
        raise ExtractionError("the artifact has no readable content")

    # La ventana es un corte por bytes y puede caer **dentro** de un caracter
    # multibyte. Si eso pasa, `utf-8` falla por el trozo suelto y gana `cp1252`,
    # que decodifica cualquier byte sin quejarse: el fichero entero se leeria mal
    # por culpa de donde cayo el corte, y sin un solo error. Se decide sobre
    # lineas completas, que por construccion nunca parten un caracter.
    sample = head
    if len(head) == SNIFF_WINDOW:
        boundary = head.rfind(b"\n")
        if boundary >= 0:
            sample = head[:boundary + 1]

    try:
        text, encoding = decode(sample)
    except UnprofilableFile as error:
        raise ExtractionError(str(error)) from error
    if not text.strip():
        raise ExtractionError("the artifact has no readable content")

    # El olfateo empieza en la cabecera declarada, no en el principio: un
    # membrete de tres lineas sin separadores decidiria que la tabla tiene una
    # sola columna.
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
            "no delimiter found from the declared header row onward; a "
            f"single-column file is not a statement (got {chosen!r})")

    wire = "utf-8" if encoding == "utf-8-sig" else encoding
    prefix = len(UTF8_BOM) if head.startswith(UTF8_BOM) else 0

    # La cabecera se lee de la muestra, que es donde tiene que estar: una
    # cabecera a sesenta kilobytes del principio no es una cabecera.
    header: tuple[str, ...] = ()
    for ordinal, values in enumerate(csv.reader(io.StringIO(text),
                                                delimiter=chosen), 1):
        if ordinal == header_row:
            header = tuple(clean_header(value, f"columna_{index + 1}")
                           for index, value in enumerate(values))
            break
    if not header:
        raise ExtractionError(
            f"record {header_row} declared as header is not within the first "
            f"{SNIFF_WINDOW} bytes")

    return (Preamble(encoding=encoding, wire_encoding=wire, delimiter=chosen,
                     header=header, header_row=header_row,
                     first_data_row=header_row + 1, byte_prefix=prefix),
            _HeadReader(head, reader))


def stream_records(reader, preamble: Preamble, *, artifact_sha256: str = "",
                   max_rows: int = MAX_EXTRACT_ROWS,
                   max_bytes: int = MAX_EXTRACT_BYTES,
                   max_seconds: float = MAX_EXTRACT_SECONDS,
                   outcome: StreamOutcome | None = None):
    """Emite registros uno a uno, con su coordenada exacta y sin acumular nada.

    Es un generador a proposito: quien lo consume decide cuantos sostiene a la
    vez. La version anterior devolvia la lista entera, y con cien mil filas eso
    eran doscientos megabytes antes de escribir la primera.

    `outcome` se rellena **mientras** se lee. Si se agota el limite de filas o de
    tiempo, el estado pasa a `truncated` y el generador termina: una lectura a
    medias que dijera `complete` haria que un total cuadrara consigo mismo con
    filas de menos.
    """
    report = outcome if outcome is not None else StreamOutcome()
    tap = _RawTap(reader)
    feeder = _StreamFeeder(_byte_lines(tap), preamble)
    csv_reader = csv.reader(feeder, delimiter=preamble.delimiter)
    digest = hashlib.sha256()
    started = time.monotonic()
    ordinal = 0
    emitted = 0

    try:
        while True:
            # El techo de bytes se comprueba antes de pedir el siguiente
            # registro. Leyendo por partes no se sabe cuanto ocupa el fichero
            # hasta que se acaba, asi que la unica forma de aplicarlo es dejar de
            # leer al alcanzarlo y decirlo.
            if tap.bytes_read > max_bytes:
                report.state = "truncated"
                report.reason = "byte_limit"
                break
            # El reloj se mira en cada vuelta y no cada quinientas filas de
            # datos. Con la condicion anterior, un fichero de cuatrocientas filas
            # —o uno lleno de lineas en blanco, que no cuentan como datos— no
            # miraba el reloj **jamas**, y el limite de tiempo declarado no
            # existia para el. Una llamada a `monotonic` por registro es ruido al
            # lado de analizar el registro.
            if time.monotonic() - started > max_seconds:
                report.state = "truncated"
                report.reason = "time_limit"
                break
            try:
                values = next(csv_reader)
            except StopIteration:
                break
            except csv.Error as error:
                report.state = "failed"
                report.reason = "malformed_delimited_file"
                raise ExtractionError(f"malformed delimited file: {error}") from error

            span = feeder.take_span()
            if span is None or span[1] <= span[0]:
                report.state = "failed"
                report.reason = "locator_unavailable"
                raise ExtractionError(
                    f"record {ordinal + 1} has no non-empty byte span; its "
                    "evidence locator cannot be proven")
            ordinal += 1
            if len(values) > MAX_COLUMNS:
                report.state = "failed"
                report.reason = "too_many_columns"
                raise ExtractionError(
                    f"record {ordinal} declares {len(values)} columns, over the "
                    f"limit of {MAX_COLUMNS}")
            for value in values:
                if len(value) > MAX_CELL_LENGTH:
                    # Recortarla convertiria un fichero roto en uno que parece
                    # bueno.
                    report.state = "failed"
                    report.reason = "cell_too_long"
                    raise ExtractionError(
                        f"a cell in record {ordinal} exceeds {MAX_CELL_LENGTH} "
                        "characters")

            if not any(value.strip() for value in values):
                continue

            is_data = ordinal >= preamble.first_data_row
            # El techo se comprueba **antes** de emitir, y solo cuando hay otra
            # fila de verdad. Comprobarlo despues marcaba truncado un fichero de
            # exactamente `max_rows` filas, que esta entero: el operador no
            # tendria forma de distinguirlo de uno al que le faltan filas, y un
            # truncamiento bloquea la publicacion.
            if is_data and emitted >= max_rows:
                report.state = "truncated"
                report.reason = "row_limit"
                break

            # Huella incremental sobre lo leido, en orden. No hace falta tener el
            # fichero para saber si dos lecturas vieron lo mismo.
            #
            # Va con la longitud delante de cada valor y no con separadores. Los
            # separadores que llevaba —0x1F y 0x1E— pueden aparecer dentro de un
            # valor, y entonces dos conjuntos distintos dan la misma huella:
            # `["a\x1fb"]` y `["a", "b"]` se resumian igual. Con la longitud
            # delante eso no puede pasar, porque la huella se puede deshacer.
            digest.update(f"{ordinal}:{len(values)}|".encode("ascii"))
            for value in values:
                encoded = value.encode("utf-8", "surrogatepass")
                digest.update(f"{len(encoded)}:".encode("ascii"))
                digest.update(encoded)

            # `record_count` describe cuantas filas se emitieron y, por tanto,
            # cuantas puede haber en `raw_record`. El ordinal conserva la
            # posicion fisica e incluye huecos en blanco; usarlo como recuento
            # hacia que el resumen afirmara mas filas que las persistidas.
            report.records += 1
            if is_data:
                emitted += 1
                report.data_rows = emitted
                if preamble.header and len(values) != len(preamble.header):
                    report.ragged_rows += 1

            # El limite pertenece a la extraccion, no al consumidor. Mientras
            # el generador esta suspendido en ``yield`` el worker puede estar
            # esperando a PostgreSQL, aplicando backpressure o renovando un
            # lease. Contar esa espera convertia una persistencia lenta en un
            # fichero truncado y hacia depender el resultado financiero de la
            # latencia de infraestructura. Desplazar el origen del reloj por el
            # tiempo suspendido conserva el limite sobre lectura/parsing sin
            # esconder un lector realmente lento.
            suspended_at = time.monotonic()
            try:
                yield ExtractedRow(record_ordinal=ordinal, byte_start=span[0],
                                   byte_end=span[1], values=tuple(values))
            finally:
                started += time.monotonic() - suspended_at

        if report.state == "complete":
            # Lo leido tiene que ser lo subido. Solo se puede comprobar sobre una
            # lectura entera: una truncada resume un prefijo, y comparar su
            # huella diria «el fichero cambio» cuando lo que paso es que no se
            # acabo de leer.
            if artifact_sha256 and tap.object_digest != artifact_sha256:
                report.state = "failed"
                report.reason = "object_digest_mismatch"
                raise ExtractionError(
                    "the bytes read do not match the digest declared for this "
                    "artifact; the object is not the one that was uploaded")
            if report.data_rows == 0:
                # Una cabecera sin filas no es un extracto vacio: es un fichero
                # roto. Dejarlo pasar como `complete` produce un conjunto
                # publicable que no dice nada, y nadie mira dos veces un cero.
                report.state = "failed"
                report.reason = "no_data_rows"
                raise ExtractionError(
                    "the artifact declares a header and carries no data rows")
    except ExtractionError:
        raise
    except Exception:
        # Cualquier otra cosa —el almacen que se cae, la conexion que se corta—
        # deja el desenlace en `failed`. Que quedara en `complete` hacia
        # indistinguible «se leyo entero» de «se dejo de leer», y la primera
        # alimenta una publicacion.
        if report.state == "complete":
            report.state = "failed"
            report.reason = "reader_error"
        raise
    finally:
        report.bytes_read = feeder.bytes_read
        report.object_digest = tap.object_digest
        report.record_digest = digest.hexdigest()
        report.effective_encoding = feeder.encoding
        # Cerrar pase lo que pase: una excepcion a mitad no puede dejar abierta
        # una conexion al almacen.
        closer = getattr(reader, "close", None)
        if closer is not None:
            closer()


def extraction_summary(preamble: Preamble, outcome: StreamOutcome) -> dict[str, object]:
    """El resumen que se guarda en el resultado de la ejecucion. Sin valores.

    Lo lee cualquiera que pueda ver el documento; las filas viven en
    `raw_record`, que exige contexto de empresa.
    """
    return {
        # `encoding` es lo que decidio la muestra; `effective_encoding`, dentro de
        # `as_dict`, es con lo que se acabo leyendo. Suelen coincidir, y cuando no,
        # decirlo es la diferencia entre una lectura explicada y una afortunada.
        "encoding": preamble.encoding,
        "delimiter": preamble.delimiter,
        "header": list(preamble.header),
        "header_row": preamble.header_row,
        "first_data_row": preamble.first_data_row,
        "column_count": preamble.column_count,
        **outcome.as_dict(),
    }
