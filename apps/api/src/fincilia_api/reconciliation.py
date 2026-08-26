"""Proyeccion read-only de candidatos de conciliacion.

Un candidato no es un match ni una decision. Esta consulta conserva esa
distancia deliberadamente: no persiste nada, no asigna puntajes y no consume
tolerancias monetarias. Los pares salen de reglas exactas y explicables sobre
dos datasets que ya pasaron los gates de completitud y linaje.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import repository


MAX_CANDIDATE_LIMIT = 200
MAX_CANDIDATE_OFFSET = 10_000
MAX_DATE_WINDOW_DAYS = 31
DEFAULT_CANDIDATE_LIMIT = 50
DEFAULT_DATE_WINDOW_DAYS = 3

ELIGIBLE_DATASET_STATES = frozenset(("validated", "published"))
ELIGIBLE_COMPLETENESS_STATES = frozenset(("verified", "accepted_exception"))

RULES = (
    "exact_amount",
    "same_currency",
    "opposite_direction",
    "different_financial_account",
    "date_within_explicit_window",
)

REVIEW_RULE_VERSION = "fnc-rec-exact-v1"
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
REVIEW_QUEUE_STATUSES = frozenset(("open", "confirmed", "rejected", "all"))
MAX_REVIEW_QUEUE_LIMIT = 100
MAX_REVIEW_QUEUE_OFFSET = 10_000
DECISION_REASONS = {
    "confirmed": frozenset((
        "documented_counterpart", "documented_transfer", "reference_supported")),
    "rejected": frozenset((
        "different_event", "timing_mismatch", "wrong_counterpart",
        "insufficient_evidence")),
}


class CandidateQueryError(Exception):
    """La solicitud no define una exploracion segura y acotada."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ReviewCommandError(Exception):
    """Una mutacion no satisface el ledger de revision."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReviewQueueQuery:
    status: str = "open"
    offset: int = 0
    limit: int = 50

    def validated(self) -> "ReviewQueueQuery":
        if self.status not in REVIEW_QUEUE_STATUSES:
            raise ReviewCommandError(
                "review-filter-invalid",
                "status must be open, confirmed, rejected or all")
        if not 0 <= self.offset <= MAX_REVIEW_QUEUE_OFFSET:
            raise ReviewCommandError(
                "review-filter-invalid", "offset must be between 0 and 10000")
        if not 1 <= self.limit <= MAX_REVIEW_QUEUE_LIMIT:
            raise ReviewCommandError(
                "review-filter-invalid", "limit must be between 1 and 100")
        return self


@dataclass(frozen=True)
class CandidateQuery:
    left_dataset_id: str
    right_dataset_id: str
    max_days: int = DEFAULT_DATE_WINDOW_DAYS
    offset: int = 0
    limit: int = DEFAULT_CANDIDATE_LIMIT

    def validated(self) -> "CandidateQuery":
        if self.left_dataset_id == self.right_dataset_id:
            raise CandidateQueryError(
                "datasets-must-differ", "two distinct datasets are required")
        if not 0 <= self.max_days <= MAX_DATE_WINDOW_DAYS:
            raise CandidateQueryError(
                "date-window-invalid", "max_days must be between 0 and 31")
        if not 0 <= self.offset <= MAX_CANDIDATE_OFFSET:
            raise CandidateQueryError(
                "candidate-offset-invalid", "offset must be between 0 and 10000")
        if not 1 <= self.limit <= MAX_CANDIDATE_LIMIT:
            raise CandidateQueryError(
                "candidate-limit-invalid", "limit must be between 1 and 200")
        return self


def _dataset_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "dataset_version_id": str(row[0]),
        "state": row[1],
        "completeness_state": row[2],
        "lineage_state": row[3],
        "movement_count": int(row[4]),
    }


def _movement(values: tuple[Any, ...], start: int) -> dict[str, Any]:
    return {
        "movement_id": str(values[start]),
        # El adaptador entrega Decimal. Punto fijo y string impiden que JSON lo
        # convierta en float justo donde una aproximacion no es aceptable.
        "amount": f"{values[start + 1]:.12f}",
        "currency": values[start + 2],
        "direction": values[start + 3],
        "description": values[start + 4],
        "reference": values[start + 5],
        "occurred_on": values[start + 6].isoformat(),
        "state": values[start + 7],
        "record_ordinal": int(values[start + 8]),
    }


def candidate_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convierte una fila SQL sin interpretar dinero ni calcular afinidad."""
    reference_match = bool(row[19])
    signals = list(RULES)
    if reference_match:
        signals.append("same_normalised_reference")
    return {
        "left": _movement(row, 0),
        "right": _movement(row, 9),
        "date_distance_days": int(row[18]),
        "signals": signals,
    }


