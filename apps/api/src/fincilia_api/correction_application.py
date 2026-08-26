"""Aplicacion atomica de overlays aprobados a una version derivada."""

from __future__ import annotations

import datetime as dt
import hmac
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg

from fincilia_contracts.release import digest_of, reproduction_key
from fincilia_contracts.tenancy import TenantContext

from .corrections import normalise_value
from .issued_contexts import issue_context


FIELD_COLUMNS = {
    "amount": "amount",
    "currency": "currency_code",
    "direction": "direction",
    "occurred_on": "occurred_on",
    "posted_on": "posted_on",
    "value_date": "value_date",
    "accounting_date": "accounting_date",
}


class ApplicationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ApprovedOverlay:
    overlay_id: str
    movement_id: str
    source_record_id: str
    field: str
    expected_digest: str
    proposed_value: str
    proposed_digest: str
    sequence: int
    reason_code: str
    created_by: str
    reviewer_id: str
    reviewed_at: dt.datetime

    def manifest_item(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "overlay_id": self.overlay_id,
            "proposed_value_digest": self.proposed_digest,
            "sequence": self.sequence,
        }


def overlay_set_digest(overlays: list[ApprovedOverlay]) -> str:
    """Huella estable del conjunto ordenado; nunca incluye el valor."""
    ordered = sorted((item.manifest_item() for item in overlays),
                     key=lambda item: (item["overlay_id"], item["field"]))
    return digest_of(ordered)


def _movement_value(row: dict[str, Any], field: str) -> str | None:
    value = row[FIELD_COLUMNS[field]]
    if value is None:
        return None
    if field == "amount":
        return f"{Decimal(value):.12f}"
    if field in {"occurred_on", "posted_on", "value_date", "accounting_date"}:
        return value.isoformat()
    return str(value)


def _fingerprint(company_id: str, movement: dict[str, Any]) -> str:
    return digest_of({
        "account": str(movement["financial_account_id"]),
        "company": company_id,
        "amount": f"{Decimal(movement['amount']):.12f}",
        "currency": movement["currency_code"],
        "direction": movement["direction"],
        "occurred_on": movement["occurred_on"].isoformat(),
        "reference": movement["reference_normalised"] or "",
    })


def _validate_dates(movement: dict[str, Any]) -> None:
    occurred = movement["occurred_on"]
    for field in ("posted_on", "value_date"):
        value = movement[field]
        if value is not None and value < occurred:
            raise ApplicationError(
                "correction-date-order",
                f"the approved {field} would precede occurred_on")


def _row(cursor) -> dict[str, Any] | None:
    value = cursor.fetchone()
    if value is None:
        return None
    return dict(zip([column.name for column in cursor.description], value))


def _existing(connection: psycopg.Connection, base_dataset_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.application_id, a.base_dataset_version_id, "
            "a.result_dataset_version_id, a.overlay_set_digest, a.applied_at, "
            "d.state, d.movement_count FROM fincilia.field_overlay_application a "
            "JOIN fincilia.dataset_version d "
            "ON d.dataset_version_id = a.result_dataset_version_id "
            "WHERE a.base_dataset_version_id = %s", (base_dataset_id,))
        found = _row(cursor)
    if found is None:
        return None
    return {
        "application_id": str(found["application_id"]),
        "base_dataset_version_id": str(found["base_dataset_version_id"]),
        "result_dataset_version_id": str(found["result_dataset_version_id"]),
        "overlay_set_digest": found["overlay_set_digest"],
        "applied_at": found["applied_at"].isoformat(),
        "state": found["state"],
        "movement_count": int(found["movement_count"]),
        "idempotent_replay": True,
    }


def _base(connection: psycopg.Connection, dataset_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.*, a.content_sha256 AS artifact_sha256, "
            "e.release_key, mv.definition_digest, mv.source_schema_digest, "
            "coalesce(rm.locale, 'es-CO') AS locale, "
            "coalesce(rm.timezone, 'America/Bogota') AS timezone, "
            "coalesce(rm.random_seed, 0) AS random_seed "
            "FROM fincilia.dataset_version d "
            "JOIN fincilia.source_artifact a ON a.artifact_id = d.artifact_id "
            "JOIN fincilia.engine_release e ON e.release_id = d.engine_release_id "
            "JOIN fincilia.column_mapping_version mv "
            "ON mv.mapping_version_id = d.mapping_version_id "
            "LEFT JOIN fincilia.reproducibility_manifest rm "
            "ON rm.dataset_version_id = d.dataset_version_id "
            "WHERE d.dataset_version_id = %s", (dataset_id,))
        return _row(cursor)


