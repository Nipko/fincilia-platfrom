"""Protocolo de arriendo del dispatcher.

El rol de runtime solo puede ejecutar estas funciones. No tiene SELECT ni
UPDATE directo sobre destinos, identidad, entregas o hechos financieros.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg


LEASE_SECONDS = 60


@dataclass(frozen=True)
class Claim:
    delivery_id: str
    company_id: str
    subject_id: str
    template_code: str
    render_context: dict[str, Any]
    locale: str
    idempotency_key: str
    encrypted_address: bytes
    address_ref: str
    kms_key_ref: str
    lease_token: str
    attempt_number: int


def claim_next(connection: psycopg.Connection, worker: str,
               lease_seconds: int = LEASE_SECONDS) -> Claim | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT delivery_id::text, company_id::text, subject_id::text, "
            "template_code, render_context, locale, idempotency_key, "
            "encrypted_address, address_ref, kms_key_ref, lease_token::text, "
            "attempt_number FROM fincilia.claim_notification_delivery(%s, %s)",
            (worker, lease_seconds),
        )
        row = cursor.fetchone()
    return Claim(*row) if row is not None else None


def finish(connection: psycopg.Connection, claim: Claim, *, outcome: str,
           provider_message_ref: str | None = None,
           reason_code: str | None = None) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.finish_notification_delivery(%s, %s, %s, %s, %s)",
            (claim.delivery_id, claim.lease_token, outcome,
             provider_message_ref, reason_code),
        )
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"


def arm(connection: psycopg.Connection, claim: Claim) -> str:
    """Persiste la frontera at-most-once justo antes de invocar al proveedor."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.arm_notification_delivery(%s, %s)",
            (claim.delivery_id, claim.lease_token),
        )
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"


def settle(connection: psycopg.Connection, claim: Claim, *, outcome: str,
           provider_message_ref: str | None = None,
           reason_code: str | None = None) -> str:
    """Resuelve un intento armado; si falla, la base conserva uncertain."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.settle_armed_notification_delivery("
            "%s, %s, %s, %s, %s)",
            (claim.delivery_id, claim.lease_token, outcome,
             provider_message_ref, reason_code),
        )
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"


def record_feedback(connection: psycopg.Connection, *, event_digest: str,
                    provider_message_ref: str, event_type: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.record_notification_feedback(%s, %s, %s)",
            (event_digest, provider_message_ref, event_type),
        )
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"
