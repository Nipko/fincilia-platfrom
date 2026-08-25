"""Estados diagnosticos y reproducibles de conciliacion de saldos.

El cliente elige evidencia ya visible; el servidor deriva empresa, cuenta,
moneda, periodo, version del motor, controles y ecuacion. Esta superficie no
ejecuta un cierre ni convierte una diferencia cero en certificacion.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg

from . import financial_lineage
from fincilia_contracts.money import MoneyError, format_money, parse_money
from fincilia_contracts.release import digest_of


DEFAULT_LIMIT = 50
MAX_LIMIT = 100
RULE_VERSION = "fnc-balance-equation-v1"
CONTROL_RULE_VERSION = "fnc-completeness-v1"
ADJUSTMENT_SIDES = frozenset({"add_to_bank", "deduct_from_bank"})
REASON_CODES = frozenset({
    "bank_fee_pending", "deposit_in_transit", "documented_timing",
    "outstanding_payment", "other_documented",
})
DECISIONS = frozenset({"confirmed", "rejected", "reversed"})
SUPPORTED_CONTROLS = frozenset({
    "provenance_integrity", "record_count", "account_identity",
    "currency_consistency", "period_coverage",
})


@dataclass(frozen=True)
class ReconciliationError(Exception):
    code: str
    detail: str


def _uuid(value: str, *, code: str = "reconciliation-input-invalid") -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ReconciliationError(code, "an input identifier is invalid") from None


def _bounded(value: int) -> int:
    if isinstance(value, bool):
        raise ReconciliationError("reconciliation-limit-invalid",
                                  "limit must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ReconciliationError("reconciliation-limit-invalid",
                                  "limit must be an integer") from None
    if parsed < 1 or parsed > MAX_LIMIT:
        raise ReconciliationError(
            "reconciliation-limit-invalid",
            f"limit must be between 1 and {MAX_LIMIT}")
    return parsed


def _assessment_row(row: tuple[Any, ...], *, replayed: bool = False) -> dict[str, Any]:
    return {
        "assessment_id": str(row[0]), "data_source_id": str(row[1]),
        "source_name": row[2], "source_expectation_id": str(row[3]),
        "financial_account_id": str(row[4]) if row[4] else None,
        "account_name": row[5], "dataset_version_id": str(row[6]),
        "period_start": row[7].isoformat(), "period_end": row[8].isoformat(),
        "state": row[9], "lineage_state": row[10],
        "created_at": row[11].isoformat(), "replayed": replayed,
    }


ASSESSMENT_SELECT = (
    "SELECT a.assessment_id, a.data_source_id, s.display_name, "
    "a.source_expectation_id, a.financial_account_id, f.display_name, "
    "a.dataset_version_id, a.period_start, a.period_end, a.state, "
    "a.lineage_state, a.created_at "
    "FROM fincilia.completeness_assessment a "
    "JOIN fincilia.data_source s ON s.data_source_id = a.data_source_id "
    " AND s.company_id = a.company_id "
    "LEFT JOIN fincilia.financial_account f "
    " ON f.account_id = a.financial_account_id AND f.company_id = a.company_id "
)


def _control_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "control_result_id": str(row[0]), "assessment_id": str(row[1]),
        "control_type": row[2], "required": bool(row[3]), "outcome": row[4],
        "expected_value": row[5], "observed_value": row[6],
        "value_type": row[7], "reason": row[8], "lineage_state": row[9],
    }


def _item_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "item_decision_id": str(row[0]), "item_root_id": str(row[1]),
        "statement_root_id": str(row[2]), "adjustment_side": row[3],
        "amount": format_money(row[4]), "currency_code": row[5],
        "reason_code": row[6], "state": row[7],
        "prepared_by": str(row[8]),
        "approved_by": str(row[9]) if row[9] else None,
        "decision_version": int(row[10]), "lineage_state": row[11],
        "created_at": row[12].isoformat(),
    }


ITEM_SELECT = (
    "SELECT item_decision_id, item_root_id, statement_root_id, adjustment_side, "
    "amount, currency_code, reason_code, state, prepared_by, approved_by, "
    "decision_version, lineage_state, created_at FROM fincilia.reconciling_item "
)


def _statement_row(row: tuple[Any, ...], *, replayed: bool = False) -> dict[str, Any]:
    return {
        "statement_id": str(row[0]), "statement_root_id": str(row[1]),
        "version": int(row[2]), "financial_account_id": str(row[3]),
        "account_name": row[4], "period_start": row[5].isoformat(),
        "period_end": row[6].isoformat(), "currency_code": row[7],
        "bank_closing_balance_id": str(row[8]),
        "books_closing_balance_id": str(row[9]),
        "completeness_assessment_ids": [str(value) for value in row[10]],
        "confirmed_reconciling_item_ids": [str(value) for value in row[11]],
        "bank_closing_balance": format_money(row[12]),
        "books_closing_balance": format_money(row[13]),
        "confirmed_additions_to_bank": format_money(row[14]),
        "confirmed_deductions_from_bank": format_money(row[15]),
        "adjusted_bank_balance": format_money(row[16]),
        "unexplained_difference": format_money(row[17]),
        "state": row[18], "lineage_state": row[19],
        "created_at": row[20].isoformat(), "replayed": replayed,
        "certifies_close": False,
    }


STATEMENT_SELECT = (
    "SELECT r.statement_id, r.statement_root_id, r.version, "
    "r.financial_account_id, a.display_name, r.period_start, r.period_end, "
    "r.currency_code, r.bank_closing_balance_id, r.books_closing_balance_id, "
    "r.completeness_assessment_ids, r.confirmed_reconciling_item_ids, "
    "bank.amount, books.amount, r.confirmed_additions_to_bank, "
    "r.confirmed_deductions_from_bank, r.adjusted_bank_balance, "
    "r.unexplained_difference, r.state, r.lineage_state, r.created_at "
    "FROM fincilia.reconciliation_statement r "
    "JOIN fincilia.financial_account a ON a.account_id = r.financial_account_id "
    " AND a.company_id = r.company_id "
    "JOIN fincilia.account_balance bank ON bank.balance_id = r.bank_closing_balance_id "
    " AND bank.company_id = r.company_id "
    "JOIN fincilia.account_balance books ON books.balance_id = r.books_closing_balance_id "
    " AND books.company_id = r.company_id "
)


def list_workspace(connection: psycopg.Connection, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    bounded = _bounded(limit)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT e.expectation_id, e.data_source_id, s.display_name, "
            "e.financial_account_id, a.display_name, e.period_start, e.period_end, "
            "e.state, e.satisfied_by, EXISTS (SELECT 1 FROM "
            "fincilia.completeness_assessment ca WHERE ca.company_id=e.company_id "
            "AND ca.source_expectation_id=e.expectation_id) "
            "FROM fincilia.source_expectation e "
            "JOIN fincilia.data_source s ON s.data_source_id=e.data_source_id "
            " AND s.company_id=e.company_id "
            "LEFT JOIN fincilia.financial_account a "
            " ON a.account_id=e.financial_account_id AND a.company_id=e.company_id "
            "ORDER BY e.period_end DESC, s.display_name LIMIT %s", (bounded + 1,))
        expectation_rows = cursor.fetchall()
        expectations = [{
            "expectation_id": str(row[0]), "data_source_id": str(row[1]),
            "source_name": row[2],
            "financial_account_id": str(row[3]) if row[3] else None,
            "account_name": row[4], "period_start": row[5].isoformat(),
            "period_end": row[6].isoformat(), "state": row[7],
            "has_artifact": row[8] is not None, "assessed": bool(row[9]),
        } for row in expectation_rows[:bounded]]

        cursor.execute(ASSESSMENT_SELECT +
                       "ORDER BY a.period_end DESC, a.created_at DESC LIMIT %s",
                       (bounded + 1,))
        assessment_rows = cursor.fetchall()
        assessments = [_assessment_row(row) for row in assessment_rows[:bounded]]
        assessment_ids = [item["assessment_id"] for item in assessments]
        controls: list[dict[str, Any]] = []
        if assessment_ids:
            cursor.execute(
                "SELECT control_result_id, assessment_id, control_type, required, "
                "outcome, expected_value, observed_value, value_type, reason, "
                "lineage_state FROM fincilia.completeness_control_result "
                "WHERE assessment_id = ANY(%s) ORDER BY assessment_id, control_type",
                (assessment_ids,))
            controls = [_control_row(row) for row in cursor.fetchall()]

        cursor.execute(STATEMENT_SELECT +
                       "ORDER BY r.period_end DESC, r.created_at DESC LIMIT %s",
                       (bounded + 1,))
        statement_rows = cursor.fetchall()
        statements = [_statement_row(row) for row in statement_rows[:bounded]]
        cursor.execute(
            ITEM_SELECT + "WHERE (company_id, item_root_id, decision_version) IN ("
            " SELECT company_id, item_root_id, max(decision_version) "
            " FROM fincilia.reconciling_item GROUP BY company_id, item_root_id) "
            "ORDER BY created_at DESC LIMIT %s", (bounded + 1,))
        item_rows = cursor.fetchall()
        items = [_item_row(row) for row in item_rows[:bounded]]
        cursor.execute(
            "SELECT (SELECT count(*) FROM fincilia.source_expectation), "
            "(SELECT count(*) FROM fincilia.completeness_assessment), "
            "(SELECT count(*) FROM fincilia.reconciliation_statement), "
            "(SELECT count(DISTINCT item_root_id) FROM fincilia.reconciling_item)")
        total_row = cursor.fetchone()
    by_assessment: dict[str, list[dict[str, Any]]] = {}
    for control in controls:
        by_assessment.setdefault(control["assessment_id"], []).append(control)
    for assessment in assessments:
        assessment["controls"] = by_assessment.get(assessment["assessment_id"], [])
    return {
        "limit": bounded, "expectations": expectations,
        "assessments": assessments, "statements": statements, "items": items,
        "totals": {
            "expectations": int(total_row[0]), "assessments": int(total_row[1]),
            "statements": int(total_row[2]), "items": int(total_row[3]),
        },
        "truncated": any(len(rows) > bounded for rows in (
            expectation_rows, assessment_rows, statement_rows, item_rows)),
        "notice": "diagnostic_only; no result certifies or executes a close",
    }


def _load_expectation_dataset(connection: psycopg.Connection,
                              expectation_id: str) -> dict[str, Any]:
    identifier = _uuid(expectation_id, code="assessment-evidence-unavailable")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT e.expectation_id, e.company_id, e.data_source_id, "
            "e.financial_account_id, e.period_start, e.period_end, "
            "e.expected_controls, d.dataset_version_id, d.record_count, "
            "d.engine_release_id, d.canonical_schema_version, d.lineage_state, "
            "a.currency_code, "
            "coalesce((SELECT count(DISTINCT m.financial_account_id) FROM "
            "fincilia.canonical_movement m WHERE m.dataset_version_id=d.dataset_version_id),0), "
            "coalesce((SELECT count(DISTINCT m.currency_code) FROM "
            "fincilia.canonical_movement m WHERE m.dataset_version_id=d.dataset_version_id),0), "
            "coalesce((SELECT bool_and(m.financial_account_id=e.financial_account_id) "
            "FROM fincilia.canonical_movement m WHERE "
            "m.dataset_version_id=d.dataset_version_id),false), "
            "coalesce((SELECT bool_and(m.currency_code=a.currency_code) "
            "FROM fincilia.canonical_movement m WHERE "
            "m.dataset_version_id=d.dataset_version_id),false) "
            "FROM fincilia.source_expectation e "
            "JOIN fincilia.dataset_version d ON d.artifact_id=e.satisfied_by "
            " AND d.company_id=e.company_id "
            "JOIN fincilia.financial_account a ON a.account_id=e.financial_account_id "
            " AND a.company_id=e.company_id "
            "WHERE e.expectation_id=%s AND e.state='satisfied' "
            " AND d.state='published' AND d.completeness_state='verified' "
            " AND d.lineage_state='complete' "
            "ORDER BY d.published_at DESC LIMIT 1", (identifier,))
        row = cursor.fetchone()
    if row is None:
        raise ReconciliationError("assessment-evidence-unavailable",
                                  "the expectation has no eligible published dataset")
    return {
        "expectation_id": str(row[0]), "company_id": str(row[1]),
        "data_source_id": str(row[2]),
        "financial_account_id": str(row[3]) if row[3] else None,
        "period_start": row[4], "period_end": row[5],
        "expected_controls": row[6] or {}, "dataset_version_id": str(row[7]),
        "record_count": int(row[8]), "engine_release_id": str(row[9]),
        "canonical_schema_version": row[10], "dataset_lineage_state": row[11],
        "currency_code": row[12], "distinct_accounts": int(row[13]),
        "distinct_currencies": int(row[14]), "account_matches": bool(row[15]),
        "currency_matches": bool(row[16]),
    }


def _control_specs(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    declared = (evidence["expected_controls"]
                if isinstance(evidence["expected_controls"], dict) else {})
    names = declared.get("controls")
    if not isinstance(names, list) or not names:
        names = ["provenance_integrity", "record_count"]
    requested = list(dict.fromkeys(str(name) for name in names))[:32]
    ordered = [name for name in requested if name in SUPPORTED_CONTROLS]
    if any(name not in SUPPORTED_CONTROLS for name in requested):
        # El esquema fisico tiene un vocabulario cerrado. Un control requerido
        # desconocido se representa una sola vez como cobertura desconocida;
        # nunca se omite ni provoca dos filas con el mismo tipo canonico.
        if "period_coverage" not in ordered:
            ordered.append("period_coverage")
    specs = []
    for name in ordered:
        if name == "period_coverage" and name not in requested:
            specs.append({"type": name, "outcome": "unknown", "expected": None,
                          "observed": None, "value_type": "unknown",
                          "reason": "a required declared control is not supported"})
            continue
        if name == "provenance_integrity":
            specs.append({"type": name, "outcome": "match", "expected": {"value": True},
                          "observed": {"value": True}, "value_type": "boolean",
                          "reason": None})
        elif name == "account_identity":
            match = evidence["distinct_accounts"] == 1 and evidence["account_matches"]
            specs.append({"type": name, "outcome": "match" if match else "mismatch",
                          "expected": {"value": "expected_account"},
                          "observed": {"consistent": match}, "value_type": "identifier",
                          "reason": None})
        elif name == "currency_consistency":
            match = evidence["distinct_currencies"] == 1 and evidence["currency_matches"]
            specs.append({"type": name, "outcome": "match" if match else "mismatch",
                          "expected": {"value": evidence["currency_code"]},
                          "observed": {"consistent": match}, "value_type": "currency_code",
                          "reason": None})
        elif (name == "record_count"
              and isinstance(declared.get("record_count"), int)
              and not isinstance(declared.get("record_count"), bool)):
            expected = int(declared["record_count"])
            observed = evidence["record_count"]
            specs.append({"type": name, "outcome": "match" if expected == observed else "mismatch",
                          "expected": {"value": expected}, "observed": {"value": observed},
                          "value_type": "integer", "reason": None})
        else:
            specs.append({"type": name, "outcome": "unknown", "expected": None,
                          "observed": None, "value_type": "unknown",
                          "reason": "the expectation does not contain a versioned expected value"})
    return specs


def create_assessment(connection: psycopg.Connection, *, company_id: str,
                      subject_id: str, expectation_id: str) -> dict[str, Any]:
    evidence = _load_expectation_dataset(connection, expectation_id)
    if evidence["company_id"] != company_id:
        raise ReconciliationError("assessment-evidence-unavailable",
                                  "the expectation has no eligible published dataset")
    specs = _control_specs(evidence)
    state = ("mismatch" if any(item["outcome"] == "mismatch" for item in specs)
             else "unknown" if any(item["outcome"] in {"unknown", "not_applicable"}
                                   for item in specs) else "verified")
    lineage = "complete" if state == "verified" else "required_pending"
    assessment_key = digest_of({
        "company_id": company_id, "expectation_id": evidence["expectation_id"],
        "dataset_version_id": evidence["dataset_version_id"], "controls": specs,
        "engine_release_id": evidence["engine_release_id"],
        "canonical_schema_version": evidence["canonical_schema_version"],
    })
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                       (assessment_key,))
        cursor.execute(
            "SELECT assessment_id FROM fincilia.completeness_assessment "
            "WHERE company_id=%s AND assessment_key=%s", (company_id, assessment_key))
        existing = cursor.fetchone()
        if existing is None:
            assessment_id = str(uuid.uuid4())
            assessment_node = None
            try:
                if lineage == "complete":
                    assessment_node = financial_lineage.materialize_assessment(
                        cursor, company_id=company_id, subject_id=subject_id,
                        assessment_id=assessment_id,
                        dataset_version_id=evidence["dataset_version_id"],
                        assessment_key=assessment_key, state=state,
                        rule_version=CONTROL_RULE_VERSION)
                cursor.execute(
                    "INSERT INTO fincilia.completeness_assessment (assessment_id, "
                    "company_id, data_source_id, source_expectation_id, "
                    "financial_account_id, dataset_version_id, period_start, "
                    "period_end, state, assessment_key, prepared_by, engine_release_id, "
                    "canonical_schema_version, lineage_state) VALUES (%s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (assessment_id, company_id, evidence["data_source_id"],
                     evidence["expectation_id"], evidence["financial_account_id"],
                     evidence["dataset_version_id"], evidence["period_start"],
                     evidence["period_end"], state, assessment_key, subject_id,
                     evidence["engine_release_id"],
                     evidence["canonical_schema_version"], lineage))
            except financial_lineage.LineageError as error:
                raise ReconciliationError(error.code, error.detail) from None
            evidence_refs = json.dumps([
                {"kind": "dataset_version", "ref": evidence["dataset_version_id"]},
                {"kind": "source_expectation", "ref": evidence["expectation_id"]},
            ])
            for spec in specs:
                control_id = str(uuid.uuid4())
                try:
                    if lineage == "complete":
                        assert assessment_node is not None
                        financial_lineage.materialize_control(
                            cursor, company_id=company_id, subject_id=subject_id,
                            control_result_id=control_id,
                            assessment_id=assessment_id,
                            dataset_version_id=evidence["dataset_version_id"],
                            control_type=spec["type"], outcome=spec["outcome"],
                            expected=spec["expected"], observed=spec["observed"],
                            rule_version=CONTROL_RULE_VERSION,
                            assessment_node_id=assessment_node)
                except financial_lineage.LineageError as error:
                    raise ReconciliationError(error.code, error.detail) from None
                cursor.execute(
                    "INSERT INTO fincilia.completeness_control_result "
                    "(control_result_id, company_id, assessment_id, control_type, "
                    "required, outcome, "
                    "expected_value, observed_value, value_type, evidence_refs, "
                    "rule_version, reason, engine_release_id, canonical_schema_version, "
                    "lineage_state) VALUES (%s, %s, %s, %s, true, %s, %s::jsonb, "
                    "%s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s)",
                    (control_id, company_id, assessment_id, spec["type"], spec["outcome"],
                     json.dumps(spec["expected"]), json.dumps(spec["observed"]),
                     spec["value_type"], evidence_refs, CONTROL_RULE_VERSION,
                     spec["reason"], evidence["engine_release_id"],
                     evidence["canonical_schema_version"], lineage))
            replayed = False
        else:
            assessment_id = str(existing[0])
            replayed = True
            if lineage == "complete":
                cursor.execute(
                    "SELECT fincilia.financial_lineage_complete("
                    "'completeness_assessment', %s, %s)",
                    (company_id, assessment_id))
                if not cursor.fetchone()[0]:
                    # Replay exacto de una fila sintetica anterior a V0031. Se
                    # agregan nodos y aristas; la evaluacion y sus controles no
                    # se reescriben ni se reinterpretan.
                    try:
                        with connection.transaction():
                            assessment_node = financial_lineage.materialize_assessment(
                                cursor, company_id=company_id, subject_id=subject_id,
                                assessment_id=assessment_id,
                                dataset_version_id=evidence["dataset_version_id"],
                                assessment_key=assessment_key, state=state,
                                rule_version=CONTROL_RULE_VERSION)
                            cursor.execute(
                                "SELECT control_result_id, control_type, outcome, "
                                "expected_value, observed_value, rule_version "
                                "FROM fincilia.completeness_control_result "
                                "WHERE company_id=%s AND assessment_id=%s "
                                "AND lineage_state='complete' ORDER BY control_type",
                                (company_id, assessment_id))
                            stored_controls = cursor.fetchall()
                            if len(stored_controls) != len(specs):
                                raise ReconciliationError(
                                    "financial-lineage-input-incomplete",
                                    "the replayed assessment controls are incomplete")
                            for control in stored_controls:
                                financial_lineage.materialize_control(
                                    cursor, company_id=company_id,
                                    subject_id=subject_id,
                                    control_result_id=str(control[0]),
                                    assessment_id=assessment_id,
                                    dataset_version_id=evidence["dataset_version_id"],
                                    control_type=control[1], outcome=control[2],
                                    expected=control[3], observed=control[4],
                                    rule_version=control[5],
                                    assessment_node_id=assessment_node)
                            cursor.execute(
                                "SELECT fincilia.financial_lineage_complete("
                                "'completeness_assessment', %s, %s)",
                                (company_id, assessment_id))
                            if not cursor.fetchone()[0]:
                                raise ReconciliationError(
                                    "financial-lineage-input-incomplete",
                                    "the replayed assessment could not prove its evidence")
                    except financial_lineage.LineageError as error:
                        raise ReconciliationError(error.code, error.detail) from None
        cursor.execute(ASSESSMENT_SELECT + "WHERE a.assessment_id=%s", (assessment_id,))
        row = cursor.fetchone()
        cursor.execute(
            "SELECT control_result_id, assessment_id, control_type, required, outcome, "
            "expected_value, observed_value, value_type, reason, lineage_state "
            "FROM fincilia.completeness_control_result WHERE assessment_id=%s "
            "ORDER BY control_type", (assessment_id,))
        controls = [_control_row(item) for item in cursor.fetchall()]
    result = _assessment_row(row, replayed=replayed)
    result["controls"] = controls
    return result


def _load_statement_scope(connection: psycopg.Connection, *, bank_id: str,
                          books_id: str, assessment_ids: list[str]) -> dict[str, Any]:
    bank = _uuid(bank_id)
    books = _uuid(books_id)
    assessments = [_uuid(value) for value in assessment_ids]
    if not assessments or len(set(assessments)) != len(assessments) or len(assessments) > 1000:
        raise ReconciliationError("statement-input-invalid",
                                  "assessment identifiers must be unique and non-empty")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT b.balance_id, b.financial_account_id, b.currency_code, "
            "(b.as_of AT TIME ZONE b.source_timezone)::date, b.balance_type, "
            "b.engine_release_id, b.canonical_schema_version "
            "FROM fincilia.account_balance b WHERE b.balance_id=ANY(%s)",
            ([bank, books],))
        balance_rows = {str(row[0]): row for row in cursor.fetchall()}
        cursor.execute(
            "SELECT assessment_id, financial_account_id, period_start, period_end "
            "FROM fincilia.completeness_assessment WHERE assessment_id=ANY(%s)",
            (assessments,))
        assessment_rows = cursor.fetchall()
    if bank not in balance_rows or books not in balance_rows or len(assessment_rows) != len(assessments):
        raise ReconciliationError("statement-evidence-unavailable",
                                  "one or more statement inputs are unavailable")
    bank_row, books_row = balance_rows[bank], balance_rows[books]
    first = assessment_rows[0]
    period_start, period_end = first[2], first[3]
    account = str(bank_row[1])
    currency = bank_row[2]
    valid = (
        bank_row[4] == "closing" and books_row[4] == "ledger"
        and str(books_row[1]) == account and books_row[2] == currency
        and bank_row[5] == books_row[5] and bank_row[6] == books_row[6]
        and period_start <= bank_row[3] <= period_end
        and period_start <= books_row[3] <= period_end
        and all((row[1] is None or str(row[1]) == account)
                and row[2] == period_start and row[3] == period_end
                for row in assessment_rows)
    )
    if not valid:
        raise ReconciliationError("statement-scope-conflict",
                                  "balances and assessments do not share account, period or version")
    return {
        "bank_id": bank, "books_id": books, "assessment_ids": sorted(assessments),
        "financial_account_id": account, "currency_code": currency,
        "period_start": period_start, "period_end": period_end,
        "engine_release_id": str(bank_row[5]), "canonical_schema_version": bank_row[6],
    }


def create_statement(connection: psycopg.Connection, *, company_id: str,
                     subject_id: str, bank_balance_id: str, books_balance_id: str,
                     assessment_ids: list[str]) -> dict[str, Any]:
    scope = _load_statement_scope(
        connection, bank_id=bank_balance_id, books_id=books_balance_id,
        assessment_ids=assessment_ids)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.reconciliation_statement_root "
            "(company_id, financial_account_id, period_start, period_end, "
            "currency_code, prepared_by) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (company_id, financial_account_id, period_start, period_end, "
            "currency_code) DO NOTHING RETURNING statement_root_id",
            (company_id, scope["financial_account_id"], scope["period_start"],
             scope["period_end"], scope["currency_code"], subject_id))
        inserted_root = cursor.fetchone()
        if inserted_root:
            root_id = str(inserted_root[0])
        else:
            cursor.execute(
                "SELECT statement_root_id FROM fincilia.reconciliation_statement_root "
                "WHERE company_id=%s AND financial_account_id=%s AND period_start=%s "
                "AND period_end=%s AND currency_code=%s",
                (company_id, scope["financial_account_id"], scope["period_start"],
                 scope["period_end"], scope["currency_code"]))
            root_id = str(cursor.fetchone()[0])
        item_ids = _eligible_statement_item_ids(
            cursor, company_id=company_id, root_id=root_id,
            currency_code=scope["currency_code"],
            engine_release_id=scope["engine_release_id"],
            canonical_schema_version=scope["canonical_schema_version"])
        statement_key = digest_of({
            "company_id": company_id, "root_id": root_id,
            "bank_id": scope["bank_id"], "books_id": scope["books_id"],
            "assessment_ids": scope["assessment_ids"], "item_ids": item_ids,
            "rule_versions": [RULE_VERSION],
        })
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                       (statement_key,))
        cursor.execute(
            "SELECT statement_id, lineage_state FROM fincilia.reconciliation_statement "
            "WHERE company_id=%s AND statement_key=%s", (company_id, statement_key))
        existing = cursor.fetchone()
        if existing is None:
            statement_id, replayed = str(uuid.uuid4()), False
            try:
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_statement "
                    "(statement_id, company_id, statement_root_id, version, "
                    "financial_account_id, period_start, period_end, currency_code, "
                    "bank_closing_balance_id, books_closing_balance_id, "
                    "completeness_assessment_ids, confirmed_reconciling_item_ids, "
                    "statement_key, prepared_by, engine_release_id, "
                    "canonical_schema_version, rule_version_ids, lineage_state) "
                    "VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s::uuid[], "
                    "%s::uuid[], %s, %s, %s, %s, %s::jsonb, 'required_pending')",
                    (statement_id, company_id, root_id, scope["financial_account_id"],
                     scope["period_start"], scope["period_end"], scope["currency_code"],
                     scope["bank_id"], scope["books_id"], scope["assessment_ids"],
                     item_ids, statement_key, subject_id, scope["engine_release_id"],
                     scope["canonical_schema_version"], json.dumps([RULE_VERSION])))
            except psycopg.errors.CheckViolation:
                raise ReconciliationError(
                    "statement-input-conflict",
                    "one or more statement inputs are no longer eligible") from None
            lineage_state = "required_pending"
        else:
            statement_id, lineage_state = str(existing[0]), existing[1]
            replayed = True
        if lineage_state == "required_pending":
            try:
                financial_lineage.materialize_statement(
                    cursor, company_id=company_id, subject_id=subject_id,
                    statement_id=statement_id)
            except financial_lineage.LineageError as error:
                raise ReconciliationError(error.code, error.detail) from None
            cursor.execute(
                "UPDATE fincilia.reconciliation_statement SET lineage_state='complete' "
                "WHERE company_id=%s AND statement_id=%s "
                "AND lineage_state='required_pending'",
                (company_id, statement_id))
            if cursor.rowcount != 1:
                raise ReconciliationError(
                    "financial-lineage-seal-conflict",
                    "the statement lineage could not be sealed atomically")
        cursor.execute(STATEMENT_SELECT + "WHERE r.statement_id=%s", (statement_id,))
        row = cursor.fetchone()
    return _statement_row(row, replayed=replayed)


def _eligible_statement_item_ids(
        cursor: psycopg.Cursor, *, company_id: str, root_id: str,
        currency_code: str, engine_release_id: str,
        canonical_schema_version: str) -> list[str]:
    """Fija solo decisiones vigentes compatibles con los saldos del statement."""
    cursor.execute(
        "SELECT item_decision_id FROM fincilia.reconciling_item i WHERE "
        "i.company_id=%s AND i.statement_root_id=%s AND i.state='confirmed' "
        "AND i.lineage_state='complete' AND i.currency_code=%s "
        "AND i.engine_release_id=%s AND i.canonical_schema_version=%s "
        "AND i.decision_version=(SELECT max(j.decision_version) FROM "
        "fincilia.reconciling_item j WHERE j.company_id=i.company_id "
        "AND j.item_root_id=i.item_root_id) ORDER BY i.item_root_id",
        (company_id, root_id, currency_code, engine_release_id,
         canonical_schema_version))
    return [str(row[0]) for row in cursor.fetchall()]


def create_item(connection: psycopg.Connection, *, company_id: str, subject_id: str,
                statement_root_id: str, amount: str, adjustment_side: str,
                reason_code: str, evidence_source_record_ids: list[str]) -> dict[str, Any]:
    root_id = _uuid(statement_root_id, code="statement-unavailable")
    if adjustment_side not in ADJUSTMENT_SIDES or reason_code not in REASON_CODES:
        raise ReconciliationError("reconciling-item-invalid",
                                  "the adjustment side or reason code is not supported")
    try:
        exact = parse_money(amount)
    except (MoneyError, TypeError):
        raise ReconciliationError("reconciling-item-invalid",
                                  "amount must be an exact decimal string") from None
    if exact <= Decimal(0):
        raise ReconciliationError("reconciling-item-invalid", "amount must be positive")
    refs = [_uuid(value, code="reconciling-item-evidence-unavailable")
            for value in evidence_source_record_ids]
    if not refs or len(refs) > 50 or len(set(refs)) != len(refs):
        raise ReconciliationError("reconciling-item-evidence-unavailable",
                                  "evidence identifiers must be unique and non-empty")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.currency_code, s.engine_release_id, s.canonical_schema_version "
            "FROM fincilia.reconciliation_statement_root r JOIN LATERAL (SELECT "
            "engine_release_id, canonical_schema_version FROM "
            "fincilia.reconciliation_statement WHERE statement_root_id=r.statement_root_id "
            "ORDER BY version DESC LIMIT 1) s ON true WHERE r.statement_root_id=%s",
            (root_id,))
        root = cursor.fetchone()
        if root is None:
            raise ReconciliationError("statement-unavailable", "the statement is unavailable")
        item_id = str(uuid.uuid4())
        evidence = json.dumps([{"kind": "source_record", "ref": value} for value in refs])
        try:
            financial_lineage.materialize_item(
                cursor, company_id=company_id, subject_id=subject_id,
                item_decision_id=item_id, evidence_source_record_ids=refs,
                decision_payload={
                    "item_root_id": item_id, "state": "proposed",
                    "adjustment_side": adjustment_side,
                    "amount": format_money(exact), "currency_code": root[0],
                    "reason_code": reason_code, "evidence_refs": refs,
                    "decision_version": 1,
                }, release_id=str(root[1]), schema_version=root[2])
            cursor.execute(
                "INSERT INTO fincilia.reconciling_item (item_decision_id, item_root_id, "
                "company_id, statement_root_id, adjustment_side, amount, currency_code, "
                "reason_code, state, evidence_refs, prepared_by, decision_version, "
                "engine_release_id, canonical_schema_version, lineage_state) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'proposed', %s::jsonb, "
                "%s, 1, %s, %s, 'complete')",
                (item_id, item_id, company_id, root_id, adjustment_side,
                 format_money(exact), root[0], reason_code, evidence, subject_id,
                 root[1], root[2]))
        except psycopg.errors.CheckViolation as error:
            if (error.diag.constraint_name or "").startswith("ck_item_evidence"):
                raise ReconciliationError(
                    "reconciling-item-evidence-unavailable",
                    "the selected evidence is unavailable") from None
            raise
        except financial_lineage.LineageError as error:
            raise ReconciliationError(error.code, error.detail) from None
        cursor.execute(ITEM_SELECT + "WHERE item_decision_id=%s", (item_id,))
        row = cursor.fetchone()
    return _item_row(row)


def decide_item(connection: psycopg.Connection, *, company_id: str, subject_id: str,
                item_root_id: str, decision: str) -> dict[str, Any]:
    root_id = _uuid(item_root_id, code="reconciling-item-unavailable")
    if decision not in DECISIONS:
        raise ReconciliationError("reconciling-item-decision-invalid",
                                  "the item decision is not supported")
    with connection.cursor() as cursor:
        # `FOR UPDATE` pediria al runtime privilegio UPDATE sobre una tabla que
        # es append-only. El trigger usa esta misma llave antes de insertar;
        # compartirla serializa la lectura y la nueva decision sin abrir UPDATE.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (root_id,),
        )
        cursor.execute(
            ITEM_SELECT + "WHERE company_id=%s AND item_root_id=%s "
            "ORDER BY decision_version DESC LIMIT 1", (company_id, root_id))
        previous = cursor.fetchone()
        if previous is None:
            raise ReconciliationError("reconciling-item-unavailable",
                                      "the reconciling item is unavailable")
        if previous[7] == decision:
            result = _item_row(previous)
            result["replayed"] = True
            return result
        valid = ((previous[7] == "proposed" and decision in {"confirmed", "rejected"})
                 or (previous[7] == "confirmed" and decision == "reversed"))
        if not valid:
            raise ReconciliationError("reconciling-item-decision-conflict",
                                      "the decision is incompatible with current state")
        if str(previous[8]) == subject_id:
            raise ReconciliationError("reconciling-item-sod-conflict",
                                      "the preparer cannot approve their own item")
        cursor.execute(
            "SELECT evidence_refs, engine_release_id, canonical_schema_version "
            "FROM fincilia.reconciling_item WHERE item_decision_id=%s", (previous[0],))
        evidence, release_id, schema = cursor.fetchone()
        decision_id = str(uuid.uuid4())
        evidence_refs = [str(item["ref"]) for item in evidence]
        try:
            financial_lineage.materialize_item(
                cursor, company_id=company_id, subject_id=subject_id,
                item_decision_id=decision_id,
                evidence_source_record_ids=evidence_refs,
                decision_payload={
                    "item_root_id": root_id, "state": decision,
                    "adjustment_side": previous[3],
                    "amount": format_money(previous[4]),
                    "currency_code": previous[5], "reason_code": previous[6],
                    "evidence_refs": evidence_refs,
                    "decision_version": int(previous[10]) + 1,
                }, release_id=str(release_id), schema_version=schema)
        except financial_lineage.LineageError as error:
            raise ReconciliationError(error.code, error.detail) from None
        cursor.execute(
            "INSERT INTO fincilia.reconciling_item (item_decision_id, item_root_id, "
            "company_id, statement_root_id, adjustment_side, amount, currency_code, "
            "reason_code, state, evidence_refs, prepared_by, approved_by, approved_at, "
            "decision_version, engine_release_id, canonical_schema_version, lineage_state) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, now(), "
            "%s, %s, %s, %s)",
            (decision_id, root_id, company_id, previous[2], previous[3], previous[4],
             previous[5], previous[6], decision, json.dumps(evidence), previous[8],
             subject_id, int(previous[10]) + 1, release_id, schema,
             "complete"))
        cursor.execute(ITEM_SELECT + "WHERE item_decision_id=%s", (decision_id,))
        row = cursor.fetchone()
    result = _item_row(row)
    result["replayed"] = False
    return result
