"""Proyeccion operativa de ciclos y recordatorios dentro de la plataforma.

`source_expectation` conserva el hecho historico; este modulo solo deriva como
se ve ese hecho hoy. No envia mensajes, no persiste el paso del tiempo y no
convierte un vencimiento en una conclusion contable.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg


DEFAULT_LIMIT = 25
MAX_LIMIT = 50
REMINDER_FILTERS = frozenset((
    "attention", "overdue", "in_grace", "due_today", "due_soon",
    "upcoming", "satisfied", "waived", "all",
))

_FILTER_SQL = {
    "attention": "reminder_state IN ('overdue', 'in_grace', 'due_today', 'due_soon')",
    "overdue": "reminder_state = 'overdue'",
    "in_grace": "reminder_state = 'in_grace'",
    "due_today": "reminder_state = 'due_today'",
    "due_soon": "reminder_state = 'due_soon'",
    "upcoming": "reminder_state = 'upcoming'",
    "satisfied": "reminder_state = 'satisfied'",
    "waived": "reminder_state = 'waived'",
    "all": "TRUE",
}

_CLASSIFIED_CTE = """
WITH clock AS (
  SELECT %s::date AS today, %s::date AS soon_through
), classified AS (
  SELECT e.expectation_id, e.data_source_id, s.display_name AS source_name,
         e.period_start, e.period_end, e.due_on, e.late_after,
         e.state AS stored_state, e.satisfied_at, e.waived_reason,
         c.responsible_subject_id,
         responsible.display_name AS responsible_name,
         CASE
           WHEN c.responsible_subject_id IS NULL THEN false
           ELSE EXISTS (
             SELECT 1
             FROM fincilia.company_grant g
             JOIN fincilia.engagement engagement
               ON engagement.company_id = g.company_id
             JOIN fincilia.membership membership
               ON membership.firm_id = engagement.firm_id
              AND membership.subject_id = g.subject_id
             JOIN fincilia.subject eligible
               ON eligible.subject_id = g.subject_id
             WHERE g.company_id = e.company_id
               AND g.subject_id = c.responsible_subject_id
               AND g.revoked_at IS NULL
               AND engagement.status = 'active'
               AND (engagement.valid_to IS NULL
                    OR engagement.valid_to >= clock.today)
               AND membership.status = 'active'
               AND eligible.status = 'active'
               AND eligible.subject_kind = 'person')
         END AS responsible_eligible,
         CASE
           WHEN e.state = 'satisfied' THEN 'satisfied'
           WHEN e.state = 'waived' THEN 'waived'
           WHEN e.state = 'late' OR clock.today > e.late_after THEN 'overdue'
           WHEN clock.today = e.due_on THEN 'due_today'
           WHEN clock.today > e.due_on THEN 'in_grace'
           WHEN e.due_on <= clock.soon_through THEN 'due_soon'
           ELSE 'upcoming'
         END AS reminder_state,
         CASE
           WHEN e.state IN ('satisfied', 'waived') THEN 0
           WHEN clock.today > e.late_after
             THEN (clock.today - e.late_after)
           ELSE 0
         END AS days_late,
         CASE
           WHEN e.state IN ('satisfied', 'waived') THEN NULL
           ELSE (e.due_on - clock.today)
         END AS days_until_due
  FROM fincilia.source_expectation e
  JOIN fincilia.data_source s
    ON s.data_source_id = e.data_source_id
   AND s.company_id = e.company_id
  LEFT JOIN fincilia.source_cycle c
    ON c.cycle_id = e.cycle_id
   AND c.company_id = e.company_id
  LEFT JOIN fincilia.subject responsible
    ON responsible.subject_id = c.responsible_subject_id
  CROSS JOIN clock
)
"""


class OperationsQueryError(Exception):
    """La consulta no define una ventana segura y reproducible."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class OperationsQuery:
    status: str = "attention"
    limit: int = DEFAULT_LIMIT
    cursor: str | None = None

    def validated(self) -> "OperationsQuery":
        if self.status not in REMINDER_FILTERS:
            raise OperationsQueryError(
                "operations-filter-invalid",
                "status must be attention, overdue, in_grace, due_today, "
                "due_soon, upcoming, satisfied, waived or all")
        if not 1 <= self.limit <= MAX_LIMIT:
            raise OperationsQueryError(
                "operations-limit-invalid", "limit must be between 1 and 50")
        if self.cursor is not None:
            decode_cursor(self.cursor)
        return self


def encode_cursor(due_on: dt.date, expectation_id: str) -> str:
    payload = f"{due_on.isoformat()}|{uuid.UUID(expectation_id)}".encode("ascii")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> tuple[dt.date, str]:
    if not value or len(value) > 128:
        raise OperationsQueryError(
            "operations-cursor-invalid", "cursor is invalid or too long")
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
        date_text, identifier = raw.split("|", 1)
        return dt.date.fromisoformat(date_text), str(uuid.UUID(identifier))
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise OperationsQueryError(
            "operations-cursor-invalid", "cursor is invalid") from error


