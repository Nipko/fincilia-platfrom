"""Alertas deterministas de calidad y su triaje humano.

Una alerta es una senal reproducible, nunca una conclusion de fraude. Las reglas
no escriben valores financieros ni cambian datasets, movimientos, matches o
cierres. PostgreSQL conserva el ledger; Valkey no participa.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import psycopg

from . import repository


RULE_VERSION = "quality-rules-v1"
MAX_SCAN_DATASETS = 100
MAX_FINDINGS_PER_RULE = 500
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_OFFSET = 10_000

STATUSES = frozenset(("open", "acknowledged", "resolved", "dismissed", "all"))
SEVERITIES = frozenset(("info", "warning", "high", "all"))
RULES = frozenset((
    "dataset_completeness_mismatch",
    "dataset_completeness_unknown",
    "dataset_rejected_records",
    "lineage_invalidated",
    "duplicate_fingerprint",
    "reference_amount_conflict",
    "posting_delay_over_31_days",
    "amount_outlier_10x_median",
))
REASONS = {
    "acknowledged": frozenset(("investigate",)),
    "resolved": frozenset((
        "reviewed_source", "corrected_upstream", "duplicate_confirmed")),
    "dismissed": frozenset((
        "expected_pattern", "false_positive", "not_applicable")),
}


class QualityError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class QualityQuery:
    status: str = "open"
    severity: str = "all"
    rule: str = "all"
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def validated(self) -> "QualityQuery":
        if self.status not in STATUSES:
            raise QualityError("quality-filter-invalid", "status is invalid")
        if self.severity not in SEVERITIES:
            raise QualityError("quality-filter-invalid", "severity is invalid")
        if self.rule != "all" and self.rule not in RULES:
            raise QualityError("quality-filter-invalid", "rule is invalid")
        if not 0 <= self.offset <= MAX_OFFSET:
            raise QualityError(
                "quality-filter-invalid", "offset must be between 0 and 10000")
        if not 1 <= self.limit <= MAX_LIMIT:
            raise QualityError(
                "quality-filter-invalid", "limit must be between 1 and 100")
        return self


@dataclass(frozen=True)
class Finding:
    rule_code: str
    scope_kind: str
    scope_ref: str
    severity: str
    discriminator: str
    occurrence_count: int = 1

    @property
    def issue_key(self) -> str:
        payload = (
            f"{RULE_VERSION}|{self.rule_code}|{self.scope_kind}|"
            f"{self.scope_ref}|{self.discriminator}")
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dataset_findings(connection: psycopg.Connection) -> Iterable[Finding]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_version_id, completeness_state, lineage_state, "
            "       rejected_count "
            "FROM fincilia.dataset_version "
            "ORDER BY prepared_at DESC, dataset_version_id LIMIT %s",
            (MAX_SCAN_DATASETS,))
        for dataset_id, completeness, lineage, rejected in cursor:
            scope = str(dataset_id)
            if completeness == "mismatch":
                yield Finding(
                    "dataset_completeness_mismatch", "dataset", scope, "high", scope)
            elif completeness == "unknown":
                yield Finding(
                    "dataset_completeness_unknown", "dataset", scope, "warning", scope)
            if int(rejected) > 0:
                yield Finding(
                    "dataset_rejected_records", "dataset", scope, "warning", scope,
                    int(rejected))
            if lineage == "invalidated":
                yield Finding("lineage_invalidated", "dataset", scope, "high", scope)


def _group_findings(connection: psycopg.Connection, *, rule_code: str,
                    sql: str, severity: str) -> tuple[list[Finding], bool]:
    with connection.cursor() as cursor:
        cursor.execute(sql, (MAX_SCAN_DATASETS, MAX_FINDINGS_PER_RULE + 1))
        rows = list(cursor)
    truncated = len(rows) > MAX_FINDINGS_PER_RULE
    findings = [
        Finding(rule_code, "dataset", str(row[0]), severity, str(row[1]), int(row[2]))
        for row in rows[:MAX_FINDINGS_PER_RULE]
    ]
    return findings, truncated


def _movement_findings(connection: psycopg.Connection, *, rule_code: str,
                       sql: str, severity: str) -> tuple[list[Finding], bool]:
    with connection.cursor() as cursor:
        cursor.execute(sql, (MAX_SCAN_DATASETS, MAX_FINDINGS_PER_RULE + 1))
        rows = list(cursor)
    truncated = len(rows) > MAX_FINDINGS_PER_RULE
    findings = [
        Finding(rule_code, "movement", str(row[0]), severity, str(row[0]))
        for row in rows[:MAX_FINDINGS_PER_RULE]
    ]
    return findings, truncated


def detect(connection: psycopg.Connection) -> tuple[list[Finding], list[str]]:
    """Evalua reglas cerradas sobre una ventana acotada de datos company-scoped."""
    findings = list(_dataset_findings(connection))
    truncated_rules: list[str] = []

    duplicate, truncated = _group_findings(
        connection,
        rule_code="duplicate_fingerprint",
        severity="high",
        sql="""
