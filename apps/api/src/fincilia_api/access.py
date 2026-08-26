"""Administracion company-scoped de miembros y roles.

La identidad llega de un IdP (o de la semilla sintetica local). Este modulo no crea
credenciales: solo administra concesiones revocables sobre una empresa ya delegada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from fincilia_contracts.tenancy import ROLES


PRIVILEGED_ROLES = frozenset({"owner", "firm_admin"})
REASON_CODES = frozenset({
    "access_required",
    "responsibility_change",
    "team_change",
    "least_privilege",
    "access_removed",
})


@dataclass(frozen=True)
class AccessManagementError(Exception):
    code: str
    detail: str


def _normalise_subject(subject_id: str) -> str:
    try:
        return str(uuid.UUID(subject_id))
    except (ValueError, TypeError, AttributeError):
        raise AccessManagementError(
            "member-not-eligible", "the selected member is not eligible") from None


def _validate(role: str, reason_code: str) -> None:
    if role not in ROLES:
        raise AccessManagementError("invalid-role", "the selected role is not supported")
    if reason_code not in REASON_CODES:
        raise AccessManagementError(
            "invalid-reason", "the selected reason code is not supported")


def list_members(connection: psycopg.Connection, company_id: str) -> list[dict[str, Any]]:
    """Miembros activos de la firma delegada y roles solo en esta company.

    No devuelve correo, issuer, external subject, credencial ni acceso en otras
    empresas. El directorio operativo no es una exportacion de identidad.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.subject_id, s.display_name, m.firm_role, "
            "       COALESCE(array_agg(DISTINCT g.company_role "
            "                 ORDER BY g.company_role) "
            "         FILTER (WHERE g.grant_id IS NOT NULL "
            "                       AND g.revoked_at IS NULL), ARRAY[]::text[]) "
            "FROM fincilia.engagement e "
            "JOIN fincilia.membership m ON m.firm_id = e.firm_id "
            "JOIN fincilia.subject s ON s.subject_id = m.subject_id "
            "LEFT JOIN fincilia.company_grant g "
            "  ON g.company_id = e.company_id AND g.subject_id = s.subject_id "
            "WHERE e.company_id = %s AND e.status = 'active' "
            "  AND (e.valid_to IS NULL OR e.valid_to >= CURRENT_DATE) "
            "  AND m.status = 'active' AND s.status = 'active' "
            "  AND s.subject_kind = 'person' "
            "GROUP BY s.subject_id, s.display_name, m.firm_role "
            "ORDER BY s.display_name, s.subject_id",
            (company_id,),
        )
        return [
            {
                "subject_id": str(row[0]),
                "display_name": row[1],
                "firm_role": row[2],
                "company_roles": list(row[3]),
            }
            for row in cursor
        ]


def _lock_company(connection: psycopg.Connection, company_id: str) -> None:
    # El mismo lock serializa grant, revoke y la comprobacion de ultimo owner.
    # Una cuenta hecha en memoria entre dos requests no es atomicidad.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT version FROM fincilia.authorization_version "
            "WHERE company_id = %s FOR UPDATE",
            (company_id,),
        )
        if cursor.fetchone() is None:
            raise AccessManagementError(
                "authorization-missing", "the company has no authorization version")


def _eligible_member(
    connection: psycopg.Connection, company_id: str, subject_id: str
) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM fincilia.engagement e "
            "JOIN fincilia.membership m ON m.firm_id = e.firm_id "
            "JOIN fincilia.subject s ON s.subject_id = m.subject_id "
            "WHERE e.company_id = %s AND m.subject_id = %s "
            "  AND e.status = 'active' "
            "  AND (e.valid_to IS NULL OR e.valid_to >= CURRENT_DATE) "
            "  AND m.status = 'active' AND s.status = 'active' "
            "  AND s.subject_kind = 'person'",
            (company_id, subject_id),
        )
        return cursor.fetchone() is not None


def _authorise_role_change(
    *, actor_id: str, target_id: str, role: str, actor_roles: tuple[str, ...],
    allow_self: bool,
) -> None:
    if actor_id == target_id and not allow_self:
        raise AccessManagementError(
            "self-role-change", "a member cannot change their own company roles")
    if role in PRIVILEGED_ROLES and "owner" not in actor_roles:
        raise AccessManagementError(
            "protected-role", "only an owner can change privileged roles")


def grant_role(
    connection: psycopg.Connection,
    *,
    company_id: str,
    actor_id: str,
    actor_roles: tuple[str, ...],
    subject_id: str,
    role: str,
    reason_code: str,
) -> dict[str, Any]:
    _validate(role, reason_code)
    target_id = _normalise_subject(subject_id)
    _authorise_role_change(
        actor_id=actor_id, target_id=target_id, role=role,
        actor_roles=actor_roles, allow_self=False,
    )
    _lock_company(connection, company_id)
    if not _eligible_member(connection, company_id, target_id):
        raise AccessManagementError(
            "member-not-eligible", "the selected member is not eligible")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT grant_id, revoked_at FROM fincilia.company_grant "
            "WHERE company_id = %s AND subject_id = %s AND company_role = %s "
            "FOR UPDATE",
            (company_id, target_id, role),
        )
        existing = cursor.fetchone()
        if existing is not None and existing[1] is None:
            return {
                "subject_id": target_id,
                "role": role,
                "changed": False,
                "replayed": True,
            }
        if existing is None:
            cursor.execute(
                "INSERT INTO fincilia.company_grant "
                "(grant_id, company_id, subject_id, company_role, granted_by) "
                "VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), company_id, target_id, role, actor_id),
            )
        else:
            cursor.execute(
                "UPDATE fincilia.company_grant "
                "SET revoked_at = NULL, granted_by = %s, granted_at = now() "
                "WHERE grant_id = %s",
                (actor_id, existing[0]),
            )
    return {"subject_id": target_id, "role": role, "changed": True, "replayed": False}


def revoke_role(
    connection: psycopg.Connection,
    *,
    company_id: str,
    actor_id: str,
    actor_roles: tuple[str, ...],
    subject_id: str,
    role: str,
    reason_code: str,
) -> dict[str, Any]:
    _validate(role, reason_code)
    target_id = _normalise_subject(subject_id)
    _authorise_role_change(
        actor_id=actor_id, target_id=target_id, role=role,
        actor_roles=actor_roles, allow_self=True,
    )
    _lock_company(connection, company_id)
    if not _eligible_member(connection, company_id, target_id):
        raise AccessManagementError(
            "member-not-eligible", "the selected member is not eligible")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT grant_id FROM fincilia.company_grant "
            "WHERE company_id = %s AND subject_id = %s AND company_role = %s "
            "  AND revoked_at IS NULL FOR UPDATE",
            (company_id, target_id, role),
        )
        existing = cursor.fetchone()
        if existing is None:
            return {
                "subject_id": target_id,
                "role": role,
                "changed": False,
                "replayed": True,
            }
        if role == "owner":
            cursor.execute(
                "SELECT grant_id FROM fincilia.company_grant "
                "WHERE company_id = %s AND company_role = 'owner' "
                "  AND revoked_at IS NULL FOR UPDATE",
                (company_id,),
            )
            if len(cursor.fetchall()) <= 1:
                raise AccessManagementError(
                    "last-owner", "the last active owner cannot be revoked")
        cursor.execute(
            "UPDATE fincilia.company_grant SET revoked_at = now() WHERE grant_id = %s",
            (existing[0],),
        )
    return {"subject_id": target_id, "role": role, "changed": True, "replayed": False}
