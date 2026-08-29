"""Perfilado de ficheros tabulares. Solo biblioteca estandar, sin efectos.

El perfil describe la **forma** de un fichero para que alguien pueda mapearlo:
que delimitador usa, si trae cabecera, cuantas filas tiene y de que tipo parece
cada columna. Es lo que el worker calcula despues de que un fichero salga de
cuarentena.

Dos reglas gobiernan el modulo y explican casi todas sus decisiones:

**Un perfil no lleva valores.** Ni ejemplos, ni minimos, ni maximos. Si los
llevara, el perfil seria una copia parcial del fichero viviendo donde vive el
metadato, con otras reglas de acceso y otra vida util. Se cuentan valores, se
miden longitudes, no se transcriben.

**Ante una ambiguedad de dinero o de fecha, no se adivina.** `1.234` puede ser
mil doscientos treinta y cuatro o uno coma doscientos treinta y cuatro, y
`02/01/2026` puede ser el 2 de enero o el 1 de febrero. Elegir en silencio
convierte un error de lectura en un asiento contable equivocado que nadie va a
revisar. El perfil dice `ambiguous_numeric` o `ambiguous_date` y deja la decision
para el mapeo, que es donde hay una persona mirando.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Final

MAX_PROFILE_ROWS: Final[int] = 200_000
MAX_COLUMNS: Final[int] = 512
MAX_HEADER_LENGTH: Final[int] = 120
SNIFF_BYTES: Final[int] = 8192
CANDIDATE_DELIMITERS: Final[tuple[str, ...]] = (",", ";", "\t", "|")
ENCODINGS: Final[tuple[str, ...]] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
# Separador que no aparece en texto tabular real. Se usa cuando el fichero
# tiene una sola columna: cada linea es un unico campo, sin inventar un
# delimitador que si podria aparecer en los datos.
SINGLE_COLUMN: Final[str] = "\x1f"
# Caracteres de control que nunca forman parte de una etiqueta. Se quitan de
# las cabeceras: ademas de no significar nada, un NUL hace que el perfil no se
# pueda guardar como JSON y el trabajo se quedaria a medias.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

INTEGER = re.compile(r"^[+-]?\d+$")
# `1234.56` y `1,234.56`: punto decimal, coma opcional de miles.
DECIMAL_DOT = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*\.\d+$|^[+-]?\d+\.\d+$")
# `1234,56` y `1.234,56`: coma decimal, punto opcional de miles. El formato
# habitual en Colombia.
DECIMAL_COMMA = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})*,\d+$|^[+-]?\d+,\d+$")
# `1.234` o `1,234` a secas: no se puede saber si el separador es de miles o
# decimal, y por eso no se decide aqui.
AMBIGUOUS_NUMERIC = re.compile(r"^[+-]?\d{1,3}[.,]\d{3}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLASH_DATE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")
BOOLEAN_VALUES: Final[frozenset[str]] = frozenset({
    "true", "false", "si", "no", "sí", "s", "n", "1", "0", "yes"})

TYPES: Final[tuple[str, ...]] = (
    "empty", "integer", "decimal_dot", "decimal_comma", "ambiguous_numeric",
    "date_iso", "date_dmy", "date_mdy", "ambiguous_date", "boolean", "text")


class UnprofilableFile(ValueError):
    """El fichero no se puede perfilar. El motivo no repite su contenido."""


@dataclass
class ColumnProfile:
    """Forma de una columna. Cuenta y mide; nunca transcribe."""

    index: int
    header: str
    non_empty: int = 0
    empty: int = 0
    min_length: int = 0
    max_length: int = 0
    observed: dict[str, int] = field(default_factory=dict)

    def observe(self, value: str) -> None:
        stripped = value.strip()
        if not stripped:
            self.empty += 1
            self.observed["empty"] = self.observed.get("empty", 0) + 1
            return
        self.non_empty += 1
        length = len(stripped)
        self.min_length = length if self.non_empty == 1 else min(self.min_length, length)
        self.max_length = max(self.max_length, length)
        kind = classify(stripped)
        self.observed[kind] = self.observed.get(kind, 0) + 1

    @property
    def inferred_type(self) -> str:
        """El tipo mayoritario entre los valores presentes, o `text`.

        Una columna con un solo valor raro no cambia de tipo, pero tampoco se
        declara homogenea: `type_confidence` dice cuanto de la columna encaja.
        """
        present = {kind: count for kind, count in self.observed.items()
                   if kind != "empty"}
        if not present:
            return "empty"
        # Una lectura inequivoca en cualquier fila resuelve la columna entera:
        # un banco no cambia de formato a mitad de un extracto. Solo la
        # contradiccion real -- dos lecturas incompatibles presentes a la vez --
        # deja la columna sin decidir.
        numeric = {"integer", "decimal_dot", "decimal_comma", "ambiguous_numeric"}
        if set(present) <= numeric and "ambiguous_numeric" in present:
            decided = {"decimal_dot", "decimal_comma"} & set(present)
            if len(decided) == 1:
                return decided.pop()
            return "ambiguous_numeric"
        dates = {"date_iso", "date_dmy", "date_mdy", "ambiguous_date"}
        if set(present) <= dates and "ambiguous_date" in present:
            decided = {"date_dmy", "date_mdy"} & set(present)
            if len(decided) == 1:
                return decided.pop()
            return "ambiguous_date"
        return max(present.items(), key=lambda item: (item[1], item[0]))[0]

    @property
    def type_confidence(self) -> float:
        present = sum(count for kind, count in self.observed.items() if kind != "empty")
        if not present:
            return 0.0
        return round(self.observed.get(self.inferred_type, 0) / present, 4)

    @property
    def ambiguous(self) -> bool:
        return self.inferred_type in {"ambiguous_numeric", "ambiguous_date"}

    def as_dict(self) -> dict[str, object]:
        return {"index": self.index, "header": self.header,
                "non_empty": self.non_empty, "empty": self.empty,
                "min_length": self.min_length, "max_length": self.max_length,
                "inferred_type": self.inferred_type,
                "type_confidence": self.type_confidence,
                "ambiguous": self.ambiguous,
                "observed": dict(sorted(self.observed.items()))}


@dataclass(frozen=True)
class TableProfile:
    encoding: str
    delimiter: str
    has_header: bool
    row_count: int
    column_count: int
    ragged_rows: int
    truncated: bool
    columns: tuple[ColumnProfile, ...]

    @property
    def needs_decision(self) -> tuple[str, ...]:
        """Columnas que una persona tiene que resolver antes de mapear."""
        return tuple(column.header for column in self.columns if column.ambiguous)

    def as_dict(self) -> dict[str, object]:
        return {"encoding": self.encoding, "delimiter": self.delimiter,
                "has_header": self.has_header, "row_count": self.row_count,
                "column_count": self.column_count, "ragged_rows": self.ragged_rows,
                "truncated": self.truncated,
                "needs_decision": list(self.needs_decision),
                "columns": [column.as_dict() for column in self.columns]}


@dataclass(frozen=True)
class SpreadsheetTableProfile:
    """Forma de una hoja empaquetada; nunca contiene ejemplos de sus celdas."""

    sheet_name: str
    sheet_ordinal: int
    has_header: bool
    row_count: int
    column_count: int
    ragged_rows: int
    truncated: bool
    columns: tuple[ColumnProfile, ...]
    technical_format: str = "xlsx"
    effective_encoding: str = "xlsx-xml"

    @property
    def needs_decision(self) -> tuple[str, ...]:
        return tuple(column.header for column in self.columns if column.ambiguous)

    def as_dict(self) -> dict[str, object]:
        return {
            "technical_format": self.technical_format,
            "encoding": self.effective_encoding,
            "delimiter": "",
            "sheet_name": self.sheet_name,
            "sheet_ordinal": self.sheet_ordinal,
            "has_header": self.has_header,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "ragged_rows": self.ragged_rows,
            "truncated": self.truncated,
            "needs_decision": list(self.needs_decision),
            "columns": [column.as_dict() for column in self.columns],
        }


def classify(value: str) -> str:
    if AMBIGUOUS_NUMERIC.match(value):
        return "ambiguous_numeric"
    if INTEGER.match(value):
        return "integer"
    if DECIMAL_DOT.match(value):
        return "decimal_dot"
    if DECIMAL_COMMA.match(value):
        return "decimal_comma"
    if ISO_DATE.match(value):
        return "date_iso"
    match = SLASH_DATE.match(value)
    if match:
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 and second <= 12:
            return "date_dmy"
        if second > 12 and first <= 12:
            return "date_mdy"
        if first <= 12 and second <= 12:
            # Los dos caben como mes. No se elige: elegir mal mueve un asiento de
            # mes y nadie lo nota hasta el cierre.
            return "ambiguous_date"
        return "text"
    if value.lower() in BOOLEAN_VALUES and not value.isdigit():
        return "boolean"
    return "text"


def clean_header(value: str, fallback: str) -> str:
    cleaned = CONTROL.sub("", value).strip()[:MAX_HEADER_LENGTH]
    return cleaned or fallback


def decode(payload: bytes) -> tuple[str, str]:
    """Devuelve `(texto, codificacion)`. Prueba en orden y se queda con la primera.

    Un NUL descarta el fichero antes de intentar nada: `latin-1` decodifica
    cualquier byte, asi que sin esta comprobacion un binario se «perfilaria» y
    produciria columnas de basura en vez de un error claro.
    """
    if b"\x00" in payload[:SNIFF_BYTES]:
        raise UnprofilableFile("the file contains control bytes and is not text")
    for encoding in ENCODINGS:
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnprofilableFile("the file is not decodable as text in any supported encoding")


def sniff_delimiter(sample: str) -> str:
    """Delimitador por conteo consistente, no por el que mas aparece.

    Un texto libre lleno de comas ganaria por frecuencia. Lo que distingue a un
    delimitador de verdad es que aparece **el mismo numero de veces** en cada
    linea.
    """
    lines = [line for line in sample.splitlines() if line.strip()][:20]
    if not lines:
        raise UnprofilableFile("the file has no content to profile")
    best, best_score = "", (0, 0)
    for candidate in CANDIDATE_DELIMITERS:
        counts = [line.count(candidate) for line in lines]
        if not counts or max(counts) == 0:
            continue
        consistent = sum(1 for count in counts if count == counts[0])
        score = (consistent, counts[0])
        if counts[0] > 0 and score > best_score:
            best, best_score = candidate, score
    if not best:
        # Ningun candidato aparece de forma consistente. Eso no es un fichero
        # roto: es un fichero de una columna, o texto libre que no se puede
        # partir con garantias. En ambos casos, partirlo seria peor.
        return SINGLE_COLUMN
    return best


def looks_like_header(row: list[str]) -> bool:
    """Una cabecera es texto no vacio y sin repetidos.

    Si la primera fila trae numeros o fechas, es un dato y tratarla como cabecera
    perderia una fila entera sin decirlo.
    """
    if not row or any(not cell.strip() for cell in row):
        return False
    if len(set(cell.strip().lower() for cell in row)) != len(row):
        return False
    return all(classify(cell.strip()) == "text" for cell in row)


def profile(payload: bytes, *, max_rows: int = MAX_PROFILE_ROWS) -> TableProfile:
    text, encoding = decode(payload)
    delimiter = sniff_delimiter(text[:64_000])
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)

    try:
        first = next(reader)
    except StopIteration:
        raise UnprofilableFile("the file has no rows") from None
    except csv.Error as error:
        raise UnprofilableFile("the file is not readable as delimited text") from error

    if len(first) > MAX_COLUMNS:
        raise UnprofilableFile(f"the file declares more than {MAX_COLUMNS} columns")

    has_header = looks_like_header(first)
    if has_header:
        headers = [clean_header(cell, f"columna_{index + 1}")
                   for index, cell in enumerate(first)]
    else:
        headers = [f"columna_{index + 1}" for index in range(len(first))]

    columns = [ColumnProfile(index, header) for index, header in enumerate(headers)]
    row_count = 0
    ragged = 0
    truncated = False

    def consume(row: list[str]) -> None:
        nonlocal ragged
        if len(row) != len(columns):
            ragged += 1
        for index, column in enumerate(columns):
            column.observe(row[index] if index < len(row) else "")

    if not has_header:
        consume(first)
        row_count += 1

    try:
        for row in reader:
            if row_count >= max_rows:
                truncated = True
                break
            if not any(cell.strip() for cell in row):
                continue
            consume(row)
            row_count += 1
    except csv.Error as error:
        raise UnprofilableFile("the file is not readable as delimited text") from error

    reported = "" if delimiter == SINGLE_COLUMN else delimiter
    return TableProfile(encoding, reported, has_header, row_count, len(columns),
                        ragged, truncated, tuple(columns))


def profile_workbook(payload: bytes, *, sheet_identity: str | None = None,
                     max_rows: int = MAX_PROFILE_ROWS) -> SpreadsheetTableProfile:
    """Perfila la hoja segura seleccionada mediante el lector compartido."""
    # Import local para que el perfilador CSV siga siendo una dependencia
    # pequena y para dejar explicita la frontera de formato.
    from .spreadsheet import (
        SpreadsheetError,
        SpreadsheetOutcome,
        sniff_workbook,
        stream_workbook_rows,
    )

    try:
        _, preamble = sniff_workbook(payload, sheet_identity=sheet_identity)
        outcome = SpreadsheetOutcome()
        rows = stream_workbook_rows(payload, preamble, max_rows=max_rows,
                                    outcome=outcome)
        columns = [ColumnProfile(index, header)
                   for index, header in enumerate(preamble.header)]
        for row in rows:
            if row.record_ordinal < preamble.first_data_row:
                continue
            while len(columns) < len(row.values):
                index = len(columns)
                columns.append(ColumnProfile(index, f"columna_{index + 1}"))
            for index, column in enumerate(columns):
                column.observe(row.values[index] if index < len(row.values) else "")
    except SpreadsheetError as error:
        raise UnprofilableFile(str(error)) from error

    return SpreadsheetTableProfile(
        sheet_name=preamble.sheet_name,
        sheet_ordinal=preamble.sheet_ordinal,
        has_header=looks_like_header(list(preamble.header)),
        row_count=outcome.data_rows,
        column_count=len(columns),
        ragged_rows=outcome.ragged_rows,
        truncated=outcome.state == "truncated",
        columns=tuple(columns),
    )


def profile_open_document(payload: bytes, *, sheet_identity: str | None = None,
                          max_rows: int = MAX_PROFILE_ROWS) -> SpreadsheetTableProfile:
    """Perfila una hoja ODS segura mediante el lector compartido."""
    from .open_document import (
        OpenDocumentError,
        OpenDocumentOutcome,
        sniff_open_document,
        stream_open_document_rows,
    )

    try:
        _, preamble = sniff_open_document(payload, sheet_identity=sheet_identity)
        outcome = OpenDocumentOutcome()
        rows = stream_open_document_rows(
            payload, preamble, max_rows=max_rows, outcome=outcome)
        columns = [ColumnProfile(index, header)
                   for index, header in enumerate(preamble.header)]
        for row in rows:
            if row.record_ordinal < preamble.first_data_row:
                continue
            while len(columns) < len(row.values):
                index = len(columns)
                columns.append(ColumnProfile(index, f"columna_{index + 1}"))
            for index, column in enumerate(columns):
                column.observe(row.values[index] if index < len(row.values) else "")
    except OpenDocumentError as error:
        raise UnprofilableFile(str(error)) from error

    return SpreadsheetTableProfile(
        sheet_name=preamble.sheet_name,
        sheet_ordinal=preamble.sheet_ordinal,
        has_header=looks_like_header(list(preamble.header)),
        row_count=outcome.data_rows,
        column_count=len(columns),
        ragged_rows=outcome.ragged_rows,
        truncated=outcome.state == "truncated",
        columns=tuple(columns),
        technical_format="ods",
        effective_encoding="ods-xml",
    )
