from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_PRINCIPLES = {
    "DED-SEPARATE-LAYERS", "DED-CANDIDATE-NOT-IDENTITY", "DED-PRESERVE-EVIDENCE",
    "DED-LEGITIMATE-IDENTICAL", "IDEM-ATOMIC-DATABASE", "IDEM-ONE-RETRY-OWNER",
    "IDEM-OUTBOX", "IDEM-CONFLICT-EXPLICIT", "IDEM-COMPANY-SCOPE",
    "IDEM-NO-RAW-KEYS-IN-LOGS",
}
REQUIRED_LAYERS = {
    "transport_delivery", "artifact_bytes", "source_observation", "economic_event",
    "published_effect",
}
REQUIRED_HARD_RULES = {
    "IDEM-ARTIFACT-EXACT", "IDEM-PROVIDER-EVENT", "IDEM-COMMAND",
    "IDEM-PROCESSING", "IDEM-PUBLICATION",
}
REQUIRED_CANDIDATES = {
    "CAND-SOURCE-OVERLAP", "CAND-MOVEMENT-SIMILARITY", "CAND-PROVIDER-ID-UNVERIFIED",
}
REQUIRED_FORBIDDEN_UNIQUENESS = {
    "NO-BUSINESS-COMPOSITE", "NO-DEDUPE-FINGERPRINT", "NO-SOURCE-LOCATOR-ALONE",
    "NO-NORMALIZED-PAYLOAD-ALONE",
}
REQUIRED_TESTS = {
    "TST-DED-001", "TST-DED-002", "TST-DED-003", "TST-DED-004", "TST-DED-005",
    "TST-IDEM-001", "TST-IDEM-002", "TST-IDEM-003", "TST-IDEM-004",
    "TST-IDEM-005", "TST-IDEM-006", "TST-IDEM-007",
}
REQUIRED_PROVIDER_EVIDENCE = {
    "documented_namespace_and_scope", "documented_immutability_or_revision_semantics",
    "replay_and_id_reuse_tests", "connector_version_binding",
    "owner_and_independent_reviewer", "observed_collision_rate_zero_in_approved_corpus",
}
REQUIRED_DECISION_FIELDS = {
    "company_id", "candidate_id", "left_movement_id", "right_movement_id", "decision",
    "reason_code", "evidence_refs", "decided_by", "decided_at", "rule_version",
    "engine_release_id", "audit_event_id", "reverses_decision_id",
}
REQUIRED_CORRECTNESS = {
    "database_unique_constraint", "database_transaction", "compare_and_set",
    "transactional_outbox", "fencing_token",
}
FORBIDDEN_SOLE_CORRECTNESS = {
    "application_precheck", "valkey_lock", "process_mutex", "delivery_order",
    "exactly_once_broker_claim",
}