WITH recent AS (
  SELECT dataset_version_id FROM fincilia.dataset_version
  ORDER BY prepared_at DESC, dataset_version_id LIMIT %s
)
SELECT m.dataset_version_id, m.dedupe_fingerprint, count(*)
FROM fincilia.canonical_movement m
JOIN recent r USING (dataset_version_id)
GROUP BY m.dataset_version_id, m.dedupe_fingerprint
HAVING count(*) > 1
ORDER BY m.dataset_version_id, m.dedupe_fingerprint
LIMIT %s
""")
    findings.extend(duplicate)
    if truncated:
        truncated_rules.append("duplicate_fingerprint")

    conflicts, truncated = _group_findings(
        connection,
        rule_code="reference_amount_conflict",
        severity="warning",
        sql="""
WITH recent AS (
  SELECT dataset_version_id FROM fincilia.dataset_version
  ORDER BY prepared_at DESC, dataset_version_id LIMIT %s
)
SELECT m.dataset_version_id, m.reference_normalised, count(*)
FROM fincilia.canonical_movement m
JOIN recent r USING (dataset_version_id)
WHERE m.reference_normalised IS NOT NULL
GROUP BY m.dataset_version_id, m.reference_normalised
HAVING count(DISTINCT (m.amount, m.currency_code, m.direction)) > 1
ORDER BY m.dataset_version_id, m.reference_normalised
LIMIT %s
""")
    findings.extend(conflicts)
    if truncated:
        truncated_rules.append("reference_amount_conflict")

    delays, truncated = _movement_findings(
        connection,
        rule_code="posting_delay_over_31_days",
        severity="warning",
        sql="""
WITH recent AS (
  SELECT dataset_version_id FROM fincilia.dataset_version
  ORDER BY prepared_at DESC, dataset_version_id LIMIT %s
)
SELECT m.movement_id
FROM fincilia.canonical_movement m
JOIN recent r USING (dataset_version_id)
WHERE m.posted_on IS NOT NULL AND m.posted_on - m.occurred_on > 31
ORDER BY m.movement_id
LIMIT %s
""")
    findings.extend(delays)
    if truncated:
        truncated_rules.append("posting_delay_over_31_days")

    outliers, truncated = _movement_findings(
        connection,
        rule_code="amount_outlier_10x_median",
        severity="warning",
        sql="""
