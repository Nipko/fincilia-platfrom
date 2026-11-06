"""Perfil operativo por empresa y modo de revision (ADR-039, FNC-SMB-001).

El perfil vive en ``fincilia.company`` y solo cambia mediante una fila del
historial append-only ``company_operating_profile_change``. PostgreSQL vuelve a
comprobar que quien cambia es owner activo y es el disparador de cada decision
quien fija ``review_mode``: estas funciones dan mensajes utiles antes de llegar a
la base, nunca sustituyen sus guardas.

- ``estricto``: la misma persona no propone y decide. Comportamiento historico.
- ``simple``: la misma persona puede decidir lo que propuso; la decision queda
  ``self_reviewed`` y se muestra como autorrevisada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from . import repository


SIMPLE = "simple"
STRICT = "estricto"
PROFILES = frozenset({SIMPLE, STRICT})
TEAM_SIZE_BANDS = {"1-2": SIMPLE, "3+": STRICT}
REVIEW_MODES = frozenset({"independent", "self_reviewed", "approved_rule"})
MIN_REASON = 10
MAX_REASON = 500
HISTORY_LIMIT = 20


@dataclass(frozen=True)
class OperatingProfileError(Exception):
    code: str
    detail: str
    status: int = 422


def current_profile(connection: psycopg.Connection, company_id: str) -> str:
    """Perfil vigente bajo el alcance ya fijado. Invisible equivale a estricto."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT operating_profile FROM fincilia.company WHERE company_id = %s",
            (company_id,))
        row = cursor.fetchone()
    if row is None or row[0] not in PROFILES:
        return STRICT
    return str(row[0])


def scoped_profile(connection: psycopg.Connection) -> str:
    """Perfil de la empresa del alcance ya fijado en la sesion (GUC)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT operating_profile FROM fincilia.company "
            "WHERE company_id::text = current_setting('fincilia.company_id', true)")
        row = cursor.fetchone()
    if row is None or row[0] not in PROFILES:
        return STRICT
    return str(row[0])


def review_mode_for(connection: psycopg.Connection, *, company_id: str,
                    proposer_id: str, decider_id: str) -> str | None:
    """Mismo criterio que ``fincilia.review_mode_for``; None significa rechazo."""
    if str(proposer_id) != str(decider_id):
        return "independent"
    if current_profile(connection, company_id) == SIMPLE:
        return "self_reviewed"
    return None


def allows_self_review(connection: psycopg.Connection, company_id: str) -> bool:
    return current_profile(connection, company_id) == SIMPLE


def resolve_initial_profile(*, operating_profile: str | None,
                            team_size_band: str | None) -> str:
    """Perfil elegido en el alta. Sin respuesta, el valor seguro es estricto.

    Una eleccion explicita del perfil prevalece sobre la banda; la banda solo
    sugiere (1-2 personas -> simple, 3 o mas -> estricto).
    """
    if operating_profile is not None:
        if operating_profile not in PROFILES:
            raise OperatingProfileError(
                "operating-profile-invalid", "operating_profile must be simple or estricto")
        return operating_profile
    if team_size_band is not None:
        if team_size_band not in TEAM_SIZE_BANDS:
            raise OperatingProfileError(
                "team-size-band-invalid", "team_size_band must be 1-2 or 3+")
        return TEAM_SIZE_BANDS[team_size_band]
    return STRICT


def _history(connection: psycopg.Connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT h.change_id, h.version, h.from_profile, h.to_profile, h.reason, "
            "       h.changed_by, s.display_name, h.changed_at "
            "FROM fincilia.company_operating_profile_change h "
            "JOIN fincilia.subject s ON s.subject_id = h.changed_by "
            "ORDER BY h.version DESC LIMIT %s", (HISTORY_LIMIT,))
        rows = cursor.fetchall()
    return [{
        "change_id": str(row[0]),
        "version": int(row[1]),
        "from_profile": row[2],
        "to_profile": row[3],
        "reason": row[4],
        "changed_by": str(row[5]),
        "changed_by_name": row[6],
        "changed_at": row[7].isoformat(),
    } for row in rows]


def read_profile(connection: psycopg.Connection, *, company_id: str,
                 roles: tuple[str, ...] | list[str]) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "operating_profile": current_profile(connection, company_id),
        "can_change": "owner" in roles,
        "history": _history(connection),
        "changed": False,
    }


def _reason(value: str) -> str:
    reason = value.strip()
    if not MIN_REASON <= len(reason) <= MAX_REASON or any(
            ord(char) < 32 for char in reason):
        raise OperatingProfileError(
            "operating-profile-reason-invalid",
            "reason must contain 10 to 500 printable characters")
    return reason


def change_profile(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, roles: tuple[str, ...] | list[str],
                   operating_profile: str, reason: str) -> dict[str, Any]:
    """Registra un cambio de perfil. Solo el owner; la base lo vuelve a exigir."""
    if operating_profile not in PROFILES:
        raise OperatingProfileError(
            "operating-profile-invalid", "operating_profile must be simple or estricto")
    if "owner" not in roles:
        raise OperatingProfileError(
            "operating-profile-owner-required",
            "only the company owner can change the operating profile", status=403)
    clean_reason = _reason(reason)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 39001))", (company_id,))
        cursor.execute(
            "SELECT operating_profile FROM fincilia.company WHERE company_id = %s "
            "FOR UPDATE", (company_id,))
        row = cursor.fetchone()
        if row is None:
            raise OperatingProfileError(
                "operating-profile-unavailable", "the company is unavailable", status=404)
        previous = str(row[0])
        if previous == operating_profile:
            return {**read_profile(connection, company_id=company_id, roles=roles),
                    "changed": False}
        cursor.execute(
            "SELECT COALESCE(max(version), 0) + 1 "
            "FROM fincilia.company_operating_profile_change WHERE company_id = %s",
            (company_id,))
        version = int(cursor.fetchone()[0])
    change_id = str(uuid.uuid4())
    try:
        with connection.transaction():
            audit_event_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action="company.operating_profile.change",
                resource_kind="company", resource_ref=company_id,
                outcome="allowed", detail={
                    "from_profile": previous, "to_profile": operating_profile,
                    "version": version, "change_id": change_id,
                })
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.company_operating_profile_change "
                    "(change_id, company_id, version, from_profile, to_profile, "
                    " reason, changed_by, audit_event_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (change_id, company_id, version, previous, operating_profile,
                     clean_reason, actor_id, audit_event_id))
    except psycopg.errors.InsufficientPrivilege:
        raise OperatingProfileError(
            "operating-profile-owner-required",
            "only the company owner can change the operating profile",
            status=403) from None
    return {**read_profile(connection, company_id=company_id, roles=roles),
            "changed": True}
