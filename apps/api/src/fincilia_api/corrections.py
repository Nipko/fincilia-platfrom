"""Correcciones tipadas propuestas sobre una version inmutable del dataset.

La propuesta guarda el valor porque un revisor necesita verlo. El audit log y
el grafo no lo copian. Aprobarla tampoco actualiza el movimiento: FNC-CLN-002
la aplicara al crear una version nueva y su evidencia digest-only.
"""

from __future__ import annotations

import datetime as dt
import hmac
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from fincilia_contracts.errors import problem
from fincilia_contracts.release import digest_of

from . import repository
from .routes import principal_dependency
from .security import Principal, ProblemError, company_context, forbidden, require

router = APIRouter(prefix="/api/v1")

SUPPORTED_FIELDS = {
    "amount": "money_decimal",
    "currency": "currency_code",
    "direction": "enum:direction",
    "occurred_on": "local_date",
    "posted_on": "local_date",
    "value_date": "local_date",
    "accounting_date": "local_date",
}
REASON_CODES = frozenset({
    "source_correction", "bank_clarification", "accounting_adjustment",
    "date_correction", "classification_correction", "other_reviewed",
})
MONEY = re.compile(r"^[0-9]{1,26}(?:\.[0-9]{1,12})?$")


class CorrectionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class TypedValue:
    value_type: str
    canonical: str
    digest: str


def normalise_value(field: str, value: Any) -> TypedValue:
    """Cierra tipos antes de tocar la base; en particular, rechaza float."""
    value_type = SUPPORTED_FIELDS.get(field)
    if value_type is None:
        raise CorrectionError("correction-field-unsupported",
                              "this canonical field cannot be corrected here")
    if not isinstance(value, str):
        raise CorrectionError("correction-value-type",
                              "a correction value must be an exact string")
    candidate = value.strip()
    if value_type == "money_decimal":
        if not MONEY.fullmatch(candidate):
            raise CorrectionError("correction-value-invalid",
                                  "amount must be a positive decimal with at most 12 decimals")
        try:
            amount = Decimal(candidate)
        except InvalidOperation:
            raise CorrectionError("correction-value-invalid",
                                  "amount is not an exact decimal") from None
        if not amount.is_finite() or amount <= 0:
            raise CorrectionError("correction-value-invalid",
                                  "amount must be a positive finite decimal")
        canonical = f"{amount:.12f}"
    elif value_type == "currency_code":
        canonical = candidate.upper()
        if not re.fullmatch(r"[A-Z]{3}", canonical):
            raise CorrectionError("correction-value-invalid",
                                  "currency must contain exactly three letters")
    elif value_type == "enum:direction":
        canonical = candidate.lower()
        if canonical not in ("inflow", "outflow"):
            raise CorrectionError("correction-value-invalid",
                                  "direction must be inflow or outflow")
    else:
        try:
            canonical = dt.date.fromisoformat(candidate).isoformat()
        except ValueError:
            raise CorrectionError("correction-value-invalid",
                                  "date must be a valid ISO date") from None
    return TypedValue(value_type, canonical, digest_of(canonical))


def validate_reason(code: str, comment: str) -> tuple[str, str]:
    if code not in REASON_CODES:
        raise CorrectionError("correction-reason-invalid", "reason code is not allowed")
    bounded = comment.strip()
    if not bounded or len(bounded.encode("utf-8")) > 500:
        raise CorrectionError("correction-reason-invalid",
                              "reason comment must contain between 1 and 500 bytes")
    return code, bounded