def _load_eligible_pair(connection: psycopg.Connection,
                        query: CandidateQuery) -> tuple[dict[str, Any], dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_version_id, state, completeness_state, lineage_state, "
            "       movement_count "
            "FROM fincilia.dataset_version "
            "WHERE dataset_version_id = ANY(%s::uuid[])",
            ([query.left_dataset_id, query.right_dataset_id],))
        found = {_dataset_row(row)["dataset_version_id"]: _dataset_row(row)
                 for row in cursor}

    # La misma respuesta cubre inexistente, otra empresa y no elegible. Revelar
    # cual de las tres condiciones ocurrio seria un oraculo de existencia.
    if set(found) != {query.left_dataset_id, query.right_dataset_id}:
        raise CandidateQueryError(
            "candidate-scope-unavailable",
            "the requested datasets are unavailable for candidate exploration")

    left = found[query.left_dataset_id]
    right = found[query.right_dataset_id]
    for dataset in (left, right):
        if (dataset["state"] not in ELIGIBLE_DATASET_STATES
                or dataset["completeness_state"] not in ELIGIBLE_COMPLETENESS_STATES
                or dataset["lineage_state"] != "complete"):
            raise CandidateQueryError(
                "candidate-scope-unavailable",
                "the requested datasets are unavailable for candidate exploration")
    return left, right


def explore_candidates(connection: psycopg.Connection, *,
                       left_dataset_id: str, right_dataset_id: str,
                       max_days: int = DEFAULT_DATE_WINDOW_DAYS,
                       offset: int = 0,
                       limit: int = DEFAULT_CANDIDATE_LIMIT) -> dict[str, Any]:
    """Compara dos datasets autorizados en SQL y devuelve una pagina estable."""
    query = CandidateQuery(
        left_dataset_id=left_dataset_id,
        right_dataset_id=right_dataset_id,
        max_days=int(max_days), offset=int(offset), limit=int(limit)).validated()
    left_dataset, right_dataset = _load_eligible_pair(connection, query)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT l.movement_id, l.amount, l.currency_code, l.direction, "
            "       l.description, l.reference_original, l.occurred_on, l.state, "
            "       lr.record_ordinal, "
            "       r.movement_id, r.amount, r.currency_code, r.direction, "
            "       r.description, r.reference_original, r.occurred_on, r.state, "
            "       rr.record_ordinal, "
            "       abs(l.occurred_on - r.occurred_on) AS date_distance_days, "
            "       (l.reference_normalised IS NOT NULL AND "
            "        l.reference_normalised = r.reference_normalised) AS reference_match "
            "FROM fincilia.canonical_movement l "
            "JOIN fincilia.source_record ls ON ls.source_record_id = l.source_record_id "
            "JOIN fincilia.raw_record lr ON lr.raw_record_id = ls.raw_record_id "
            "JOIN fincilia.canonical_movement r "
            "  ON r.dataset_version_id = %s "
            " AND r.amount = l.amount "
            " AND r.currency_code = l.currency_code "
            " AND r.direction <> l.direction "
            " AND r.financial_account_id <> l.financial_account_id "
            " AND abs(l.occurred_on - r.occurred_on) <= %s "
            " AND r.state IN ('proposed', 'confirmed') "
            " AND r.lineage_state = 'complete' "
            "JOIN fincilia.source_record rs ON rs.source_record_id = r.source_record_id "
            "JOIN fincilia.raw_record rr ON rr.raw_record_id = rs.raw_record_id "
            "WHERE l.dataset_version_id = %s "
            "  AND l.state IN ('proposed', 'confirmed') "
            "  AND l.lineage_state = 'complete' "
            "ORDER BY reference_match DESC, date_distance_days, "
            "         lr.record_ordinal, rr.record_ordinal, l.movement_id, r.movement_id "
            "LIMIT %s OFFSET %s",
            (query.right_dataset_id, query.max_days, query.left_dataset_id,
             query.limit + 1, query.offset))
        rows = list(cursor)

    truncated = len(rows) > query.limit
    candidates = [candidate_from_row(row) for row in rows[:query.limit]]
    return {
        "mode": "candidate_only",
        "proves_balance_reconciliation": False,
        "rules": list(RULES),
        "reference_role": "explanatory_order_only",
        "max_days": query.max_days,
        "offset": query.offset,
        "limit": query.limit,
        "truncated": truncated,
        "left_dataset": left_dataset,
        "right_dataset": right_dataset,
        "candidates": candidates,
    }


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise ReviewCommandError(
            "review-request-invalid", f"{field} must be a UUID") from None


