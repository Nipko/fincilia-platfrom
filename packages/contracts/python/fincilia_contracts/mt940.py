"""Lectura de extractos SWIFT MT940. Solo biblioteca estandar.

ADR-039 §5 admite MT940 como formato estructurado. Este modulo lo lee y
comprueba su aritmetica; no concilia ni publica nada.

Tres reglas:

1. **El saldo se comprueba siempre.** Por cada extracto, saldo inicial mas la
   suma de movimientos tiene que dar el saldo final. El resultado se informa en
   `balance_check` con su estado; un descuadre nunca pasa en silencio y un
   extracto sin saldos queda `incomplete`, nunca `balanced`.
2. **El dinero es `Decimal` estricto.** El MT940 usa coma decimal; un importe
   que no encaje con esa forma no se arregla, se deja fuera y se explica.
3. **Todo movimiento sabe de donde salio:** indice de extracto, etiqueta y
   numero de linea, mas las lineas de su `:86:`.

Convencion de anio: el MT940 escribe fechas `YYMMDD`. La norma SWIFT no trae
siglo; aqui se lee en la ventana 2000-2099, que es la de cualquier extracto
emitido por un sistema vigente. Es una regla declarada del formato, no una
inferencia sobre un dato tabular libre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

from .money import (CurrencyError, MoneyError, ZERO, add, format_money,
                    parse_currency, parse_money, subtract)

MAX_MT940_BYTES: Final[int] = 10 * 1024 * 1024
MAX_MT940_LINES: Final[int] = 500_000
# SWIFT limita a 65 caracteres; algunos bancos se pasan. 512 deja margen sin
# admitir una «linea» que en realidad es un fichero entero sin saltos.
MAX_LINE_LENGTH: Final[int] = 512
MAX_STATEMENTS: Final[int] = 10_000
MAX_INFORMATION: Final[int] = 2_000

TAG = re.compile(r"^:(\d{2}[A-Z]?):(.*)$")
BALANCE = re.compile(r"^([CD])(\d{6})([A-Z]{3})(\d{1,15},\d{0,12})$")
STATEMENT_LINE = re.compile(
    r"^(?P<value>\d{6})(?P<entry>\d{4})?(?P<mark>RC|RD|C|D)(?P<funds>[A-Z])?"
    r"(?P<amount>\d{1,15},\d{0,12})(?P<type>[NSF][A-Z0-9]{3})"
    r"(?P<customer>.*?)(?://(?P<bank>.*))?$")
LOOSE_STATEMENT_HEAD = re.compile(r"^\d{6}(?:\d{4})?(?:RC|RD|C|D)")
KNOWN_TAGS: Final[frozenset[str]] = frozenset({
    "20", "21", "25", "25P", "28", "28C", "60F", "60M", "61", "86", "62F", "62M",
    "64", "65", "13D", "34F", "90D", "90C"})


class MT940Error(ValueError):
    """El fichero no se puede leer como MT940. Nunca repite el contenido."""


@dataclass(frozen=True)
class Finding:
    code: str
    location: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}


@dataclass(frozen=True)
class Balance:
    tag: str
    mark: str
    booked_on: str
    currency: str
    amount: Decimal
    lineage: dict[str, Any]

    @property
    def signed(self) -> Decimal:
        return self.amount if self.mark == "C" else -self.amount

    def as_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "mark": self.mark, "booked_on": self.booked_on,
                "currency": self.currency, "amount": format_money(self.amount),
                "signed_amount": format_money(self.signed),
                "lineage": dict(self.lineage)}


@dataclass(frozen=True)
class Transaction:
    value_date: str
    entry_date: str | None
    mark: str
    direction: str
    amount: Decimal
    funds_code: str
    type_code: str
    customer_reference: str
    bank_reference: str
    supplementary: str
    information: str
    lineage: dict[str, Any]

    @property
    def signed(self) -> Decimal:
        return self.amount if self.direction == "inflow" else -self.amount

    def as_dict(self) -> dict[str, Any]:
        return {"value_date": self.value_date, "entry_date": self.entry_date,
                "mark": self.mark, "direction": self.direction,
                "amount": format_money(self.amount),
                "signed_amount": format_money(self.signed),
                "funds_code": self.funds_code, "type_code": self.type_code,
                "customer_reference": self.customer_reference,
                "bank_reference": self.bank_reference,
                "supplementary": self.supplementary, "information": self.information,
                "lineage": dict(self.lineage)}


@dataclass(frozen=True)
class BalanceCheck:
    """`balanced`, `mismatch`, `incomplete` o `currency_mismatch`. Nada mas."""

    status: str
    opening: Decimal | None
    movements: Decimal
    expected_closing: Decimal | None
    closing: Decimal | None

    @property
    def difference(self) -> Decimal | None:
        if self.expected_closing is None or self.closing is None:
            return None
        return subtract(self.closing, self.expected_closing)

    def as_dict(self) -> dict[str, Any]:
        def render(value: Decimal | None) -> str | None:
            return None if value is None else format_money(value)
        return {"status": self.status, "opening": render(self.opening),
                "movements": format_money(self.movements),
                "expected_closing": render(self.expected_closing),
                "closing": render(self.closing), "difference": render(self.difference)}


@dataclass(frozen=True)
class Statement:
    index: int
    transaction_reference: str
    account: str
    statement_number: str
    opening: Balance | None
    closing: Balance | None
    closing_available: Balance | None
    transactions: tuple[Transaction, ...]
    balance_check: BalanceCheck
    findings: tuple[Finding, ...]

    @property
    def status(self) -> str:
        return ("complete" if not self.findings and self.balance_check.status == "balanced"
                else "partial")

    def as_dict(self) -> dict[str, Any]:
        def render(value: Balance | None) -> dict[str, Any] | None:
            return None if value is None else value.as_dict()
        return {"index": self.index, "status": self.status,
                "transaction_reference": self.transaction_reference,
                "account": self.account, "statement_number": self.statement_number,
                "opening": render(self.opening), "closing": render(self.closing),
                "closing_available": render(self.closing_available),
                "transactions": [item.as_dict() for item in self.transactions],
                "balance_check": self.balance_check.as_dict(),
                "findings": [item.as_dict() for item in self.findings]}


@dataclass(frozen=True)
class MT940Result:
    statements: tuple[Statement, ...]
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def status(self) -> str:
        return ("complete" if not self.findings
                and all(item.status == "complete" for item in self.statements)
                else "partial")

    @property
    def balance_check(self) -> str:
        """El peor estado entre extractos: un solo descuadre descuadra el fichero."""
        order = ("balanced", "incomplete", "currency_mismatch", "mismatch")
        worst = 0
        for statement in self.statements:
            worst = max(worst, order.index(statement.balance_check.status))
        return order[worst]

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "balance_check": self.balance_check,
                "statements": [item.as_dict() for item in self.statements],
                "findings": [item.as_dict() for item in self.findings]}

    def manifest(self) -> dict[str, Any]:
        """Forma sin valores ni referencias."""
        return {"document_kind": "mt940", "status": self.status,
                "balance_check": self.balance_check,
                "statement_count": len(self.statements),
                "transaction_count": sum(len(item.transactions) for item in self.statements),
                "statement_checks": [item.balance_check.status for item in self.statements],
                "finding_codes": sorted({item.code for item in self.findings}
                                        | {finding.code for item in self.statements
                                           for finding in item.findings})}


# --------------------------------------------------------------------------- #
# Deteccion
# --------------------------------------------------------------------------- #

def looks_like_mt940(head: bytes) -> bool:
    """Firma de contenido: empieza como MT940 y trae `:20:`, `:25:` y saldo inicial."""
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        text = head.decode("latin-1")
    lines = [line.strip() for line in text.lstrip("﻿").splitlines() if line.strip()]
    if not lines:
        return False
    first = lines[0]
    if not (first.startswith("{1:") or first.startswith(":20:")
            or first.startswith(":940:") or first == "940"):
        return False
    has = {tag: any(line.startswith(tag) for line in lines)
           for tag in (":20:", ":25:", ":60F:", ":60M:")}
    return has[":20:"] and has[":25:"] and (has[":60F:"] or has[":60M:"])


# --------------------------------------------------------------------------- #
# Lectura
# --------------------------------------------------------------------------- #

def _decode(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        # El juego de caracteres SWIFT es casi ASCII; latin-1 cubre lo que algunos
        # bancos escriben fuera de el sin inventar bytes.
        return payload.decode("latin-1")


def _date(value: str) -> str | None:
    year, month, day = 2000 + int(value[0:2]), int(value[2:4]), int(value[4:6])
    if not 1 <= month <= 12:
        return None
    limit = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    if month == 2 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        limit = 28
    if not 1 <= day <= limit:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _entry_date(value_date: str, mmdd: str) -> str | None:
    year = int(value_date[0:4])
    value_month = int(value_date[5:7])
    month = int(mmdd[0:2])
    # El asiento puede caer en el anio vecino cuando el valor es de diciembre o
    # de enero; la regla esta escrita, no se adivina por proximidad libre.
    if value_month == 12 and month == 1:
        year += 1
    elif value_month == 1 and month == 12:
        year -= 1
    return _date(f"{year % 100:02d}{mmdd}") if 2000 <= year <= 2099 else None


def _amount(raw: str, location: str) -> Decimal:
    integer, _, decimals = raw.partition(",")
    return parse_money(f"{integer}.{decimals or '0'}", location)


def _logical_lines(text: str) -> list[tuple[int, str, str]]:
    """Agrupa etiqueta y continuaciones: `(linea_inicial, etiqueta, contenido)`.

    El contenido conserva los saltos internos como `\\n` para poder separar la
    primera linea de `:61:` de su informacion suplementaria.
    """
    lines = text.splitlines()
    if len(lines) > MAX_MT940_LINES:
        raise MT940Error(f"the file exceeds {MAX_MT940_LINES} lines")
    logical: list[list[Any]] = []
    in_text_block = False
    for number, raw in enumerate(lines, start=1):
        if len(raw) > MAX_LINE_LENGTH:
            raise MT940Error(f"line {number} exceeds {MAX_LINE_LENGTH} characters")
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        # Sobre SWIFT: `{1:...}{2:...}{4:` abre el bloque de texto y `-}` lo cierra.
        if stripped.startswith("{"):
            in_text_block = "{4:" in stripped
            if in_text_block:
                remainder = stripped.split("{4:", 1)[1].strip()
                if remainder:
                    line = remainder
                else:
                    continue
            else:
                continue
        if stripped.startswith("-}") or stripped == "-":
            in_text_block = False
            continue
        match = TAG.match(line)
        if match:
            logical.append([number, match.group(1), match.group(2), [number]])
        elif logical:
            logical[-1][2] += "\n" + line
            logical[-1][3].append(number)
        elif stripped in {"940", ":940:"} or re.fullmatch(r"[A-Z0-9]{8,11}", stripped):
            # Cabeceras de algunos bancos antes del primer `:20:`.
            continue
        else:
            raise MT940Error(f"line {number} is outside any MT940 tag")
    return [(item[0], item[1], item[2]) for item in logical]


class _Builder:
    def __init__(self, index: int, line: int) -> None:
        self.index = index
        self.line = line
        self.reference = ""
        self.account = ""
        self.number = ""
        self.opening: Balance | None = None
        self.closing: Balance | None = None
        self.available: Balance | None = None
        self.transactions: list[Transaction] = []
        self.findings: list[Finding] = []
        self.pending: dict[str, Any] | None = None
        self.unreadable_movements = 0

    def lineage(self, tag: str, line: int) -> dict[str, Any]:
        return {"locator_kind": "mt940_tag", "statement_index": self.index,
                "tag": tag, "line_number": line}

    def flush_pending(self) -> None:
        if self.pending is not None:
            self.transactions.append(Transaction(**self.pending))
            self.pending = None


def parse_mt940(payload: bytes) -> MT940Result:
    """Lee un fichero MT940 con uno o varios extractos y comprueba sus saldos."""
    if not payload:
        raise MT940Error("an empty file carries no statement")
    if len(payload) > MAX_MT940_BYTES:
        raise MT940Error(f"the file exceeds {MAX_MT940_BYTES} bytes")
    if b"\x00" in payload:
        raise MT940Error("binary content is not an MT940 statement")
    logical = _logical_lines(_decode(payload))
    if not logical:
        raise MT940Error("the file has no MT940 tags")

    findings: list[Finding] = []
    builders: list[_Builder] = []
    current: _Builder | None = None
    # Las lineas `:86:` siguen a su `:61:`; un `:86:` sin `:61:` es informacion
    # del extracto y se guarda como hallazgo informativo, no se pega a nada.
    for line, tag, content in logical:
        if tag == "20":
            if current is not None:
                current.flush_pending()
            if len(builders) >= MAX_STATEMENTS:
                raise MT940Error(f"the file exceeds {MAX_STATEMENTS} statements")
            current = _Builder(len(builders) + 1, line)
            current.reference = content.strip()[:35]
            builders.append(current)
            continue
        if current is None:
            raise MT940Error(f"line {line}: tag :{tag}: appears before any :20:")
        if tag not in KNOWN_TAGS:
            current.findings.append(Finding("unknown_tag", f"line {line}",
                                            f"tag :{tag}: is not part of MT940"))
            continue
        # Solo `:61:` (informacion suplementaria) y `:86:` admiten lineas de
        # continuacion. Una linea suelta tras un saldo no se pega en silencio:
        # el fichero no sigue el formato y no se lee a medias.
        extra_lines = content.count("\n")
        if (tag not in {"61", "86"} and extra_lines) or (tag == "61" and extra_lines > 2):
            raise MT940Error(f"line {line}: tag :{tag}: carries unexpected continuation lines")
        if tag not in {"61", "86"}:
            # Cualquier otra etiqueta cierra el movimiento en curso.
            current.flush_pending()
        if tag in {"25", "25P"}:
            current.account = content.strip()[:35]
        elif tag in {"28", "28C"}:
            current.number = content.strip()[:16]
        elif tag in {"60F", "60M", "62F", "62M", "64"}:
            balance = _balance(current, tag, content.strip(), line)
            if balance is None:
                continue
            if tag.startswith("60"):
                current.opening = balance
            elif tag.startswith("62"):
                current.closing = balance
            else:
                current.available = balance
        elif tag == "61":
            current.flush_pending()
            current.pending = _statement_line(current, content, line)
        elif tag == "86":
            text = " ".join(part.strip() for part in content.split("\n")).strip()
            if current.pending is not None:
                joined = (current.pending["information"] + " " + text).strip()
                current.pending["information"] = joined[:MAX_INFORMATION]
                current.pending["lineage"].setdefault("information_lines", []).append(line)
            else:
                current.findings.append(Finding(
                    "statement_information", f"line {line}",
                    ":86: without a preceding :61: is kept out of movements"))
    if current is not None:
        current.flush_pending()

    statements = tuple(_finish(builder) for builder in builders)
    if not statements:
        raise MT940Error("the file has no statement")
    return MT940Result(statements, tuple(findings))


def _balance(builder: _Builder, tag: str, content: str, line: int) -> Balance | None:
    match = BALANCE.match(content)
    location = f"statement {builder.index} line {line} :{tag}:"
    if not match:
        builder.findings.append(Finding("malformed_balance", location,
                                        "the balance does not follow mark/date/currency/amount"))
        return None
    mark, raw_date, currency, raw_amount = match.groups()
    booked_on = _date(raw_date)
    if booked_on is None:
        builder.findings.append(Finding("malformed_date", location,
                                        "the balance date is not a calendar date"))
        return None
    try:
        amount = _amount(raw_amount, location)
    except MoneyError:
        builder.findings.append(Finding("malformed_amount", location,
                                        "the balance amount cannot be read exactly"))
        return None
    try:
        parse_currency(currency)
    except CurrencyError:
        builder.findings.append(Finding("unsupported_currency", location,
                                        "the currency is not supported by the product"))
    return Balance(tag, mark, booked_on, currency, amount, builder.lineage(tag, line))


def _statement_line(builder: _Builder, content: str,
                    line: int) -> dict[str, Any] | None:
    first, _, rest = content.partition("\n")
    location = f"statement {builder.index} line {line} :61:"
    match = STATEMENT_LINE.match(first.strip())
    if not match:
        builder.unreadable_movements += 1
        code = ("malformed_amount" if LOOSE_STATEMENT_HEAD.match(first.strip())
                else "malformed_statement_line")
        builder.findings.append(Finding(code, location,
                                        "the statement line does not follow the MT940 layout"))
        return None
    value_date = _date(match.group("value"))
    if value_date is None:
        builder.unreadable_movements += 1
        builder.findings.append(Finding("malformed_date", location,
                                        "the value date is not a calendar date"))
        return None
    entry_date = None
    if match.group("entry"):
        entry_date = _entry_date(value_date, match.group("entry"))
        if entry_date is None:
            builder.unreadable_movements += 1
            builder.findings.append(Finding("malformed_date", location,
                                            "the entry date is not a calendar date"))
            return None
    try:
        amount = _amount(match.group("amount"), location)
    except MoneyError:
        builder.unreadable_movements += 1
        builder.findings.append(Finding("malformed_amount", location,
                                        "the movement amount cannot be read exactly"))
        return None
    mark = match.group("mark")
    # C/D: credito/debito. RC/RD: reverso; el reverso de un credito saca dinero y
    # el de un debito lo devuelve.
    direction = "inflow" if mark in {"C", "RD"} else "outflow"
    return {
        "value_date": value_date, "entry_date": entry_date, "mark": mark,
        "direction": direction, "amount": amount,
        "funds_code": match.group("funds") or "",
        "type_code": match.group("type"),
        "customer_reference": (match.group("customer") or "").strip()[:16],
        "bank_reference": (match.group("bank") or "").strip()[:16],
        "supplementary": " ".join(part.strip() for part in rest.split("\n")).strip()[:34],
        "information": "",
        "lineage": builder.lineage("61", line),
    }


def _finish(builder: _Builder) -> Statement:
    findings = list(builder.findings)
    for name, value in (("transaction_reference", builder.reference),
                        ("account", builder.account)):
        if not value:
            findings.append(Finding("missing_field", f"statement {builder.index}",
                                    f"{name} is required"))
    movements = ZERO
    for item in builder.transactions:
        movements = add(movements, item.signed)

    opening = builder.opening.signed if builder.opening else None
    closing = builder.closing.signed if builder.closing else None
    if builder.opening is None or builder.closing is None or builder.unreadable_movements:
        # Sin un extremo, o con un movimiento ilegible, la suma no prueba nada.
        status = "incomplete"
        expected = add(opening, movements) if opening is not None else None
    elif builder.opening.currency != builder.closing.currency:
        status = "currency_mismatch"
        expected = None
    else:
        expected = add(opening, movements)
        status = "balanced" if expected == closing else "mismatch"
    if status == "mismatch":
        findings.append(Finding("balance_mismatch", f"statement {builder.index}",
                                "opening balance plus movements differs from closing balance"))
    check = BalanceCheck(status, opening, movements, expected, closing)
    return Statement(builder.index, builder.reference, builder.account, builder.number,
                     builder.opening, builder.closing, builder.available,
                     tuple(builder.transactions), check, tuple(findings))
