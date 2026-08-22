"""Dinero exacto para el producto Fincilia.

Implementacion de producto de la regla que `tools/completeness_engine` especifica:
el dinero es `Decimal` con escala canonica y un `float` se **rechaza**, nunca se
convierte. `tests/product/test_money_agrees_with_spec.py` comprueba que ambas
implementaciones coinciden sobre el mismo conjunto de casos.

Por que importa tanto: aceptar un `float` aqui seria aceptar que `0.1 + 0.2` no es
`0.3` y que un cierre pueda cuadrar por suerte. El error no aparece en la prueba
que escribes, aparece tres meses despues en un saldo que nadie sabe explicar.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Final

# `numeric(38, 12)` en el modelo canonico.
MONEY_SCALE: Final[int] = 12
MONEY_PRECISION: Final[int] = 38
MONEY_QUANTUM: Final[Decimal] = Decimal(1).scaleb(-MONEY_SCALE)
ZERO: Final[Decimal] = Decimal(0).quantize(MONEY_QUANTUM)

# ISO 4217 de las monedas que el producto acepta hoy. Ampliar esta lista es una
# decision de Accounting, no un detalle de implementacion.
SUPPORTED_CURRENCIES: Final[frozenset[str]] = frozenset({"COP", "USD", "EUR"})


class MoneyError(ValueError):
    """Un importe no puede interpretarse como dinero exacto."""


class CurrencyError(ValueError):
    """La moneda falta, no se reconoce o se mezclo con otra."""


def parse_money(value: Any, field: str = "amount") -> Decimal:
    """Convierte a `Decimal` exacto y cuantizado. Un `float` se rechaza."""
    if isinstance(value, bool) or isinstance(value, float):
        raise MoneyError(f"{field}: money must not be a float; got {value!r}")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, int):
        candidate = Decimal(value)
    elif isinstance(value, str):
        try:
            candidate = Decimal(value.strip())
        except InvalidOperation as error:
            raise MoneyError(f"{field}: {value!r} is not an exact decimal") from error
    else:
        raise MoneyError(f"{field}: unsupported money type {type(value).__name__}")
    if not candidate.is_finite():
        raise MoneyError(f"{field}: money must be finite; got {value!r}")
    exponent = candidate.as_tuple().exponent
    if not isinstance(exponent, int) or -exponent > MONEY_SCALE:
        raise MoneyError(f"{field}: money carries more than {MONEY_SCALE} decimal places")
    quantized = candidate.quantize(MONEY_QUANTUM)
    if len(quantized.as_tuple().digits) > MONEY_PRECISION:
        raise MoneyError(f"{field}: money exceeds {MONEY_PRECISION} significant digits")
    return quantized


def format_money(value: Decimal) -> str:
    """Forma canonica en punto fijo. Nunca notacion cientifica.

    `str(Decimal(0).quantize(...))` produce `0E-12`, que es correcto y suficiente
    para que dos representaciones del mismo importe dejen de compararse.
    """
    return f"{value:.{MONEY_SCALE}f}"


def parse_currency(value: Any, field: str = "currency_code") -> str:
    """Moneda explicita y soportada. Nunca se infiere ni se asume una por defecto."""
    if not isinstance(value, str) or not value.strip():
        raise CurrencyError(f"{field}: currency is required and never inferred")
    code = value.strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise CurrencyError(f"{field}: {code!r} is not a supported currency")
    return code


def add(left: Decimal, right: Decimal) -> Decimal:
    return (left + right).quantize(MONEY_QUANTUM)


def subtract(left: Decimal, right: Decimal) -> Decimal:
    return (left - right).quantize(MONEY_QUANTUM)


def is_exact_zero(value: Decimal) -> bool:
    """Cero exacto. Un cero conseguido por redondeo no es cuadre."""
    return value == ZERO


def require_same_currency(left: str, right: str) -> str:
    """Sumar importes de monedas distintas produce un numero sin significado."""
    if left != right:
        raise CurrencyError(f"cannot combine {left} with {right} without an explicit rate")
    return left
