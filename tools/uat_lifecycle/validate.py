from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "docs" / "platform" / "uat-lifecycle.json"


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    environments = contract.get("environments", {})
    uat = environments.get("uat", {})
    production = environments.get("production", {})
    isolation = contract.get("isolation", {})
    promotion = contract.get("promotion", {})
    reset = contract.get("reset", {})

    if contract.get("decision") != "ADR-033":
        errors.append("UAT-DECISION")
    if uat.get("purpose") != "user_acceptance_testing" or uat.get("resettable") is not True:
        errors.append("UAT-ENVIRONMENT")
    if uat.get("production_traffic") is not False:
        errors.append("UAT-NOT-PRODUCTION")
    if production.get("resettable") is not False:
        errors.append("PRODUCTION-NOT-RESETTABLE")
    if production.get("state") != "not_provisioned":
        errors.append("PRODUCTION-STATE")
    if isolation.get("shared_resource_kinds") != []:
        errors.append("ENVIRONMENT-SHARED-STATE")

    required_separation = {
        "postgresql", "object_storage", "valkey", "kms_keys", "secrets",
        "identity_pool", "backups", "audit_sink",
    }
    if set(isolation.get("required_separate_resource_kinds", [])) != required_separation:
        errors.append("ENVIRONMENT-SEPARATION-INCOMPLETE")

    if promotion.get("unit") != "immutable_artifact_digest":
        errors.append("PROMOTION-NOT-IMMUTABLE")
    for field in ("copy_uat_database", "copy_uat_accounts", "copy_uat_objects"):
        if promotion.get(field) is not False:
            errors.append(f"PROMOTION-DATA-COPY:{field}")
    for field in ("require_supply_chain_attestation", "require_uat_acceptance_evidence"):
        if promotion.get(field) is not True:
            errors.append(f"PROMOTION-EVIDENCE:{field}")

    if reset.get("strategy") != "replace_uat_data_plane":
        errors.append("RESET-IN-PLACE-FORBIDDEN")
    if reset.get("web_trigger_available") is not False:
        errors.append("RESET-WEB-TRIGGER")
    ttl = reset.get("confirmation_token_ttl_seconds")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0 or ttl > 900:
        errors.append("RESET-TOKEN-TTL")
    if not reset.get("production_resource_patterns_forbidden"):
        errors.append("RESET-PRODUCTION-DENYLIST")
    if not reset.get("allowlisted_resource_kinds"):
        errors.append("RESET-ALLOWLIST")

    required_preconditions = {
        "environment_identity_is_uat", "new_writes_frozen",
        "resource_inventory_captured", "backup_completed",
        "restore_drill_passed", "confirmation_token_valid",
        "target_allowlist_exact", "production_targets_absent",
    }
    if set(reset.get("required_preconditions", [])) != required_preconditions:
        errors.append("RESET-PREFLIGHT-INCOMPLETE")

    required_postconditions = {
        "migrations_replayed_from_zero", "bootstrap_reference_reconfigured",
        "initial_superadmin_reclaimed", "old_sessions_invalidated",
        "old_uat_keys_retired", "health_and_tenancy_smoke_passed",
        "evidence_manifest_persisted",
    }
    if set(reset.get("required_postconditions", [])) != required_postconditions:
        errors.append("RESET-POSTCONDITIONS-INCOMPLETE")
    if reset.get("bootstrap_policy") != "reconfigure_reference_never_copy_assignment":
        errors.append("RESET-BOOTSTRAP-COPY")
    if reset.get("execution_state") != "disabled_pending_rehearsal_and_independent_review":
        errors.append("RESET-PREMATURELY-ENABLED")
    if set(contract.get("reviews_required", [])) != {
        "Security", "Privacy/Legal", "Architecture/Database", "SRE", "QA",
    }:
        errors.append("RESET-REVIEWS-INCOMPLETE")
    return errors


def main() -> int:
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    errors = validate_contract(contract)
    print(json.dumps({"errors": errors, "ok": not errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