def _idempotency_key(value: str) -> str:
    candidate = (value or "").strip()
    if not IDEMPOTENCY_KEY.fullmatch(candidate):
        raise ReviewCommandError(
            "idempotency-key-invalid",
            "Idempotency-Key must contain 16 to 128 safe characters")
    return candidate


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lock_command(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, key: str) -> None:
    # La llave es solo para serializar contendientes; la unicidad durable sigue
    # en la tabla. `hashtextextended` evita construir un bigint en Python.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"match-command:{company_id}:{actor_id}:{key}",))


def _receipt(connection: psycopg.Connection, *, actor_id: str,
             key: str) -> tuple[str, str, str, str] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT action, request_digest, result_kind, result_ref "
            "FROM fincilia.match_command_receipt "
            "WHERE actor_id = %s AND idempotency_key = %s",
            (actor_id, key))
        row = cursor.fetchone()
    if row is None:
        return None
    return row[0], str(row[1]).strip(), row[2], str(row[3])


def _write_receipt(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, action: str, key: str, digest: str,
                   result_kind: str, result_ref: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.match_command_receipt "
            "(company_id, actor_id, action, idempotency_key, request_digest, "
            " result_kind, result_ref) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (company_id, actor_id, action, key, digest,
             result_kind, result_ref))


def _review_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    decision = None if row[10] is None else {
        "decision_id": str(row[10]),
        "decision": row[11],
        "reason_code": row[12],
        "decided_by": str(row[13]),
        "decided_by_name": row[14],
        "decided_at": row[15].isoformat(),
    }
    return {
        "candidate_id": str(row[0]),
        "left_movement_id": str(row[1]),
        "right_movement_id": str(row[2]),
        "rule_version": row[3],
        "signals": list(row[4]),
        "date_window_days": int(row[5]),
        "date_distance_days": int(row[6]),
        "proposed_by": str(row[7]),
        "proposed_by_name": row[8],
        "proposed_at": row[9].isoformat(),
        "left_dataset_id": str(row[16]),
        "right_dataset_id": str(row[17]),
        "confirmation_conflict": bool(row[18]),
        "status": decision["decision"] if decision else "open",
        "decision": decision,
        "financial_effect": "none",
        "proves_balance_reconciliation": False,
    }


REVIEW_SELECT = (
    "SELECT c.candidate_id, c.left_movement_id, c.right_movement_id, "
    "       c.rule_version, c.signals, c.date_window_days, "
    "       c.date_distance_days, c.proposed_by, proposer.display_name, "
    "       c.proposed_at, d.decision_id, d.decision, d.reason_code, "
    "       d.decided_by, decider.display_name, d.decided_at, "
    "       lm.dataset_version_id, rm.dataset_version_id, "
    "       EXISTS (SELECT 1 FROM fincilia.match_confirmation_member member "
    "               WHERE member.company_id = c.company_id "
    "                 AND member.candidate_id <> c.candidate_id "
    "                 AND member.movement_id IN "
    "                     (c.left_movement_id, c.right_movement_id)) "
    "         AS confirmation_conflict "
    "FROM fincilia.match_candidate c "
    "JOIN fincilia.subject proposer ON proposer.subject_id = c.proposed_by "
    "LEFT JOIN fincilia.match_decision d ON d.candidate_id = c.candidate_id "
    "LEFT JOIN fincilia.subject decider ON decider.subject_id = d.decided_by "
    "JOIN fincilia.canonical_movement lm ON lm.movement_id = c.left_movement_id "
    "JOIN fincilia.canonical_movement rm ON rm.movement_id = c.right_movement_id ")


