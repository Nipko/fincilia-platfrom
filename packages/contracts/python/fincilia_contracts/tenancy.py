"""Contexto de tenancy resuelto en servidor (paquete compartido).

Regla que ordena todo el modulo, tomada de `AGENTS.md` y del modelo de tenancy:

> La autorizacion se resuelve **server-side**; nunca se confia en el `company_id`
> que envia el cliente.

Por eso `TenantContext` solo se construye a partir de reclamaciones ya verificadas
por el servidor. Un `company_id` que llega en el cuerpo o en la query se compara
contra el contexto; jamas lo define.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Roles del producto. El orden no implica jerarquia: cada permiso se declara.
ROLES: Final[tuple[str, ...]] = (
    "owner",
    "firm_admin",
    "preparer",
    "reviewer",
    "auditor",
    "read_only",
)

# La firma es un alcance distinto de una company. Estos permisos existen antes
# de que haya una empresa que pueda formar un TenantContext, por eso no se
# mezclan con la matriz financiera company-scoped.
FIRM_ROLES: Final[tuple[str, ...]] = ("owner", "firm_admin", "member")
FIRM_PERMISSIONS: Final[tuple[str, ...]] = ("company.provision",)
FIRM_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "owner": frozenset(FIRM_PERMISSIONS),
    "firm_admin": frozenset(FIRM_PERMISSIONS),
    "member": frozenset(),
}

# Permisos atomicos. Un permiso ausente es denegacion; no hay comodines.
PERMISSIONS: Final[tuple[str, ...]] = (
    "company.read",
    "document.upload",
    "document.read",
    "dataset.map",
    "dataset.publish",
    "dataset.export",
    "financial_account.manage",
    "data_source.manage",
    "movement.read",
    "match.propose",
    "match.confirm",
    "match.reject",
    "close.prepare",
    "close.approve",
    "audit.read",
    "member.manage",
    "quality.read",
    "quality.manage",
    "report.read",
    "report.export",
)

# Matriz explicita. Un rol que no aparece aqui no tiene ningun permiso.
ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "owner": frozenset(PERMISSIONS),
    "firm_admin": frozenset({
        "company.read", "document.upload", "document.read", "dataset.map",
        "financial_account.manage", "data_source.manage",
        "movement.read", "match.propose", "match.reject", "close.prepare",
        "audit.read", "member.manage", "quality.read", "quality.manage",
        "report.read",
    }),
    "preparer": frozenset({
        "company.read", "document.upload", "document.read", "dataset.map",
        "dataset.export", "movement.read", "match.propose", "match.reject",
        "close.prepare", "quality.read", "quality.manage", "report.read",
        "report.export",
    }),
    "reviewer": frozenset({
        "company.read", "document.read", "dataset.publish", "dataset.export",
        "movement.read", "match.confirm", "match.reject", "close.approve",
        "audit.read", "quality.read", "quality.manage", "report.read",
        "report.export",
    }),
    "auditor": frozenset({
        "company.read", "document.read", "dataset.export", "movement.read",
        "audit.read", "quality.read", "report.read", "report.export",
    }),
    "read_only": frozenset({
        "company.read", "document.read", "movement.read", "quality.read",
        "report.read",
    }),
}

# Segregacion de funciones: quien puede proponer no puede confirmar lo suyo.
# Se expresa como pares de permisos que un mismo sujeto no ejerce sobre el mismo
# objeto, y se comprueba en el dominio, no solo en el rol.
SEGREGATED_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("match.propose", "match.confirm"),
    ("close.prepare", "close.approve"),
    ("dataset.map", "dataset.publish"),
)


class AuthorizationError(PermissionError):
    """La operacion no esta autorizada en este contexto."""


@dataclass(frozen=True)
class TenantContext:
    """Alcance verificado por el servidor para una peticion.

    `authorization_version` viaja con el contexto para que una revocacion invalide
    trabajo en vuelo: si la version cambio, lo que se autorizo antes ya no vale.
    """

    subject_id: str
    firm_id: str
    company_id: str
    roles: tuple[str, ...]
    authorization_version: int
    engagement_id: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.subject_id or not self.firm_id or not self.company_id:
            raise AuthorizationError(
                "a tenant context always names a subject, a firm and a company")
        unknown = sorted(set(self.roles) - set(ROLES))
        if unknown:
            raise AuthorizationError(f"unknown roles: {unknown}")
        if self.authorization_version < 1:
            raise AuthorizationError("authorization_version starts at 1")
        object.__setattr__(self, "permissions", derive_permissions(self.roles))

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if permission not in PERMISSIONS:
            raise AuthorizationError(f"unknown permission {permission!r}")
        if permission not in self.permissions:
            raise AuthorizationError(
                f"subject lacks {permission} on company {self.company_id}")

    def require_company(self, claimed_company_id: str) -> None:
        """El `company_id` del cliente se compara; nunca define el alcance."""
        if claimed_company_id != self.company_id:
            raise AuthorizationError(
                "the requested company does not match the authorised context")


def derive_permissions(roles: tuple[str, ...] | list[str]) -> frozenset[str]:
    """Union de permisos. Un rol desconocido no aporta nada: falla cerrado."""
    granted: set[str] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)


def derive_firm_permissions(role: str) -> frozenset[str]:
    """Permisos previos a company. Un rol desconocido no concede nada."""
    return FIRM_ROLE_PERMISSIONS.get(role, frozenset())


def require_firm_permission(role: str, permission: str) -> None:
    if permission not in FIRM_PERMISSIONS:
        raise AuthorizationError(f"unknown firm permission {permission!r}")
    if permission not in derive_firm_permissions(role):
        raise AuthorizationError(f"firm role lacks {permission}")


def violates_segregation(permission: str, already_exercised: set[str]) -> str | None:
    """Devuelve el permiso en conflicto, si ejercer `permission` rompe la SoD."""
    for left, right in SEGREGATED_PAIRS:
        if permission == right and left in already_exercised:
            return left
        if permission == left and right in already_exercised:
            return right
    return None