def _approved(connection: psycopg.Connection, dataset_id: str) -> list[ApprovedOverlay]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM fincilia.field_overlay o "
            "LEFT JOIN fincilia.field_overlay_review r ON r.overlay_id = o.overlay_id "
            "WHERE o.dataset_version_id = %s AND r.decision IS NULL", (dataset_id,))
        if int(cursor.fetchone()[0]):
            raise ApplicationError(
                "correction-pending-review",
                "all correction proposals must be reviewed before application")
        cursor.execute(
            "SELECT o.overlay_id, o.movement_id, o.source_record_id, "
            "o.target_field, o.expected_base_digest, o.proposed_value, "
            "o.proposed_value_digest, o.sequence, o.reason_code, o.created_by, "
            "r.reviewer_id, r.reviewed_at "
            "FROM fincilia.field_overlay o "
            "JOIN fincilia.field_overlay_review r ON r.overlay_id = o.overlay_id "
            "LEFT JOIN fincilia.field_overlay_application_item ai "
            "ON ai.overlay_id = o.overlay_id "
            "WHERE o.dataset_version_id = %s AND r.decision = 'approved' "
            "AND ai.overlay_id IS NULL ORDER BY o.overlay_id", (dataset_id,))
        rows = cursor.fetchall()
    return [ApprovedOverlay(
        overlay_id=str(row[0]), movement_id=str(row[1]),
        source_record_id=str(row[2]), field=row[3], expected_digest=row[4],
        proposed_value=row[5], proposed_digest=row[6], sequence=int(row[7]),
        reason_code=row[8], created_by=str(row[9]), reviewer_id=str(row[10]),
        reviewed_at=row[11]) for row in rows]


