"""Planes, suscripciones y uso sin conceder autorización financiera.

El catálogo está versionado y no contiene precio mientras la decisión comercial
esté pendiente. La selección disponible en UAT es una evaluación sin cobro; no
se presenta como trial, suscripción pagada ni checkout.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Any

import psycopg


PLAN_CODES = frozenset({"starter", "business", "accountant"})


@dataclass(frozen=True)
class BillingError(Exception):
    code: str
    detail: str
    status: int = 422


def _plan(row: tuple) -> dict[str, Any]:
    return {
        "plan_version_id": str(row[0]), "plan_code": row[1],
        "version": int(row[2]), "display_name": row[3],
        "audience_code": row[4], "catalog_state": row[5],
        "features": {
            "multi_company_portfolio": row[6],
            "team_review_workflows": row[7],
            "advanced_quality_controls": row[8],
            "foundational_security": row[9],
            "basic_data_export": row[10],
        },
        "limits": {
            "companies": row[11], "active_members": row[12],
            "monthly_documents": row[13], "storage_bytes": row[14],
        },
        "commercial": {
            "configured": row[15] is not None,
            "currency_code": row[15], "unit_amount_minor": row[16],
            "trial_days": row[17],
        },
    }


PLAN_COLUMNS = (
    "plan_version_id, plan_code, version, display_name, audience_code, "
    "catalog_state, multi_company_portfolio, team_review_workflows, "
    "advanced_quality_controls, foundational_security, basic_data_export, "
    "max_companies, max_active_members, max_monthly_documents, "
    "max_storage_bytes, currency_code, unit_amount_minor, trial_days"
)


def _plan_columns(alias: str) -> str:
    return ", ".join(f"{alias}.{column.strip()}" for column in PLAN_COLUMNS.split(","))


def list_plans(connection: psycopg.Connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {PLAN_COLUMNS} FROM fincilia.billing_plan_version "
            "WHERE catalog_state <> 'retired' "
            "ORDER BY CASE plan_code WHEN 'starter' THEN 1 "
            "WHEN 'business' THEN 2 ELSE 3 END, version DESC")
        return [_plan(row) for row in cursor.fetchall()]


def _assert_manager(connection: psycopg.Connection, *, firm_id: str,
                    subject_id: str) -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT firm_role FROM fincilia.membership "
                "WHERE firm_id = %s AND subject_id = %s AND status = 'active'",
                (firm_id, subject_id))
            row = cursor.fetchone()
    except psycopg.errors.InvalidTextRepresentation:
        raise BillingError("billing-forbidden", "firm is not manageable", 403) from None
    if row is None or row[0] not in {"owner", "firm_admin"}:
        raise BillingError("billing-forbidden", "firm is not manageable", 403)
    return str(row[0])


def _current_subscription(connection: psycopg.Connection,
                          firm_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subscription.subscription_id::text, subscription.status, "
            "subscription.sequence, subscription.source_code, "
            "subscription.started_at, subscription.trial_ends_at, "
            f"{_plan_columns('plan')} "
            "FROM fincilia.firm_subscription subscription "
            "JOIN fincilia.billing_plan_version plan "
            "ON plan.plan_version_id = subscription.plan_version_id "
            "WHERE subscription.firm_id = %s AND subscription.ended_at IS NULL",
            (firm_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "subscription_id": row[0], "status": row[1], "sequence": int(row[2]),
        "source_code": row[3], "started_at": row[4].isoformat(),
        "trial_ends_at": row[5].isoformat() if row[5] else None,
        "plan": _plan(row[6:]),
    }


def read_overview(connection: psycopg.Connection, *, firm_id: str,
                  subject_id: str) -> dict[str, Any]:
    role = _assert_manager(
        connection, firm_id=firm_id, subject_id=subject_id)
    now = dt.datetime.now(dt.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT configuration_state, provider_code, billing_country, "
            "tax_profile_state FROM fincilia.billing_account WHERE firm_id = %s",
            (firm_id,))
        account = cursor.fetchone()
        cursor.execute(
            "SELECT metric_code, COALESCE(sum(quantity), 0)::bigint "
            "FROM fincilia.firm_usage_event "
            "WHERE firm_id = %s AND observed_at >= %s "
            "GROUP BY metric_code ORDER BY metric_code",
            (firm_id, month_start))
        usage = {row[0]: int(row[1]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT event.event_code, event.reason_code, event.occurred_at, "
            "plan.plan_code FROM fincilia.subscription_event event "
            "JOIN fincilia.firm_subscription subscription "
            "ON subscription.subscription_id = event.subscription_id "
            "JOIN fincilia.billing_plan_version plan "
            "ON plan.plan_version_id = subscription.plan_version_id "
            "WHERE event.firm_id = %s "
            "ORDER BY event.occurred_at DESC, event.subscription_event_id DESC "
            "LIMIT 20", (firm_id,))
        history = [{
            "event_code": row[0], "reason_code": row[1],
            "occurred_at": row[2].isoformat(), "plan_code": row[3],
        } for row in cursor.fetchall()]
    return {
        "firm_id": firm_id, "manager_role": role,
        "subscription": _current_subscription(connection, firm_id),
        "billing_account": {
            "configuration_state": account[0] if account else "unconfigured",
            "provider_code": account[1] if account else None,
            "billing_country": account[2] if account else None,
            "tax_profile_state": account[3] if account else "unconfigured",
        },
        "usage": {
            "period_start": month_start.date().isoformat(),
            "documents_uploaded": usage.get("documents_uploaded", 0),
            "storage_bytes": usage.get("storage_bytes", 0),
            "meter_state": "observed_append_only",
        },
        "history": history,
        "payments_state": "disabled",
    }


def select_evaluation(connection: psycopg.Connection, *, firm_id: str,
                      subject_id: str, plan_code: str,
                      idempotency_key: str) -> dict[str, Any]:
    _assert_manager(connection, firm_id=firm_id, subject_id=subject_id)
    if plan_code not in PLAN_CODES:
        raise BillingError("billing-plan-invalid", "plan is not available")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                       (f"billing:{firm_id}",))
        cursor.execute(
            "SELECT subscription.plan_version_id, plan.plan_code "
            "FROM fincilia.firm_subscription subscription "
            "JOIN fincilia.billing_plan_version plan "
            "ON plan.plan_version_id = subscription.plan_version_id "
            "WHERE subscription.firm_id = %s "
            "AND subscription.idempotency_key = %s",
            (firm_id, idempotency_key))
        replay = cursor.fetchone()
        if replay is not None:
            if replay[1] != plan_code:
                raise BillingError(
                    "billing-idempotency-conflict",
                    "idempotency key was already used for another plan", 409)
            return {**read_overview(
                connection, firm_id=firm_id, subject_id=subject_id),
                "replayed": True}

        cursor.execute(
            f"SELECT {PLAN_COLUMNS} FROM fincilia.billing_plan_version "
            "WHERE plan_code = %s AND catalog_state = 'evaluation' "
            "ORDER BY version DESC LIMIT 1", (plan_code,))
        plan_row = cursor.fetchone()
        if plan_row is None:
            raise BillingError("billing-plan-unavailable", "plan is unavailable", 409)

        cursor.execute(
            "SELECT subscription_id, sequence FROM fincilia.firm_subscription "
            "WHERE firm_id = %s AND ended_at IS NULL FOR UPDATE", (firm_id,))
        current = cursor.fetchone()
        sequence = int(current[1]) + 1 if current else 1
        event_code = "evaluation_changed" if current else "evaluation_started"
        if current:
            cursor.execute(
                "UPDATE fincilia.firm_subscription SET status = 'superseded', "
                "ended_at = now() WHERE subscription_id = %s", (current[0],))
        cursor.execute(
            "INSERT INTO fincilia.billing_account (firm_id) VALUES (%s) "
            "ON CONFLICT (firm_id) DO NOTHING", (firm_id,))
        cursor.execute(
            "INSERT INTO fincilia.firm_subscription "
            "(firm_id, plan_version_id, status, source_code, sequence, "
            "activated_by, idempotency_key) "
            "VALUES (%s, %s, 'evaluation', 'self_service_evaluation', %s, %s, %s) "
            "RETURNING subscription_id",
            (firm_id, plan_row[0], sequence, subject_id, idempotency_key))
        subscription_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO fincilia.subscription_event "
            "(firm_id, subscription_id, actor_subject_id, event_code, reason_code) "
            "VALUES (%s, %s, %s, %s, 'uat_evaluation_selection')",
            (firm_id, subscription_id, subject_id, event_code))
    return {**read_overview(
        connection, firm_id=firm_id, subject_id=subject_id), "replayed": False}


def record_usage(connection: psycopg.Connection, *, firm_id: str,
                 company_id: str, subject_id: str, artifact_id: str,
                 byte_size: int) -> None:
    """Registra dos métricas del hecho creado, nunca de un replay."""
    for metric, quantity in (("documents_uploaded", 1), ("storage_bytes", byte_size)):
        key = hashlib.sha256(
            f"v1|{firm_id}|{company_id}|{artifact_id}|{metric}".encode("utf-8")
        ).hexdigest()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.firm_usage_event "
                "(firm_id, company_id, metric_code, quantity, idempotency_key, "
                "actor_subject_id) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (firm_id, metric_code, idempotency_key) DO NOTHING",
                (firm_id, company_id, metric, quantity, key, subject_id))


class DisabledPaymentPort:
    def checkout(self, *_args, **_kwargs):
        raise BillingError(
            "payments-disabled",
            "checkout is disabled until provider and commercial configuration are approved",
            503)