def _load_review(connection: psycopg.Connection, *, candidate_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(REVIEW_SELECT + "WHERE c.candidate_id = %s",
                       (candidate_id,))
        row = cursor.fetchone()
    return None if row is None else _review_from_row(row)


def _load_receipt_result(connection: psycopg.Connection, *,
                         result_kind: str, result_ref: str) -> dict[str, Any]:
    candidate_id = result_ref
    if result_kind == "decision":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT candidate_id FROM fincilia.match_decision "
                "WHERE decision_id = %s", (result_ref,))
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("idempotency receipt points to a missing decision")
        candidate_id = str(row[0])
    review = _load_review(connection, candidate_id=candidate_id)
    if review is None:
        raise RuntimeError("idempotency receipt points to a missing candidate")
    return review


def _replay_or_conflict(connection: psycopg.Connection, *, action: str,
                        digest: str, receipt: tuple[str, str, str, str] | None
                        ) -> dict[str, Any] | None:
    if receipt is None:
        return None
    seen_action, seen_digest, result_kind, result_ref = receipt
    if seen_action != action or seen_digest != digest:
        raise ReviewCommandError(
            "idempotency-conflict",
            "the idempotency key was already used for another command")
    result = _load_receipt_result(
        connection, result_kind=result_kind, result_ref=result_ref)
    return {**result, "replayed": True, "created": False}


def _candidate_for_review(connection: psycopg.Connection, *,
                          left_dataset_id: str, right_dataset_id: str,
                          left_movement_id: str, right_movement_id: str,
                          max_days: int) -> dict[str, Any]:
    query = CandidateQuery(
        left_dataset_id=left_dataset_id,
        right_dataset_id=right_dataset_id,
        max_days=int(max_days)).validated()
    _load_eligible_pair(connection, query)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT l.movement_id, r.movement_id, "
            "       abs(l.occurred_on - r.occurred_on), "
            "       (l.reference_normalised IS NOT NULL AND "
            "        l.reference_normalised = r.reference_normalised), "
            "       l.engine_release_id, r.engine_release_id, "
            "       l.canonical_schema_version, r.canonical_schema_version "
            "FROM fincilia.canonical_movement l "
            "JOIN fincilia.canonical_movement r ON r.movement_id = %s "
            "WHERE l.movement_id = %s "
            "  AND l.dataset_version_id = %s AND r.dataset_version_id = %s "
            "  AND l.amount = r.amount AND l.currency_code = r.currency_code "
            "  AND l.direction <> r.direction "
            "  AND l.financial_account_id <> r.financial_account_id "
            "  AND abs(l.occurred_on - r.occurred_on) <= %s "
            "  AND l.state IN ('proposed', 'confirmed') "
            "  AND r.state IN ('proposed', 'confirmed') "
            "  AND l.lineage_state = 'complete' "
            "  AND r.lineage_state = 'complete'",
            (right_movement_id, left_movement_id, left_dataset_id,
             right_dataset_id, query.max_days))
        row = cursor.fetchone()
    if row is None:
        raise ReviewCommandError(
            "candidate-scope-unavailable",
            "the requested pair is unavailable for review")
    signals = list(RULES)
    if row[3]:
        signals.append("same_normalised_reference")
    movement_ids = sorted((str(row[0]), str(row[1])))
    release_ids = sorted({str(row[4]), str(row[5])})
    schema_versions = sorted({row[6], row[7]})
    return {
        "left_movement_id": movement_ids[0],
        "right_movement_id": movement_ids[1],
        "signals": signals,
        "date_window_days": query.max_days,
        "date_distance_days": int(row[2]),
        "engine_release_ids": release_ids,
        "canonical_schema_versions": schema_versions,
    }


