"""Contratos compartidos del producto Fincilia.

Codigo de producto, no especificacion. Lo consumen `apps/api` y `workers/*` a
traves de `PYTHONPATH`, sin instalarse como paquete publicado.
"""

from fincilia_contracts.errors import ProblemDetail, problem
from fincilia_contracts.money import (
    MONEY_SCALE,
    SUPPORTED_CURRENCIES,
    ZERO,
    CurrencyError,
    MoneyError,
    add,
    format_money,
    is_exact_zero,
    parse_currency,
    parse_money,
    require_same_currency,
    subtract,
)
from fincilia_contracts.tenancy import (
    PERMISSIONS,
    ROLE_PERMISSIONS,
    ROLES,
    AuthorizationError,
    TenantContext,
    derive_permissions,
    violates_segregation,
)

__all__ = [
    "MONEY_SCALE", "SUPPORTED_CURRENCIES", "ZERO", "CurrencyError", "MoneyError",
    "add", "format_money", "is_exact_zero", "parse_currency", "parse_money",
    "require_same_currency", "subtract",
    "PERMISSIONS", "ROLES", "ROLE_PERMISSIONS", "AuthorizationError", "TenantContext",
    "derive_permissions", "violates_segregation",
    "ProblemDetail", "problem",
]
