"""Expedientes digest-only para revision previa al cierre.

El ledger fija exactamente el diagnostico de ``close_readiness`` que una
persona vio. No calcula dinero, no acepta excepciones, no crea snapshots y no
habilita un cierre. Una decision positiva solo afirma que otro sujeto reviso la
misma manifestacion que sigue vigente al decidir.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from fincilia_contracts.tenancy import derive_permissions

from . import access, close_readiness, repository


MANIFEST_SCHEMA_VERSION = "close-evidence-v1"
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
DECISION_REASONS = {
    "evidence_reviewed": frozenset({"controls_reviewed"}),
    "changes_requested": frozenset({
        "missing_evidence", "inconsistent_scope", "quality_blocker",
        "lineage_gap", "reconciliation_gap",
    }),
}


@dataclass(frozen=True)
class CloseReviewError(Exception):
    code: str
    detail: str


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise CloseReviewError(
            "close-review-input-invalid", f"{field} must be a UUID") from None


def _date(value: str | dt.date, *, field: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise CloseReviewError(
            "close-review-input-invalid", f"{field} must be an ISO date") from None


def _key(value: str) -> str:
    if not IDEMPOTENCY.fullmatch(value):
        raise CloseReviewError(
            "close-review-idempotency-invalid",
            "Idempotency-Key must contain 16 to 128 safe characters")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_manifest(period: dict[str, Any]) -> dict[str, Any]:
    """Reduce el diagnostico a identidades, estados y conteos estables.

    Los ``detail``, nombres y timestamps quedan deliberadamente fuera: pueden
    contener texto mutable o aportado por una persona y no hacen falta para
    demostrar que se reviso la misma evidencia financiera.
    """
    controls = sorted(({
        "code": str(item["code"]),
        "state": str(item["state"]),
        "count": int(item["count"]),
    } for item in period.get("controls", [])), key=lambda item: item["code"])
    sources = sorted(({
        "expectation_id": item["expectation_id"],
        "data_source_id": item["data_source_id"],
        "financial_account_id": item.get("financial_account_id"),
        "expectation_state": item["expectation_state"],
        "dataset_version_id": item.get("dataset_version_id"),
        "dataset_state": item.get("dataset_state"),
        "completeness_state": item.get("completeness_state"),
        "lineage_state": item.get("lineage_state"),
        "rejected_count": int(item.get("rejected_count", 0)),
        "movement_count": int(item.get("movement_count", 0)),
    } for item in period.get("sources", [])), key=lambda item: item["expectation_id"])
    accounts = sorted(({
        "financial_account_id": item["financial_account_id"],
        "source_count": int(item["source_count"]),
        "assessment_count": int(item["assessment_count"]),
        "statement_root_id": item.get("statement_root_id"),
        "statement_id": item.get("statement_id"),
        "statement_version": item.get("statement_version"),
        "statement_state": item.get("statement_state"),
        "statement_lineage_state": item.get("statement_lineage_state"),
        "coverage_state": item["coverage_state"],
    } for item in period.get("account_reconciliations", [])),
        key=lambda item: item["financial_account_id"])
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "diagnostic_status": period["status"],
        "controls": controls,
        "sources": sources,
        "accounts": accounts,
    }


def _exact_period(connection: psycopg.Connection, *, period_start: dt.date,
                  period_end: dt.date) -> dict[str, Any]:
    if period_end < period_start:
        raise CloseReviewError(
            "close-review-period-invalid", "period_end must not precede period_start")
    diagnostic = close_readiness.list_close_readiness(
        connection, limit=close_readiness.MAX_LIMIT)
    for period in diagnostic["items"]:
        if (period["period_start"] == period_start.isoformat()
                and period["period_end"] == period_end.isoformat()):
            return period
    raise CloseReviewError(
        "close-review-period-unavailable",
        "the requested period is not in the current company diagnostic window")


def eligible_reviewers(connection: psycopg.Connection,
                       *, company_id: str) -> list[dict[str, Any]]:
    """Personas vigentes con capacidad de revision, sin correo ni otros tenants."""
    candidates = []
    for member in access.list_members(connection, company_id):
        roles = tuple(member["company_roles"])
        if "close.approve" not in derive_permissions(roles):
            continue
        candidates.append({
            "subject_id": member["subject_id"],
            "display_name": member["display_name"],
            "company_roles": list(roles),
        })
    return candidates


def _reviewer_is_eligible(connection: psycopg.Connection, subject_id: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.is_close_reviewer_eligible("
            "current_setting('fincilia.company_id')::uuid, %s)",
            (subject_id,))
        return bool(cursor.fetchone()[0])


PACKET_SELECT = (
    "SELECT p.packet_id, p.period_start, p.period_end, p.version, "
    "p.manifest_schema_version, p.manifest, p.manifest_digest, "
    "p.diagnostic_status, p.prepared_by, author.display_name, "
    "p.assigned_reviewer_id, reviewer.display_name, p.prepared_at, "
    "d.decision_id, d.decision, d.reason_code, d.decided_by, decider.display_name, "
    "d.decided_at, fincilia.is_close_reviewer_eligible("
    "p.company_id, p.assigned_reviewer_id) "
    "FROM fincilia.close_review_packet p "
    "JOIN fincilia.subject author ON author.subject_id=p.prepared_by "
    "JOIN fincilia.subject reviewer ON reviewer.subject_id=p.assigned_reviewer_id "
    "LEFT JOIN fincilia.close_review_decision d "
    "  ON d.packet_id=p.packet_id AND d.company_id=p.company_id "
    "LEFT JOIN fincilia.subject decider ON decider.subject_id=d.decided_by "
)


def _packet_row(row: tuple[Any, ...], *, replayed: bool = False) -> dict[str, Any]:
    decision = row[14]
    return {
        "packet_id": str(row[0]),
        "period_start": row[1].isoformat(),
        "period_end": row[2].isoformat(),
        "version": int(row[3]),
        "manifest_schema_version": row[4],
        "manifest": row[5],
        "manifest_digest": row[6],
        "diagnostic_status": row[7],
        "prepared_by": str(row[8]),
        "preparer_name": row[9],
        "assigned_reviewer_id": str(row[10]),
        "reviewer_name": row[11],
        "prepared_at": row[12].isoformat(),
        "decision_id": str(row[13]) if row[13] else None,
        "decision": decision,
        "reason_code": row[15],
        "decided_by": str(row[16]) if row[16] else None,
        "decider_name": row[17],
        "decided_at": row[18].isoformat() if row[18] else None,
        "reviewer_eligible": bool(row[19]),
        "status": decision or "pending_review",
        "replayed": replayed,
        "financial_effect": "none",
        "certifies_close": False,
        "can_execute_close": False,
    }


def load_packet(connection: psycopg.Connection, packet_id: str,
                *, replayed: bool = False) -> dict[str, Any] | None:
    packet_id = _uuid(packet_id, field="packet_id")
    with connection.cursor() as cursor:
        cursor.execute(PACKET_SELECT + "WHERE p.packet_id=%s", (packet_id,))
        row = cursor.fetchone()
    return _packet_row(row, replayed=replayed) if row else None


def list_packets(connection: psycopg.Connection, *, limit: int = DEFAULT_LIMIT,
                 period_start: str | None = None,
                 period_end: str | None = None) -> dict[str, Any]:
    bounded = int(limit)
    if not 1 <= bounded <= MAX_LIMIT:
        raise CloseReviewError(
            "close-review-limit-invalid", "limit must be between 1 and 100")
    filters = []
    parameters: list[Any] = []
    if (period_start is None) != (period_end is None):
        raise CloseReviewError(
            "close-review-period-invalid", "both period dates are required")
    if period_start is not None and period_end is not None:
        start = _date(period_start, field="period_start")
        end = _date(period_end, field="period_end")
        if end < start:
            raise CloseReviewError(
                "close-review-period-invalid", "period_end must not precede period_start")
        filters.append("p.period_start=%s AND p.period_end=%s")
        parameters.extend((start, end))
    where = "WHERE " + " AND ".join(filters) if filters else ""
    parameters.append(bounded + 1)
    with connection.cursor() as cursor:
        cursor.execute(
            PACKET_SELECT + where
            + " ORDER BY p.period_end DESC, p.period_start DESC, p.version DESC, "
              "p.packet_id LIMIT %s", tuple(parameters))
        rows = list(cursor)
    return {
        "items": [_packet_row(row) for row in rows[:bounded]],
        "has_more": len(rows) > bounded,
        "limit": bounded,
        "financial_effect": "none",
        "certifies_close": False,
        "can_execute_close": False,
    }


def _lock_command(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"close-review-command:{company_id}:{actor_id}:{key}",))


def _receipt(connection: psycopg.Connection, *, actor_id: str,
             key: str) -> tuple[Any, ...] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT action, request_digest, result_kind, result_ref "
            "FROM fincilia.close_review_command_receipt "
            "WHERE actor_id=%s AND idempotency_key=%s",
            (actor_id, key))
        return cursor.fetchone()


def _replay(connection: psycopg.Connection, *, action: str, digest: str,
            receipt: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt[0] != action or receipt[1] != digest:
        raise CloseReviewError(
            "close-review-idempotency-conflict",
            "the idempotency key was already used with another command")
    if receipt[2] == "packet":
        result = load_packet(connection, str(receipt[3]), replayed=True)
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT packet_id FROM fincilia.close_review_decision "
                "WHERE decision_id=%s", (receipt[3],))
            row = cursor.fetchone()
        result = load_packet(connection, str(row[0]), replayed=True) if row else None
    if result is None:
        raise RuntimeError("close review receipt points to no visible result")
    return result


def _write_receipt(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, action: str, key: str, digest: str,
                   result_kind: str, result_ref: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.close_review_command_receipt "
            "(company_id, actor_id, action, idempotency_key, request_digest, "
            " result_kind, result_ref) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (company_id, actor_id, action, key, digest, result_kind, result_ref))


def prepare_packet(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, idempotency_key: str, period_start: str,
                   period_end: str, assigned_reviewer_id: str) -> dict[str, Any]:
    start = _date(period_start, field="period_start")
    end = _date(period_end, field="period_end")
    reviewer_id = _uuid(assigned_reviewer_id, field="assigned_reviewer_id")
    if reviewer_id == actor_id:
        raise CloseReviewError(
            "close-review-segregation-of-duties",
            "the preparer cannot be assigned to review their own packet")
    key = _key(idempotency_key)
    payload = {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "assigned_reviewer_id": reviewer_id,
    }
    digest = _digest(payload)
    _lock_command(
        connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay(
        connection, action="prepare", digest=digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay
    if not _reviewer_is_eligible(connection, reviewer_id):
        raise CloseReviewError(
            "close-review-reviewer-ineligible",
            "the assigned person no longer has close review access")

    period = _exact_period(connection, period_start=start, period_end=end)
    manifest = build_manifest(period)
    manifest_digest = _digest(manifest)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"close-review-period:{company_id}:{start}:{end}",))
        cursor.execute(
            "SELECT COALESCE(max(version), 0) + 1 "
            "FROM fincilia.close_review_packet "
            "WHERE period_start=%s AND period_end=%s", (start, end))
        version = int(cursor.fetchone()[0])

    packet_id = str(uuid.uuid4())
    with connection.transaction():
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action="close.review.prepare", resource_kind="close_review_packet",
            resource_ref=packet_id, outcome="allowed", detail={
                "period_start": start.isoformat(), "period_end": end.isoformat(),
                "version": version, "diagnostic_status": period["status"],
                "manifest_digest": manifest_digest,
            })
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.close_review_packet "
                "(packet_id, company_id, period_start, period_end, version, "
                " manifest_schema_version, manifest, manifest_digest, "
                " diagnostic_status, prepared_by, assigned_reviewer_id, "
                " audit_event_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                " %s, %s, %s, %s)",
                (packet_id, company_id, start, end, version,
                 MANIFEST_SCHEMA_VERSION, Jsonb(manifest), manifest_digest,
                 period["status"], actor_id, reviewer_id, audit_event_id))
        _write_receipt(
            connection, company_id=company_id, actor_id=actor_id,
            action="prepare", key=key, digest=digest,
            result_kind="packet", result_ref=packet_id)
    result = load_packet(connection, packet_id)
    if result is None:
        raise RuntimeError("created close review packet cannot be read back")
    return result


def decide_packet(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, idempotency_key: str, packet_id: str,
                  decision: str, reason_code: str) -> dict[str, Any]:
    packet_id = _uuid(packet_id, field="packet_id")
    if decision not in DECISION_REASONS or reason_code not in DECISION_REASONS[decision]:
        raise CloseReviewError(
            "close-review-decision-invalid",
            "decision and reason_code are not an allowed combination")
    key = _key(idempotency_key)
    payload = {
        "packet_id": packet_id, "decision": decision, "reason_code": reason_code,
    }
    digest = _digest(payload)
    _lock_command(
        connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay(
        connection, action=decision, digest=digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"close-review-packet:{company_id}:{packet_id}",))
    packet = load_packet(connection, packet_id)
    if packet is None:
        raise CloseReviewError(
            "close-review-packet-unavailable", "the review packet is unavailable")
    if packet["decision"] is not None:
        raise CloseReviewError(
            "close-review-already-decided", "the review packet is already terminal")
    if packet["assigned_reviewer_id"] != actor_id or packet["prepared_by"] == actor_id:
        raise CloseReviewError(
            "close-review-segregation-of-duties",
            "only the assigned independent reviewer can decide this packet")
    if not _reviewer_is_eligible(connection, actor_id):
        raise CloseReviewError(
            "close-review-reviewer-ineligible",
            "the assigned person no longer has close review access")

    current_period = _exact_period(
        connection,
        period_start=_date(packet["period_start"], field="period_start"),
        period_end=_date(packet["period_end"], field="period_end"))
    current_manifest = build_manifest(current_period)
    current_digest = _digest(current_manifest)
    if current_digest != packet["manifest_digest"]:
        raise CloseReviewError(
            "close-review-evidence-stale",
            "the diagnostic evidence changed; prepare a new packet version")
    if decision == "evidence_reviewed" and current_period["status"] != "ready_for_review":
        raise CloseReviewError(
            "close-review-evidence-blocked",
            "blocked diagnostic evidence can only receive changes_requested")

    decision_id = str(uuid.uuid4())
    with connection.transaction():
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action=f"close.review.{decision}", resource_kind="close_review_packet",
            resource_ref=packet_id, outcome="allowed", detail={
                "decision": decision, "reason_code": reason_code,
                "manifest_digest": current_digest,
            })
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.close_review_decision "
                "(decision_id, company_id, packet_id, decision, reason_code, "
                " observed_manifest_digest, decided_by, audit_event_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (decision_id, company_id, packet_id, decision, reason_code,
                 current_digest, actor_id, audit_event_id))
        _write_receipt(
            connection, company_id=company_id, actor_id=actor_id,
            action=decision, key=key, digest=digest,
            result_kind="decision", result_ref=decision_id)
    result = load_packet(connection, packet_id)
    if result is None:
        raise RuntimeError("decided close review packet cannot be read back")
    return result
