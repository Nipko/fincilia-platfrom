"""Acceso acotado al plano de administración de Fincilia."""

from __future__ import annotations

import psycopg


def claim_initial_superadmin(connection: psycopg.Connection, *, subject_id: str,
                             verified_email_ref: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.claim_initial_platform_superadmin(%s, %s)",
            (subject_id, verified_email_ref),
        )
        row = cursor.fetchone()
    return bool(row and row[0])


def roles(connection: psycopg.Connection) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT platform_role FROM fincilia.platform_roles_for_current_subject()"
        )
        return [row[0] for row in cursor.fetchall()]


def overview(connection: psycopg.Connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute("SELECT fincilia.platform_admin_overview()")
        row = cursor.fetchone()
    return dict(row[0]) if row else {}


def identities(connection: psycopg.Connection, *, limit: int) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subject_id, display_name, status, created_at, active_firms, "
            "platform_roles FROM fincilia.platform_admin_identities(%s)", (limit,)
        )
        rows = cursor.fetchall()
    return [{
        "subject_id": row[0], "display_name": row[1], "status": row[2],
        "created_at": row[3].isoformat(), "active_firms": int(row[4]),
        "platform_roles": list(row[5] or []),
    } for row in rows]


def organizations(connection: psycopg.Connection, *, limit: int) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT firm_id, legal_name, status, created_at, active_members "
            "FROM fincilia.platform_admin_organizations(%s)", (limit,)
        )
        rows = cursor.fetchall()
    return [{
        "firm_id": row[0], "legal_name": row[1], "status": row[2],
        "created_at": row[3].isoformat(), "active_members": int(row[4]),
    } for row in rows]


def audit_events(connection: psycopg.Connection, *, limit: int) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT event_id, actor_subject_id, actor_name, action, resource_kind, "
            "resource_ref, outcome, detail, occurred_at "
            "FROM fincilia.platform_admin_audit(%s)", (limit,)
        )
        rows = cursor.fetchall()
    return [{
        "event_id": row[0], "actor_subject_id": row[1], "actor_name": row[2],
        "action": row[3], "resource_kind": row[4], "resource_ref": row[5],
        "outcome": row[6], "detail": row[7], "occurred_at": row[8].isoformat(),
    } for row in rows]


def set_subject_status(connection: psycopg.Connection, *, subject_id: str,
                       status: str, reason_code: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subject_id, display_name, status, created_at "
            "FROM fincilia.platform_admin_set_subject_status(%s, %s, %s)",
            (subject_id, status, reason_code),
        )
        row = cursor.fetchone()
    if row is None:
        raise LookupError("platform subject not found")
    return {"subject_id": row[0], "display_name": row[1], "status": row[2],
            "created_at": row[3].isoformat()}


def grant_role(connection: psycopg.Connection, *, subject_id: str,
               platform_role: str, reason_code: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT assignment_id, subject_id, platform_role, status, granted_at "
            "FROM fincilia.platform_admin_grant_role(%s, %s, %s)",
            (subject_id, platform_role, reason_code),
        )
        row = cursor.fetchone()
    if row is None:
        raise LookupError("platform role grant failed")
    return {"assignment_id": row[0], "subject_id": row[1],
            "platform_role": row[2], "status": row[3],
            "granted_at": row[4].isoformat()}


def revoke_role(connection: psycopg.Connection, *, subject_id: str,
                platform_role: str, reason_code: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.platform_admin_revoke_role(%s, %s, %s)",
            (subject_id, platform_role, reason_code),
        )
        row = cursor.fetchone()
    return bool(row and row[0])
