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


def operational_diagnostics(connection: psycopg.Connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute("SELECT fincilia.platform_operational_diagnostics()")
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


# --------------------------------------------------------------------------- #
# Versiones del motor (ADR-039 §6, FNC-SMB-005)
# --------------------------------------------------------------------------- #

RELEASE_READER_ROLES = ("platform_superadmin", "platform_operator", "platform_auditor")


def _require_platform_role(connection: psycopg.Connection,
                           allowed: tuple[str, ...]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.current_subject_has_platform_role(%s::text[])",
            (list(allowed),))
        row = cursor.fetchone()
    if not row or row[0] is not True:
        raise psycopg.errors.InsufficientPrivilege("platform access denied")


def engine_releases(connection: psycopg.Connection) -> list[dict]:
    """Versiones del motor con lo que se aprobaria. Solo roles de plataforma."""
    from fincilia_contracts.release import digest_of

    _require_platform_role(connection, RELEASE_READER_ROLES)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.release_key, r.state, r.classification, "
            "       r.canonical_schema_version, r.components, r.created_at, "
            "       a.actor_identity, a.approval_ref, a.occurred_at, "
            "       a.components_digest "
            "FROM fincilia.engine_release r "
            "LEFT JOIN fincilia.release_approval a "
            "       ON a.release_id = r.release_id AND a.action = 'approved' "
            "ORDER BY r.created_at DESC, r.release_key LIMIT 100")
        rows = cursor.fetchall()
    return [{
        "release_key": row[0], "state": row[1], "classification": row[2],
        "canonical_schema_version": row[3], "components": row[4] or [],
        "components_digest": digest_of(row[4] or []),
        "created_at": row[5].isoformat(),
        "approval": None if row[6] is None else {
            "actor_identity": row[6], "approval_ref": row[7],
            "approved_at": row[8].isoformat(),
            "components_digest": str(row[9]).strip(),
            "covers_current_components": str(row[9]).strip() == digest_of(row[4] or []),
        },
    } for row in rows]


def approve_engine_release(connection: psycopg.Connection, *, release_key: str,
                           components_digest: str, approval_ref: str,
                           rationale: str) -> dict:
    """Firma lo que se mostro. La base vuelve a exigir el rol y los componentes."""
    import json

    from fincilia_contracts.release import digest_of

    _require_platform_role(connection, ("platform_superadmin", "platform_operator"))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT components FROM fincilia.engine_release WHERE release_key = %s",
            (release_key,))
        row = cursor.fetchone()
    if row is None:
        raise LookupError("engine release not found")
    components = row[0] or []
    if digest_of(components) != components_digest:
        raise ValueError("the components shown are not the components stored")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT release_id, release_key, state, actor_identity, approved_at "
            "FROM fincilia.platform_admin_approve_engine_release("
            "  %s, %s::jsonb, %s, %s, %s)",
            (release_key, json.dumps(components), components_digest,
             approval_ref, rationale))
        result = cursor.fetchone()
    return {"release_id": result[0], "release_key": result[1], "state": result[2],
            "actor_identity": result[3], "approved_at": result[4].isoformat(),
            "components_digest": components_digest}