def propose_review(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, idempotency_key: str,
                   left_dataset_id: str, right_dataset_id: str,
                   left_movement_id: str, right_movement_id: str,
                   max_days: int) -> dict[str, Any]:
    """Materializa un expediente solo si el par sigue siendo elegible."""
    key = _idempotency_key(idempotency_key)
    payload = {
        "left_dataset_id": _uuid(left_dataset_id, field="left_dataset_id"),
        "right_dataset_id": _uuid(right_dataset_id, field="right_dataset_id"),
        "left_movement_id": _uuid(left_movement_id, field="left_movement_id"),
        "right_movement_id": _uuid(right_movement_id, field="right_movement_id"),
        "max_days": int(max_days),
        "rule_version": REVIEW_RULE_VERSION,
    }
    digest = _digest(payload)
    _lock_command(connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay_or_conflict(
        connection, action="propose", digest=digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay

    candidate = _candidate_for_review(
        connection,
        left_dataset_id=payload["left_dataset_id"],
        right_dataset_id=payload["right_dataset_id"],
        left_movement_id=payload["left_movement_id"],
        right_movement_id=payload["right_movement_id"],
        max_days=payload["max_days"],
    )
    pair_lock = (
        f"match-pair:{company_id}:{REVIEW_RULE_VERSION}:"
        f"{candidate['left_movement_id']}:{candidate['right_movement_id']}")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (pair_lock,))
        cursor.execute(
            "SELECT candidate_id FROM fincilia.match_candidate "
            "WHERE rule_version = %s AND left_movement_id = %s "
            "AND right_movement_id = %s",
            (REVIEW_RULE_VERSION, candidate["left_movement_id"],
             candidate["right_movement_id"]))
        existing = cursor.fetchone()
    if existing is None:
        candidate_id = str(uuid.uuid4())
        audit_event_id = repository.record_audit(
            connection, subject_id=actor_id, company_id=company_id,
            action="match.propose", resource_kind="match_candidate",
            resource_ref=candidate_id, outcome="allowed",
            detail={"rule_version": REVIEW_RULE_VERSION})
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.match_candidate "
                "(candidate_id, company_id, left_movement_id, right_movement_id, "
                " rule_version, signals, date_window_days, date_distance_days, "
                " engine_release_ids, canonical_schema_versions, proposed_by, "
                " audit_event_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s)",
                (candidate_id, company_id, candidate["left_movement_id"],
                 candidate["right_movement_id"], REVIEW_RULE_VERSION,
                 candidate["signals"], candidate["date_window_days"],
                 candidate["date_distance_days"], candidate["engine_release_ids"],
                 candidate["canonical_schema_versions"], actor_id, audit_event_id))
        created = True
    else:
        candidate_id = str(existing[0])
        created = False
    _write_receipt(
        connection, company_id=company_id, actor_id=actor_id, action="propose",
        key=key, digest=digest, result_kind="candidate", result_ref=candidate_id)
    review = _load_review(connection, candidate_id=candidate_id)
    if review is None:
        raise RuntimeError("created candidate cannot be read back")
    return {**review, "replayed": False, "created": created}


