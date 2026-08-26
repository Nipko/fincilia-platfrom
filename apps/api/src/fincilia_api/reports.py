"""Informes operativos historicos sobre la fuente de verdad company-scoped.

No es un balance ni un cierre. Los importes solo resumen movimientos de datasets
publicados, verificados y con linaje completo; PostgreSQL conserva el decimal y
la API lo serializa como texto de punto fijo.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg


ALLOWED_DAYS = frozenset((30, 90, 180, 365))
RECENT_DATASET_LIMIT = 12
CSV_HEADERS = (
    "month", "currency", "movement_count", "inflow_amount", "outflow_amount",
)


class ReportError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReportWindow:
    days: int
    as_of: dt.date

    @classmethod
    def validated(cls, days: int, as_of: dt.date | None,
                  *, today: dt.date | None = None) -> "ReportWindow":
        if days not in ALLOWED_DAYS:
            raise ReportError(
                "report-range-invalid", "days must be 30, 90, 180 or 365")
        clock = today or dt.datetime.now(dt.timezone.utc).date()
        end = as_of or clock
        if end > clock:
            raise ReportError(
                "report-date-invalid", "as_of cannot be later than today in UTC")
        if end < dt.date(2000, 1, 1):
            raise ReportError("report-date-invalid", "as_of is outside the supported range")
        return cls(days=days, as_of=end)

    @property
    def start(self) -> dt.date:
        return self.as_of - dt.timedelta(days=self.days - 1)

    @property
    def end_exclusive(self) -> dt.date:
        return self.as_of + dt.timedelta(days=1)


def fixed_decimal(value: Decimal | int) -> str:
    if isinstance(value, float):
        raise TypeError("financial values cannot be floats")
    return f"{Decimal(value):.12f}"


def _counts(row: tuple[Any, ...], names: tuple[str, ...]) -> dict[str, int]:
    return {name: int(row[index] or 0) for index, name in enumerate(names)}


def operational_report(connection: psycopg.Connection, *, days: int,
                       as_of: dt.date | None = None,
                       today: dt.date | None = None) -> dict[str, Any]:
    window = ReportWindow.validated(days, as_of, today=today)
    bounds = (window.start, window.end_exclusive)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE zone = 'raw'), "
            "count(*) FILTER (WHERE zone = 'quarantine'), coalesce(sum(byte_size), 0) "
            "FROM fincilia.source_artifact "
            "WHERE uploaded_at >= %s::date AND uploaded_at < %s::date", bounds)
        documents = _counts(cursor.fetchone(), (
            "total", "accepted", "quarantined", "bytes"))

        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE state = 'draft'), "
            "count(*) FILTER (WHERE state = 'validated'), "
            "count(*) FILTER (WHERE state = 'published'), "
            "count(*) FILTER (WHERE state = 'rejected'), "
            "coalesce(sum(record_count), 0), coalesce(sum(movement_count), 0), "
            "coalesce(sum(rejected_count), 0), "
            "count(*) FILTER (WHERE completeness_state = 'mismatch'), "
            "count(*) FILTER (WHERE completeness_state = 'unknown'), "
            "count(*) FILTER (WHERE lineage_state = 'invalidated') "
            "FROM fincilia.dataset_version "
            "WHERE prepared_at >= %s::date AND prepared_at < %s::date", bounds)
        datasets = _counts(cursor.fetchone(), (
            "total", "draft", "validated", "published", "rejected", "records",
            "movements", "rejected_records", "completeness_mismatch",
            "completeness_unknown", "lineage_invalidated"))

        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE d.decision IS NULL), "
            "count(*) FILTER (WHERE d.decision = 'confirmed'), "
            "count(*) FILTER (WHERE d.decision = 'rejected') "
            "FROM fincilia.match_candidate c LEFT JOIN fincilia.match_decision d "
            "ON d.candidate_id = c.candidate_id AND d.company_id = c.company_id "
            "WHERE c.proposed_at >= %s::date AND c.proposed_at < %s::date", bounds)
        reconciliation = _counts(cursor.fetchone(), (
            "candidates", "pending", "confirmed", "rejected"))

        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE status = 'open'), "
            "count(*) FILTER (WHERE status = 'acknowledged'), "
            "count(*) FILTER (WHERE status IN ('resolved', 'dismissed')), "
            "count(*) FILTER (WHERE severity = 'high' AND status IN ('open', 'acknowledged')) "
            "FROM fincilia.quality_issue "
            "WHERE last_seen_at >= %s::date AND last_seen_at < %s::date", bounds)
        quality = _counts(cursor.fetchone(), (
            "signals", "open", "acknowledged", "closed", "active_high"))

        cursor.execute(
            "WITH months AS ("
            " SELECT generate_series(date_trunc('month', %s::date), "
            " date_trunc('month', %s::date), interval '1 month')::date AS bucket"
            "), documents AS ("
            " SELECT date_trunc('month', uploaded_at)::date AS bucket, count(*) total"
            " FROM fincilia.source_artifact WHERE uploaded_at >= %s::date "
            " AND uploaded_at < %s::date GROUP BY 1"
            "), datasets AS ("
            " SELECT date_trunc('month', prepared_at)::date AS bucket, count(*) total"
            " FROM fincilia.dataset_version WHERE prepared_at >= %s::date "
            " AND prepared_at < %s::date GROUP BY 1"
            "), movements AS ("
            " SELECT date_trunc('month', occurred_on)::date AS bucket, count(*) total"
            " FROM fincilia.canonical_movement WHERE occurred_on >= %s::date "
            " AND occurred_on < %s::date GROUP BY 1"
            ") SELECT m.bucket, coalesce(a.total, 0), coalesce(d.total, 0), "
            "coalesce(v.total, 0) FROM months m LEFT JOIN documents a USING (bucket) "
            "LEFT JOIN datasets d USING (bucket) LEFT JOIN movements v USING (bucket) "
            "ORDER BY m.bucket",
            (window.start, window.as_of, *bounds, *bounds, *bounds))
        activity_series = [{
            "month": row[0].isoformat(), "documents": int(row[1]),
            "datasets": int(row[2]), "movements": int(row[3]),
        } for row in cursor]

        eligible_cte = (
            "WITH eligible AS (SELECT m.* FROM fincilia.canonical_movement m "
            "JOIN fincilia.dataset_version d ON d.dataset_version_id = m.dataset_version_id "
            "AND d.company_id = m.company_id WHERE m.occurred_on >= %s::date "
            "AND m.occurred_on < %s::date AND d.state = 'published' "
            "AND d.completeness_state = 'verified' AND d.lineage_state = 'complete' "
            "AND m.lineage_state = 'complete' AND m.state <> 'voided') ")
        cursor.execute(
            eligible_cte +
            "SELECT currency_code, count(*), "
            "coalesce(sum(amount) FILTER (WHERE direction = 'inflow'), 0), "
            "coalesce(sum(amount) FILTER (WHERE direction = 'outflow'), 0) "
            "FROM eligible GROUP BY currency_code ORDER BY currency_code", bounds)
        money_totals = [{
            "currency": row[0], "movement_count": int(row[1]),
            "inflow_amount": fixed_decimal(row[2]),
            "outflow_amount": fixed_decimal(row[3]),
        } for row in cursor]

        cursor.execute(
            eligible_cte +
            ", months AS (SELECT generate_series(date_trunc('month', %s::date), "
            "date_trunc('month', %s::date), interval '1 month')::date AS bucket), "
            "currencies AS (SELECT DISTINCT currency_code FROM eligible) "
            "SELECT months.bucket, currencies.currency_code, count(e.movement_id), "
            "coalesce(sum(e.amount) FILTER (WHERE e.direction = 'inflow'), 0), "
            "coalesce(sum(e.amount) FILTER (WHERE e.direction = 'outflow'), 0) "
            "FROM months CROSS JOIN currencies LEFT JOIN eligible e "
            "ON date_trunc('month', e.occurred_on)::date = months.bucket "
            "AND e.currency_code = currencies.currency_code "
            "GROUP BY months.bucket, currencies.currency_code "
            "ORDER BY months.bucket, currencies.currency_code",
            (*bounds, window.start, window.as_of))
        money_series = [{
            "month": row[0].isoformat(), "currency": row[1],
            "movement_count": int(row[2]),
            "inflow_amount": fixed_decimal(row[3]),
            "outflow_amount": fixed_decimal(row[4]),
        } for row in cursor]

        cursor.execute(
            "SELECT dataset_version_id, artifact_id, state, completeness_state, "
            "lineage_state, record_count, movement_count, rejected_count, prepared_at "
            "FROM fincilia.dataset_version WHERE prepared_at >= %s::date "
            "AND prepared_at < %s::date ORDER BY prepared_at DESC, dataset_version_id "
            "LIMIT %s", (*bounds, RECENT_DATASET_LIMIT))
        recent_datasets = [{
            "dataset_version_id": str(row[0]), "artifact_id": str(row[1]),
            "state": row[2], "completeness_state": row[3],
            "lineage_state": row[4], "record_count": int(row[5]),
            "movement_count": int(row[6]), "rejected_count": int(row[7]),
            "prepared_at": row[8].isoformat(),
        } for row in cursor]

    return {
        "range": {"days": window.days, "start": window.start.isoformat(),
                  "end": window.as_of.isoformat(), "timezone": "UTC"},
        "summary": {"documents": documents, "datasets": datasets,
                    "reconciliation": reconciliation, "quality": quality},
        "activity_series": activity_series,
        "money_totals": money_totals,
        "money_series": money_series,
        "recent_datasets": recent_datasets,
        "notice": (
            "operational_non_certified; synthetic_only; no_balance_or_close; "
            "money_series_uses_verified_published_complete_lineage_only"),
    }


def report_csv(report: dict[str, Any]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect="excel", lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for item in report["money_series"]:
        writer.writerow(tuple(str(item[name]) for name in CSV_HEADERS))
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