def _load_movements(connection: psycopg.Connection, dataset_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fincilia.canonical_movement "
            "WHERE dataset_version_id = %s ORDER BY movement_id", (dataset_id,))
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def apply_approved(connection: psycopg.Connection, *, tenant: TenantContext,
                   dataset_id: str, hmac_key: str) -> dict[str, Any]:
    """Crea la version derivada completa dentro de la transaccion del caller."""
    company_id = tenant.company_id
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 23))",
            (f"overlay-application:{company_id}:{dataset_id}",))

    replay = _existing(connection, dataset_id)
    if replay is not None:
        return replay

    base = _base(connection, dataset_id)
    if base is None:
        raise ApplicationError("correction-dataset-unknown", "dataset is unavailable")
    if base["state"] != "validated":
        raise ApplicationError(
            "correction-dataset-state",
            "only a validated dataset can produce a corrected version")
    if base["lineage_plan_id"] is None or base["lineage_state"] != "complete":
        raise ApplicationError(
            "correction-lineage-incomplete",
            "the base dataset does not carry complete reproducible lineage")

    overlays = _approved(connection, dataset_id)
    if not overlays:
        raise ApplicationError(
            "correction-none-approved",
            "the dataset has no unapplied approved corrections")

    movements = _load_movements(connection, dataset_id)
    by_id = {str(item["movement_id"]): item for item in movements}
    overlays_by_movement: dict[str, list[ApprovedOverlay]] = {}
    for overlay in overlays:
        movement = by_id.get(overlay.movement_id)
        if movement is None or str(movement["source_record_id"]) != overlay.source_record_id:
            raise ApplicationError(
                "correction-target-drift", "an approved correction lost its target")
        typed = normalise_value(overlay.field, overlay.proposed_value)
        current = _movement_value(movement, overlay.field)
        current_digest = (movement["field_digests"] or {}).get(
            overlay.field, digest_of(current))
        if not hmac.compare_digest(str(current_digest), overlay.expected_digest):
            raise ApplicationError(
                "correction-base-stale", "an approved correction no longer matches its base")
        if not hmac.compare_digest(typed.digest, overlay.proposed_digest):
            raise ApplicationError(
                "correction-proposal-drift", "an approved correction digest is inconsistent")
        overlays_by_movement.setdefault(overlay.movement_id, []).append(overlay)

    required_fields = sorted({overlay.field for overlay in overlays})
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT canonical_field, step_id FROM fincilia.lineage_transform_step "
            "WHERE plan_id = %s AND stage = 'transformed_value' "
            "AND canonical_field = ANY(%s)",
            (base["lineage_plan_id"], required_fields))
        step_by_field = {row[0]: row[1] for row in cursor.fetchall()}
    missing_steps = sorted(set(required_fields) - set(step_by_field))
    if missing_steps:
        raise ApplicationError(
            "correction-lineage-step-missing",
            "the transform plan cannot locate approved field(s): "
            + ", ".join(missing_steps))

    application_id = str(uuid.uuid4())
    result_dataset_id = str(uuid.uuid4())
    set_digest = overlay_set_digest(overlays)
    issued = issue_context(
        connection, tenant=tenant, purpose_code="processing_job",
        resource_kind="source_artifact", resource_ref=str(base["artifact_id"]),
        idempotency_key=f"overlay-application:{dataset_id}",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7),
        hmac_key=hmac_key)

    source_map: dict[str, str] = {}
    movement_map: dict[str, str] = {}
    output_rows: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.record_overlay_application_run(%s, %s, %s, %s::jsonb)",
            (company_id, base["artifact_id"], issued.context_id,
             json.dumps({"mode": "approved_field_overlays",
                         "base_dataset_version_id": dataset_id,
                         "result_dataset_version_id": result_dataset_id},
                        sort_keys=True, separators=(",", ":"))))
        run_id = str(cursor.fetchone()[0])
        cursor.execute(
            "INSERT INTO fincilia.dataset_version (dataset_version_id, company_id, "
            "processing_run_id, mapping_version_id, artifact_id, engine_release_id, "
            "canonical_schema_version, revision, state, completeness_state, "
            "lineage_state, record_count, expected_record_count, movement_count, "
            "rejected_count, prepared_by, validated_by, validated_at, "
            "lineage_plan_id, supersedes_dataset_version_id) VALUES (%s, %s, %s, "
            "%s, %s, %s, %s, %s, 'validated', %s, 'complete', %s, %s, %s, %s, "
            "%s, %s, now(), %s, %s)",
            (result_dataset_id, company_id, run_id, base["mapping_version_id"],
             base["artifact_id"], base["engine_release_id"],
             base["canonical_schema_version"], int(base["revision"]) + 1,
             base["completeness_state"], base["record_count"],
             base["expected_record_count"], base["movement_count"],
             base["rejected_count"], tenant.subject_id, tenant.subject_id,
             base["lineage_plan_id"], dataset_id))

        cursor.execute(
            "SELECT * FROM fincilia.source_record WHERE dataset_version_id = %s "
            "ORDER BY source_record_id", (dataset_id,))
        source_columns = [column.name for column in cursor.description]
        for values in cursor.fetchall():
            source = dict(zip(source_columns, values))
            new_id = str(uuid.uuid4())
            source_map[str(source["source_record_id"])] = new_id
            cursor.execute(
                "INSERT INTO fincilia.source_record (source_record_id, company_id, "
                "dataset_version_id, data_source_id, raw_record_id, record_family, "
                "provider_event_id, source_payload, state, rejection_code, "
                "engine_release_id, canonical_schema_version, lineage_state) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)",
                (new_id, company_id, result_dataset_id, source["data_source_id"],
                 source["raw_record_id"], source["record_family"],
                 source["provider_event_id"], json.dumps(source["source_payload"]),
                 source["state"], source["rejection_code"],
                 source["engine_release_id"], source["canonical_schema_version"],
                 source["lineage_state"]))

        for movement in movements:
            original_id = str(movement["movement_id"])
            new_id = str(uuid.uuid4())
            movement_map[original_id] = new_id
            effective = dict(movement)
            digests = dict(movement["field_digests"] or {})
            for overlay in overlays_by_movement.get(original_id, []):
                typed = normalise_value(overlay.field, overlay.proposed_value)
                column = FIELD_COLUMNS[overlay.field]
                effective[column] = (Decimal(typed.canonical)
                                     if overlay.field == "amount"
                                     else dt.date.fromisoformat(typed.canonical)
                                     if overlay.field in {"occurred_on", "posted_on",
                                                          "value_date", "accounting_date"}
                                     else typed.canonical)
                digests[overlay.field] = typed.digest
            _validate_dates(effective)
            effective["dedupe_fingerprint"] = _fingerprint(company_id, effective)
            new_source = source_map[str(movement["source_record_id"])]
            cursor.execute(
                "INSERT INTO fincilia.canonical_movement (movement_id, company_id, "
                "dataset_version_id, source_record_id, financial_account_id, kind, "
                "amount, currency_code, direction, description, reference_original, "
                "reference_normalised, occurred_on, posted_on, value_date, "
                "accounting_date, dedupe_fingerprint, state, engine_release_id, "
                "canonical_schema_version, lineage_state, field_digests) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                (new_id, company_id, result_dataset_id, new_source,
                 effective["financial_account_id"], effective["kind"],
                 effective["amount"], effective["currency_code"],
                 effective["direction"], effective["description"],
                 effective["reference_original"], effective["reference_normalised"],
                 effective["occurred_on"], effective["posted_on"],
                 effective["value_date"], effective["accounting_date"],
                 effective["dedupe_fingerprint"], effective["state"],
                 effective["engine_release_id"],
                 effective["canonical_schema_version"], effective["lineage_state"],
                 json.dumps(digests, sort_keys=True, separators=(",", ":"))))
            output_rows.append({
                "amount": f"{Decimal(effective['amount']):.12f}",
                "currency": effective["currency_code"],
                "direction": effective["direction"],
                "occurred_on": effective["occurred_on"].isoformat(),
                "source_record_id": new_source,
            })

        cursor.execute(
            "SELECT * FROM fincilia.movement_evidence_link "
            "WHERE movement_id = ANY(%s::uuid[]) ORDER BY link_id",
            (list(movement_map),))
        link_columns = [column.name for column in cursor.description]
        for values in cursor.fetchall():
            link = dict(zip(link_columns, values))
            source_id = source_map.get(str(link["source_record_id"]),
                                       str(link["source_record_id"]))
            cursor.execute(
                "INSERT INTO fincilia.movement_evidence_link (link_id, company_id, "
                "movement_id, source_record_id, link_role, allocated_amount, "
                "currency_code, engine_release_id, canonical_schema_version, "
                "lineage_state) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s)",
                (company_id, movement_map[str(link["movement_id"])], source_id,
                 link["link_role"], link["allocated_amount"], link["currency_code"],
                 link["engine_release_id"], link["canonical_schema_version"],
                 link["lineage_state"]))

        # Hereda overrides anteriores, porque el nuevo dataset sigue necesitando
        # explicar las correcciones que ya formaban parte de su base.
        cursor.execute(
            "SELECT * FROM fincilia.lineage_row_override "
            "WHERE dataset_version_id = %s ORDER BY source_record_id, field_name, "
            "override_ordinal", (dataset_id,))
        inherited_columns = [column.name for column in cursor.description]
        for values in cursor.fetchall():
            inherited = dict(zip(inherited_columns, values))
            cursor.execute(
                "INSERT INTO fincilia.lineage_row_override (company_id, "
                "dataset_version_id, source_record_id, raw_record_id, field_name, "
                "base_plan_step_id, override_kind, original_value_digest, "
                "resulting_value_digest, rule_version, reason_code, "
                "override_ordinal, created_by, approved_by, approved_at, created_at, "
                "engine_release_id, canonical_schema_version) VALUES (%s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (company_id, result_dataset_id,
                 source_map[str(inherited["source_record_id"])],
                 inherited["raw_record_id"], inherited["field_name"],
                 inherited["base_plan_step_id"], inherited["override_kind"],
                 inherited["original_value_digest"],
                 inherited["resulting_value_digest"], inherited["rule_version"],
                 inherited["reason_code"], inherited["override_ordinal"],
                 inherited["created_by"], inherited["approved_by"],
                 inherited["approved_at"], inherited["created_at"],
                 inherited["engine_release_id"],
                 inherited["canonical_schema_version"]))

        cursor.execute(
            "INSERT INTO fincilia.field_overlay_application (application_id, "
            "company_id, base_dataset_version_id, result_dataset_version_id, "
            "overlay_set_digest, applied_by, authorization_version) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s)",
            (application_id, company_id, dataset_id, result_dataset_id,
             set_digest, tenant.subject_id, tenant.authorization_version))

        for overlay in overlays:
            movement = by_id[overlay.movement_id]
            new_source = source_map[overlay.source_record_id]
            cursor.execute(
                "SELECT coalesce(max(override_ordinal), 0) + 1 "
                "FROM fincilia.lineage_row_override WHERE dataset_version_id = %s "
                "AND source_record_id = %s AND field_name = %s",
                (result_dataset_id, new_source, overlay.field))
            ordinal = int(cursor.fetchone()[0])
            cursor.execute(
                "INSERT INTO fincilia.lineage_row_override (company_id, "
                "dataset_version_id, source_record_id, raw_record_id, field_name, "
                "base_plan_step_id, override_kind, original_value_digest, "
                "resulting_value_digest, rule_version, reason_code, "
                "override_ordinal, created_by, approved_by, approved_at, "
                "engine_release_id, canonical_schema_version) SELECT %s, %s, %s, "
                "s.raw_record_id, %s, %s, 'overlay_applied', %s, %s, "
                "'field-overlay-v1', %s, %s, %s, %s, %s, %s, %s "
                "FROM fincilia.source_record s WHERE s.source_record_id = %s "
                "RETURNING override_id",
                (company_id, result_dataset_id, new_source, overlay.field,
                 step_by_field[overlay.field],
                 overlay.expected_digest, overlay.proposed_digest,
                 overlay.reason_code, ordinal, overlay.created_by,
                 overlay.reviewer_id, overlay.reviewed_at,
                 base["engine_release_id"], base["canonical_schema_version"], new_source))
            override_id = str(cursor.fetchone()[0])
            cursor.execute(
                "INSERT INTO fincilia.field_overlay_application_item (company_id, "
                "application_id, overlay_id, base_movement_id, result_movement_id, "
                "lineage_override_id, original_value_digest, "
                "resulting_value_digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (company_id, application_id, overlay.overlay_id,
                 overlay.movement_id, movement_map[overlay.movement_id], override_id,
                 overlay.expected_digest, overlay.proposed_digest))

        deterministic_config = {
            "base_dataset_version_id": dataset_id,
            "overlay_set_digest": set_digest,
            "overlays": [item.manifest_item() for item in overlays],
            "processing_mode": "approved_field_overlays-v1",
        }
        manifest = {
            "canonical_schema_version": base["canonical_schema_version"],
            "company_id": company_id,
            "deterministic_config": deterministic_config,
            "engine_release_key": base["release_key"],
            "input_artifact_sha256": base["artifact_sha256"],
            "locale": base["locale"],
            "mapping_definition_digest": base["definition_digest"],
            "mapping_version_id": str(base["mapping_version_id"]),
            "random_seed": int(base["random_seed"]),
            "source_schema_digest": base["source_schema_digest"],
            "timezone": base["timezone"],
        }
        cursor.execute(
            "INSERT INTO fincilia.reproducibility_manifest (manifest_id, company_id, "
            "dataset_version_id, engine_release_id, input_artifact_sha256, "
            "mapping_version_id, deterministic_config, locale, timezone, "
            "random_seed, output_digests, reproduction_key) VALUES "
            "(gen_random_uuid(), %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, "
            "%s::jsonb, %s)",
            (company_id, result_dataset_id, base["engine_release_id"],
             base["artifact_sha256"], base["mapping_version_id"],
             json.dumps(deterministic_config, sort_keys=True, separators=(",", ":")),
             base["locale"], base["timezone"], base["random_seed"],
             json.dumps({"canonical_movements_sha256": digest_of(output_rows),
                         "overlay_set_sha256": set_digest}, sort_keys=True,
                        separators=(",", ":")), reproduction_key(manifest)))

    return {
        "application_id": application_id,
        "base_dataset_version_id": dataset_id,
        "result_dataset_version_id": result_dataset_id,
        "overlay_set_digest": set_digest,
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "state": "validated",
        "movement_count": len(movements),
        "applied_correction_count": len(overlays),
        "idempotent_replay": False,
    }
