"""Cadencia de carga del extracto y recordatorio en la app (FNC-SMB-006).

La pyme responde «¿Cada cuanto subes tu extracto?» (semanal, quincenal o
mensual). La cadencia vive en un historial append-only; solo el owner la cambia
y PostgreSQL lo vuelve a exigir. El recordatorio usa el mecanismo existente de
`notification_intent` + `notification_delivery`, pero **solo dentro de la app**:
la entrega por correo nace `suppressed` con motivo `in_app_only`.

Gancho ADR-037: `EXTERNAL_CHANNELS` esta vacio a proposito. Cuando un adaptador
externo se apruebe, este modulo es el unico sitio donde decidir si esta
plantilla puede encolarse; una migracion nueva tendra que relajar la guarda
`ck_notification_delivery_in_app_only`. Hoy no se envia correo ni WhatsApp.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from . import repository


CADENCES = ("weekly", "biweekly", "monthly")
CADENCE_LABELS = {"weekly": "semanal", "biweekly": "quincenal", "monthly": "mensual"}
# Dias antes del vencimiento del periodo en que aparece el recordatorio. Es una
# hipotesis de producto; se calibra con uso real despues de DRG-01.
REMINDER_LEAD_DAYS = {"weekly": 2, "biweekly": 4, "monthly": 7}
# Lunes fijo que ancla los bloques quincenales: determinista y sin estado.
BIWEEKLY_ANCHOR = dt.date(2024, 1, 1)
TEMPLATE = "statement_upload_due"
# Gancho ADR-037: ningun canal externo esta autorizado para esta plantilla.
EXTERNAL_CHANNELS: tuple[str, ...] = ()
HISTORY_LIMIT = 10


@dataclass(frozen=True)
class UploadScheduleError(Exception):
    code: str
    detail: str
    status: int = 422


@dataclass(frozen=True)
class UploadPeriod:
    start: dt.date
    end: dt.date

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()} / {self.end.isoformat()}"


def period_for(cadence: str, today: dt.date) -> UploadPeriod:
    """Periodo vigente que contiene `today`, ambos extremos incluidos."""
    if cadence == "weekly":
        start = today - dt.timedelta(days=today.weekday())
        return UploadPeriod(start, start + dt.timedelta(days=6))
    if cadence == "biweekly":
        offset = (today - BIWEEKLY_ANCHOR).days % 14
        start = today - dt.timedelta(days=offset)
        return UploadPeriod(start, start + dt.timedelta(days=13))
    if cadence == "monthly":
        start = today.replace(day=1)
        following = (start + dt.timedelta(days=32)).replace(day=1)
        return UploadPeriod(start, following - dt.timedelta(days=1))
    raise UploadScheduleError("upload-cadence-invalid",
                              "cadence must be weekly, biweekly or monthly")


def reminder_state(cadence: str, today: dt.date, *, uploaded: bool) -> str:
    """`received`, `upcoming` o `due_soon`. Nunca afirma que algo cuadra."""
    if uploaded:
        return "received"
    period = period_for(cadence, today)
    days_left = (period.end - today).days
    return "due_soon" if days_left <= REMINDER_LEAD_DAYS[cadence] else "upcoming"


def _today(local_now: dt.datetime | None) -> dt.date:
    if local_now is None:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Bogota")).date()
    return local_now.date()


def _history(connection: psycopg.Connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT h.change_id, h.version, h.cadence, h.changed_by, s.display_name, "
            "       h.changed_at "
            "FROM fincilia.company_upload_schedule_change h "
            "JOIN fincilia.subject s ON s.subject_id = h.changed_by "
            "ORDER BY h.version DESC LIMIT %s", (HISTORY_LIMIT,))
        rows = cursor.fetchall()
    return [{"change_id": str(row[0]), "version": int(row[1]), "cadence": row[2],
             "changed_by": str(row[3]), "changed_by_name": row[4],
             "changed_at": row[5].isoformat()} for row in rows]


def _uploaded_in(connection: psycopg.Connection, period: UploadPeriod) -> bool:
    # Fechas de recepcion, no de movimientos: el recordatorio pregunta si se
    # subio algo en el periodo, no si el periodo quedo completo o conciliado.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM fincilia.source_artifact "
            "WHERE uploaded_at >= %s::date "
            "  AND uploaded_at < (%s::date + 1))",
            (period.start, period.end))
        return bool(cursor.fetchone()[0])


def read_schedule(connection: psycopg.Connection, *, company_id: str,
                  roles: tuple[str, ...] | list[str],
                  local_now: dt.datetime | None = None) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (company_id,))
        cadence = cursor.fetchone()[0]
    today = _today(local_now)
    current = None
    if cadence in CADENCES:
        period = period_for(cadence, today)
        uploaded = _uploaded_in(connection, period)
        current = {
            "period_start": period.start.isoformat(),
            "period_end": period.end.isoformat(),
            "due_on": period.end.isoformat(),
            "uploaded": uploaded,
            "reminder_state": reminder_state(cadence, today, uploaded=uploaded),
        }
    return {
        "company_id": company_id,
        "cadence": cadence if cadence in CADENCES else None,
        "can_change": "owner" in roles,
        "current_period": current,
        "history": _history(connection),
        "channels": {"in_app": True, "external": list(EXTERNAL_CHANNELS)},
        "notice": "in_app_only; no_email_or_whatsapp_sent; adr_037_adapters_disabled",
        "changed": False,
    }


def change_schedule(connection: psycopg.Connection, *, company_id: str,
                    actor_id: str, roles: tuple[str, ...] | list[str],
                    cadence: str, local_now: dt.datetime | None = None
                    ) -> dict[str, Any]:
    """Registra la cadencia. Solo el owner; la base lo vuelve a exigir."""
    if cadence not in CADENCES:
        raise UploadScheduleError("upload-cadence-invalid",
                                  "cadence must be weekly, biweekly or monthly")
    if "owner" not in roles:
        raise UploadScheduleError(
            "upload-schedule-owner-required",
            "only the company owner can change the upload schedule", status=403)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 39006))", (company_id,))
        cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (company_id,))
        previous = cursor.fetchone()[0]
        if previous == cadence:
            return read_schedule(connection, company_id=company_id, roles=roles,
                                 local_now=local_now)
        cursor.execute(
            "SELECT COALESCE(max(version), 0) + 1 "
            "FROM fincilia.company_upload_schedule_change WHERE company_id = %s",
            (company_id,))
        version = int(cursor.fetchone()[0])
    change_id = str(uuid.uuid4())
    try:
        with connection.transaction():
            audit_event_id = repository.record_audit(
                connection, subject_id=actor_id, company_id=company_id,
                action="company.upload_schedule.change", resource_kind="company",
                resource_ref=company_id, outcome="allowed",
                detail={"from": previous, "to": cadence, "version": version,
                        "change_id": change_id})
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.company_upload_schedule_change "
                    "(change_id, company_id, version, cadence, changed_by, "
                    " audit_event_id) VALUES (%s, %s, %s, %s, %s, %s)",
                    (change_id, company_id, version, cadence, actor_id,
                     audit_event_id))
    except psycopg.errors.InsufficientPrivilege:
        raise UploadScheduleError(
            "upload-schedule-owner-required",
            "only the company owner can change the upload schedule",
            status=403) from None
    return {**read_schedule(connection, company_id=company_id, roles=roles,
                            local_now=local_now), "changed": True}


def _delivery_key(company_id: str, subject_id: str, business_key: str) -> str:
    return hashlib.sha256(
        f"v1|{company_id}|{subject_id}|{TEMPLATE}|{business_key}|email".encode("utf-8")
    ).hexdigest()


def sync_upload_reminder(connection: psycopg.Connection, *, company_id: str,
                         subject_id: str, local_now: dt.datetime | None = None
                         ) -> dict[str, int]:
    """Crea, una vez por periodo y persona, el recordatorio en la app.

    Idempotente: la clave de negocio es la cadencia y el inicio del periodo.
    Sin cadencia, con carga en el periodo o fuera de la ventana: no crea nada.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT fincilia.company_upload_cadence(%s)", (company_id,))
        cadence = cursor.fetchone()[0]
    if cadence not in CADENCES:
        return {"created": 0, "replayed": 0, "suppressed": 0}
    today = _today(local_now)
    period = period_for(cadence, today)
    if reminder_state(cadence, today,
                      uploaded=_uploaded_in(connection, period)) != "due_soon":
        return {"created": 0, "replayed": 0, "suppressed": 0}
    business_key = f"upload:{cadence}:{period.start.isoformat()}:{company_id}"
    context = {"period_label": period.label, "due_on": period.end.isoformat(),
               "action_url": f"/recordatorios?empresa={company_id}"}
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.notification_intent "
            "(company_id, subject_id, template_code, business_key, render_context) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (company_id, subject_id, template_code, business_key) "
            "DO NOTHING RETURNING intent_id::text",
            (company_id, subject_id, TEMPLATE, business_key,
             json.dumps(context, sort_keys=True)))
        row = cursor.fetchone()
        if row is None:
            return {"created": 0, "replayed": 1, "suppressed": 0}
        # Gancho ADR-037: con EXTERNAL_CHANNELS vacio, siempre `in_app_only`.
        cursor.execute(
            "INSERT INTO fincilia.notification_delivery "
            "(company_id, subject_id, intent_id, channel, status, "
            " suppression_reason, idempotency_key, in_app_only) "
            "VALUES (%s, %s, %s, 'email', 'suppressed', 'in_app_only', %s, true)",
            (company_id, subject_id, row[0],
             _delivery_key(company_id, subject_id, business_key)))
    return {"created": 1, "replayed": 0, "suppressed": 1}