def _target(connection: psycopg.Connection, *, dataset_id: str,
            movement_id: str, field: str) -> dict[str, Any] | None:
    if field not in SUPPORTED_FIELDS:
        raise CorrectionError("correction-field-unsupported",
                              "this canonical field cannot be corrected here")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.state, m.source_record_id, m.amount, m.currency_code, "
            "m.direction, m.occurred_on, m.posted_on, m.value_date, "
            "m.accounting_date, m.field_digests, d.engine_release_id, "
            "d.canonical_schema_version, d.mapping_version_id "
            "FROM fincilia.dataset_version d JOIN fincilia.canonical_movement m "
            "ON m.dataset_version_id = d.dataset_version_id "
            "WHERE d.dataset_version_id = %s AND m.movement_id = %s",
            (dataset_id, movement_id))
        row = cursor.fetchone()
    if row is None:
        return None
    values = {
        "amount": f"{row[2]:.12f}", "currency": row[3], "direction": row[4],
        "occurred_on": row[5].isoformat(),
        "posted_on": row[6].isoformat() if row[6] else None,
        "value_date": row[7].isoformat() if row[7] else None,
        "accounting_date": row[8].isoformat() if row[8] else None,
    }
    digests = row[9] or {}
    current = values[field]
    return {
        "state": row[0], "source_record_id": str(row[1]), "current": current,
        "current_digest": digests.get(field, digest_of(current)),
        "engine_release_id": str(row[10]), "canonical_schema_version": row[11],
        "mapping_version_id": str(row[12]),
    }


def correction_targets(connection: psycopg.Connection, *, dataset_id: str,
                       movement_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field, value_type in SUPPORTED_FIELDS.items():
        target = _target(connection, dataset_id=dataset_id,
                         movement_id=movement_id, field=field)
        if target is None:
            return []
        result.append({"field": field, "value_type": value_type,
                       "current_value": target["current"],
                       "expected_base_digest": target["current_digest"]})
    return result


def propose(connection: psycopg.Connection, *, company_id: str, dataset_id: str,
            movement_id: str, field: str, expected_base_digest: str,
            new_value: Any, reason_code: str, reason_comment: str,
            subject_id: str, authorization_version: int) -> dict[str, Any]:
    typed = normalise_value(field, new_value)
    reason_code, reason_comment = validate_reason(reason_code, reason_comment)
    target = _target(connection, dataset_id=dataset_id,
                     movement_id=movement_id, field=field)
    if target is None:
        raise CorrectionError("correction-target-unknown", "correction target is unavailable")
    if target["state"] != "validated":
        raise CorrectionError("correction-dataset-state",
                              "only a validated dataset accepts correction proposals")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_base_digest or ""):
        raise CorrectionError("correction-base-invalid", "base digest is invalid")
    if not hmac.compare_digest(target["current_digest"], expected_base_digest):
        raise CorrectionError("correction-base-stale",
                              "the field changed; reload before proposing a correction")
    if typed.canonical == target["current"]:
        raise CorrectionError("correction-no-op", "the proposed value equals the current value")

    lock_key = f"{company_id}:{dataset_id}:{movement_id}:{field}"
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
        cursor.execute(
            "SELECT o.overlay_id, o.sequence, r.decision "
            "FROM fincilia.field_overlay o LEFT JOIN fincilia.field_overlay_review r "
            "ON r.overlay_id = o.overlay_id WHERE o.dataset_version_id = %s "
            "AND o.movement_id = %s AND o.target_field = %s "
            "ORDER BY o.sequence DESC LIMIT 1", (dataset_id, movement_id, field))
        latest = cursor.fetchone()
        if latest is not None and latest[2] != "rejected":
            raise CorrectionError("correction-already-active",
                                  "this field already has a pending or approved proposal")
        sequence = 1 if latest is None else int(latest[1]) + 1
        supersedes = None if latest is None else str(latest[0])
        cursor.execute(
            "INSERT INTO fincilia.field_overlay (company_id, dataset_version_id, "
            "movement_id, source_record_id, target_field, expected_base_digest, "
            "value_type, proposed_value, proposed_value_digest, reason_code, "
            "reason_comment, sequence, supersedes_overlay_id, created_by, "
            "authorization_version, engine_release_id, canonical_schema_version, "
            "mapping_version_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING overlay_id, created_at",
            (company_id, dataset_id, movement_id, target["source_record_id"], field,
             expected_base_digest, typed.value_type, typed.canonical, typed.digest,
             reason_code, reason_comment, sequence, supersedes, subject_id,
             authorization_version, target["engine_release_id"],
             target["canonical_schema_version"], target["mapping_version_id"]))
        overlay_id, created_at = cursor.fetchone()
    return {"overlay_id": str(overlay_id), "dataset_version_id": dataset_id,
            "movement_id": movement_id, "field": field,
            "current_value": target["current"], "proposed_value": typed.canonical,
            "value_type": typed.value_type, "reason_code": reason_code,
            "reason_comment": reason_comment, "sequence": sequence,
            "status": "pending_review", "created_by": subject_id,
            "created_at": created_at.isoformat(), "applied": False}