@dataclass(frozen=True, order=True)
class IdempotencyModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {item["id"]: item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _entity(canonical: dict[str, Any], entity_id: str) -> dict[str, Any]:
    return next((item for item in canonical.get("entities", []) if item.get("id") == entity_id), {})


def _architecture_owner(architecture: dict[str, Any], entity_id: str) -> str | None:
    for module in architecture.get("modules", []):
        if entity_id in module.get("owns", []):
            return module.get("id")
    return None


def _exact_catalog(
    errors: list[IdempotencyModelError], items: Any, expected: set[str], location: str, code: str
) -> None:
    identifiers = _ids(items)
    if set(identifiers) != expected or len(identifiers) != len(expected):
        errors.append(IdempotencyModelError(code, location, f"ids must be exact; got {identifiers}"))


def validate_model(
    model: dict[str, Any],
    canonical: dict[str, Any],
    architecture: dict[str, Any],
    dfd: dict[str, Any],
) -> list[IdempotencyModelError]:
    errors: list[IdempotencyModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(IdempotencyModelError(code, location, message))

    if model.get("schema_version") != 1 or model.get("task_id") != "FNC-DOM-004":
        fail("IDM-METADATA", "$", "schema_version 1 and task FNC-DOM-004 are required")
    if model.get("status") != "review_pending" or model.get("human_acceptance") != "pending":
        fail("IDM-ACCEPTANCE", "$", "human acceptance must remain pending")
    if model.get("data_ceiling") != "synthetic_only":
        fail("IDM-DATA-CEILING", "data_ceiling", "only synthetic data is allowed")
    if model.get("execution_mode") != "contract_only_no_productive_merge":
        fail("IDM-EXECUTION", "execution_mode", "productive merge must stay disabled")

    _exact_catalog(errors, model.get("principles"), REQUIRED_PRINCIPLES, "principles", "IDM-PRINCIPLES")
    _exact_catalog(errors, model.get("identity_layers"), REQUIRED_LAYERS, "identity_layers", "IDM-LAYERS")
    _exact_catalog(errors, model.get("hard_idempotency_rules"), REQUIRED_HARD_RULES, "hard_idempotency_rules", "IDM-HARD-RULES")
    _exact_catalog(errors, model.get("candidate_rules"), REQUIRED_CANDIDATES, "candidate_rules", "IDM-CANDIDATES")
    _exact_catalog(errors, model.get("forbidden_hard_uniqueness"), REQUIRED_FORBIDDEN_UNIQUENESS, "forbidden_hard_uniqueness", "IDM-FORBIDDEN-UNIQUE")
    _exact_catalog(errors, model.get("required_tests"), REQUIRED_TESTS, "required_tests", "IDM-TEST-COVERAGE")

    layers = _by_id(model.get("identity_layers"))
    expected_entities = {
        "transport_delivery": "inbox_receipt",
        "artifact_bytes": "artifact_version",
        "source_observation": "source_record",
        "economic_event": "money_movement",
        "published_effect": "outbox_event",
    }
    for layer_id, entity_id in expected_entities.items():
        if layers.get(layer_id, {}).get("authoritative_entity") != entity_id:
            fail("IDM-LAYER-ENTITY", f"identity_layers.{layer_id}", f"must use {entity_id}")
    if layers.get("economic_event", {}).get("hard_identity_allowed") is not False:
        fail("IDM-ECONOMIC-HARD-ID", "identity_layers.economic_event", "business events cannot use hard attribute identity")
    if layers.get("source_observation", {}).get("hard_identity_allowed") != "only_with_verified_provider_identity_contract":
        fail("IDM-SOURCE-ASSURANCE", "identity_layers.source_observation", "provider identity contract is required")

    owners = {
        "inbox_receipt": "platform", "artifact_version": "ingestion", "source_record": "clean",
        "money_movement": "finance", "outbox_event": "platform", "dedupe_candidate": "finance",
        "dedupe_decision": "finance",
    }
    for entity_id, expected_owner in owners.items():
        actual = _architecture_owner(architecture, entity_id)
        if actual != expected_owner:
            fail("IDM-ARCHITECTURE-OWNER", f"architecture.{entity_id}", f"expected {expected_owner}, got {actual}")

    rules = _by_id(model.get("hard_idempotency_rules"))
    for rule_id, rule in rules.items():
        if rule.get("atomic_mechanism") in {None, "application_precheck", "valkey_lock"}:
            fail("IDM-ATOMICITY", f"hard_idempotency_rules.{rule_id}", "database atomicity is required")
        if rule.get("same_key_same_payload") in {None, "create_second_effect"}:
            fail("IDM-REPLAY", f"hard_idempotency_rules.{rule_id}", "same payload replay must not create a second effect")
        if rule.get("same_key_different_payload") in {None, "acknowledge_existing_receipt", "return_success"}:
            fail("IDM-PAYLOAD-CONFLICT", f"hard_idempotency_rules.{rule_id}", "different payload must conflict")

    artifact = rules.get("IDEM-ARTIFACT-EXACT", {})
    if artifact.get("scope_fields") != ["company_id", "data_source_id"] or artifact.get("identity_material") != ["content_sha256_exact_bytes"]:
        fail("IDM-ARTIFACT-KEY", "hard_idempotency_rules.IDEM-ARTIFACT-EXACT", "exact artifact key changed")
    provider = rules.get("IDEM-PROVIDER-EVENT", {})
    if provider.get("scope_fields") != ["connection_id"] or provider.get("identity_material") != ["provider_event_id_hmac"]:
        fail("IDM-PROVIDER-KEY", "hard_idempotency_rules.IDEM-PROVIDER-EVENT", "provider receipt must be connection scoped and HMACed")
    if provider.get("payload_digest") != "canonical_transport_payload_sha256":
        fail("IDM-PROVIDER-DIGEST", "hard_idempotency_rules.IDEM-PROVIDER-EVENT", "payload digest is required")
    command = rules.get("IDEM-COMMAND", {})
    if set(command.get("scope_fields", [])) != {"company_id", "principal_id", "operation_id"}:
        fail("IDM-COMMAND-SCOPE", "hard_idempotency_rules.IDEM-COMMAND", "command scope is incomplete")
    processing = rules.get("IDEM-PROCESSING", {})
    if set(processing.get("identity_material", [])) != {"parser_version", "recipe_version", "canonical_schema_version", "engine_release_id"}:
        fail("IDM-PROCESSING-VERSION", "hard_idempotency_rules.IDEM-PROCESSING", "all engine versions are required")
    publication = rules.get("IDEM-PUBLICATION", {})
    if publication.get("atomic_mechanism") != "domain_transaction_with_unique_outbox_record":
        fail("IDM-PUBLICATION-OUTBOX", "hard_idempotency_rules.IDEM-PUBLICATION", "domain and outbox must be atomic")

    provider_contract = model.get("provider_identity_contract", {})
    if set(provider_contract.get("states", [])) != {"unverified", "verified", "suspended"}:
        fail("IDM-PROVIDER-STATES", "provider_identity_contract.states", "provider states must remain exact")
    if provider_contract.get("default_state") != "unverified" or provider_contract.get("unverified_effect") != "candidate_only_never_hard_identity":
        fail("IDM-PROVIDER-DEFAULT", "provider_identity_contract", "unknown provider identity must fail closed")
    if set(provider_contract.get("verified_requires", [])) != REQUIRED_PROVIDER_EVIDENCE:
        fail("IDM-PROVIDER-EVIDENCE", "provider_identity_contract.verified_requires", "verification evidence is incomplete")
    if not {"identifier_reuse", "scope_drift", "semantic_drift", "unexplained_collision"} <= set(provider_contract.get("suspended_on", [])):
        fail("IDM-PROVIDER-SUSPEND", "provider_identity_contract.suspended_on", "suspension triggers are incomplete")

    for candidate_id, candidate in _by_id(model.get("candidate_rules")).items():
        if candidate.get("unique_constraint_forbidden") is not True:
            fail("IDM-CANDIDATE-UNIQUE", f"candidate_rules.{candidate_id}", "candidate fingerprint cannot be unique")
        if candidate.get("automatic_effect") != "none":
            fail("IDM-CANDIDATE-AUTO", f"candidate_rules.{candidate_id}", "candidate cannot mutate domain state")
        if not candidate.get("features"):
            fail("IDM-CANDIDATE-FEATURES", f"candidate_rules.{candidate_id}", "candidate features cannot be empty")

    forbidden = _by_id(model.get("forbidden_hard_uniqueness"))
    expected_business_fields = {"company_id", "financial_account_id", "posting_date", "amount", "direction", "reference"}
    if set(forbidden.get("NO-BUSINESS-COMPOSITE", {}).get("fields", [])) != expected_business_fields:
        fail("IDM-BUSINESS-COMPOSITE", "forbidden_hard_uniqueness.NO-BUSINESS-COMPOSITE", "business composite must remain forbidden")

    fingerprint = model.get("fingerprint_policy", {})
    expected_fingerprint = {
        "exact_artifact_hash": "sha256_over_original_bytes_before_transformation",
        "transport_payload_digest": "deterministic_canonicalization_defined_per_connector_version",
        "candidate_fingerprint": "versioned_hmac_over_normalized_candidate_features",
        "candidate_fingerprint_secret": "vault_managed_rotatable_key",
    }
    for field, value in expected_fingerprint.items():
        if fingerprint.get(field) != value:
            fail("IDM-FINGERPRINT", f"fingerprint_policy.{field}", f"must equal {value}")
    if fingerprint.get("raw_values_in_logs") is not False or fingerprint.get("hash_or_hmac_is_not_anonymization") is not True:
        fail("IDM-FINGERPRINT-PRIVACY", "fingerprint_policy", "hashes cannot weaken log/privacy rules")

    inbox = model.get("inbox_state_machine", {})
    required_inbox_states = {"received", "processing", "succeeded", "retryable_failed", "terminal_failed", "conflict"}
    if set(inbox.get("states", [])) != required_inbox_states or set(inbox.get("terminal", [])) != {"succeeded", "terminal_failed", "conflict"}:
        fail("IDM-INBOX-STATES", "inbox_state_machine", "inbox states or terminals changed")
    if inbox.get("retry_owner") != "platform_durable_workflow" or inbox.get("lease_requires_fencing_token") is not True:
        fail("IDM-INBOX-RETRY", "inbox_state_machine", "workflow ownership and fencing are required")
    if inbox.get("application_precheck_is_authority") is not False:
        fail("IDM-INBOX-PRECHECK", "inbox_state_machine", "application precheck cannot be authoritative")

    decision = model.get("dedupe_decision_contract", {})
    if decision.get("owner_module") != "finance" or set(decision.get("entities", [])) != {"dedupe_candidate", "dedupe_decision"}:
        fail("IDM-DEDUPE-OWNER", "dedupe_decision_contract", "Finance owns dedupe candidate and decision")
    if set(decision.get("required_fields", [])) != REQUIRED_DECISION_FIELDS:
        fail("IDM-DEDUPE-FIELDS", "dedupe_decision_contract.required_fields", "decision fields are incomplete")
    if set(decision.get("candidate_states", [])) != {"open", "confirmed_same_event", "confirmed_distinct", "dismissed", "superseded"}:
        fail("IDM-DEDUPE-STATES", "dedupe_decision_contract.candidate_states", "candidate states changed")
    required_decision_values = {
        "decision_history": "append_only",
        "reversal": "new_decision_referencing_prior_decision",
        "confirmed_same_event_product_effect": "blocked_until_accounting_and_architecture_define_supersession_semantics",
    }
    for field, value in required_decision_values.items():
        if decision.get(field) != value:
            fail("IDM-DEDUPE-HISTORY", f"dedupe_decision_contract.{field}", f"must equal {value}")
    for field in ("source_evidence_deleted", "movement_physical_delete", "automatic_same_event_decision_enabled"):
        if decision.get(field) is not False:
            fail("IDM-DEDUPE-DESTRUCTIVE", f"dedupe_decision_contract.{field}", "destructive or automatic dedupe is forbidden")

    concurrency = model.get("concurrency_contract", {})
    if set(concurrency.get("correctness_primitives", [])) != REQUIRED_CORRECTNESS:
        fail("IDM-CONCURRENCY-PRIMITIVES", "concurrency_contract.correctness_primitives", "correctness primitives are incomplete")
    if set(concurrency.get("forbidden_as_sole_correctness", [])) != FORBIDDEN_SOLE_CORRECTNESS:
        fail("IDM-CONCURRENCY-FORBIDDEN", "concurrency_contract.forbidden_as_sole_correctness", "unsafe primitives must remain forbidden")
    if concurrency.get("retry_owner") != "platform_durable_workflow" or concurrency.get("domain_handler_schedules_retries") is not False or concurrency.get("connector_schedules_retries") is not False:
        fail("IDM-RETRY-OWNER", "concurrency_contract", "exactly one workflow owns retries")
    if concurrency.get("outbox_same_transaction_as_domain_change") is not True or concurrency.get("consumer_receipt_before_effect_forbidden") is not True:
        fail("IDM-OUTBOX", "concurrency_contract", "outbox/effect ordering is unsafe")

    security = model.get("security_contract", {})
    if security.get("company_scope_source") != "server_verified_authorization_context" or security.get("cross_company_candidate_forbidden") is not True:
        fail("IDM-COMPANY-SCOPE", "security_contract", "company scope must be server verified and isolated")
    for required_true in ("raw_identifier_log_forbidden", "provider_signature_verified_before_claim", "conflict_is_security_signal"):
        if security.get(required_true) is not True:
            fail("IDM-SECURITY", f"security_contract.{required_true}", "security control cannot be disabled")

    artifact_entity = _entity(canonical, "artifact_version")
    artifact_constraints = {item.get("id"): item for item in artifact_entity.get("unique_constraints", [])}
    exact_constraint = artifact_constraints.get("uq_exact_artifact_redelivery", {})
    if set(exact_constraint.get("fields", [])) != {"company_id", "data_source_id", "content_sha256"} or exact_constraint.get("kind") != "hard_idempotency":
        fail("IDM-CANONICAL-ARTIFACT", "canonical.artifact_version", "exact artifact constraint is missing")
    movement = _entity(canonical, "money_movement")
    for constraint in movement.get("unique_constraints", []):
        if constraint.get("kind") != "entity_identity":
            fail("IDM-CANONICAL-MOVEMENT-UNIQUE", "canonical.money_movement", "business movement uniqueness is forbidden")
    movement_fields = {item.get("name"): item for item in movement.get("fields", [])}
    if movement_fields.get("dedupe_fingerprint", {}).get("value_rule") != "candidate_only_never_unique":
        fail("IDM-CANONICAL-FINGERPRINT", "canonical.money_movement.dedupe_fingerprint", "fingerprint must stay candidate-only")
    evidence_link = _entity(canonical, "movement_evidence_link")
    if {rel.get("target") for rel in evidence_link.get("relationships", [])} != {"money_movement", "source_record"}:
        fail("IDM-CANONICAL-EVIDENCE", "canonical.movement_evidence_link", "movement/evidence separation is missing")

    threat_ids = _ids(dfd.get("threat_catalog", []))
    control_ids = _ids(dfd.get("control_catalog", []))
    if "T12" not in threat_ids or "C-IDEMP" not in control_ids:
        fail("IDM-DFD-COVERAGE", "dfd", "duplicate effect threat and idempotency control are required")

    return sorted(errors)


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FNC-DOM-004 executable contract")
    parser.add_argument("--model", type=Path, default=Path("docs/domain/idempotency-dedupe.json"))
    parser.add_argument("--canonical", type=Path, default=Path("docs/domain/canonical-model.json"))
    parser.add_argument("--architecture", type=Path, default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    args = parser.parse_args()
    errors = validate_model(_load(args.model), _load(args.canonical), _load(args.architecture), _load(args.dfd))
    print(json.dumps({"errors": [item.as_dict() for item in errors], "ok": not errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
