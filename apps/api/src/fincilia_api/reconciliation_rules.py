"""Reglas de conciliacion aprobadas por una persona (ADR-039 §4, FNC-SMB-003).

Una regla nace de una decision humana («¿aplicar siempre?»), describe
condiciones deterministas y nace `proposed`. Solo confirma algo cuando:

- esta `active`, lo que exige una aprobacion: en perfil `simple` el autor puede
  aprobarla (`self_reviewed`); en `estricto`, otra persona;
- el candidato cumple **todas** sus condiciones;
- las dos fuentes son `verified` o `accepted_exception`.

La decision queda `approved_rule` con `rule_id`, `rule_version` y
`decided_by` = quien aprobo la regla. PostgreSQL vuelve a comprobar cada punto
anterior en el disparador de `match_decision`: este modulo da mensajes utiles,
la base es la que aguanta. Pausar o retirar una regla nunca borra decisiones;
deshacer una aplicacion es una fila de reversion append-only.

Ningun LLM crea, aprueba ni aplica reglas, y el patron es una subcadena
normalizada: nunca se ejecuta una expresion regular escrita por una persona.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import match_signals, operating_profile, reconciliation, repository

MAX_APPLY_SCAN = 2_000
RULE_ACTIONS = {"pause": ("active", "paused", "paused_by_person"),
                "resume": ("paused", "active", "resumed_by_person"),
                "retire": (None, "retired", "retired_by_person")}
REVERSAL_REASONS = frozenset((
    "different_event", "timing_mismatch", "wrong_counterpart",
    "insufficient_evidence", "rule_too_broad"))


class RuleCommandError(Exception):
    def __init__(self, code: str, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _uuid(value: str, field: str) -> str:
    try:
        return reconciliation._uuid(value, field=field)
    except reconciliation.ReviewCommandError as error:
        raise RuleCommandError(error.code, error.detail) from None


def _key(value: str) -> str:
    try:
        return reconciliation._idempotency_key(value)
    except reconciliation.ReviewCommandError as error:
        raise RuleCommandError(error.code, error.detail) from None


# --------------------------------------------------------------------------- #
# Recibos de idempotencia
# --------------------------------------------------------------------------- #

def _replay(connection: psycopg.Connection, *, company_id: str, actor_id: str,
            key: str, action: str, digest: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"rule-command:{company_id}:{actor_id}:{key}",))
        cursor.execute(
            "SELECT action, request_digest, result "
            "FROM fincilia.reconciliation_rule_receipt "
            "WHERE actor_id = %s AND idempotency_key = %s", (actor_id, key))
        row = cursor.fetchone()
    if row is None:
        return None
    if row[0] != action or str(row[1]).strip() != digest:
        raise RuleCommandError(
            "idempotency-conflict",
            "the idempotency key was already used for another command", 409)
    return dict(row[2])


def _write_receipt(connection: psycopg.Connection, *, company_id: str,
                   actor_id: str, key: str, action: str, digest: str,
                   result: dict[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.reconciliation_rule_receipt "
            "(company_id, actor_id, action, idempotency_key, request_digest, result) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (company_id, actor_id, action, key, digest, Jsonb(result)))


# --------------------------------------------------------------------------- #
# Lectura
# --------------------------------------------------------------------------- #

RULE_SELECT = (
    "SELECT r.rule_id, r.version, r.conditions, r.created_by, author.display_name, "
    "       r.created_at, r.created_from_decision_id, "
    "       fincilia.reconciliation_rule_status(r.rule_id), "
    "       a.approved_by, approver.display_name, a.review_mode, a.approved_at, "
    "       (SELECT count(*) FROM fincilia.match_decision d "
    "         WHERE d.rule_id = r.rule_id), "
    "       (SELECT count(*) FROM fincilia.match_decision d "
    "          JOIN fincilia.match_decision_reversal rv "
    "            ON rv.decision_id = d.decision_id "
    "         WHERE d.rule_id = r.rule_id) "
    "FROM fincilia.reconciliation_rule r "
    "JOIN fincilia.subject author ON author.subject_id = r.created_by "
    "LEFT JOIN fincilia.reconciliation_rule_approval a ON a.rule_id = r.rule_id "
    "LEFT JOIN fincilia.subject approver ON approver.subject_id = a.approved_by ")


def describe(conditions: dict[str, Any]) -> list[str]:
    """La regla en frases llanas, construidas solo desde sus condiciones."""
    sentences = [f"La descripción contiene «{conditions['description_contains']}»"]
    if conditions.get("direction") == "inflow":
        sentences.append("Solo ingresos")
    elif conditions.get("direction") == "outflow":
        sentences.append("Solo egresos")
    if conditions.get("financial_account_id"):
        sentences.append("Solo en la cuenta indicada")
    tolerance = Decimal(conditions["max_amount_difference"])
    if tolerance == 0:
        sentences.append("Mismo valor exacto")
    else:
        sentences.append(
            f"Diferencia de hasta {match_signals.format_cop(tolerance)}")
    sentences.append(f"Moneda {conditions['currency']}")
    return sentences


def _rule_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    conditions = dict(row[2])
    return {
        "rule_id": str(row[0]),
        "version": int(row[1]),
        "conditions": conditions,
        "description": describe(conditions),
        "created_by": str(row[3]),
        "created_by_name": row[4],
        "created_at": row[5].isoformat(),
        "created_from_decision_id": None if row[6] is None else str(row[6]),
        "status": row[7],
        "approval": None if row[8] is None else {
            "approved_by": str(row[8]), "approved_by_name": row[9],
            "review_mode": row[10], "approved_at": row[11].isoformat()},
        "applied_count": int(row[12]),
        "reverted_count": int(row[13]),
        "financial_effect": "none",
    }


def get_rule(connection: psycopg.Connection, *, rule_id: str) -> dict[str, Any]:
    rule_id = _uuid(rule_id, "rule_id")
    with connection.cursor() as cursor:
        cursor.execute(RULE_SELECT + "WHERE r.rule_id = %s", (rule_id,))
        row = cursor.fetchone()
    if row is None:
        raise RuleCommandError("rule-unavailable", "the rule is unavailable", 404)
    return _rule_from_row(row)


def list_rules(connection: psycopg.Connection, *, status: str | None = None,
               limit: int = 100) -> list[dict[str, Any]]:
    if status not in (None, "proposed", "active", "paused", "retired"):
        raise RuleCommandError("rule-filter-invalid",
                               "status must be proposed, active, paused or retired")
    if not 1 <= int(limit) <= 200:
        raise RuleCommandError("rule-filter-invalid", "limit must be between 1 and 200")
    statement = RULE_SELECT
    params: list[Any] = []
    if status is not None:
        statement += "WHERE fincilia.reconciliation_rule_status(r.rule_id) = %s "
        params.append(status)
    statement += "ORDER BY r.created_at DESC, r.rule_id LIMIT %s"
    params.append(int(limit))
    with connection.cursor() as cursor:
        cursor.execute(statement, tuple(params))
        return [_rule_from_row(row) for row in cursor]


# --------------------------------------------------------------------------- #
# «¿Aplicar siempre?»: propuesta desde una decision humana
# --------------------------------------------------------------------------- #

def _decision_context(connection: psycopg.Connection, decision_id: str) -> tuple:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.decision_id, d.decision, d.review_mode, c.candidate_id, "
            "       c.amount_difference, "
            "       l.description, l.reference_original, l.financial_account_id, "
            "       l.direction, l.currency_code, "
            "       r.description, r.reference_original, r.financial_account_id, "
            "       r.direction, r.currency_code "
            "FROM fincilia.match_decision d "
            "JOIN fincilia.match_candidate c ON c.candidate_id = d.candidate_id "
            "JOIN fincilia.canonical_movement l ON l.movement_id = c.left_movement_id "
            "JOIN fincilia.canonical_movement r ON r.movement_id = c.right_movement_id "
            "WHERE d.decision_id = %s", (decision_id,))
        row = cursor.fetchone()
    if row is None or row[1] != "confirmed" or row[2] == "approved_rule":
        raise RuleCommandError(
            "rule-source-unavailable",
            "a rule is proposed only from a confirmed human decision", 409)
    return row


def propose_from_decision(connection: psycopg.Connection, *, company_id: str,
                          decision_id: str) -> dict[str, Any]:
    """Condiciones pre-rellenadas desde una decision confirmada. No escribe nada."""
    decision_id = _uuid(decision_id, "decision_id")
    row = _decision_context(connection, decision_id)
    sides = []
    for offset in (5, 10):
        description, reference = row[offset], row[offset + 1]
        pattern = match_signals.suggested_pattern(description, reference)
        has_id = bool(match_signals.counterparty_ids(description, reference))
        sides.append((has_id, len(pattern), -offset, pattern, row[offset + 2],
                      row[offset + 3], row[offset + 4]))
    # Determinista: el lado con NIT; si no, el patron mas largo; si no, el izquierdo.
    _, _, _, pattern, account, direction, currency = max(sides)
    difference = row[4]
    profile = operating_profile.current_profile(connection, company_id)
    if len(pattern) < 3:
        return {"source_decision_id": decision_id, "conditions": None,
                "reason": "pattern_not_derivable", "operating_profile": profile}
    conditions = match_signals.validated_conditions({
        "description_contains": pattern,
        "financial_account_id": str(account),
        "direction": direction,
        "max_amount_difference": "0" if difference is None
        else format(Decimal(difference).normalize(), "f"),
        "currency": currency,
    })
    return {
        "source_decision_id": decision_id,
        "conditions": conditions,
        "description": describe(conditions),
        "operating_profile": profile,
        "approval_required": ("el autor puede aprobarla (autorrevisada)"
                              if profile == operating_profile.SIMPLE
                              else "la aprueba una persona distinta del autor"),
    }


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #

def create_rule(connection: psycopg.Connection, *, company_id: str, actor_id: str,
                idempotency_key: str, conditions: dict[str, Any],
                created_from_decision_id: str | None) -> dict[str, Any]:
    key = _key(idempotency_key)
    try:
        clean = match_signals.validated_conditions(conditions)
    except match_signals.RuleConditionError as error:
        raise RuleCommandError("rule-conditions-invalid", str(error)) from None
    source = (None if created_from_decision_id is None
              else _uuid(created_from_decision_id, "created_from_decision_id"))
    digest = _digest({"conditions": clean, "source": source})
    replay = _replay(connection, company_id=company_id, actor_id=actor_id, key=key,
                     action="create", digest=digest)
    if replay is not None:
        return {**get_rule(connection, rule_id=replay["rule_id"]), "replayed": True}
    if source is not None:
        _decision_context(connection, source)
    rule_id = str(uuid.uuid4())
    try:
        with connection.transaction():
            audit_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action="match.rule.create", resource_kind="reconciliation_rule",
                resource_ref=rule_id, outcome="allowed",
                detail={"source_decision": source,
                        "conditions_digest": _digest(clean)})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_rule "
                    "(rule_id, company_id, version, conditions, conditions_digest, "
                    " created_by, created_from_decision_id, audit_event_id) "
                    "VALUES (%s, %s, 1, %s, %s, %s, %s, %s)",
                    (rule_id, company_id, Jsonb(clean), _digest(clean), actor_id,
                     source, audit_id))
    except (psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation):
        raise RuleCommandError(
            "rule-conditions-invalid",
            "the rule conditions or its source are not valid in this company") from None
    _write_receipt(connection, company_id=company_id, actor_id=actor_id, key=key,
                   action="create", digest=digest, result={"rule_id": rule_id})
    return {**get_rule(connection, rule_id=rule_id), "replayed": False}


def approve_rule(connection: psycopg.Connection, *, company_id: str, actor_id: str,
                 idempotency_key: str, rule_id: str) -> dict[str, Any]:
    key = _key(idempotency_key)
    rule_id = _uuid(rule_id, "rule_id")
    digest = _digest({"rule_id": rule_id})
    replay = _replay(connection, company_id=company_id, actor_id=actor_id, key=key,
                     action="approve", digest=digest)
    if replay is not None:
        return {**get_rule(connection, rule_id=rule_id), "replayed": True}
    rule = get_rule(connection, rule_id=rule_id)
    if rule["status"] != "proposed":
        raise RuleCommandError("rule-not-proposed",
                               "only a proposed rule can be approved", 409)
    if (rule["created_by"] == actor_id
            and not operating_profile.allows_self_review(connection, company_id)):
        raise RuleCommandError(
            "segregation-of-duties",
            "in the strict profile another person approves the rule", 409)
    try:
        # Auditoria y fila en el mismo savepoint: un rechazo de la base no deja
        # una auditoria `allowed` huerfana junto a la `denied` de la ruta.
        with connection.transaction():
            audit_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action="match.rule.approve", resource_kind="reconciliation_rule",
                resource_ref=rule_id, outcome="allowed",
                detail={"version": rule["version"]})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_rule_approval "
                    "(company_id, rule_id, approved_by, audit_event_id) "
                    "VALUES (%s, %s, %s, %s)", (company_id, rule_id, actor_id, audit_id))
    except psycopg.errors.InsufficientPrivilege:
        raise RuleCommandError(
            "segregation-of-duties",
            "in the strict profile another person approves the rule", 409) from None
    except (psycopg.errors.UniqueViolation, psycopg.errors.CheckViolation):
        raise RuleCommandError("rule-not-proposed",
                               "only a proposed rule can be approved", 409) from None
    _write_receipt(connection, company_id=company_id, actor_id=actor_id, key=key,
                   action="approve", digest=digest, result={"rule_id": rule_id})
    return {**get_rule(connection, rule_id=rule_id), "replayed": False}


def transition_rule(connection: psycopg.Connection, *, company_id: str,
                    actor_id: str, idempotency_key: str, rule_id: str,
                    action: str) -> dict[str, Any]:
    if action not in RULE_ACTIONS:
        raise RuleCommandError("rule-action-invalid",
                               "action must be pause, resume or retire")
    key = _key(idempotency_key)
    rule_id = _uuid(rule_id, "rule_id")
    digest = _digest({"rule_id": rule_id, "action": action})
    replay = _replay(connection, company_id=company_id, actor_id=actor_id, key=key,
                     action=action, digest=digest)
    if replay is not None:
        return {**get_rule(connection, rule_id=rule_id), "replayed": True}
    rule = get_rule(connection, rule_id=rule_id)
    expected, target, reason = RULE_ACTIONS[action]
    if (expected is not None and rule["status"] != expected) or rule["status"] == "retired":
        raise RuleCommandError("rule-transition-invalid",
                               f"a {rule['status']} rule cannot {action}", 409)
    try:
        with connection.transaction():
            audit_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action=f"match.rule.{action}", resource_kind="reconciliation_rule",
                resource_ref=rule_id, outcome="allowed",
                detail={"from": rule["status"], "to": target})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_rule_transition "
                    "(company_id, rule_id, sequence, from_status, to_status, "
                    " reason_code, actor_id, audit_event_id) "
                    "SELECT %s, %s, COALESCE(max(sequence), 0) + 1, %s, %s, %s, %s, %s "
                    "FROM fincilia.reconciliation_rule_transition WHERE rule_id = %s",
                    (company_id, rule_id, rule["status"], target, reason, actor_id,
                     audit_id, rule_id))
    except (psycopg.errors.CheckViolation, psycopg.errors.UniqueViolation,
            psycopg.errors.SerializationFailure):
        raise RuleCommandError("rule-transition-invalid",
                               f"the rule cannot {action} now", 409) from None
    _write_receipt(connection, company_id=company_id, actor_id=actor_id, key=key,
                   action=action, digest=digest, result={"rule_id": rule_id})
    return {**get_rule(connection, rule_id=rule_id), "replayed": False}


def _active_rules(connection: psycopg.Connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.rule_id, r.version, r.conditions, a.approved_by "
            "FROM fincilia.reconciliation_rule r "
            "JOIN fincilia.reconciliation_rule_approval a ON a.rule_id = r.rule_id "
            "WHERE fincilia.reconciliation_rule_status(r.rule_id) = 'active' "
            "ORDER BY r.created_at, r.rule_id")
        return [{"rule_id": str(row[0]), "version": int(row[1]),
                 "conditions": dict(row[2]), "approved_by": str(row[3])}
                for row in cursor]


def _actively_confirmed(connection: psycopg.Connection,
                        movement_ids: list[str]) -> set[str]:
    if not movement_ids:
        return set()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT m.movement_id FROM fincilia.match_confirmation_member m "
            "WHERE m.movement_id = ANY(%s::uuid[]) "
            "  AND NOT EXISTS (SELECT 1 FROM fincilia.match_decision_reversal rv "
            "                  WHERE rv.decision_id = m.decision_id)",
            (movement_ids,))
        return {str(row[0]) for row in cursor}


def apply_rules(connection: psycopg.Connection, *, company_id: str, actor_id: str,
                idempotency_key: str, left_dataset_id: str, right_dataset_id: str,
                max_days: int) -> dict[str, Any]:
    """Confirma los candidatos que cumplen una regla activa, sin elegir por nadie.

    Un movimiento que cumple la misma condicion con dos contrapartes no se
    confirma: la regla no decide entre dos facturas iguales. Tampoco se toca lo
    que ya tiene una confirmacion vigente.
    """
    key = _key(idempotency_key)
    left = _uuid(left_dataset_id, "left_dataset_id")
    right = _uuid(right_dataset_id, "right_dataset_id")
    if not 0 <= int(max_days) <= reconciliation.MAX_DATE_WINDOW_DAYS:
        raise RuleCommandError("date-window-invalid", "max_days must be between 0 and 31")
    digest = _digest({"left": left, "right": right, "max_days": int(max_days)})
    replay = _replay(connection, company_id=company_id, actor_id=actor_id, key=key,
                     action="apply", digest=digest)
    if replay is not None:
        return {**replay, "replayed": True}

    rules = _active_rules(connection)
    tolerance = max((Decimal(rule["conditions"]["max_amount_difference"])
                     for rule in rules), default=Decimal(0))
    tolerance = min(tolerance, reconciliation.MAX_TOLERANCE_AMOUNT)
    try:
        query = reconciliation.CandidateQuery(
            left_dataset_id=left, right_dataset_id=right, max_days=int(max_days),
            tolerance_amount=tolerance).validated()
        # Mismo gate que el explorador: partial, unknown, mismatch o un linaje
        # incompleto dejan el par fuera, y la base lo vuelve a exigir.
        reconciliation._load_eligible_pair(connection, query)
    except reconciliation.CandidateQueryError as error:
        raise RuleCommandError(error.code, error.detail, 403
                               if error.code == "candidate-scope-unavailable"
                               else 422) from None

    rows, truncated = reconciliation.candidate_rows(connection, query,
                                                    cap=MAX_APPLY_SCAN)
    matches: list[tuple[tuple, dict[str, Any]]] = []
    for row in rows:
        difference = reconciliation._difference(row[20])
        left_side = match_signals.RuleSide(row[4], str(row[21]), row[3], row[2])
        right_side = match_signals.RuleSide(row[13], str(row[22]), row[12], row[11])
        for rule in rules:
            if match_signals.rule_matches(rule["conditions"], left_side, right_side,
                                          difference):
                matches.append((row, rule))
                break
    usage = Counter()
    for row, _ in matches:
        usage[str(row[0])] += 1
        usage[str(row[9])] += 1
    confirmed = _actively_confirmed(
        connection, sorted({str(row[0]) for row, _ in matches}
                           | {str(row[9]) for row, _ in matches}))

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row, rule in matches:
        pair = {"left_movement_id": str(row[0]), "right_movement_id": str(row[9]),
                "rule_id": rule["rule_id"]}
        if usage[str(row[0])] > 1 or usage[str(row[9])] > 1:
            skipped.append({**pair, "reason": "ambiguous"})
            continue
        if str(row[0]) in confirmed or str(row[9]) in confirmed:
            skipped.append({**pair, "reason": "already_confirmed"})
            continue
        candidate = reconciliation.candidate_payload_from_row(
            row, max_days=query.max_days, query=query)
        try:
            with connection.transaction():
                candidate_id, _ = reconciliation.materialize_candidate(
                    connection, company_id=company_id, actor_id=actor_id,
                    candidate=candidate)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM fincilia.match_decision WHERE candidate_id = %s",
                        (candidate_id,))
                    if cursor.fetchone() is not None:
                        skipped.append({**pair, "reason": "already_decided"})
                        continue
                audit_id = repository.record_audit(
                    connection, subject_id=actor_id, company_id=company_id,
                    action="match.rule.apply", resource_kind="match_candidate",
                    resource_ref=candidate_id, outcome="allowed",
                    detail={"rule_id": rule["rule_id"],
                            "rule_version": rule["version"],
                            "approved_by": rule["approved_by"]})
                evidence = [{"kind": "movement", "ref": candidate["left_movement_id"]},
                            {"kind": "movement", "ref": candidate["right_movement_id"]}]
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO fincilia.match_decision "
                        "(company_id, candidate_id, decision, reason_code, "
                        " evidence_refs, decided_by, audit_event_id, review_mode, "
                        " rule_id, rule_version) "
                        "VALUES (%s, %s, 'confirmed', 'approved_rule_match', %s, %s, "
                        "        %s, 'approved_rule', %s, %s) RETURNING decision_id",
                        (company_id, candidate_id, Jsonb(evidence),
                         rule["approved_by"], audit_id, rule["rule_id"],
                         rule["version"]))
                    decision_id = str(cursor.fetchone()[0])
        except psycopg.errors.UniqueViolation:
            skipped.append({**pair, "reason": "already_confirmed"})
            continue
        except psycopg.errors.CheckViolation:
            skipped.append({**pair, "reason": "rule_not_eligible"})
            continue
        except psycopg.errors.ObjectNotInPrerequisiteState:
            skipped.append({**pair, "reason": "period_closed"})
            continue
        applied.append({**pair, "candidate_id": candidate_id,
                        "decision_id": decision_id,
                        "rule_version": rule["version"],
                        "decided_by": rule["approved_by"],
                        "review_mode": "approved_rule"})
    result = {
        "left_dataset_id": left, "right_dataset_id": right,
        "max_days": query.max_days, "active_rules": len(rules),
        "evaluated_candidates": len(rows), "scan_truncated": truncated,
        "applied": applied, "skipped": skipped,
        "financial_effect": "none", "proves_balance_reconciliation": False,
    }
    _write_receipt(connection, company_id=company_id, actor_id=actor_id, key=key,
                   action="apply", digest=digest, result=result)
    return {**result, "replayed": False}


def revert_decision(connection: psycopg.Connection, *, company_id: str,
                    actor_id: str, idempotency_key: str, decision_id: str,
                    reason_code: str) -> dict[str, Any]:
    """Deshace una aplicacion de regla con una fila nueva; nada se borra."""
    key = _key(idempotency_key)
    decision_id = _uuid(decision_id, "decision_id")
    if reason_code not in REVERSAL_REASONS:
        raise RuleCommandError("reversal-reason-invalid",
                               "reason_code is not a reversal reason")
    digest = _digest({"decision_id": decision_id, "reason_code": reason_code})
    replay = _replay(connection, company_id=company_id, actor_id=actor_id, key=key,
                     action="revert", digest=digest)
    if replay is not None:
        review = reconciliation.get_review(connection, candidate_id=replay["candidate_id"])
        return {**review, "replayed": True}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.candidate_id, d.decision, d.review_mode, rv.reversal_id "
            "FROM fincilia.match_decision d "
            "LEFT JOIN fincilia.match_decision_reversal rv "
            "       ON rv.decision_id = d.decision_id "
            "WHERE d.decision_id = %s", (decision_id,))
        row = cursor.fetchone()
    if row is None:
        raise RuleCommandError("decision-unavailable", "the decision is unavailable", 404)
    if row[1] != "confirmed" or row[2] != "approved_rule":
        raise RuleCommandError("reversal-not-allowed",
                               "only a rule application can be reverted", 409)
    if row[3] is not None:
        raise RuleCommandError("decision-already-reverted",
                               "the rule application was already reverted", 409)
    candidate_id = str(row[0])
    try:
        with connection.transaction():
            audit_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action="match.rule.revert", resource_kind="match_decision",
                resource_ref=decision_id, outcome="allowed",
                detail={"reason": reason_code})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.match_decision_reversal "
                    "(company_id, decision_id, candidate_id, reason_code, "
                    " reversed_by, audit_event_id) VALUES (%s, %s, %s, %s, %s, %s)",
                    (company_id, decision_id, candidate_id, reason_code, actor_id,
                     audit_id))
    except psycopg.errors.UniqueViolation:
        raise RuleCommandError("decision-already-reverted",
                               "the rule application was already reverted", 409) from None
    except psycopg.errors.ObjectNotInPrerequisiteState:
        raise RuleCommandError("period-closed",
                               "the accounting period of this match is closed", 409) from None
    _write_receipt(connection, company_id=company_id, actor_id=actor_id, key=key,
                   action="revert", digest=digest, result={"candidate_id": candidate_id})
    review = reconciliation.get_review(connection, candidate_id=candidate_id)
    return {**review, "replayed": False}
