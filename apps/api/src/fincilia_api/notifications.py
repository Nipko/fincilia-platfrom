"""Preferencias e intenciones de notificación, sin adaptador externo activo."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg

from . import operations


TEMPLATES = frozenset({
    "period_due_soon", "period_due_today", "period_in_grace", "period_overdue",
})
STATE_TEMPLATE = {
    "due_soon": "period_due_soon",
    "due_today": "period_due_today",
    "in_grace": "period_in_grace",
    "overdue": "period_overdue",
}
LOCALES = frozenset({"es-CO", "en-US"})


@dataclass(frozen=True)
class NotificationError(Exception):
    code: str
    detail: str


def _time(value: str, field: str) -> dt.time:
    try:
        parsed = dt.time.fromisoformat(value)
    except (TypeError, ValueError):
        raise NotificationError(
            "notification-preference-invalid", f"{field} must be HH:MM") from None
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise NotificationError(
            "notification-preference-invalid", f"{field} must be minute precision")
    return parsed


def validate_preference(*, enabled: bool, locale: str, timezone: str,
                        quiet_from: str, quiet_until: str) -> dict[str, Any]:
    if type(enabled) is not bool:  # noqa: E721 - bool exacto, no entero 0/1
        raise NotificationError(
            "notification-preference-invalid", "enabled must be boolean")
    if locale not in LOCALES:
        raise NotificationError(
            "notification-preference-invalid", "locale is not supported")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise NotificationError(
            "notification-preference-invalid", "timezone is not recognised") from None
    start = _time(quiet_from, "quiet_from")
    end = _time(quiet_until, "quiet_until")
    if start == end:
        raise NotificationError(
            "notification-preference-invalid", "quiet hours cannot cover the whole day")
    return {
        "enabled": enabled, "locale": locale, "timezone": timezone,
        "quiet_from": start, "quiet_until": end,
    }


def read_preference(connection: psycopg.Connection, *, subject_id: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT preference_id::text, enabled, locale, timezone, quiet_from, "
            "quiet_until, updated_at FROM fincilia.notification_preference "
            "WHERE subject_id = %s AND channel = 'email' "
            "AND purpose_code = 'operational_reminder'", (subject_id,))
        row = cursor.fetchone()
    if row is None:
        return {
            "preference_id": None, "channel": "email",
            "purpose_code": "operational_reminder", "enabled": False,
            "locale": "es-CO", "timezone": "America/Bogota",
            "quiet_from": "20:00", "quiet_until": "07:00", "updated_at": None,
            "destination_state": "provider_configuration_pending",
        }
    return {
        "preference_id": row[0], "channel": "email",
        "purpose_code": "operational_reminder", "enabled": row[1],
        "locale": row[2], "timezone": row[3],
        "quiet_from": row[4].strftime("%H:%M"),
        "quiet_until": row[5].strftime("%H:%M"),
        "updated_at": row[6].isoformat(),
        "destination_state": "provider_configuration_pending",
    }


def write_preference(connection: psycopg.Connection, *, company_id: str,
                     subject_id: str, enabled: bool, locale: str, timezone: str,
                     quiet_from: str, quiet_until: str) -> dict[str, Any]:
    value = validate_preference(
        enabled=enabled, locale=locale, timezone=timezone,
        quiet_from=quiet_from, quiet_until=quiet_until)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.notification_preference "
            "(company_id, subject_id, channel, purpose_code, enabled, locale, "
            "timezone, quiet_from, quiet_until) "
            "VALUES (%s, %s, 'email', 'operational_reminder', %s, %s, %s, %s, %s) "
            "ON CONFLICT (company_id, subject_id, channel, purpose_code) DO UPDATE "
            "SET enabled = EXCLUDED.enabled, locale = EXCLUDED.locale, "
            "timezone = EXCLUDED.timezone, quiet_from = EXCLUDED.quiet_from, "
            "quiet_until = EXCLUDED.quiet_until, updated_at = now()",
            (company_id, subject_id, value["enabled"], value["locale"],
             value["timezone"], value["quiet_from"], value["quiet_until"]))
    return read_preference(connection, subject_id=subject_id)


def _delivery_key(company_id: str, subject_id: str, template: str,
                  business_key: str) -> str:
    return hashlib.sha256(
        f"v1|{company_id}|{subject_id}|{template}|{business_key}|email".encode("utf-8")
    ).hexdigest()


def _safe_context(period: dict[str, Any], company_id: str) -> dict[str, str]:
    # No nombres de fuente, importes, cuentas, documentos ni identificadores
    # fiscales. Fechas y ruta interna son suficientes para el recordatorio.
    return {
        "period_label": f"{period['period_start']} / {period['period_end']}",
        "due_on": str(period["due_on"]),
        "action_url": f"/recordatorios?empresa={company_id}",
    }


def sync_reminders(connection: psycopg.Connection, *, company_id: str,
                   subject_id: str, evaluated_at: dt.datetime) -> dict[str, int]:
    preference = read_preference(connection, subject_id=subject_id)
    cursor: str | None = None
    created = replayed = suppressed = 0
    while True:
        page = operations.list_operational_periods(
            connection, evaluated_at=evaluated_at, subject_id=subject_id,
            status="attention", limit=operations.MAX_LIMIT, cursor=cursor)
        for period in page["items"]:
            template = STATE_TEMPLATE.get(period["reminder_state"])
            if (template is None or not period["responsible_eligible"]
                    or period["responsible_subject_id"] != subject_id):
                continue
            business_key = str(period["expectation_id"])
            context = _safe_context(period, company_id)
            with connection.cursor() as db_cursor:
                db_cursor.execute(
                    "INSERT INTO fincilia.notification_intent "
                    "(company_id, subject_id, template_code, business_key, render_context) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb) "
                    "ON CONFLICT (company_id, subject_id, template_code, business_key) "
                    "DO NOTHING RETURNING intent_id::text",
                    (company_id, subject_id, template, business_key,
                     json.dumps(context, sort_keys=True)))
                row = db_cursor.fetchone()
                if row is None:
                    replayed += 1
                    continue
                reason = ("adapter_unconfigured" if preference["enabled"]
                          else "user_opt_out")
                db_cursor.execute(
                    "INSERT INTO fincilia.notification_delivery "
                    "(company_id, subject_id, intent_id, channel, status, "
                    "suppression_reason, idempotency_key) "
                    "VALUES (%s, %s, %s, 'email', 'suppressed', %s, %s)",
                    (company_id, subject_id, row[0], reason,
                     _delivery_key(company_id, subject_id, template, business_key)))
            created += 1
            suppressed += 1
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    return {"created": created, "replayed": replayed, "suppressed": suppressed}


def list_deliveries(connection: psycopg.Connection, *, subject_id: str,
                    limit: int = 50) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100:
        raise NotificationError(
            "notification-limit-invalid", "limit must be between 1 and 100")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT delivery.delivery_id::text, intent.template_code, "
            "intent.render_context, delivery.status, delivery.suppression_reason, "
            "delivery.attempt_count, delivery.created_at, delivery.updated_at "
            "FROM fincilia.notification_delivery delivery "
            "JOIN fincilia.notification_intent intent "
            "ON intent.intent_id = delivery.intent_id "
            "AND intent.company_id = delivery.company_id "
            "WHERE delivery.subject_id = %s "
            "ORDER BY delivery.created_at DESC, delivery.delivery_id DESC LIMIT %s",
            (subject_id, limit))
        rows = cursor.fetchall()
    return [{
        "delivery_id": str(row[0]), "template_code": row[1],
        "context": row[2], "status": row[3], "suppression_reason": row[4],
        "attempt_count": row[5], "created_at": row[6].isoformat(),
        "updated_at": row[7].isoformat(),
    } for row in rows]


class NotificationAdapter:
    def deliver(self, *_args, **_kwargs):
        raise NotImplementedError


class DisabledNotificationAdapter(NotificationAdapter):
    def deliver(self, *_args, **_kwargs):
        raise NotificationError(
            "notification-adapter-disabled",
            "external delivery is disabled until provider configuration is approved")