def list_proposals(connection: psycopg.Connection, *, dataset_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT o.overlay_id, o.movement_id, o.target_field, o.value_type, "
            "o.proposed_value, o.reason_code, o.reason_comment, o.sequence, "
            "o.created_by, a.display_name, o.created_at, r.decision, r.reviewer_id, "
            "rv.display_name, r.rationale, r.reviewed_at "
            "FROM fincilia.field_overlay o "
            "JOIN fincilia.subject a ON a.subject_id = o.created_by "
            "LEFT JOIN fincilia.field_overlay_review r ON r.overlay_id = o.overlay_id "
            "LEFT JOIN fincilia.subject rv ON rv.subject_id = r.reviewer_id "
            "WHERE o.dataset_version_id = %s ORDER BY o.created_at, o.overlay_id",
            (dataset_id,))
        rows = cursor.fetchall()
    return [{"overlay_id": str(row[0]), "dataset_version_id": dataset_id,
             "movement_id": str(row[1]), "field": row[2], "value_type": row[3],
             "proposed_value": row[4], "reason_code": row[5],
             "reason_comment": row[6], "sequence": row[7],
             "created_by": str(row[8]), "author_name": row[9],
             "created_at": row[10].isoformat(),
             "status": row[11] or "pending_review", "applied": False,
             "reviewer_id": str(row[12]) if row[12] else None,
             "reviewer_name": row[13], "review_rationale": row[14],
             "reviewed_at": row[15].isoformat() if row[15] else None}
            for row in rows]


def review(connection: psycopg.Connection, *, overlay_id: str, decision: str,
           rationale: str, reviewer_id: str) -> dict[str, Any]:
    if decision not in ("approved", "rejected"):
        raise CorrectionError("correction-review-invalid", "decision is not allowed")
    rationale = rationale.strip()
    if not rationale or len(rationale.encode("utf-8")) > 500:
        raise CorrectionError("correction-review-invalid",
                              "rationale must contain between 1 and 500 bytes")
    with connection.cursor() as cursor:
        # `FOR UPDATE` exige privilegio UPDATE aunque no se cambie la propuesta.
        # El runtime no lo tiene a propósito: un overlay es append-only. Este
        # lock serializa las revisiones sin ampliar privilegios sobre la tabla.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))",
            (f"field-overlay-review:{overlay_id}",))
        cursor.execute(
            "SELECT o.company_id, o.dataset_version_id, o.created_by, r.review_id "
            "FROM fincilia.field_overlay o LEFT JOIN fincilia.field_overlay_review r "
            "ON r.overlay_id = o.overlay_id WHERE o.overlay_id = %s",
            (overlay_id,))
        row = cursor.fetchone()
        if row is None:
            raise CorrectionError("correction-unknown", "correction is unavailable")
        if str(row[2]) == reviewer_id:
            raise CorrectionError("segregation-of-duties",
                                  "the author cannot review their own correction")
        if row[3] is not None:
            raise CorrectionError("correction-already-reviewed",
                                  "this correction already has a review")
        cursor.execute(
            "INSERT INTO fincilia.field_overlay_review (company_id, overlay_id, "
            "decision, reviewer_id, rationale) VALUES (%s, %s, %s, %s, %s) "
            "RETURNING review_id, reviewed_at",
            (str(row[0]), overlay_id, decision, reviewer_id, rationale))
        review_id, reviewed_at = cursor.fetchone()
    return {"review_id": str(review_id), "overlay_id": overlay_id,
            "dataset_version_id": str(row[1]), "decision": decision,
            "reviewer_id": reviewer_id, "rationale": rationale,
            "reviewed_at": reviewed_at.isoformat(), "applied": False}


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movement_id: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=32)
    expected_base_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    new_value: str = Field(min_length=1, max_length=128)
    reason_code: str = Field(min_length=1, max_length=64)
    reason_comment: str = Field(min_length=1, max_length=500)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    rationale: str = Field(min_length=1, max_length=500)


