"""Cierre y reapertura append-only de periodos contables.

El modulo solo fija una evidencia ya revisada. No crea asientos, no calcula
dinero y no convierte un informe en certificado. PostgreSQL conserva la
autoridad del estado y bloquea escrituras financieras aun si se evita la API.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import datetime as dt
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import close_review, repository


SNAPSHOT_SCHEMA_VERSION = "accounting-close-v1"
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
REOPEN_REASONS = frozenset({
    "late_evidence", "material_error", "regulatory_adjustment",
    "scope_correction", "other_documented",
})
REOPEN_DECISION_REASONS = {
    "approved": frozenset({"documented_basis_confirmed"}),
    "rejected": frozenset({
        "insufficient_basis", "wrong_scope", "duplicate_request",
    }),
}


@dataclass(frozen=True)
class ClosePeriodError(Exception):
    code: str
    detail: str


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ClosePeriodError(
            "accounting-period-input-invalid", f"{field} must be a UUID") from None


def _key(value: str) -> str:
    if not IDEMPOTENCY.fullmatch(value):
        raise ClosePeriodError(
            "accounting-period-idempotency-invalid",
            "Idempotency-Key must contain 16 to 128 safe characters")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_snapshot(packet: dict[str, Any],
                   manifest: dict[str, Any]) -> dict[str, Any]:
    """Copia solo referencias y estados digest-only del expediente revisado."""
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "packet_id": packet["packet_id"],
        "packet_version": int(packet["version"]),
        "manifest_digest": packet["manifest_digest"],
        "controls": manifest["controls"],
        "sources": manifest["sources"],
        "accounts": manifest["accounts"],
    }


PERIOD_SELECT = (
    "SELECT c.close_id, c.period_start, c.period_end, c.version, c.packet_id, "
    "c.observed_manifest_digest, c.snapshot_schema_version, c.snapshot, "
    "c.snapshot_digest, c.closed_by, closer.display_name, c.closed_at, "
    "r.request_id, r.reason_code, r.rationale, r.requested_by, "
    "requester.display_name, r.requested_at, d.decision_id, d.decision, "
    "d.reason_code, d.decided_by, decider.display_name, d.decided_at "
    "FROM fincilia.accounting_period_close c "
    "JOIN fincilia.subject closer ON closer.subject_id=c.closed_by "
    "LEFT JOIN fincilia.accounting_period_reopen_request r "
    "  ON r.close_id=c.close_id AND r.company_id=c.company_id "
    "LEFT JOIN fincilia.subject requester ON requester.subject_id=r.requested_by "
    "LEFT JOIN fincilia.accounting_period_reopen_decision d "
    "  ON d.request_id=r.request_id AND d.company_id=r.company_id "
    "LEFT JOIN fincilia.subject decider ON decider.subject_id=d.decided_by "
)


def _row(row: tuple[Any, ...], *, replayed: bool = False) -> dict[str, Any]:
    decision = row[19]
    status = "reopened" if decision == "approved" else (
        "reopen_requested" if row[12] is not None and decision is None else "closed")
    return {
        "close_id": str(row[0]),
        "period_start": row[1].isoformat(),
        "period_end": row[2].isoformat(),
        "version": int(row[3]),
        "packet_id": str(row[4]),
        "observed_manifest_digest": row[5],
        "snapshot_schema_version": row[6],
        "snapshot": row[7],
        "snapshot_digest": row[8],
        "closed_by": str(row[9]),
        "closer_name": row[10],
        "closed_at": row[11].isoformat(),
        "status": status,
        "reopen_request": None if row[12] is None else {
            "request_id": str(row[12]),
            "reason_code": row[13],
            "rationale": row[14],
            "requested_by": str(row[15]),
            "requester_name": row[16],
            "requested_at": row[17].isoformat(),
            "decision_id": str(row[18]) if row[18] else None,
            "decision": decision,
            "decision_reason_code": row[20],
            "decided_by": str(row[21]) if row[21] else None,
            "decider_name": row[22],
            "decided_at": row[23].isoformat() if row[23] else None,
        },
        "replayed": replayed,
        "financial_effect": "period_state_only",
        "certifies_financial_statements": False,
    }


def load_close(connection: psycopg.Connection, close_id: str,
               *, replayed: bool = False) -> dict[str, Any] | None:
    close_id = _uuid(close_id, field="close_id")
    with connection.cursor() as cursor:
        cursor.execute(PERIOD_SELECT + "WHERE c.close_id=%s", (close_id,))
        row = cursor.fetchone()
    return _row(row, replayed=replayed) if row else None


def list_closes(connection: psycopg.Connection, *, limit: int = DEFAULT_LIMIT,
                period_start: str | None = None,
                period_end: str | None = None) -> dict[str, Any]:
    bounded = int(limit)
    if not 1 <= bounded <= MAX_LIMIT:
        raise ClosePeriodError(
            "accounting-period-limit-invalid", "limit must be between 1 and 100")
    filters: list[str] = []
    parameters: list[Any] = []
    if (period_start is None) != (period_end is None):
        raise ClosePeriodError(
            "accounting-period-range-invalid", "both period dates are required")
    if period_start is not None:
        try:
            start = dt.date.fromisoformat(period_start)
            end = dt.date.fromisoformat(period_end or "")
        except ValueError:
            raise ClosePeriodError(
                "accounting-period-range-invalid", "period dates must be ISO dates") from None
        if end < start:
            raise ClosePeriodError(
                "accounting-period-range-invalid", "period_end precedes period_start")
        filters.append("c.period_start=%s AND c.period_end=%s")
        parameters.extend((start, end))
    where = "WHERE " + " AND ".join(filters) if filters else ""
    parameters.append(bounded + 1)
    with connection.cursor() as cursor:
        cursor.execute(
            PERIOD_SELECT + where
            + " ORDER BY c.period_end DESC, c.period_start DESC, c.version DESC, "
              "c.close_id LIMIT %s", tuple(parameters))
        rows = list(cursor)
    return {
        "items": [_row(row) for row in rows[:bounded]],
        "has_more": len(rows) > bounded,
        "limit": bounded,
    }


def _lock_command(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"accounting-period-command:{company_id}:{actor_id}:{key}",))


def _company_lock(connection: psycopg.Connection, company_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 35006))",
            (company_id,))


def _receipt(connection: psycopg.Connection, *, actor_id: str,
             key: str) -> tuple[Any, ...] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT action, request_digest, result_kind, result_ref "
            "FROM fincilia.accounting_period_command_receipt "
            "WHERE actor_id=%s AND idempotency_key=%s", (actor_id, key))
        return cursor.fetchone()


def _close_for_result(connection: psycopg.Connection, result_kind: str,
                      result_ref: str, *, replayed: bool) -> dict[str, Any] | None:
    if result_kind == "close":
        return load_close(connection, result_ref, replayed=replayed)
    with connection.cursor() as cursor:
        if result_kind == "reopen_request":
            cursor.execute(
                "SELECT close_id FROM fincilia.accounting_period_reopen_request "
                "WHERE request_id=%s", (result_ref,))
        else:
            cursor.execute(
                "SELECT r.close_id FROM fincilia.accounting_period_reopen_decision d "
                "JOIN fincilia.accounting_period_reopen_request r "
                "ON r.request_id=d.request_id AND r.company_id=d.company_id "
                "WHERE d.decision_id=%s", (result_ref,))
        row = cursor.fetchone()
    return load_close(connection, str(row[0]), replayed=replayed) if row else None


def _replay(connection: psycopg.Connection, *, action: str, digest: str,
            receipt: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt[0] != action or receipt[1] != digest:
        raise ClosePeriodError(
            "accounting-period-idempotency-conflict",
            "the idempotency key was already used with another command")
    result = _close_for_result(
        connection, str(receipt[2]), str(receipt[3]), replayed=True)
    if result is None:
        raise RuntimeError("accounting period receipt points to no visible result")
    return result


def _write_receipt(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, action: str, key: str, digest: str,
                   result_kind: str, result_ref: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.accounting_period_command_receipt "
            "(company_id, actor_id, action, idempotency_key, request_digest, "
            "result_kind, result_ref) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (company_id, actor_id, action, key, digest, result_kind, result_ref))


def close_period(connection: psycopg.Connection, *, company_id: str,
                 actor_id: str, idempotency_key: str, packet_id: str) -> dict[str, Any]:
    packet_id = _uuid(packet_id, field="packet_id")
    key = _key(idempotency_key)
    request_digest = _digest({"packet_id": packet_id})
    _lock_command(connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay(
        connection, action="close", digest=request_digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay
    _company_lock(connection, company_id)
    packet = close_review.load_packet(connection, packet_id)
    if packet is None:
        raise ClosePeriodError(
            "accounting-period-packet-unavailable", "review packet is unavailable")
    if packet["decision"] != "evidence_reviewed":
        raise ClosePeriodError(
            "accounting-period-not-reviewed", "review packet is not evidence_reviewed")
    if packet["decided_by"] != actor_id or packet["prepared_by"] == actor_id:
        raise ClosePeriodError(
            "accounting-period-segregation-of-duties",
            "only the assigned independent reviewer can close this period")
    manifest, current_digest = close_review.current_manifest(
        connection, period_start=packet["period_start"],
        period_end=packet["period_end"])
    if current_digest != packet["manifest_digest"]:
        raise ClosePeriodError(
            "accounting-period-evidence-stale",
            "period evidence changed after review; create a new packet")
    snapshot = build_snapshot(packet, manifest)
    snapshot_digest = _digest(snapshot)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(max(version), 0) + 1 "
            "FROM fincilia.accounting_period_close "
            "WHERE period_start=%s AND period_end=%s",
            (packet["period_start"], packet["period_end"]))
        version = int(cursor.fetchone()[0])
    close_id = str(uuid.uuid4())
    with connection.transaction():
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action="accounting.period.close", resource_kind="accounting_period",
            resource_ref=close_id, outcome="allowed", detail={
                "period_start": packet["period_start"],
                "period_end": packet["period_end"], "version": version,
                "packet_id": packet_id, "manifest_digest": current_digest,
                "snapshot_digest": snapshot_digest,
            })
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.accounting_period_close "
                "(close_id, company_id, period_start, period_end, version, packet_id, "
                "observed_manifest_digest, snapshot_schema_version, snapshot, "
                "snapshot_digest, closed_by, audit_event_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (close_id, company_id, packet["period_start"], packet["period_end"],
                 version, packet_id, current_digest, SNAPSHOT_SCHEMA_VERSION,
                 Jsonb(snapshot), snapshot_digest, actor_id, audit_event_id))
        _write_receipt(
            connection, company_id=company_id, actor_id=actor_id, action="close",
            key=key, digest=request_digest, result_kind="close", result_ref=close_id)
    result = load_close(connection, close_id)
    if result is None:
        raise RuntimeError("created accounting period close cannot be read back")
    return result


def request_reopen(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, idempotency_key: str, close_id: str,
                   reason_code: str, rationale: str) -> dict[str, Any]:
    close_id = _uuid(close_id, field="close_id")
    if reason_code not in REOPEN_REASONS:
        raise ClosePeriodError(
            "accounting-period-reopen-reason-invalid", "reopen reason is not allowed")
    rationale = rationale.strip()
    if not 10 <= len(rationale) <= 500 or any(ord(char) < 32 for char in rationale):
        raise ClosePeriodError(
            "accounting-period-reopen-rationale-invalid",
            "rationale must contain 10 to 500 printable characters")
    key = _key(idempotency_key)
    request_digest = _digest({
        "close_id": close_id, "reason_code": reason_code, "rationale": rationale,
    })
    _lock_command(connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay(
        connection, action="request_reopen", digest=request_digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay
    _company_lock(connection, company_id)
    current = load_close(connection, close_id)
    if current is None:
        raise ClosePeriodError(
            "accounting-period-unavailable", "accounting period is unavailable")
    if current["status"] != "closed" or current["reopen_request"] is not None:
        raise ClosePeriodError(
            "accounting-period-reopen-unavailable",
            "period is not an active close without a request")
    request_id = str(uuid.uuid4())
    with connection.transaction():
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action="accounting.period.reopen.request",
            resource_kind="accounting_period", resource_ref=close_id,
            outcome="allowed", detail={"reason_code": reason_code})
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.accounting_period_reopen_request "
                "(request_id, company_id, close_id, reason_code, rationale, "
                "requested_by, audit_event_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (request_id, company_id, close_id, reason_code, rationale,
                 actor_id, audit_event_id))
        _write_receipt(
            connection, company_id=company_id, actor_id=actor_id,
            action="request_reopen", key=key, digest=request_digest,
            result_kind="reopen_request", result_ref=request_id)
    result = load_close(connection, close_id)
    if result is None:
        raise RuntimeError("reopen request cannot be read back")
    return result


def decide_reopen(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, idempotency_key: str, request_id: str,
                  decision: str, reason_code: str) -> dict[str, Any]:
    request_id = _uuid(request_id, field="request_id")
    if (decision not in REOPEN_DECISION_REASONS
            or reason_code not in REOPEN_DECISION_REASONS[decision]):
        raise ClosePeriodError(
            "accounting-period-reopen-decision-invalid",
            "decision and reason_code are not an allowed combination")
    action = "approve_reopen" if decision == "approved" else "reject_reopen"
    key = _key(idempotency_key)
    request_digest = _digest({
        "request_id": request_id, "decision": decision, "reason_code": reason_code,
    })
    _lock_command(connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay(
        connection, action=action, digest=request_digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay
    _company_lock(connection, company_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT close_id, requested_by FROM fincilia.accounting_period_reopen_request "
            "WHERE request_id=%s", (request_id,))
        requested = cursor.fetchone()
        cursor.execute(
            "SELECT 1 FROM fincilia.accounting_period_reopen_decision "
            "WHERE request_id=%s", (request_id,))
        terminal = cursor.fetchone()
    if requested is None:
        raise ClosePeriodError(
            "accounting-period-reopen-unavailable", "reopen request is unavailable")
    if str(requested[1]) == actor_id:
        raise ClosePeriodError(
            "accounting-period-segregation-of-duties",
            "the requester cannot decide their own reopen request")
    if terminal is not None:
        raise ClosePeriodError(
            "accounting-period-reopen-already-decided", "reopen request is terminal")
    decision_id = str(uuid.uuid4())
    with connection.transaction():
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action=f"accounting.period.reopen.{decision}",
            resource_kind="accounting_period", resource_ref=str(requested[0]),
            outcome="allowed", detail={"decision": decision,
                                        "reason_code": reason_code})
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.accounting_period_reopen_decision "
                "(decision_id, company_id, request_id, decision, reason_code, "
                "decided_by, audit_event_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (decision_id, company_id, request_id, decision, reason_code,
                 actor_id, audit_event_id))
        _write_receipt(
            connection, company_id=company_id, actor_id=actor_id, action=action,
            key=key, digest=request_digest, result_kind="reopen_decision",
            result_ref=decision_id)
    result = load_close(connection, str(requested[0]))
    if result is None:
        raise RuntimeError("reopen decision cannot be read back")
    return result
