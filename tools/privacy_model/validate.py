"""Validación ejecutable del mapa de privacidad de Fincilia (FNC-PRV-001).

Solo biblioteca estándar. Determinista: no consulta red, reloj, entorno ni
aleatoriedad. La única lectura externa son los ficheros del repositorio que
recibe por parámetro.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_SCHEMA_VERSION = 1
REQUIRED_TASK_ID = "FNC-PRV-001"
REQUIRED_DATA_CEILING = "synthetic_only"
REQUIRED_LEGAL_VALIDATION = "pending_human"
REQUIRED_REGION_DECISION = "pending_A-02"

REQUIRED_PRIVACY_RISKS = {"TM-005", "TM-010", "TM-011", "TM-012", "TM-014"}
REQUIRED_ACTIVITY_IDS = {f"PA-{index:02d}" for index in range(1, 26)}
REQUIRED_RIGHTS_IDS = {
    "RW-ACCESS", "RW-RECTIFY", "RW-UPDATE", "RW-REVOKE", "RW-DELETE",
    "RW-PORTABILITY", "RW-OBJECT", "RW-PROOF_OF_AUTHORIZATION", "RW-COMPLAINT",
}
REQUIRED_DPIA_IDS = {f"DPIA-{index:02d}" for index in range(1, 14)}
REQUIRED_GATE_IDS = {"S1-READY", "DRG-00", "DRG-01", "GA-01", "L-01", "L-02", "A-02", "S-01"}
REQUIRED_ROLE_IDS = {
    "processor_candidate", "controller_candidate", "joint_or_context_dependent",
    "not_determined_pending_legal",
}
REQUIRED_SUBJECT_IDS = {
    "firm_accountant", "firm_employee", "sme_administrator", "sme_employee_or_contractor",
    "third_party_natural_person_in_documents", "auditor_user", "support_user",
    "service_principal_non_human", "legal_entity_company",
}
REQUIRED_PURPOSE_IDS = {
    "identity_and_access", "company_administration", "delegated_accounting_operation",
    "evidence_ingestion", "parsing_and_mapping", "reconciliation_and_close",
    "reporting_and_export", "connector_operation", "reminders_and_notifications",
    "security_and_audit", "support_and_break_glass", "usage_metering_and_billing",
    "deletion_and_portability", "backup_and_disaster_recovery",
    "ai_assistance_disabled_by_default", "operational_analytics",
    "legal_obligation_compliance",
}

REQUIRED_DELETION_STATES = {
    "requested", "verified", "blocked_by_hold", "tombstoned",
    "purge_in_progress", "backup_pending", "reconciled", "completed", "failed",
}
DELETE_LEDGER_STORE = "security_archive"

VERIFIED_COMPANY_SCOPES = {
    "required_verified",
    "preserved_verified",
    "multi_company_per_company_authorized",
}
PENDING_LEGAL_BASIS_STATES = {
    "pending_legal", "pending_contract", "pending_legal_and_contract",
}
ACCEPTED_TOKENS = {"accepted", "approved", "final", "signed", "resolved", "done", "closed"}

SECRET_ALLOWED_STORES = {"vault"}
NON_AUTHORITATIVE_STORES = {
    "valkey", "analytics_projection", "browser_storage", "mobile_device",
    "logs_traces", "temporal", "backups", "email_push_delivery",
}

EXPORT_REQUIRED_CONTROLS = {
    "reauthorization_on_create_and_download",
    "export_manifest_and_hash",
    "authorization_version_bound",
    "short_ttl_opaque_single_scope_link",
}
SUPPORT_REQUIRED_CONTROLS = {
    "just_in_time_grant_only",
    "explicit_reason_required",
    "time_bounded_expiration",
    "independent_review_after_access",
}
PORTFOLIO_REQUIRED_CONTROLS = {
    "authoritative_candidate_enumeration",
    "per_company_authorization",
}

# Una duración concreta es exactamente lo que L-01 todavía no ha decidido.
DURATION_PATTERN = re.compile(
    r"\d+\s*[-_ ]?\s*"
    r"(days?|months?|years?|hours?|minutes?|weeks?"
    r"|dias?|d[ií]as?|meses|mes|anos?|a[nñ]os?|horas?|minutos?|semanas?)\b",
    re.IGNORECASE,
)
DURATION_KEY_PATTERN = re.compile(
    r"(duration|days|months|years|hours|ttl|period|retention_time)", re.IGNORECASE
)

ACTIVITY_REQUIRED_FIELDS = (
    "id", "name", "purpose_id", "actor", "subject_categories", "data_categories",
    "classifications", "source_flows", "company_scope", "stores", "recipients",
    "provisional_role", "legal_basis_state", "region_state", "cross_border_state",
    "retention_policy_ids", "deletion_triggers", "legal_hold_behavior", "external_ai",
    "minimization_controls", "allowed_log_fields", "forbidden_log_fields",
    "rights_workflows", "threat_refs", "owner_role", "reviewer_roles",
    "target_gate", "status",
)


@dataclass(frozen=True, order=True)
class PrivacyModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item["id"] for item in items if isinstance(item, dict) and "id" in item}


def _duplicate_ids(items: Any) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    if not isinstance(items, list):
        return duplicates
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        identifier = item["id"]
        if identifier in seen:
            duplicates.add(identifier)
        seen.add(identifier)
    return duplicates


def _reachable_states(initial: str, transitions: list[dict[str, Any]]) -> set[str]:
    reachable = {initial}
    changed = True
    while changed:
        changed = False
        for transition in transitions:
            if transition.get("from") in reachable and transition.get("to") not in reachable:
                reachable.add(transition.get("to"))
                changed = True
    return reachable


def _walk_strings(value: Any, key: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.extend(_walk_strings(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_strings(child, key))
    else:
        found.append((key, value))
    return found


def validate_model(
    model: dict[str, Any],
    dfd_model: dict[str, Any],
    threat_model: dict[str, Any],
    repository_root: Path,
) -> list[PrivacyModelError]:
    errors: list[PrivacyModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(PrivacyModelError(code, location, message))

    # -- 1..6 cabecera y techos no negociables ---------------------------
    if model.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        fail("PRV-SCHEMA-VERSION", "schema_version",
             f"expected {REQUIRED_SCHEMA_VERSION}, got {model.get('schema_version')!r}")
    if model.get("task_id") != REQUIRED_TASK_ID:
        fail("PRV-TASK-ID", "task_id", f"expected {REQUIRED_TASK_ID}")
    if model.get("data_ceiling") != REQUIRED_DATA_CEILING:
        fail("PRV-DATA-CEILING", "data_ceiling", f"expected {REQUIRED_DATA_CEILING}")
    if model.get("legal_validation") != REQUIRED_LEGAL_VALIDATION:
        fail("PRV-LEGAL-VALIDATION", "legal_validation",
             "an agent cannot record legal validation as anything but pending_human")
    if model.get("region_decision") != REQUIRED_REGION_DECISION:
        fail("PRV-REGION-DECISION", "region_decision",
             "region stays pending_A-02 until Architecture and Legal decide")
    if model.get("external_ai_enabled") is not False:
        fail("PRV-EXTERNAL-AI-GLOBAL", "external_ai_enabled",
             "external AI must stay disabled during E0")
    if model.get("status") != "review_pending":
        fail("PRV-STATUS", "status", "the model stays review_pending")
    if model.get("human_acceptance") != "pending":
        fail("PRV-HUMAN-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")

    activities = model.get("processing_activities", [])
    if not isinstance(activities, list) or not activities:
        fail("PRV-ACTIVITIES-MISSING", "processing_activities", "no processing activities declared")
        return sorted(set(errors))

    store_entries = model.get("stores", [])
    store_ids = _ids(store_entries)
    purpose_ids = _ids(model.get("purposes", []))
    policy_entries = model.get("retention_policies", [])
    policy_ids = _ids(policy_entries)
    recipient_entries = model.get("recipient_registry", [])
    recipient_ids = _ids(recipient_entries)
    rights_ids = _ids(model.get("rights_workflows", []))
    gate_ids = _ids(model.get("gates", []))
    subject_ids = _ids(model.get("data_subject_categories", []))
    role_ids = _ids(model.get("processing_roles", []))

    catalog_expectations = (
        ("processing_activities", activities, REQUIRED_ACTIVITY_IDS),
        ("purposes", model.get("purposes", []), REQUIRED_PURPOSE_IDS),
        ("rights_workflows", model.get("rights_workflows", []), REQUIRED_RIGHTS_IDS),
        ("dpia_triggers", model.get("dpia_triggers", []), REQUIRED_DPIA_IDS),
        ("gates", model.get("gates", []), REQUIRED_GATE_IDS),
        ("processing_roles", model.get("processing_roles", []), REQUIRED_ROLE_IDS),
        ("data_subject_categories", model.get("data_subject_categories", []), REQUIRED_SUBJECT_IDS),
    )
    for catalog_name, entries, expected_ids in catalog_expectations:
        actual_ids = _ids(entries)
        if actual_ids != expected_ids or not isinstance(entries, list) or len(entries) != len(expected_ids):
            fail("PRV-CATALOG-COVERAGE", catalog_name,
                 f"catalog ids must be exact; missing={sorted(expected_ids - actual_ids)}, extra={sorted(actual_ids - expected_ids)}")

    for catalog_name in (
        "processing_activities", "stores", "purposes", "retention_policies",
        "recipient_registry", "rights_workflows", "gates", "data_subject_categories",
        "processing_roles", "dpia_triggers", "parties", "unresolved_decisions",
    ):
        for duplicate in sorted(_duplicate_ids(model.get(catalog_name, []))):
            fail("PRV-CATALOG-DUPLICATE", f"{catalog_name}[{duplicate}]", "catalog id is duplicated")

    dfd_flow_ids = {flow["id"] for flow in dfd_model.get("flows", [])}
    dfd_store_ids = set(dfd_model.get("stores", []))
    dfd_class_ids = _ids(dfd_model.get("classifications", []))
    denylist = set(dfd_model.get("global_log_denylist", []))
    dfd_policy_ids = {
        persistence["retention_policy_id"]
        for flow in dfd_model.get("flows", [])
        for persistence in flow.get("persistence", [])
        if "retention_policy_id" in persistence
    }
    threat_ids = _ids(threat_model.get("risks", []))

    # -- 7 cobertura de flujos -------------------------------------------
    covered_flows: set[str] = set()
    for activity in activities:
        covered_flows.update(activity.get("source_flows", []))
    missing_flows = sorted(dfd_flow_ids - covered_flows)
    if missing_flows:
        fail("PRV-FLOW-COVERAGE", "processing_activities",
             f"DFD flows not covered by any activity: {missing_flows}")
    unknown_flows = sorted(covered_flows - dfd_flow_ids)
    if unknown_flows:
        fail("PRV-FLOW-REFERENCE", "processing_activities",
             f"unknown flow references: {unknown_flows}")

    # -- 8 cobertura de stores -------------------------------------------
    missing_stores = sorted(dfd_store_ids - store_ids)
    if missing_stores:
        fail("PRV-STORE-COVERAGE", "stores", f"DFD stores not modelled: {missing_stores}")
    referenced_stores: set[str] = set()
    for activity in activities:
        referenced_stores.update(activity.get("stores", []))
    unused_dfd_stores = sorted(dfd_store_ids - referenced_stores)
    if unused_dfd_stores:
        fail("PRV-STORE-UNREFERENCED", "processing_activities",
             f"DFD stores not touched by any activity: {unused_dfd_stores}")

    # -- 9 cobertura de retención ----------------------------------------
    missing_policies = sorted(dfd_policy_ids - policy_ids)
    if missing_policies:
        fail("PRV-RETENTION-COVERAGE", "retention_policies",
             f"DFD retention policies not modelled: {missing_policies}")

    # -- 10 cobertura de riesgos de privacidad ---------------------------
    covered_threats: set[str] = set()
    for activity in activities:
        covered_threats.update(activity.get("threat_refs", []))
    missing_risks = sorted(REQUIRED_PRIVACY_RISKS - covered_threats)
    if missing_risks:
        fail("PRV-RISK-COVERAGE", "processing_activities",
             f"mandatory privacy risks not covered: {missing_risks}")

    # -- 14 clase secret solo en vault (a nivel de store) ----------------
    for entry in store_entries:
        location = f"stores[{entry.get('id')}]"
        allowed = set(entry.get("allowed_classifications", []))
        forbidden = set(entry.get("forbidden_classifications", []))
        unknown_classes = (allowed | forbidden) - dfd_class_ids
        if unknown_classes:
            fail("PRV-CLASSIFICATION-REFERENCE", location,
                 f"unknown classifications: {sorted(unknown_classes)}")
        if allowed & forbidden:
            fail("PRV-STORE-CLASS-CONFLICT", location,
                 f"classifications cannot be both allowed and forbidden: {sorted(allowed & forbidden)}")
        if "secret" in allowed and entry.get("id") not in SECRET_ALLOWED_STORES:
            fail("PRV-SECRET-STORE", location, "class secret may only persist in vault")
        if "prohibited" in allowed:
            fail("PRV-PROHIBITED-CLASS", location, "class prohibited is never persistable")
        # -- 23 stores efímeros o derivados nunca son autoridad ----------
        if entry.get("id") in NON_AUTHORITATIVE_STORES:
            if entry.get("financial_authority") is not False:
                fail("PRV-STORE-AUTHORITY", location,
                     "ephemeral, client-side or derived stores cannot hold financial authority")
            authority = str(entry.get("authority", ""))
            if "authoritative" in authority:
                fail("PRV-STORE-AUTHORITY", location,
                     f"authority {authority!r} contradicts a non-authoritative store")

    # -- actividades ------------------------------------------------------
    seen_activity_ids: set[str] = set()
    for activity in activities:
        activity_id = activity.get("id", "<missing>")
        location = f"processing_activities[{activity_id}]"

        for field in ACTIVITY_REQUIRED_FIELDS:
            if field not in activity:
                fail("PRV-ACTIVITY-FIELD", location, f"missing required field {field!r}")
        if activity_id in seen_activity_ids:
            fail("PRV-ACTIVITY-DUPLICATE", location, "duplicate activity id")
        seen_activity_ids.add(activity_id)

        classifications = set(activity.get("classifications", []))
        stores = set(activity.get("stores", []))
        controls = set(activity.get("minimization_controls", []))

        if not classifications or not classifications <= dfd_class_ids:
            fail("PRV-CLASSIFICATION-REFERENCE", location,
                 f"activity classifications must be non-empty DFD classes: {sorted(classifications - dfd_class_ids)}")
        for required_collection in (
            "subject_categories", "data_categories", "stores", "retention_policy_ids",
            "rights_workflows", "evidence",
        ):
            value = activity.get(required_collection)
            if not isinstance(value, list) or not value:
                fail("PRV-ACTIVITY-COLLECTION", location,
                     f"{required_collection} must be a non-empty list")

        # -- 11 referencias válidas -------------------------------------
        if activity.get("purpose_id") not in purpose_ids:
            fail("PRV-PURPOSE-REFERENCE", location,
                 f"unknown purpose {activity.get('purpose_id')!r}")
        for store_id in sorted(stores - store_ids):
            fail("PRV-STORE-REFERENCE", location, f"unknown store {store_id!r}")
        for policy_id in sorted(set(activity.get("retention_policy_ids", [])) - policy_ids):
            fail("PRV-POLICY-REFERENCE", location, f"unknown retention policy {policy_id!r}")
        for recipient_id in sorted(set(activity.get("recipients", [])) - recipient_ids):
            fail("PRV-RECIPIENT-REFERENCE", location, f"unknown recipient {recipient_id!r}")
        for workflow_id in sorted(set(activity.get("rights_workflows", [])) - rights_ids):
            fail("PRV-RIGHTS-REFERENCE", location, f"unknown rights workflow {workflow_id!r}")
        for threat_id in sorted(set(activity.get("threat_refs", [])) - threat_ids):
            fail("PRV-THREAT-REFERENCE", location, f"unknown threat {threat_id!r}")
        for subject_id in sorted(set(activity.get("subject_categories", [])) - subject_ids):
            fail("PRV-SUBJECT-REFERENCE", location, f"unknown subject category {subject_id!r}")
        if activity.get("provisional_role") not in role_ids:
            fail("PRV-ROLE-REFERENCE", location,
                 f"unknown provisional role {activity.get('provisional_role')!r}")
        if activity.get("target_gate") not in gate_ids:
            fail("PRV-GATE-REFERENCE", location,
                 f"unknown target gate {activity.get('target_gate')!r}")

        # -- 12 ninguna actividad procesa clase prohibited ---------------
        if "prohibited" in classifications:
            fail("PRV-PROHIBITED-CLASS", location,
                 "prohibited content is never a processable data class")

        # -- 13 financial_sensitive exige company scope verificado -------
        if "financial_sensitive" in classifications:
            if activity.get("company_scope") not in VERIFIED_COMPANY_SCOPES:
                fail("PRV-FINANCIAL-SCOPE", location,
                     "financial_sensitive requires a verified company scope")

        # -- 14 clase secret solo en vault (a nivel de actividad) --------
        if "secret" in classifications and not stores <= SECRET_ALLOWED_STORES:
            fail("PRV-SECRET-STORE", location,
                 "an activity handling class secret may only use vault")

        # -- 16 IA externa desactivada -----------------------------------
        external_ai = activity.get("external_ai", {})
        if not isinstance(external_ai, dict) or external_ai.get("enabled") is not False:
            fail("PRV-EXTERNAL-AI-ACTIVITY", location, "external AI must stay disabled")
        elif external_ai.get("fail_closed") is not True or external_ai.get("gateway_required") is not True:
            fail("PRV-EXTERNAL-AI-ACTIVITY", location,
                 "external AI must remain gateway-only and fail-closed")

        # -- 17 ninguna base legal aceptada ------------------------------
        basis = activity.get("legal_basis_state")
        if basis not in PENDING_LEGAL_BASIS_STATES:
            fail("PRV-LEGAL-BASIS", location,
                 f"legal_basis_state {basis!r} must remain pending until Legal decides")

        # -- 5 región por actividad --------------------------------------
        if activity.get("region_state") != REQUIRED_REGION_DECISION:
            fail("PRV-REGION-DECISION", location, "region_state must stay pending_A-02")
        cross_border = str(activity.get("cross_border_state", ""))
        if "pending" not in cross_border:
            fail("PRV-CROSS-BORDER", location,
                 "cross_border_state cannot be resolved before A-02")

        # -- 24 allowlist de logs vs denylist del DFD --------------------
        forbidden_in_allowlist = sorted(set(activity.get("allowed_log_fields", [])) & denylist)
        if forbidden_in_allowlist:
            fail("PRV-LOG-DENYLIST", location,
                 f"allowed log fields intersect the DFD denylist: {forbidden_in_allowlist}")
        missing_denylist = sorted(denylist - set(activity.get("forbidden_log_fields", [])))
        if missing_denylist:
            fail("PRV-LOG-FORBIDDEN", location,
                 f"forbidden_log_fields must contain the DFD denylist, missing: {missing_denylist}")

        # -- 25 owner y reviewer independientes --------------------------
        owner = activity.get("owner_role")
        reviewers = activity.get("reviewer_roles", [])
        if not owner:
            fail("PRV-OWNER-MISSING", location, "owner_role is required")
        if not reviewers:
            fail("PRV-REVIEWER-MISSING", location, "at least one reviewer role is required")
        if owner and owner in set(reviewers):
            fail("PRV-OWNER-INDEPENDENCE", location,
                 f"owner {owner!r} cannot also be a reviewer of its own activity")

        # -- 26 export y portabilidad ------------------------------------
        name = str(activity.get("name", ""))
        if "export" in name or "portability" in name:
            missing_controls = sorted(EXPORT_REQUIRED_CONTROLS - controls)
            if missing_controls:
                fail("PRV-EXPORT-CONTROLS", location,
                     f"export or portability activity misses controls: {missing_controls}")

        # -- 27 soporte y break-glass ------------------------------------
        if activity.get("purpose_id") == "support_and_break_glass":
            missing_controls = sorted(SUPPORT_REQUIRED_CONTROLS - controls)
            if missing_controls:
                fail("PRV-SUPPORT-CONTROLS", location,
                     f"support activity misses controls: {missing_controls}")

        # -- 28 portafolio multiempresa ----------------------------------
        if activity.get("company_scope") == "multi_company_per_company_authorized":
            missing_controls = sorted(PORTFOLIO_REQUIRED_CONTROLS - controls)
            if missing_controls:
                fail("PRV-PORTFOLIO-CONTROLS", location,
                     f"multi-company activity misses controls: {missing_controls}")
            if any("cache" in control and "candidate" in control for control in controls):
                fail("PRV-PORTFOLIO-CONTROLS", location,
                     "the candidate company list may never come from a consolidated cache")

        if activity.get("status") != "review_pending":
            fail("PRV-ACTIVITY-STATUS", location, "activities stay review_pending")

        # -- 29 rutas de evidencia existentes ----------------------------
        for item in activity.get("evidence", []):
            path_value = item.get("path") if isinstance(item, dict) else None
            if not path_value:
                fail("PRV-EVIDENCE-PATH", location, "evidence entry without path")
                continue
            raw_path = Path(path_value)
            root = repository_root.resolve()
            if raw_path.is_absolute() or ".." in raw_path.parts:
                fail("PRV-EVIDENCE-PATH", location,
                     f"evidence path must be canonical and repository-relative: {path_value}")
                continue
            candidate = (root / raw_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                fail("PRV-EVIDENCE-PATH", location,
                     f"evidence path escapes the repository: {path_value}")
                continue
            if not candidate.is_file():
                fail("PRV-EVIDENCE-PATH", location, f"evidence path does not exist: {path_value}")

    # -- 18 sin duraciones numéricas inventadas ---------------------------
    for policy in policy_entries:
        location = f"retention_policies[{policy.get('id')}]"
        required_policy_fields = {
            "class", "stores", "computation_start", "expiry_trigger", "duration_state",
            "legal_hold", "derived_affected", "purge_method", "purge_evidence",
            "backup_restore_behavior", "owner_role", "reviewer_roles", "pending_decision",
        }
        missing_policy_fields = sorted(required_policy_fields - set(policy))
        if missing_policy_fields:
            fail("PRV-RETENTION-FIELDS", location,
                 f"retention policy fields are missing: {missing_policy_fields}")
        if policy.get("duration_state") not in {"pending_legal", "pending_contract"}:
            fail("PRV-RETENTION-DURATION", location,
                 "duration_state must remain pending_legal or pending_contract")
        for key, value in _walk_strings(policy):
            if isinstance(value, str) and DURATION_PATTERN.search(value):
                fail("PRV-RETENTION-DURATION", location,
                     f"numeric retention duration is not decided yet: {value!r}")
            if isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and DURATION_KEY_PATTERN.search(key):
                fail("PRV-RETENTION-DURATION", location,
                     f"numeric duration in field {key!r}: {value!r}")
        for store_id in sorted(set(policy.get("stores", [])) - store_ids):
            fail("PRV-STORE-REFERENCE", location, f"unknown store {store_id!r}")
        if not policy.get("owner_role"):
            fail("PRV-OWNER-MISSING", location, "retention policy needs an owner role")
        if not policy.get("reviewer_roles"):
            fail("PRV-REVIEWER-MISSING", location, "retention policy needs independent reviewer roles")
        if policy.get("owner_role") in set(policy.get("reviewer_roles", [])):
            fail("PRV-OWNER-INDEPENDENCE", location,
                 "retention owner cannot be its own reviewer")

    # -- workflows de derechos y triggers DPIA no se degradan ------------
    right_state_fields = ("applicability_state", "sla_state", "exceptions_state", "appeal_state")
    for workflow in model.get("rights_workflows", []):
        location = f"rights_workflows[{workflow.get('id')}]"
        for field in right_state_fields:
            if "pending" not in str(workflow.get(field, "")):
                fail("PRV-RIGHTS-PENDING", location,
                     f"{field} must remain pending Legal determination")
        if workflow.get("scope_resolution") != "authoritative_per_company_never_from_cache":
            fail("PRV-RIGHTS-SCOPE", location,
                 "rights scope must resolve authoritatively per company")
        if workflow.get("controller_processor_routing") != "if_processor_route_to_controller_and_do_not_answer_directly":
            fail("PRV-RIGHTS-ROUTING", location,
                 "controller/processor routing must remain explicit")
        if not set(workflow.get("store_search", [])) <= store_ids or not workflow.get("store_search"):
            fail("PRV-RIGHTS-STORES", location, "rights workflow store search is empty or unknown")
        if not set(workflow.get("applies_to_subject_categories", [])) <= subject_ids:
            fail("PRV-RIGHTS-SUBJECTS", location, "rights workflow references unknown subjects")
        owner = workflow.get("owner_role")
        reviewers = set(workflow.get("reviewer_roles", []))
        if not owner or not reviewers or owner in reviewers:
            fail("PRV-OWNER-INDEPENDENCE", location,
                 "rights workflow requires an independent owner/reviewer split")

    for trigger in model.get("dpia_triggers", []):
        location = f"dpia_triggers[{trigger.get('id')}]"
        if not isinstance(trigger.get("trigger"), str) or not trigger.get("trigger"):
            fail("PRV-DPIA-TRIGGER", location, "DPIA trigger must be non-empty")
        if trigger.get("gate") not in gate_ids:
            fail("PRV-DPIA-GATE", location, "DPIA trigger references an unknown gate")

    # -- 19 delete ledger en security_archive y fuera del restore ---------
    machine = model.get("deletion_state_machine", {})
    if machine.get("ledger_store") != DELETE_LEDGER_STORE:
        fail("PRV-DELETE-LEDGER-STORE", "deletion_state_machine",
             f"the delete ledger must live in {DELETE_LEDGER_STORE}")
    if machine.get("ledger_outside_ordinary_restore") is not True:
        fail("PRV-DELETE-LEDGER-STORE", "deletion_state_machine",
             "the delete ledger must sit outside the ordinary restore scope")
    for policy in policy_entries:
        if policy.get("id") == "L-01-DELETE-LEDGER":
            if set(policy.get("stores", [])) != {DELETE_LEDGER_STORE}:
                fail("PRV-DELETE-LEDGER-STORE", "retention_policies[L-01-DELETE-LEDGER]",
                     "the delete ledger policy must target security_archive only")

    # -- 20 restore reaplica tombstones antes de reabrir ------------------
    if machine.get("restore_requires_tombstone_reapplication_before_service_reopen") is not True:
        fail("PRV-RESTORE-TOMBSTONE", "deletion_state_machine",
             "restore must reapply tombstones before the service reopens")
    if machine.get("raw_overwrite_to_delete") is not False:
        fail("PRV-RESTORE-TOMBSTONE", "deletion_state_machine",
             "raw evidence is never overwritten to delete it")

    # -- 21 y 22 máquina de estados de borrado ---------------------------
    states = set(machine.get("states", []))
    missing_states = sorted(REQUIRED_DELETION_STATES - states)
    if missing_states:
        fail("PRV-DELETE-STATES", "deletion_state_machine",
             f"missing deletion states: {missing_states}")
    extra_states = sorted(states - REQUIRED_DELETION_STATES)
    if extra_states:
        fail("PRV-DELETE-STATES", "deletion_state_machine",
             f"unknown deletion states: {extra_states}")
    if machine.get("initial") != "requested":
        fail("PRV-DELETE-STATES", "deletion_state_machine", "initial state must be requested")

    transitions = machine.get("transitions", [])
    for transition in transitions:
        source = transition.get("from")
        target = transition.get("to")
        if source not in states or target not in states:
            fail("PRV-DELETE-TRANSITION", "deletion_state_machine",
                 f"transition references unknown state: {source!r} -> {target!r}")
        if source == "requested" and target == "completed":
            fail("PRV-DELETE-SHORTCUT", "deletion_state_machine",
                 "completed can never be reached directly from requested")
    predecessors = {t.get("from") for t in transitions if t.get("to") == "completed"}
    if predecessors and predecessors != {"reconciled"}:
        fail("PRV-DELETE-SHORTCUT", "deletion_state_machine",
             f"completed must only follow reconciled, found {sorted(predecessors)}")
    required_path = ["tombstoned", "purge_in_progress", "backup_pending", "reconciled"]
    if machine.get("completed_requires_path_through") != required_path:
        fail("PRV-DELETE-REQUIRED-PATH", "deletion_state_machine",
             f"completed path must pass through {required_path}")
    reachable = _reachable_states("requested", transitions)
    if reachable != states:
        fail("PRV-DELETE-REACHABILITY", "deletion_state_machine",
             f"unreachable states from requested: {sorted(states - reachable)}")
    if set(machine.get("terminal", [])) != {"completed", "failed"}:
        fail("PRV-DELETE-TERMINAL", "deletion_state_machine",
             "completed and failed must be the only terminal states")
    if machine.get("legal_hold_silent_activation") is not False:
        fail("PRV-LEGAL-HOLD", "deletion_state_machine",
             "a legal hold is never activated silently")

    # -- 15 destinatarios externos ----------------------------------------
    recipient_state_fields = (
        "contract_state", "region_state", "role_state",
        "deletion_support_state", "rights_support_state",
    )
    for recipient in recipient_entries:
        location = f"recipient_registry[{recipient.get('id')}]"
        if recipient.get("kind") != "external":
            continue
        for field in recipient_state_fields:
            value = recipient.get(field)
            if not value:
                fail("PRV-RECIPIENT-STATE", location, f"external recipient missing {field}")
            elif str(value).lower() in ACCEPTED_TOKENS:
                fail("PRV-RECIPIENT-STATE", location,
                     f"{field} cannot be {value!r} before a human decision")
        if recipient.get("region_state") != REQUIRED_REGION_DECISION:
            fail("PRV-REGION-DECISION", location, "recipient region_state must stay pending_A-02")
        if recipient.get("selected") is not False:
            fail("PRV-RECIPIENT-STATE", location, "no external provider is selected during E0")
        if recipient.get("egress_default") != "deny":
            fail("PRV-RECIPIENT-STATE", location, "egress stays deny-by-default")

    # -- gates: ninguno superado ------------------------------------------
    for gate in model.get("gates", []):
        location = f"gates[{gate.get('id')}]"
        if gate.get("status") != "not_met":
            fail("PRV-GATE-STATUS", location, "an agent cannot mark a gate as met")
        if str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("PRV-GATE-STATUS", location, "gate acceptance stays pending_human")

    # -- decisiones abiertas ----------------------------------------------
    for decision in model.get("unresolved_decisions", []):
        location = f"unresolved_decisions[{decision.get('id')}]"
        if decision.get("state") != "pending_human":
            fail("PRV-DECISION-STATE", location, "unresolved decisions stay pending_human")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia executable privacy map")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/privacy/privacy-map.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    parser.add_argument("--threat-model", type=Path, default=Path("docs/security/threat-model.json"))
    args = parser.parse_args()
    repository_root = Path.cwd()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    dfd_model = json.loads(args.dfd.read_text(encoding="utf-8"))
    threat_model = json.loads(args.threat_model.read_text(encoding="utf-8"))
    errors = validate_model(model, dfd_model, threat_model, repository_root)
    print(json.dumps(
        {"errors": [error.as_dict() for error in errors], "ok": not errors},
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