def _problem(error: CorrectionError, title: str) -> ProblemError:
    if error.code in ("correction-target-unknown", "correction-unknown"):
        return forbidden()
    conflict = {"correction-base-stale", "correction-no-op",
                "correction-already-active", "segregation-of-duties",
                "correction-already-reviewed", "correction-dataset-state"}
    return ProblemError(problem(error.code, title, 409 if error.code in conflict else 422,
                                error.detail))


@router.get("/companies/{company_id}/datasets/{dataset_id}/corrections",
            tags=["corrections"])
def get_corrections(request: Request, company_id: str, dataset_id: str,
                    principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    with request.app.state.database.session(company_id=context.company_id,
                                            subject_id=principal.subject_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM fincilia.dataset_version WHERE dataset_version_id = %s",
                           (dataset_id,))
            if cursor.fetchone() is None:
                raise forbidden()
        return list_proposals(connection, dataset_id=dataset_id)


@router.get(
    "/companies/{company_id}/datasets/{dataset_id}/movements/{movement_id}/correction-targets",
    tags=["corrections"],
)
def get_correction_targets(
        request: Request, company_id: str, dataset_id: str, movement_id: str,
        principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """Valores y huellas actuales que una UI autorizada puede proponer cambiar."""
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    with request.app.state.database.session(company_id=context.company_id,
                                            subject_id=principal.subject_id) as connection:
        targets = correction_targets(connection, dataset_id=dataset_id,
                                     movement_id=movement_id)
        if not targets:
            raise forbidden()
        return targets


@router.post("/companies/{company_id}/datasets/{dataset_id}/corrections",
             tags=["corrections"], status_code=201)
def create_correction(request: Request, company_id: str, dataset_id: str,
                      body: ProposalRequest,
                      principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    refusal: CorrectionError | None = None
    created: dict[str, Any] | None = None
    with request.app.state.database.session(company_id=context.company_id,
                                            subject_id=principal.subject_id) as connection:
        try:
            created = propose(
                connection, company_id=context.company_id, dataset_id=dataset_id,
                movement_id=body.movement_id, field=body.field,
                expected_base_digest=body.expected_base_digest,
                new_value=body.new_value, reason_code=body.reason_code,
                reason_comment=body.reason_comment, subject_id=principal.subject_id,
                authorization_version=context.authorization_version)
        except CorrectionError as error:
            refusal = error
        if refusal is None and created is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="field_overlay.propose",
                resource_kind="dataset", resource_ref=dataset_id,
                outcome="allowed",
                detail={"overlay_id": created["overlay_id"], "field": body.field,
                        "reason_code": body.reason_code})
        elif refusal is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="field_overlay.propose",
                resource_kind="dataset", resource_ref=dataset_id,
                outcome="denied", detail={"reason": refusal.code, "field": body.field})
    if refusal is not None:
        raise _problem(refusal, "The correction cannot be proposed")
    if created is None:
        raise RuntimeError("correction proposal completed without a result")
    return created


@router.post("/companies/{company_id}/corrections/{overlay_id}/review",
             tags=["corrections"])
def review_correction(request: Request, company_id: str, overlay_id: str,
                      body: ReviewRequest,
                      principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "dataset.publish")
    refusal: CorrectionError | None = None
    reviewed: dict[str, Any] | None = None
    with request.app.state.database.session(company_id=context.company_id,
                                            subject_id=principal.subject_id) as connection:
        try:
            reviewed = review(connection, overlay_id=overlay_id,
                              decision=body.decision, rationale=body.rationale,
                              reviewer_id=principal.subject_id)
        except CorrectionError as error:
            refusal = error
        if refusal is None and reviewed is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="field_overlay.review",
                resource_kind="dataset", resource_ref=reviewed["dataset_version_id"],
                outcome="allowed",
                detail={"overlay_id": overlay_id, "decision": body.decision})
        elif refusal is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="field_overlay.review",
                resource_kind="field_overlay", resource_ref=overlay_id,
                outcome="denied", detail={"reason": refusal.code})
    if refusal is not None:
        raise _problem(refusal, "The correction cannot be reviewed")
    if reviewed is None:
        raise RuntimeError("correction review completed without a result")
    return reviewed
