from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = {
    "connector_id", "version", "countries", "source_kind", "institutions", "account_types",
    "auth", "history", "identity", "freshness", "error_taxonomy", "completeness",
    "fallback", "region", "subprocessors", "cost", "owner",
}
REQUIRED_CAPABILITIES = {
    "read_accounts", "read_transactions", "read_balances", "backfill", "incremental",
    "webhook", "corrections", "pending_to_posted",
}
REQUIRED_CONTROLS = {
    "record_count", "debit_total", "credit_total", "opening_balance", "closing_balance",
    "period_coverage", "sequence_cursor", "account_identity", "currency_consistency",
}
REQUIRED_GATES = {
    "GATE-COVERAGE", "GATE-IDENTITY", "GATE-COMPLETENESS", "GATE-SECURITY",
    "GATE-PRIVACY-LEGAL", "GATE-SLA-COST", "GATE-FALLBACK",
}
REQUIRED_TESTS = {f"TST-CON-{index:03d}" for index in range(1, 16)}
FORBIDDEN_AUTH = {"bank_username", "bank_password", "otp", "private_certificate", "raw_access_token"}


@dataclass(frozen=True, order=True)
class ConnectorModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _gate_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def validate_model(
    model: dict[str, Any], manifest_schema: dict[str, Any], completeness: dict[str, Any],
    idempotency: dict[str, Any], events: dict[str, Any], privacy: dict[str, Any],
) -> list[ConnectorModelError]:
    errors: list[ConnectorModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(ConnectorModelError(code, location, message))

    if model.get("schema_version") != 1 or model.get("task_id") != "FNC-ARC-005":
        fail("CON-METADATA", "$", "schema 1 and task FNC-ARC-005 are required")
    if model.get("status") != "review_pending" or model.get("human_acceptance") != "pending":
        fail("CON-ACCEPTANCE", "$", "human acceptance must remain pending")
    if model.get("data_ceiling") != "synthetic_only":
        fail("CON-DATA", "data_ceiling", "only synthetic data is allowed")
    if model.get("mode") != "read_only" or model.get("payments_enabled") is not False:
        fail("CON-SCOPE", "$", "connector remains read-only with payments disabled")
    if model.get("platform_receives_bank_credentials") is not False:
        fail("CON-CREDENTIALS", "platform_receives_bank_credentials", "platform cannot receive bank credentials")

    sections = set(model.get("manifest_required_sections", []))
    schema_sections = set(manifest_schema.get("required", []))
    if sections != REQUIRED_SECTIONS or schema_sections != REQUIRED_SECTIONS:
        fail("CON-MANIFEST-SECTIONS", "manifest_required_sections", "model and JSON Schema required sections must be exact")
    if manifest_schema.get("additionalProperties") is not False:
        fail("CON-MANIFEST-CLOSED", "connector-manifest.schema.json", "manifest must reject unknown top-level fields")

    if set(model.get("lifecycle_states", [])) != {"draft", "review_pending", "certified", "suspended", "retired"}:
        fail("CON-LIFECYCLE", "lifecycle_states", "connector lifecycle changed")
    capability = model.get("capability_contract", {})
    if set(capability.get("required", [])) != REQUIRED_CAPABILITIES:
        fail("CON-CAPABILITIES", "capability_contract.required", "capability evidence is incomplete")
    if set(capability.get("truth_values", [])) != {"supported", "unsupported", "unknown_pending_evidence"} or capability.get("unknown_is_not_supported") is not True:
        fail("CON-CAPABILITY-UNKNOWN", "capability_contract", "unknown cannot be treated as supported")
    if capability.get("write_capabilities_default") != "forbidden":
        fail("CON-WRITE", "capability_contract.write_capabilities_default", "write capabilities default forbidden")

    auth = model.get("authorization_contract", {})
    if set(auth.get("forbidden_inputs", [])) != FORBIDDEN_AUTH:
        fail("CON-AUTH-FORBIDDEN", "authorization_contract.forbidden_inputs", "forbidden credentials changed")
    if auth.get("secret_storage") != "vault_reference_only":
        fail("CON-SECRET-STORAGE", "authorization_contract.secret_storage", "secrets must remain vault references")
    for field in ("minimum_scopes", "consent_expiry_visible", "revocation_supported", "authorization_version_required", "revalidate_before_fetch_and_publish"):
        if auth.get(field) is not True:
            fail("CON-AUTH", f"authorization_contract.{field}", "authorization control cannot be disabled")

    sync = model.get("sync_contract", {})
    if set(sync.get("cursor_scope", [])) != {"company_id", "connection_id", "account_id", "connector_version"}:
        fail("CON-CURSOR-SCOPE", "sync_contract.cursor_scope", "cursor scope is incomplete")
    for field in ("pagination_required", "cursor_versioned", "page_evidence_required", "overlap_window_versioned", "pending_never_aliases_posted", "correction_is_new_version", "deletion_is_tombstone_or_explicit_provider_event"):
        if sync.get(field) is not True:
            fail("CON-SYNC", f"sync_contract.{field}", "sync invariant cannot be disabled")
    if sync.get("empty_page_means_complete") is not False:
        fail("CON-EMPTY-PAGE", "sync_contract.empty_page_means_complete", "empty page is not completeness proof")

    identity = model.get("identity_contract", {})
    if identity.get("default_assurance") != "unverified" or identity.get("verified_requires_dom004_provider_contract") is not True:
        fail("CON-IDENTITY", "identity_contract", "provider identity must start unverified and follow DOM-004")
    if identity.get("business_composite_unique_forbidden") is not True or identity.get("cross_source_dedupe_candidate_only") is not True:
        fail("CON-DEDUPE", "identity_contract", "cross-source similarity cannot become hard identity")

    complete = model.get("completeness_contract", {})
    if set(complete.get("required_controls", [])) != REQUIRED_CONTROLS:
        fail("CON-COMPLETENESS-CONTROLS", "completeness_contract.required_controls", "control set is incomplete")
    if complete.get("unavailable_required_control") != "unknown":
        fail("CON-COMPLETENESS-UNKNOWN", "completeness_contract", "unavailable control must be unknown")
    if complete.get("pagination_exhaustion_alone_is_proof") is not False or complete.get("balance_or_match_coverage_alone_is_proof") is not False:
        fail("CON-COMPLETENESS-PROOF", "completeness_contract", "weak completeness proof is forbidden")
    if complete.get("publication_requires_verified_or_explicit_exception") is not True or complete.get("exception_requires_sod_expiry_evidence") is not True:
        fail("CON-COMPLETENESS-PUBLISH", "completeness_contract", "publication/exception gate is incomplete")

    retry = model.get("retry_contract", {})
    if retry.get("adapter_retries") is not False or retry.get("circuit_breaker_schedules_retry") is not False:
        fail("CON-RETRY-OWNER", "retry_contract", "adapter and circuit breaker cannot retry")
    if set(retry.get("failure_classes", [])) != {"retryable", "rate_limited", "fatal", "requires_human", "unknown"}:
        fail("CON-ERROR-TAXONOMY", "retry_contract.failure_classes", "failure taxonomy must align ARC-004")
    if retry.get("schedule_owner") != "parent_queue_or_durable_workflow" or retry.get("unknown_outcome") != "reconcile_before_retry":
        fail("CON-RETRY-SAFETY", "retry_contract", "retry ownership/outcome is unsafe")

    webhook = model.get("webhook_contract", {})
    for field in ("signature_before_inbox", "timestamp_nonce_replay_required", "payload_digest_required", "connection_scoped_idempotency", "manual_replay_audited"):
        if webhook.get(field) is not True:
            fail("CON-WEBHOOK", f"webhook_contract.{field}", "webhook control cannot be disabled")
    if webhook.get("same_id_different_payload") != "conflict_suspend_and_investigate":
        fail("CON-WEBHOOK-CONFLICT", "webhook_contract.same_id_different_payload", "payload conflict must suspend")

    fallback = model.get("fallback_contract", {})
    for field in ("file_supported", "permanent_not_temporary", "same_canonical_model", "same_completeness_gates", "same_lineage_and_evidence", "feed_failure_does_not_block_file", "overlap_creates_candidate_not_delete", "visible_in_product"):
        if fallback.get(field) is not True:
            fail("CON-FALLBACK", f"fallback_contract.{field}", "permanent file fallback cannot be weakened")

    if set(model.get("degraded_states", [])) != {"healthy", "stale", "provider_down", "auth_expired", "partial", "schema_drift", "suspended"}:
        fail("CON-DEGRADED-STATES", "degraded_states", "degraded states changed")
    degraded = model.get("degraded_contract", {})
    for field in ("last_success_and_freshness_visible", "gap_and_cursor_visible", "never_assume_zero_or_complete", "schema_drift_blocks_publication", "fallback_action_visible"):
        if degraded.get(field) is not True:
            fail("CON-DEGRADED", f"degraded_contract.{field}", "degraded behavior must fail visibly")

    security = model.get("security_contract", {})
    for field in ("egress_allowlist_versioned", "ssrf_private_ranges_and_redirects_blocked", "tls_required", "short_lived_capability", "company_scope_server_resolved", "raw_payload_or_secret_logs_forbidden", "worker_direct_internet_forbidden", "connector_gateway_only"):
        if security.get(field) is not True:
            fail("CON-SECURITY", f"security_contract.{field}", "security control cannot be disabled")

    legal = model.get("legal_cost_contract", {})
    for field in ("region_state", "subprocessors_state", "dpa_state", "retention_state", "sla_state"):
        if legal.get(field) != "pending_human":
            fail("CON-LEGAL-PENDING", f"legal_cost_contract.{field}", "human decision must remain pending")
    if legal.get("cost_state") != "pending_quote_and_max_usage_model" or legal.get("no_production_before_approval") is not True:
        fail("CON-COST-PENDING", "legal_cost_contract", "cost/production gate remains pending")

    gate_ids = _gate_ids(model.get("certification_gates"))
    if set(gate_ids) != REQUIRED_GATES or len(gate_ids) != len(REQUIRED_GATES):
        fail("CON-GATES", "certification_gates", "certification gates must be exact")
    for gate in model.get("certification_gates", []):
        if gate.get("state") != "pending_human" or not gate.get("owner") or not gate.get("reviewer") or gate.get("owner") == gate.get("reviewer"):
            fail("CON-GATE-PENDING", f"certification_gates.{gate.get('id')}", "gate needs pending human independent review")
    if set(model.get("required_tests", [])) != REQUIRED_TESTS or len(model.get("required_tests", [])) != len(REQUIRED_TESTS):
        fail("CON-TESTS", "required_tests", "required tests must be exact")

    dom_controls = {item.get("id") for item in completeness.get("control_types", [])}
    if not {"record_count", "debit_total", "credit_total", "opening_balance", "closing_balance", "period_coverage", "sequence_cursor", "account_identity", "currency_consistency"} <= dom_controls:
        fail("CON-DOM003", "completeness-balances.json", "DOM-003 controls are missing")
    if idempotency.get("provider_identity_contract", {}).get("default_state") != "unverified":
        fail("CON-DOM004", "idempotency-dedupe.json", "DOM-004 provider identity must default unverified")
    if events.get("retry_policy_contract", {}).get("adapter_schedules_retry") is not False:
        fail("CON-ARC004", "events-retries.json", "ARC-004 adapter retry alignment failed")
    if privacy.get("external_ai_policy", {}).get("enabled") is True:
        fail("CON-PRIVACY", "privacy-map.json", "connector cannot enable unrelated external AI")

    return sorted(errors)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FNC-ARC-005 connector contract")
    parser.add_argument("--model", type=Path, default=Path("docs/contracts/connectors/connector-contract.json"))
    parser.add_argument("--manifest-schema", type=Path, default=Path("docs/contracts/connectors/connector-manifest.schema.json"))
    parser.add_argument("--completeness", type=Path, default=Path("docs/domain/completeness-balances.json"))
    parser.add_argument("--idempotency", type=Path, default=Path("docs/domain/idempotency-dedupe.json"))
    parser.add_argument("--events", type=Path, default=Path("docs/architecture/events-retries.json"))
    parser.add_argument("--privacy", type=Path, default=Path("docs/privacy/privacy-map.json"))
    args = parser.parse_args()
    errors = validate_model(*(_load(path) for path in (args.model, args.manifest_schema, args.completeness, args.idempotency, args.events, args.privacy)))
    print(json.dumps({"errors": [item.as_dict() for item in errors], "ok": not errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
