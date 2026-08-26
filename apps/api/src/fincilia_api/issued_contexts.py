"""Emision y revalidacion de autorizacion que sobrevive a una peticion.

No es una sesion ni un bearer token. Es un recibo company-scoped para jobs,
exports, enlaces o schedules. Emitirlo exige un ``TenantContext`` ya resuelto
server-side; usarlo vuelve a comprobar la autoridad viva en PostgreSQL.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg

from fincilia_contracts.tenancy import AuthorizationError, TenantContext

from . import repository

PURPOSE_PERMISSIONS = {
    "processing_job": "document.upload",
    "dataset_export": "dataset.export",
    "report_export": "report.export",
    "shared_link": "document.read",
    "scheduled_capability": "company.read",
}
RESOURCE_KIND = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
REASON_CODES = frozenset({
    "access_removed", "engagement_changed", "security_response",
    "resource_retired", "superseded",
})
MIN_KEY_LENGTH = 32
MIN_IDEMPOTENCY_LENGTH = 16
MAX_IDEMPOTENCY_LENGTH = 128
MAX_LIFETIME = timedelta(days=30)


class IssuedContextError(ValueError):
    """La capability no puede emitirse o usarse; nunca incluye el recurso."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class IssuedContext:
    context_id: str
    company_id: str
    subject_id: str
    firm_id: str
    engagement_id: str
    purpose_code: str
    resource_kind: str
    authorization_version: int
    issued_at: datetime
    expires_at: datetime


def _digest(value: str, *, key: str, domain: str, company_id: str) -> str:
    if not isinstance(key, str) or len(key) < MIN_KEY_LENGTH:
        raise IssuedContextError(
            "invalid-key", "authorization context HMAC key is not configured")
    material = "\x1f".join((domain, company_id, value))
    return hmac.new(key.encode(), material.encode(), hashlib.sha256).hexdigest()