def decide_review(connection: psycopg.Connection, *, company_id: str,
                  actor_id: str, idempotency_key: str, candidate_id: str,
                  decision: str, reason_code: str) -> dict[str, Any]:
    candidate_id = _uuid(candidate_id, field="candidate_id")
    if decision not in DECISION_REASONS or reason_code not in DECISION_REASONS[decision]:
        raise ReviewCommandError(
            "review-decision-invalid", "decision and reason_code are incompatible")
    key = _idempotency_key(idempotency_key)
    payload = {"candidate_id": candidate_id, "decision": decision,
               "reason_code": reason_code}
    digest = _digest(payload)
    action = "confirm" if decision == "confirmed" else "reject"
    _lock_command(connection, company_id=company_id, actor_id=actor_id, key=key)
    replay = _replay_or_conflict(
        connection, action=action, digest=digest,
        receipt=_receipt(connection, actor_id=actor_id, key=key))
    if replay is not None:
        return replay

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"match-candidate:{company_id}:{candidate_id}",))
    review = _load_review(connection, candidate_id=candidate_id)
    if review is None:
        raise ReviewCommandError(
            "candidate-scope-unavailable", "the candidate is unavailable")
    if review["decision"] is not None:
        raise ReviewCommandError(
            "candidate-already-decided", "the candidate already has a terminal decision")
    if decision == "confirmed" and review["proposed_by"] == actor_id:
        raise ReviewCommandError(
            "segregation-of-duties", "the proposer cannot confirm this candidate")
    if decision == "confirmed" and review["confirmation_conflict"]:
        raise ReviewCommandError(
            "movement-already-confirmed",
            "one of the candidate movements already belongs to another confirmation")

    evidence_refs = [
        {"kind": "movement", "ref": review["left_movement_id"]},
        {"kind": "movement", "ref": review["right_movement_id"]},
    ]
    try:
        # Esta transaccion anidada es un savepoint cuando la sesion ya esta en
        # una transaccion. Si la PK de miembros pierde una carrera, revierte
        # tambien la auditoria `allowed` y deja la sesion apta para que routes
        # confirme una auditoria `denied` separada.
        with connection.transaction():
            audit_event_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action=f"match.{action}", resource_kind="match_candidate",
                resource_ref=candidate_id, outcome="allowed",
                detail={"decision": decision, "reason_code": reason_code})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.match_decision "
                    "(company_id, candidate_id, decision, reason_code, evidence_refs, "
                    " decided_by, audit_event_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING decision_id",
                    (company_id, candidate_id, decision, reason_code,
                     Jsonb(evidence_refs), actor_id, audit_event_id))
                decision_id = str(cursor.fetchone()[0])
            _write_receipt(
                connection, company_id=company_id, actor_id=actor_id, action=action,
                key=key, digest=digest, result_kind="decision", result_ref=decision_id)
    except psycopg.errors.UniqueViolation as error:
        if error.diag.constraint_name == "pk_match_confirmation_member":
            raise ReviewCommandError(
                "movement-already-confirmed",
                "one of the candidate movements already belongs to another confirmation"
            ) from None
        raise
    result = _load_review(connection, candidate_id=candidate_id)
    if result is None:
        raise RuntimeError("decided candidate cannot be read back")
    return {**result, "replayed": False, "created": True}


def list_reviews(connection: psycopg.Connection, *, left_dataset_id: str,
                 right_dataset_id: str, limit: int = 200) -> list[dict[str, Any]]:
    left = _uuid(left_dataset_id, field="left_dataset_id")
    right = _uuid(right_dataset_id, field="right_dataset_id")
    bounded = max(1, min(int(limit), 200))
    with connection.cursor() as cursor:
        cursor.execute(
            REVIEW_SELECT
            + "WHERE ((lm.dataset_version_id = %s AND rm.dataset_version_id = %s) "
              "    OR (lm.dataset_version_id = %s AND rm.dataset_version_id = %s)) "
              "ORDER BY c.proposed_at DESC, c.candidate_id LIMIT %s",
            (left, right, right, left, bounded))
        return [_review_from_row(row) for row in cursor]


def list_review_queue(connection: psycopg.Connection, *, status: str = "open",
                      offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """Devuelve trabajo company-scoped sin agregar importes ni saldos."""
    query = ReviewQueueQuery(
        status=status, offset=int(offset), limit=int(limit)).validated()
    predicate = ""
    params: list[Any] = []
    if query.status == "open":
        predicate = "WHERE d.decision_id IS NULL "
    elif query.status in {"confirmed", "rejected"}:
        predicate = "WHERE d.decision = %s "
        params.append(query.status)
    params.extend((query.limit + 1, query.offset))
    with connection.cursor() as cursor:
        cursor.execute(
            REVIEW_SELECT + predicate
            + "ORDER BY (d.decision_id IS NOT NULL), c.proposed_at ASC, "
              "c.candidate_id LIMIT %s OFFSET %s",
            tuple(params))
        rows = list(cursor)
    return {
        "status": query.status,
        "offset": query.offset,
        "limit": query.limit,
        "truncated": len(rows) > query.limit,
        "items": [_review_from_row(row) for row in rows[:query.limit]],
        "financial_effect": "none",
        "proves_balance_reconciliation": False,
    }