WITH recent AS (
  SELECT dataset_version_id FROM fincilia.dataset_version
  ORDER BY prepared_at DESC, dataset_version_id LIMIT %s
), baselines AS (
  SELECT m.dataset_version_id, m.currency_code, m.direction,
         percentile_disc(0.5) WITHIN GROUP (ORDER BY m.amount) AS median_amount,
         count(*) AS sample_size
  FROM fincilia.canonical_movement m
  JOIN recent r USING (dataset_version_id)
  GROUP BY m.dataset_version_id, m.currency_code, m.direction
)
SELECT m.movement_id
FROM fincilia.canonical_movement m
JOIN baselines b USING (dataset_version_id, currency_code, direction)
WHERE b.sample_size >= 20 AND m.amount > b.median_amount * 10
ORDER BY m.movement_id
LIMIT %s
""")
    findings.extend(outliers)
    if truncated:
        truncated_rules.append("amount_outlier_10x_median")
    return findings, truncated_rules


def scan(connection: psycopg.Connection, *, company_id: str,
         actor_id: str) -> dict[str, Any]:
    findings, truncated_rules = detect(connection)
    created = 0
    refreshed = 0
    with connection.cursor() as cursor:
        for finding in findings:
            cursor.execute(
                "INSERT INTO fincilia.quality_issue "
                "(company_id, issue_key, rule_code, rule_version, scope_kind, "
                " scope_ref, severity, occurrence_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (company_id, issue_key) DO UPDATE SET "
                "severity = EXCLUDED.severity, "
                "occurrence_count = GREATEST(fincilia.quality_issue.occurrence_count, "
                "                            EXCLUDED.occurrence_count), "
                "last_seen_at = now(), updated_at = now() "
                "RETURNING (xmax = 0)",
                (company_id, finding.issue_key, finding.rule_code, RULE_VERSION,
                 finding.scope_kind, finding.scope_ref, finding.severity,
                 finding.occurrence_count))
            if bool(cursor.fetchone()[0]):
                created += 1
            else:
                refreshed += 1
    repository.record_audit(
        connection, subject_id=actor_id, company_id=company_id,
        action="quality.scan", resource_kind="company", resource_ref=company_id,
        outcome="allowed", detail={
            "rule_version": RULE_VERSION,
            "findings": len(findings),
            "created": created,
            "refreshed": refreshed,
            "truncated_rules": truncated_rules,
        })
    return {
        "rule_version": RULE_VERSION,
        "datasets_examined_limit": MAX_SCAN_DATASETS,
        "findings": len(findings),
        "created": created,
        "refreshed": refreshed,
        "truncated": bool(truncated_rules),
        "truncated_rules": truncated_rules,
        "financial_effect": "none",
    }


def _issue(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "issue_id": str(row[0]),
        "rule_code": row[1],
        "rule_version": row[2],
        "scope_kind": row[3],
        "scope_ref": str(row[4]),
        "severity": row[5],
        "status": row[6],
        "occurrence_count": int(row[7]),
        "assigned_to": str(row[8]) if row[8] is not None else None,
        "assigned_to_name": row[9],
        "reviewed_by": str(row[10]) if row[10] is not None else None,
        "reviewed_by_name": row[11],
        "resolution_reason": row[12],
        "first_seen_at": row[13].isoformat(),
        "last_seen_at": row[14].isoformat(),
        "updated_at": row[15].isoformat(),
        "financial_effect": "none",
        "proves_fraud": False,
    }


ISSUE_SELECT = (
    "SELECT q.issue_id, q.rule_code, q.rule_version, q.scope_kind, q.scope_ref, "
    "       q.severity, q.status, q.occurrence_count, q.assigned_to, "
    "       assignee.display_name, q.reviewed_by, reviewer.display_name, "
    "       q.resolution_reason, q.first_seen_at, q.last_seen_at, q.updated_at "
    "FROM fincilia.quality_issue q "
    "LEFT JOIN fincilia.subject assignee ON assignee.subject_id = q.assigned_to "
    "LEFT JOIN fincilia.subject reviewer ON reviewer.subject_id = q.reviewed_by ")


def list_issues(connection: psycopg.Connection, *, status: str = "open",
                severity: str = "all", rule: str = "all", offset: int = 0,
                limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    query = QualityQuery(status, severity, rule, int(offset), int(limit)).validated()
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (("q.status", query.status), ("q.severity", query.severity),
                          ("q.rule_code", query.rule)):
        if value != "all":
            clauses.append(f"{column} = %s")
            params.append(value)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*), "
            "count(*) FILTER (WHERE status = 'open'), "
            "count(*) FILTER (WHERE status = 'acknowledged'), "
            "count(*) FILTER (WHERE status = 'resolved'), "
            "count(*) FILTER (WHERE status = 'dismissed'), "
            "count(*) FILTER (WHERE severity = 'high'), "
            "count(*) FILTER (WHERE severity = 'warning'), "
            "count(*) FILTER (WHERE severity = 'info') "
            "FROM fincilia.quality_issue")
        summary = cursor.fetchone()
        cursor.execute(
            ISSUE_SELECT + where
            + " ORDER BY CASE q.severity WHEN 'high' THEN 0 WHEN 'warning' THEN 1 "
              " ELSE 2 END, q.last_seen_at DESC, q.issue_id LIMIT %s OFFSET %s",
            tuple(params + [query.limit + 1, query.offset]))
        rows = list(cursor)
    names = ("total", "open", "acknowledged", "resolved", "dismissed",
             "high", "warning", "info")
    return {
        "filter": {"status": query.status, "severity": query.severity,
                   "rule": query.rule},
        "offset": query.offset,
        "limit": query.limit,
        "truncated": len(rows) > query.limit,
        "summary": {name: int(summary[index]) for index, name in enumerate(names)},
        "items": [_issue(row) for row in rows[:query.limit]],
        "notice": "quality_signal_only; human_review_required; no_fraud_assertion",
    }


def triage(connection: psycopg.Connection, *, company_id: str, actor_id: str,
           issue_id: str, status: str, reason_code: str,
           rationale: str) -> dict[str, Any]:
    try:
        issue_id = str(uuid.UUID(issue_id))
    except (ValueError, TypeError, AttributeError):
        raise QualityError("quality-issue-unavailable", "the issue is unavailable") from None
    rationale = rationale.strip()
    if status not in REASONS or reason_code not in REASONS[status]:
        raise QualityError(
            "quality-transition-invalid", "status and reason_code are incompatible")
    if not 10 <= len(rationale) <= 500:
        raise QualityError(
            "quality-transition-invalid", "rationale must contain 10 to 500 characters")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, resolution_reason FROM fincilia.quality_issue "
            "WHERE issue_id = %s FOR UPDATE", (issue_id,))
        current = cursor.fetchone()
    if current is None:
        raise QualityError("quality-issue-unavailable", "the issue is unavailable")
    from_status = current[0]

    if from_status == status:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT reason_code, rationale, actor_id FROM fincilia.quality_issue_event "
                "WHERE issue_id = %s AND to_status = %s "
                "ORDER BY occurred_at DESC, event_id DESC LIMIT 1",
                (issue_id, status))
            previous = cursor.fetchone()
        if previous == (reason_code, rationale, uuid.UUID(actor_id)):
            result = load_issue(connection, issue_id)
            if result is None:
                raise RuntimeError("replayed quality issue disappeared")
            return {**result, "replayed": True}
        raise QualityError("quality-issue-terminal", "the issue was already reviewed")

    allowed = ((from_status == "open" and status in REASONS)
               or (from_status == "acknowledged" and status in {"resolved", "dismissed"}))
    if not allowed:
        raise QualityError("quality-issue-terminal", "the issue was already reviewed")

    audit_event_id = repository.record_audit(
        connection, subject_id=actor_id, company_id=company_id,
        action=f"quality.{status}", resource_kind="quality_issue",
        resource_ref=issue_id, outcome="allowed",
        detail={"from_status": from_status, "to_status": status,
                "reason_code": reason_code})
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.quality_issue SET status = %s, "
            "assigned_to = CASE WHEN %s = 'acknowledged' THEN %s ELSE assigned_to END, "
            "reviewed_by = %s, reviewed_at = now(), resolution_reason = %s, "
            "updated_at = now() WHERE issue_id = %s",
            (status, status, actor_id, actor_id, reason_code, issue_id))
        cursor.execute(
            "INSERT INTO fincilia.quality_issue_event "
            "(company_id, issue_id, from_status, to_status, reason_code, rationale, "
            " actor_id, audit_event_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (company_id, issue_id, from_status, status, reason_code, rationale,
             actor_id, audit_event_id))
    result = load_issue(connection, issue_id)
    if result is None:
        raise RuntimeError("updated quality issue cannot be read back")
    return {**result, "replayed": False}


def load_issue(connection: psycopg.Connection, issue_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(ISSUE_SELECT + "WHERE q.issue_id = %s", (issue_id,))
        row = cursor.fetchone()
    return None if row is None else _issue(row)