def _validate_uuid(value: str, *, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise IssuedContextError("invalid-identifier", f"{field} is not a UUID") from None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise IssuedContextError("invalid-expiry", "expires_at must include a timezone")
    return value.astimezone(timezone.utc)


def _one(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip([column.name for column in cursor.description], row))


def _as_context(row: dict[str, Any]) -> IssuedContext:
    return IssuedContext(
        context_id=str(row["context_id"]), company_id=str(row["company_id"]),
        subject_id=str(row["subject_id"]), firm_id=str(row["firm_id"]),
        engagement_id=str(row["engagement_id"]),
        purpose_code=row["purpose_code"], resource_kind=row["resource_kind"],
        authorization_version=int(row["authorization_version"]),
        issued_at=row["issued_at"], expires_at=row["expires_at"],
    )


def _lock_current_authority(connection: psycopg.Connection,
                            tenant: TenantContext) -> None:
    """Fija la version hasta el commit y rechaza una fotografia ya obsoleta.

    Sin el lock, una revocacion concurrente podria confirmar entre la ultima
    comprobacion y el INSERT. El contexto quedaria inerte al primer uso, pero la
    auditoria afirmaria que se emitio bajo autoridad viva. Bloquear la fila de
    version hace que uno de los dos ordenes sea cierto y completo.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT auth_version.version FROM fincilia.authorization_version "
            "auth_version JOIN fincilia.subject subject_row "
            "  ON subject_row.subject_id = %s "
            "JOIN fincilia.engagement engagement "
            "  ON engagement.company_id = auth_version.company_id "
            " AND engagement.engagement_id = %s AND engagement.firm_id = %s "
            "JOIN fincilia.membership membership "
            "  ON membership.subject_id = %s AND membership.firm_id = %s "
            "WHERE auth_version.company_id = %s AND auth_version.version = %s "
            "  AND subject_row.status = 'active' "
            "  AND engagement.status = 'active' "
            "  AND (engagement.valid_to IS NULL "
            "       OR engagement.valid_to >= CURRENT_DATE) "
            "  AND membership.status = 'active' "
            "  AND EXISTS (SELECT 1 FROM fincilia.company_grant grant_row "
            "              WHERE grant_row.company_id = auth_version.company_id "
            "                AND grant_row.subject_id = %s "
            "                AND grant_row.revoked_at IS NULL) "
            "FOR SHARE OF auth_version",
            (tenant.subject_id, tenant.engagement_id, tenant.firm_id,
             tenant.subject_id, tenant.firm_id, tenant.company_id,
             tenant.authorization_version, tenant.subject_id))
        if cursor.fetchone() is None:
            raise IssuedContextError(
                "stale-authorization", "current authorization is no longer valid")


def issue_context(connection: psycopg.Connection, *, tenant: TenantContext,
                  purpose_code: str, resource_kind: str, resource_ref: str,
                  idempotency_key: str, expires_at: datetime,
                  hmac_key: str) -> IssuedContext:
    """Emite o reproduce exactamente una capability, dentro de la transaccion."""
    permission = PURPOSE_PERMISSIONS.get(purpose_code)
    if permission is None:
        raise IssuedContextError("unknown-purpose", "purpose is not allowlisted")
    try:
        tenant.require(permission)
    except AuthorizationError:
        raise IssuedContextError(
            "permission-denied", "the current authorization cannot issue this purpose") from None
    if not RESOURCE_KIND.fullmatch(resource_kind or ""):
        raise IssuedContextError("invalid-resource-kind", "resource kind is invalid")
    if not isinstance(resource_ref, str) or not resource_ref:
        raise IssuedContextError("invalid-resource", "resource reference is required")
    if not isinstance(idempotency_key, str) or not (
            MIN_IDEMPOTENCY_LENGTH <= len(idempotency_key) <= MAX_IDEMPOTENCY_LENGTH):
        raise IssuedContextError(
            "invalid-idempotency-key", "idempotency key length is invalid")

    expiry = _aware_utc(expires_at)
    now = datetime.now(timezone.utc)
    if expiry <= now or expiry > now + MAX_LIFETIME:
        raise IssuedContextError(
            "invalid-expiry", "expiry must be in the future and at most 30 days away")

    _lock_current_authority(connection, tenant)

    resource_digest = _digest(
        resource_ref, key=hmac_key, domain="resource-ref-v1",
        company_id=tenant.company_id)
    idempotency_digest = _digest(
        idempotency_key, key=hmac_key, domain="idempotency-v1",
        company_id=tenant.company_id)
    issuance_material = json.dumps({
        "authorization_version": tenant.authorization_version,
        "company_id": tenant.company_id,
        "engagement_id": tenant.engagement_id,
        "expires_at": expiry.isoformat(),
        "firm_id": tenant.firm_id,
        "purpose_code": purpose_code,
        "resource_kind": resource_kind,
        "resource_ref_digest": resource_digest,
        "subject_id": tenant.subject_id,
    }, separators=(",", ":"), sort_keys=True)
    issuance_digest = _digest(
        issuance_material, key=hmac_key, domain="issuance-v1",
        company_id=tenant.company_id)
    context_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.issued_authorization_context ("
            "context_id, company_id, subject_id, firm_id, engagement_id, "
            "purpose_code, resource_kind, resource_ref_digest, "
            "authorization_version, expires_at, idempotency_key_digest, "
            "issuance_digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s) ON CONFLICT (company_id, idempotency_key_digest) "
            "DO NOTHING RETURNING context_id, company_id, subject_id, firm_id, "
            "engagement_id, purpose_code, resource_kind, authorization_version, "
            "issued_at, expires_at",
            (context_id, tenant.company_id, tenant.subject_id, tenant.firm_id,
             tenant.engagement_id, purpose_code, resource_kind, resource_digest,
             tenant.authorization_version, expiry, idempotency_digest,
             issuance_digest))
        row = _one(cursor)
        replayed = row is None
        if replayed:
            cursor.execute(
                "SELECT context_id, company_id, subject_id, firm_id, engagement_id, "
                "purpose_code, resource_kind, authorization_version, issued_at, "
                "expires_at, issuance_digest FROM "
                "fincilia.issued_authorization_context "
                "WHERE company_id = %s AND idempotency_key_digest = %s",
                (tenant.company_id, idempotency_digest))
            row = _one(cursor)
            if row is None or not hmac.compare_digest(
                    str(row.get("issuance_digest", "")), issuance_digest):
                raise IssuedContextError(
                    "idempotency-conflict", "idempotency key belongs to another request")

    context = _as_context(row)
    repository.record_audit(
        connection, subject_id=tenant.subject_id, company_id=tenant.company_id,
        action="authorization.context.issue", resource_kind="authorization_context",
        resource_ref=context.context_id, outcome="allowed",
        detail={"purpose_code": purpose_code, "replayed": replayed})
    return context


def revalidate_context(connection: psycopg.Connection, *, tenant: TenantContext,
                       context_id: str, purpose_code: str,
                       resource_kind: str, resource_ref: str,
                       hmac_key: str) -> IssuedContext | None:
    """Devuelve el contexto solo si toda la ruta sigue viva en este instante."""
    identifier = _validate_uuid(context_id, field="context_id")
    if purpose_code not in PURPOSE_PERMISSIONS or not RESOURCE_KIND.fullmatch(
            resource_kind or "") or not resource_ref:
        return None
    expected_digest = _digest(
        resource_ref, key=hmac_key, domain="resource-ref-v1",
        company_id=tenant.company_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT issued.context_id, issued.company_id, issued.subject_id, "
            "issued.firm_id, issued.engagement_id, issued.purpose_code, "
            "issued.resource_kind, issued.authorization_version, issued.issued_at, "
            "issued.expires_at FROM fincilia.issued_authorization_context issued "
            "JOIN fincilia.subject subject_row "
            "  ON subject_row.subject_id = issued.subject_id "
            "JOIN fincilia.engagement engagement "
            "  ON engagement.engagement_id = issued.engagement_id "
            " AND engagement.company_id = issued.company_id "
            " AND engagement.firm_id = issued.firm_id "
            "JOIN fincilia.membership membership "
            "  ON membership.subject_id = issued.subject_id "
            " AND membership.firm_id = issued.firm_id "
            "JOIN fincilia.authorization_version version "
            "  ON version.company_id = issued.company_id "
            " AND version.version = issued.authorization_version "
            "WHERE issued.context_id = %s AND issued.company_id = %s "
            "  AND issued.subject_id = %s AND issued.firm_id = %s "
            "  AND issued.engagement_id = %s AND issued.purpose_code = %s "
            "  AND issued.resource_kind = %s AND issued.resource_ref_digest = %s "
            "  AND issued.expires_at > now() AND subject_row.status = 'active' "
            "  AND engagement.status = 'active' "
            "  AND (engagement.valid_to IS NULL OR engagement.valid_to >= CURRENT_DATE) "
            "  AND membership.status = 'active' "
            "  AND EXISTS (SELECT 1 FROM fincilia.company_grant grant_row "
            "              WHERE grant_row.company_id = issued.company_id "
            "                AND grant_row.subject_id = issued.subject_id "
            "                AND grant_row.revoked_at IS NULL) "
            "  AND NOT EXISTS (SELECT 1 "
            "                  FROM fincilia.issued_authorization_revocation revoked "
            "                  WHERE revoked.company_id = issued.company_id "
            "                    AND revoked.context_id = issued.context_id)",
            (identifier, tenant.company_id, tenant.subject_id, tenant.firm_id,
             tenant.engagement_id, purpose_code, resource_kind, expected_digest))
        row = _one(cursor)
    if row is None:
        return None
    context = _as_context(row)
    repository.record_audit(
        connection, subject_id=tenant.subject_id, company_id=tenant.company_id,
        action="authorization.context.use", resource_kind="authorization_context",
        resource_ref=context.context_id, outcome="allowed",
        detail={"purpose_code": purpose_code})
    return context


def revoke_context(connection: psycopg.Connection, *, tenant: TenantContext,
                   context_id: str, reason_code: str) -> bool:
    """Agrega un tombstone. Repetir la misma revocacion no reescribe nada."""
    identifier = _validate_uuid(context_id, field="context_id")
    if reason_code not in REASON_CODES:
        raise IssuedContextError("invalid-reason", "revocation reason is not allowlisted")
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.issued_authorization_revocation "
            "(company_id, context_id, revoked_by, reason_code) "
            "SELECT company_id, context_id, %s, %s "
            "FROM fincilia.issued_authorization_context "
            "WHERE context_id = %s AND company_id = %s "
            "ON CONFLICT (company_id, context_id) DO NOTHING",
            (tenant.subject_id, reason_code, identifier, tenant.company_id))
        changed = cursor.rowcount == 1
    repository.record_audit(
        connection, subject_id=tenant.subject_id, company_id=tenant.company_id,
        action="authorization.context.revoke", resource_kind="authorization_context",
        resource_ref=identifier, outcome="allowed",
        detail={"reason_code": reason_code, "replayed": not changed})
    return changed