def classify_state(*, stored_state: str, due_on: dt.date,
                   late_after: dt.date, today: dt.date) -> str:
    """Referencia pura para contratos, fixtures y explicacion de la UI."""
    if stored_state == "satisfied":
        return "satisfied"
    if stored_state == "waived":
        return "waived"
    if stored_state == "late" or today > late_after:
        return "overdue"
    if today == due_on:
        return "due_today"
    if today > due_on:
        return "in_grace"
    if due_on <= today + dt.timedelta(days=7):
        return "due_soon"
    return "upcoming"


def _item(row: tuple[Any, ...], subject_id: str) -> dict[str, Any]:
    return {
        "expectation_id": str(row[0]),
        "data_source_id": str(row[1]),
        "source_name": row[2],
        "period_start": row[3].isoformat(),
        "period_end": row[4].isoformat(),
        "due_on": row[5].isoformat(),
        "late_after": row[6].isoformat(),
        "stored_state": row[7],
        "satisfied_at": row[8].isoformat() if row[8] is not None else None,
        "waived_reason": row[9],
        "responsible_subject_id": str(row[10]) if row[10] is not None else None,
        "responsible_name": row[11],
        "responsible_eligible": bool(row[12]),
        "assigned_to_me": row[10] is not None and str(row[10]) == subject_id,
        "reminder_state": row[13],
        "days_late": int(row[14]),
        "days_until_due": int(row[15]) if row[15] is not None else None,
    }


def list_operational_periods(
        connection: psycopg.Connection, *, today: dt.date, subject_id: str,
        status: str = "attention", limit: int = DEFAULT_LIMIT,
        cursor: str | None = None) -> dict[str, Any]:
    """Lista y resume periodos company-scoped bajo la RLS de la sesion."""
    query = OperationsQuery(status=status, limit=limit, cursor=cursor).validated()
    soon_through = today + dt.timedelta(days=7)
    filter_sql = _FILTER_SQL[query.status]
    cursor_sql = ""
    cursor_params: tuple[Any, ...] = ()
    if query.cursor:
        cursor_due, cursor_id = decode_cursor(query.cursor)
        cursor_sql = "AND (due_on, expectation_id) > (%s::date, %s::uuid)"
        cursor_params = (cursor_due, cursor_id)

    summary_sql = _CLASSIFIED_CTE + f"""
SELECT count(*) AS period_count,
       count(DISTINCT data_source_id) AS source_count,
       count(*) FILTER (WHERE reminder_state = 'overdue') AS overdue,
       count(*) FILTER (WHERE reminder_state = 'in_grace') AS in_grace,
       count(*) FILTER (WHERE reminder_state = 'due_today') AS due_today,
       count(*) FILTER (WHERE reminder_state = 'due_soon') AS due_soon,
       count(*) FILTER (WHERE reminder_state = 'upcoming') AS upcoming,
       count(*) FILTER (WHERE reminder_state = 'satisfied') AS satisfied,
       count(*) FILTER (WHERE reminder_state = 'waived') AS waived,
       count(*) FILTER (WHERE {filter_sql}) AS filtered_total,
       min(due_on), max(due_on)
FROM classified
"""
    item_sql = _CLASSIFIED_CTE + f"""
SELECT expectation_id, data_source_id, source_name, period_start, period_end,
       due_on, late_after, stored_state, satisfied_at, waived_reason,
       responsible_subject_id, responsible_name, responsible_eligible,
       reminder_state, days_late, days_until_due
FROM classified
WHERE {filter_sql} {cursor_sql}
ORDER BY due_on ASC, expectation_id ASC
LIMIT %s
"""

    clock_params = (today, soon_through)
    with connection.cursor() as db_cursor:
        db_cursor.execute(summary_sql, clock_params)
        summary_row = db_cursor.fetchone()
        db_cursor.execute(
            item_sql, clock_params + cursor_params + (query.limit + 1,))
        rows = list(db_cursor)

    if summary_row is None:
        raise RuntimeError("operational summary returned no row")
    has_more = len(rows) > query.limit
    visible_rows = rows[:query.limit]
    items = [_item(row, subject_id) for row in visible_rows]
    next_cursor = None
    if has_more and visible_rows:
        next_cursor = encode_cursor(
            visible_rows[-1][5], str(visible_rows[-1][0]))

    summary_names = (
        "period_count", "source_count", "overdue", "in_grace", "due_today",
        "due_soon", "upcoming", "satisfied", "waived", "filtered_total",
    )
    summary = {name: int(summary_row[index])
               for index, name in enumerate(summary_names)}
    summary["oldest_due_on"] = (
        summary_row[10].isoformat() if summary_row[10] is not None else None)
    summary["newest_due_on"] = (
        summary_row[11].isoformat() if summary_row[11] is not None else None)

    return {
        "as_of": today.isoformat(),
        "due_soon_through": soon_through.isoformat(),
        "filter": query.status,
        "limit": query.limit,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "summary": summary,
        "items": items,
        "notice": (
            "in_app_projection_only; no email, push, SMS or certified close "
            "is asserted"),
    }
