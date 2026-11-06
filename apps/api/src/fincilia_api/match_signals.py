"""Senales deterministas de cruce y su explicacion en lenguaje llano (FNC-SMB-003).

ADR-039 §4. Cada pieza de este modulo es una funcion pura sobre texto y `Decimal`:

- no hay puntaje: un candidato es la lista de senales que cumple, y se ordena
  por cuantas cumple, por distancia de fechas y por diferencia de monto;
- no hay LLM ni expresion regular aportada por una persona: los patrones son
  constantes revisadas en este fichero y el patron de una regla es una
  subcadena normalizada;
- el dinero nunca pasa por `float`.

`normalise_text` replica exactamente `fincilia.normalise_match_text` (V0069):
la base vuelve a evaluar las reglas con la funcion SQL y ambas tienen que
coincidir caracter por caracter.

Contraparte. El modelo canonico no tiene un campo de NIT. En vez de ampliar el
contrato del movimiento, la senal `same_counterparty_id` se deriva de forma
determinista del texto ya publicado (descripcion y referencia): la marca `NIT`
seguida de un identificador. Una factura DIAN extraida por FNC-SMB-002 compone
su descripcion con `NIT <identificador del cliente>`, de modo que el linaje del
identificador sigue llegando al elemento UBL de origen.

Bre-B. La referencia de pago es la marca `BRE-B`/`BREB` seguida de un
identificador alfanumerico de 6 a 40 caracteres. Es una hipotesis sintetica a
calibrar con corpus autorizado (DRG-00), igual que las plantillas bancarias.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

_ACCENTS = str.maketrans("áàäâãéèëêíìïîóòöôõúùüûñç", "aaaaaeeeeiiiiooooouuuunc")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NIT = re.compile(r"\bNIT\b[\s.:#-]*([A-Z0-9](?:[A-Z0-9.-]{2,38}[A-Z0-9]))",
                  re.IGNORECASE)
_NUMERIC_NIT_WITH_DV = re.compile(r"^(\d{6,12})-\d$")
_BREB = re.compile(r"\bBRE-?B\b[\s.:#-]*([A-Z0-9][A-Z0-9-]{4,39}[A-Z0-9])",
                   re.IGNORECASE)
_MIN_CONTAINED_REFERENCE = 4

# Orden fijo en que se guardan y explican las senales.
BASE_SIGNALS = ("same_currency", "opposite_direction", "different_financial_account",
                "date_within_explicit_window")
AFFINITY_SIGNALS = ("same_normalised_reference", "same_counterparty_id",
                    "reference_contained", "payment_reference")
SIGNAL_ORDER = ("exact_amount", "amount_within_tolerance", *BASE_SIGNALS,
                *AFFINITY_SIGNALS)


def normalise_text(value: str | None) -> str:
    """Minusculas, sin tildes, solo letras y digitos separados por un espacio."""
    lowered = (value or "").lower().translate(_ACCENTS)
    return _NON_ALNUM.sub(" ", lowered).strip()


def counterparty_ids(*texts: str | None) -> frozenset[str]:
    """Identificadores marcados con `NIT` en los textos, normalizados."""
    found: set[str] = set()
    for text in texts:
        for match in _NIT.finditer(text or ""):
            token = match.group(1).upper().replace(".", "")
            numeric = _NUMERIC_NIT_WITH_DV.match(token)
            # El digito de verificacion no identifica: 900123456-7 y 900123456
            # son el mismo NIT escrito de dos formas.
            found.add(numeric.group(1) if numeric else token)
    return frozenset(found)


def payment_references(*texts: str | None) -> frozenset[str]:
    found: set[str] = set()
    for text in texts:
        for match in _BREB.finditer(text or ""):
            found.add(match.group(1).upper().replace("-", ""))
    return frozenset(found)


def reference_contained(reference: str | None, description: str | None) -> bool:
    """La referencia de un lado aparece entera en la descripcion del otro."""
    needle = normalise_text(reference)
    if len(needle.replace(" ", "")) < _MIN_CONTAINED_REFERENCE:
        return False
    haystack = f" {normalise_text(description)} "
    return f" {needle} " in haystack


@dataclass(frozen=True)
class Side:
    description: str
    reference: str | None


def affinity_signals(left: Side, right: Side, *,
                     same_normalised_reference: bool) -> list[str]:
    signals: list[str] = []
    if same_normalised_reference:
        signals.append("same_normalised_reference")
    if counterparty_ids(left.description, left.reference) & counterparty_ids(
            right.description, right.reference):
        signals.append("same_counterparty_id")
    if (reference_contained(left.reference, right.description)
            or reference_contained(right.reference, left.description)):
        signals.append("reference_contained")
    if payment_references(left.description, left.reference) & payment_references(
            right.description, right.reference):
        signals.append("payment_reference")
    return signals


def ordered(signals: Iterable[str]) -> list[str]:
    present = set(signals)
    return [item for item in SIGNAL_ORDER if item in present]


def format_cop(amount: Decimal) -> str:
    """`$1.190` o `$1.190,50`: convenio colombiano, sin pasar por float."""
    if amount < 0:
        raise ValueError("a difference is never negative")
    quantized = amount.quantize(Decimal("0.01"))
    integer, _, cents = f"{quantized:f}".partition(".")
    grouped = f"{int(integer):,}".replace(",", ".")
    return f"${grouped}" if cents in ("", "00") else f"${grouped},{cents}"


def explanation(signals: Iterable[str], *, date_distance_days: int,
                amount_difference: Decimal | None) -> list[str]:
    """Frases cortas en espanol, una por senal relevante, en orden fijo."""
    present = set(signals)
    sentences: list[str] = []
    if "exact_amount" in present:
        sentences.append("Mismo valor")
    if "amount_within_tolerance" in present and amount_difference is not None:
        sentences.append(
            f"Diferencia de {format_cop(amount_difference)} "
            "(posible retención o comisión)")
    if "same_counterparty_id" in present:
        sentences.append("NIT del pagador coincide")
    if "payment_reference" in present:
        sentences.append("Misma referencia de pago Bre-B")
    if "same_normalised_reference" in present:
        sentences.append("Misma referencia")
    if "reference_contained" in present:
        sentences.append("La referencia aparece en la descripción de la otra partida")
    if date_distance_days == 0:
        sentences.append("Misma fecha")
    elif date_distance_days == 1:
        sentences.append("Fechas a 1 día")
    else:
        sentences.append(f"Fechas a {date_distance_days} días")
    if "opposite_direction" in present:
        sentences.append("Un ingreso frente a un egreso")
    return sentences


def rank_key(signals: list[str], date_distance_days: int,
             amount_difference: Decimal | None,
             tie_breakers: tuple) -> tuple:
    """Mas senales primero, luego fechas mas cercanas y menor diferencia."""
    return (-len(signals), date_distance_days,
            amount_difference if amount_difference is not None else Decimal(0),
            *tie_breakers)


# --------------------------------------------------------------------------- #
# Reglas
# --------------------------------------------------------------------------- #

RULE_SCHEMA = "fnc-rule-v1"
MAX_RULE_TOLERANCE = Decimal("10000000")
_DECIMAL_TEXT = re.compile(r"^[0-9]{1,15}(\.[0-9]{1,12})?$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class RuleConditionError(ValueError):
    pass


def validated_conditions(raw: dict) -> dict:
    """Las mismas seis claves y limites que `fincilia.valid_rule_conditions`."""
    if not isinstance(raw, dict):
        raise RuleConditionError("conditions must be an object")
    pattern = normalise_text(str(raw.get("description_contains") or ""))
    if not 3 <= len(pattern) <= 120:
        raise RuleConditionError(
            "description_contains needs 3 to 120 letters or digits")
    account = raw.get("financial_account_id")
    if account is not None:
        account = str(account).lower()
        if not _UUID.fullmatch(account):
            raise RuleConditionError("financial_account_id must be a UUID")
    direction = raw.get("direction")
    if direction is not None and direction not in ("inflow", "outflow"):
        raise RuleConditionError("direction must be inflow, outflow or null")
    tolerance = raw.get("max_amount_difference", "0")
    if isinstance(tolerance, (float, bool)) or not isinstance(tolerance, (str, int)):
        raise RuleConditionError("max_amount_difference must be a decimal string")
    tolerance = str(tolerance).strip()
    if not _DECIMAL_TEXT.fullmatch(tolerance) or Decimal(tolerance) > MAX_RULE_TOLERANCE:
        raise RuleConditionError(
            "max_amount_difference must be a decimal between 0 and 10000000")
    currency = str(raw.get("currency") or "").upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise RuleConditionError("currency must be an ISO 4217 code")
    return {"schema": RULE_SCHEMA, "description_contains": pattern,
            "financial_account_id": account, "direction": direction,
            "max_amount_difference": tolerance, "currency": currency}


@dataclass(frozen=True)
class RuleSide:
    description: str
    financial_account_id: str
    direction: str
    currency: str


def rule_matches(conditions: dict, left: RuleSide, right: RuleSide,
                 amount_difference: Decimal | None) -> bool:
    """Espejo de la comprobacion del disparador de `match_decision`."""
    currency = conditions["currency"]
    if left.currency != currency or right.currency != currency:
        return False
    difference = amount_difference if amount_difference is not None else Decimal(0)
    if difference > Decimal(conditions["max_amount_difference"]):
        return False
    pattern = conditions["description_contains"]
    for side in (left, right):
        if (pattern in normalise_text(side.description)
                and (conditions["financial_account_id"] is None
                     or side.financial_account_id == conditions["financial_account_id"])
                and (conditions["direction"] is None
                     or side.direction == conditions["direction"])):
            return True
    return False


def suggested_pattern(description: str, reference: str | None) -> str:
    """Patron propuesto desde una decision: el NIT si lo hay; si no, las palabras.

    Se quitan los tokens con digitos (numeros de factura, fechas, consecutivos)
    porque harian que la regla solo sirviera para el caso que la origino.
    """
    ids = sorted(counterparty_ids(description, reference))
    normalised = normalise_text(description)
    for token in ids:
        candidate = normalise_text(f"NIT {token}")
        if candidate and candidate in normalised:
            return candidate[:120]
    words = [word for word in normalised.split() if not any(c.isdigit() for c in word)]
    return " ".join(words)[:120].strip()
