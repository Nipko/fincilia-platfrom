"""Mapeo de un fichero tabular a movimientos canonicos. Solo biblioteca estandar.

Aqui es donde un fichero deja de ser un fichero y empieza a ser dinero, y por eso
el modulo esta escrito alrededor de una idea: **ante la duda, no se publica**.

Tres reglas explican casi todas las decisiones.

**Nada se infiere en silencio.** El formato de fecha, el separador decimal, la
moneda y como se lee la direccion son elecciones del mapeo, no adivinanzas del
codigo. `03/04/26` puede ser el 3 de abril o el 4 de marzo, y `1.234` puede ser
mil doscientos treinta y cuatro o uno coma doscientos treinta y cuatro. Elegir mal
mueve un asiento de mes o multiplica un importe por mil, y nadie lo nota hasta el
cierre.

**El signo no es la direccion.** Un extracto colombiano trae debitos y creditos en
columnas separadas; otro trae un importe con signo. Son dos convenios distintos y
el mapeo dice cual, en vez de mirar el signo y suponer.

**Una fila que no encaja no se publica.** Se cuenta, se explica y se queda fuera.
Publicar «lo que se pudo» produce un total que no cuadra con el fichero y que
nadie sabra reconstruir.

El perfilado (`profiling.py`) describe la forma de un fichero y marca lo que es
ambiguo. Este modulo consume esa marca: una columna ambigua **bloquea** la
publicacion hasta que una persona elija. El perfil propone; aqui alguien decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from .money import MoneyError, parse_currency, parse_money

# Campos canonicos que un mapeo puede alimentar. `direction` no esta: se deriva
# del convenio declarado, no de una columna que alguien renombro.
CANONICAL_FIELDS: Final[tuple[str, ...]] = (
    "occurred_on", "description", "reference", "amount", "debit", "credit",
    "direction", "currency")
REQUIRED_FIELDS: Final[tuple[str, ...]] = ("occurred_on", "description")

DATE_FORMATS: Final[tuple[str, ...]] = ("iso", "dmy", "mdy")
DECIMAL_FORMATS: Final[tuple[str, ...]] = ("dot", "comma")
DIRECTION_MODES: Final[tuple[str, ...]] = (
    "debit_credit_columns", "signed_amount", "explicit_direction")
# El contrato canonico declara `inflow`/`outflow`. El vocabulario de un extracto
# es debito/credito, y la correspondencia se hace **aqui**, una sola vez: un
# debito saca dinero de la cuenta, un credito lo mete.
DIRECTIONS: Final[tuple[str, ...]] = ("inflow", "outflow")
INFLOW_WORDS: Final[frozenset[str]] = frozenset({
    "inflow", "credito", "crédito", "credit", "abono", "entrada", "haber"})
OUTFLOW_WORDS: Final[frozenset[str]] = frozenset({
    "outflow", "debito", "débito", "debit", "cargo", "salida", "debe"})

ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
SLASH_DATE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$")
THOUSANDS_DOT = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?$")
THOUSANDS_COMMA = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")

MAX_DESCRIPTION = 500
MAX_REFERENCE = 120
DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class MappingError(ValueError):
    """El mapeo no es utilizable. Nunca se publica nada con uno asi."""


@dataclass(frozen=True)
class Finding:
    """Un motivo por el que algo no se puede publicar."""

    code: str
    location: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}


@dataclass(frozen=True)
class ColumnMapping:
    """Como se lee un fichero. Todo lo ambiguo esta decidido aqui, o no se publica."""

    columns: dict[str, int]
    date_format: str
    decimal_format: str
    currency: str
    direction_mode: str
    header_row: int = 1
    first_data_row: int = 2

    def column_of(self, name: str) -> int | None:
        return self.columns.get(name)


@dataclass(frozen=True)
class Movement:
    """Un movimiento canonico. El importe es exacto y la moneda va siempre."""

    row_number: int
    occurred_on: str
    description: str
    reference: str
    amount: Decimal
    currency: str
    direction: str
    source_column: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {"row_number": self.row_number, "occurred_on": self.occurred_on,
                "description": self.description, "reference": self.reference,
                # Cadena en punto fijo, no `float`: serializar dinero como coma
                # flotante es perderlo en el unico sitio donde no se puede perder.
                "amount": f"{self.amount:.12f}", "currency": self.currency,
                "direction": self.direction, "source_column": dict(self.source_column)}


@dataclass(frozen=True)
class Rejection:
    row_number: int
    code: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"row_number": self.row_number, "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class MappingResult:
    movements: tuple[Movement, ...]
    rejections: tuple[Rejection, ...]

    @property
    def publishable(self) -> bool:
        """Se publica lo valido, y lo rechazado se cuenta. Nunca se publica a medias
        un fichero sin decir cuanto se quedo fuera."""
        return bool(self.movements)

    def as_dict(self) -> dict[str, Any]:
        return {"movements": [item.as_dict() for item in self.movements],
                "rejections": [item.as_dict() for item in self.rejections],
                "accepted": len(self.movements), "rejected": len(self.rejections)}


# --------------------------------------------------------------------------- #
# Validacion del mapeo, antes de tocar una sola fila
# --------------------------------------------------------------------------- #

def validate_mapping(mapping: ColumnMapping,
                     profile: dict | None = None) -> list[Finding]:
    """Motivos por los que este mapeo no puede publicar. Vacio significa que puede.

    Se comprueba contra el perfil cuando hay uno: una columna que el perfilador
    marco ambigua bloquea, porque el perfil no adivino y el mapeo tampoco deberia.
    """
    findings: list[Finding] = []

    if mapping.date_format not in DATE_FORMATS:
        findings.append(Finding("MAP-DATE-FORMAT", "date_format",
                                f"{mapping.date_format!r} is not a declared format"))
    if mapping.decimal_format not in DECIMAL_FORMATS:
        findings.append(Finding("MAP-DECIMAL-FORMAT", "decimal_format",
                                f"{mapping.decimal_format!r} is not a declared format"))
    if mapping.direction_mode not in DIRECTION_MODES:
        findings.append(Finding("MAP-DIRECTION-MODE", "direction_mode",
                                f"{mapping.direction_mode!r} is not a declared mode"))
    try:
        parse_currency(mapping.currency)
    except Exception:  # noqa: BLE001 - el motivo exacto lo da el modulo de dinero
        # Sin moneda no hay importe: un numero sin unidad no es dinero.
        findings.append(Finding("MAP-CURRENCY", "currency",
                                "an explicit supported currency is required"))

    for name in REQUIRED_FIELDS:
        if mapping.column_of(name) is None:
            findings.append(Finding("MAP-MISSING-COLUMN", name,
                                    "this canonical field has no source column"))

    unknown = sorted(set(mapping.columns) - set(CANONICAL_FIELDS))
    if unknown:
        findings.append(Finding("MAP-UNKNOWN-FIELD", ", ".join(unknown),
                                "not a canonical field"))
    if any(index < 0 for index in mapping.columns.values()):
        findings.append(Finding("MAP-COLUMN-INDEX", "columns",
                                "a column index is never negative"))

    findings.extend(_validate_direction(mapping))
    if profile is not None:
        findings.extend(_validate_against_profile(mapping, profile))
    return findings


def _validate_direction(mapping: ColumnMapping) -> list[Finding]:
    findings: list[Finding] = []
    if mapping.direction_mode == "debit_credit_columns":
        if mapping.column_of("debit") is None or mapping.column_of("credit") is None:
            findings.append(Finding(
                "MAP-DIRECTION-COLUMNS", "direction_mode",
                "this mode needs both a debit and a credit column"))
        if mapping.column_of("debit") == mapping.column_of("credit"):
            findings.append(Finding(
                "MAP-DIRECTION-COLUMNS", "direction_mode",
                "debit and credit cannot be the same column"))
    elif mapping.direction_mode == "signed_amount":
        if mapping.column_of("amount") is None:
            findings.append(Finding("MAP-DIRECTION-COLUMNS", "amount",
                                    "this mode needs a single amount column"))
    elif mapping.direction_mode == "explicit_direction":
        if mapping.column_of("amount") is None or mapping.column_of("direction") is None:
            findings.append(Finding(
                "MAP-DIRECTION-COLUMNS", "direction_mode",
                "this mode needs an amount column and a direction column"))
    return findings


def _validate_against_profile(mapping: ColumnMapping, profile: dict) -> list[Finding]:
    """El perfil marco lo ambiguo; publicar sobre eso seria elegir por la persona."""
    findings: list[Finding] = []
    columns = profile.get("columns") or []
    by_index = {int(item["index"]): item for item in columns}

    for name, index in sorted(mapping.columns.items()):
        column = by_index.get(index)
        if column is None:
            findings.append(Finding("MAP-COLUMN-ABSENT", name,
                                    f"column {index} is not in the profile"))
            continue
        if column.get("ambiguous"):
            findings.append(Finding(
                "MAP-AMBIGUOUS-COLUMN", f"{name} -> {column.get('header')}",
                f"the profile could not decide between readings of "
                f"{column.get('inferred_type')}; a person has to choose"))

    # Y si el fichero cambio de forma, el mapeo anterior deja de ser valido: sus
    # indices apuntarian a otras columnas sin que nada fallara.
    declared = profile.get("column_count")
    if declared is not None and mapping.columns:
        if max(mapping.columns.values()) >= int(declared):
            findings.append(Finding(
                "MAP-SCHEMA-DRIFT", "columns",
                f"the mapping points past column {int(declared) - 1}; the file no "
                "longer has the shape this mapping was written for"))
    return findings


# --------------------------------------------------------------------------- #
# Lectura de valores
# --------------------------------------------------------------------------- #

def parse_date(value: str, date_format: str) -> str:
    """Fecha en ISO. Lo que no encaje con el formato **declarado** se rechaza."""
    text = (value or "").strip()
    if not text:
        raise MappingError("a movement always has a date")

    match = ISO_DATE.match(text)
    if match:
        if date_format != "iso":
            raise MappingError(f"the value is ISO but the mapping declares {date_format}")
        year, month, day = (int(part) for part in match.groups())
        return _iso(year, month, day)

    match = SLASH_DATE.match(text)
    if not match:
        raise MappingError("the value is not a date in any recognised shape")
    first, second, third = match.groups()
    if len(third) == 2:
        # Un ano de dos digitos es ambiguo por definicion y no se completa con una
        # regla de siglo inventada: 26 puede ser 1926 o 2026.
        raise MappingError("a two-digit year is ambiguous and is never completed")
    if date_format == "iso":
        raise MappingError("the mapping declares ISO but the value is not ISO")
    day, month = (int(first), int(second)) if date_format == "dmy" else (int(second), int(first))
    return _iso(int(third), month, day)


def _iso(year: int, month: int, day: int) -> str:
    if not 1 <= month <= 12:
        raise MappingError("month out of range")
    limit = DAYS_IN_MONTH[month - 1]
    if month == 2 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        limit = 28
    if not 1 <= day <= limit:
        raise MappingError("day out of range for that month")
    if not 1900 <= year <= 2999:
        raise MappingError("year out of range")
    return f"{year:04d}-{month:02d}-{day:02d}"


def normalise_amount(value: str, decimal_format: str) -> str:
    """Deja el importe en la forma que `parse_money` entiende, sin redondear nada.

    El separador lo dice el mapeo. Interpretar `1.234` sin saber el convenio es
    elegir entre mil doscientos treinta y cuatro y uno coma doscientos treinta y
    cuatro, y las dos lecturas son plausibles.
    """
    text = (value or "").strip().replace(" ", "").replace(" ", "")
    if not text:
        raise MappingError("an empty cell is not an amount")
    # El separador de miles se quita **solo** si agrupa de tres en tres. Quitarlo a
    # ciegas convierte un valor malformado como `1,23,45` en un numero plausible
    # (`12345`), que es la peor manera de fallar: sin error y con otro importe.
    if decimal_format == "dot":
        if "," in text:
            if not THOUSANDS_COMMA.match(text):
                raise MappingError("the thousands separators do not group in threes")
            text = text.replace(",", "")
        if text.count(".") > 1:
            raise MappingError("more than one decimal point")
    else:
        if "." in text:
            if not THOUSANDS_DOT.match(text):
                raise MappingError("the thousands separators do not group in threes")
            text = text.replace(".", "")
        if text.count(",") > 1:
            raise MappingError("more than one decimal comma")
        text = text.replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        raise MappingError("the value is not a number in the declared format")
    return text


def parse_direction(value: str) -> str:
    word = (value or "").strip().lower()
    if word in INFLOW_WORDS:
        return "inflow"
    if word in OUTFLOW_WORDS:
        return "outflow"
    raise MappingError("the direction column does not say inflow or outflow")


# --------------------------------------------------------------------------- #
# Aplicacion
# --------------------------------------------------------------------------- #

def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def apply_row(mapping: ColumnMapping, row: list[str], row_number: int) -> Movement:
    """Convierte una fila. Lanza `MappingError` con el motivo si no encaja."""
    occurred_on = parse_date(_cell(row, mapping.column_of("occurred_on")),
                             mapping.date_format)
    description = _cell(row, mapping.column_of("description")).strip()[:MAX_DESCRIPTION]
    if not description:
        raise MappingError("a movement always has a description")
    reference = _cell(row, mapping.column_of("reference")).strip()[:MAX_REFERENCE]

    amount, direction = _amount_and_direction(mapping, row)
    if amount == 0:
        # Un movimiento de cero no mueve nada y ensucia cualquier conciliacion.
        raise MappingError("a movement of zero is not a movement")

    return Movement(row_number, occurred_on, description, reference, amount,
                    parse_currency(mapping.currency), direction,
                    {name: index for name, index in sorted(mapping.columns.items())})


def _amount_and_direction(mapping: ColumnMapping,
                          row: list[str]) -> tuple[Decimal, str]:
    if mapping.direction_mode == "debit_credit_columns":
        debit = _cell(row, mapping.column_of("debit")).strip()
        credit = _cell(row, mapping.column_of("credit")).strip()
        if debit and credit:
            # Las dos columnas con valor es una fila que dice dos cosas
            # incompatibles. No se elige una: se rechaza y se cuenta.
            raise MappingError("a row cannot be both a debit and a credit")
        if not debit and not credit:
            raise MappingError("the row has neither a debit nor a credit")
        raw = debit or credit
        direction = "outflow" if debit else "inflow"
        amount = parse_money(normalise_amount(raw, mapping.decimal_format))
        if amount < 0:
            raise MappingError("a debit or credit column carries no sign")
        return amount, direction

    raw = _cell(row, mapping.column_of("amount")).strip()
    amount = parse_money(normalise_amount(raw, mapping.decimal_format))
    if mapping.direction_mode == "signed_amount":
        # Solo aqui el signo significa direccion, y solo porque el mapeo lo dijo.
        direction = "outflow" if amount < 0 else "inflow"
        return abs(amount), direction

    direction = parse_direction(_cell(row, mapping.column_of("direction")))
    if amount < 0:
        raise MappingError("an explicit direction and a signed amount contradict")
    return amount, direction


def apply(mapping: ColumnMapping, rows: list[list[str]], *,
          first_row_number: int | None = None) -> MappingResult:
    """Aplica el mapeo a las filas. Lo que no encaja se rechaza con su motivo."""
    findings = validate_mapping(mapping)
    if findings:
        raise MappingError(
            "the mapping is not publishable: "
            + ", ".join(f"{item.code} {item.location}" for item in findings))

    start = mapping.first_data_row if first_row_number is None else first_row_number
    movements: list[Movement] = []
    rejections: list[Rejection] = []
    for offset, row in enumerate(rows):
        number = start + offset
        try:
            movements.append(apply_row(mapping, row, number))
        except (MappingError, MoneyError) as error:
            rejections.append(Rejection(number, "row_not_mappable", str(error)))
        except Exception as error:  # noqa: BLE001 - una fila rara no tumba el lote
            rejections.append(Rejection(number, "row_error", type(error).__name__))
    return MappingResult(tuple(movements), tuple(rejections))
