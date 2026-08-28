"""Reglas fail-closed del laboratorio que aún no existe.

Un diseño válido no prueba implementación. Por eso toda evidencia y control debe
permanecer en ``not_run``/``false`` hasta FNC-PLT-004 y FNC-QA-001.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


SOURCE_PATHS = {
    "THREAT": "docs/security/threat-model.json",
    "PRIVACY": "docs/privacy/privacy-map.json",
    "REGION": "docs/architecture/region-transmission-decision.json",
    "RETENTION": "docs/privacy/retention-deletion-matrix.json",
}
CONTROL_IDS = frozenset({
    "IAM-01", "IAM-02", "IAM-03", "IAM-04", "IAM-05", "IAM-06", "IAM-07",
    "NET-01", "NET-02", "NET-03", "NET-04", "NET-05", "NET-06", "NET-07",
    "CMP-01", "CMP-02", "CMP-03", "CMP-04", "CMP-05", "CMP-06",
    "DAT-01", "DAT-02", "DAT-03", "DAT-04", "DAT-05", "DAT-06", "DAT-07",
    "STO-01", "STO-02", "STO-03", "STO-04", "OBS-01", "OBS-02",
    "OPS-01", "OPS-02", "OPS-03", "OPS-04",
})
CRITICAL_REQUIREMENTS = {
    "IAM-01": "managed_idp_required_no_local_password_authority_for_real_data",
    "IAM-02": "named_human_subjects_only_no_shared_accounts",
    "IAM-03": "phishing_resistant_mfa_required",
    "IAM-04": "aal3_step_up_for_approval_export_delete_and_break_glass",
    "IAM-05": "jit_privilege_maximum_60_minutes",
    "IAM-06": "short_lived_workload_identity_no_static_credentials",
    "IAM-07": "break_glass_requires_dual_control_and_post_review",
    "NET-01": "no_public_endpoint_or_public_ip",
    "NET-02": "ingress_default_deny",
    "NET-03": "egress_default_deny",
    "NET-04": "quarantine_and_processing_have_zero_external_egress",
    "NET-05": "stores_and_control_plane_use_private_endpoints_only",
    "NET-06": "dns_and_egress_allowlists_are_empty_until_a02",
    "NET-07": "management_uses_audited_identity_aware_broker",
    "CMP-01": "signed_pinned_image_and_verified_provenance",
    "CMP-02": "non_root_read_only_root_filesystem",
    "CMP-03": "no_privileged_mode_host_mount_or_host_namespace",
    "CMP-04": "no_dynamic_package_install_or_network_fallback",
    "CMP-05": "encrypted_ephemeral_scratch_destroyed_after_run",
    "CMP-06": "per_run_company_capability_and_authorization_revalidation",
    "DAT-01": "approved_manifest_and_gate_evidence_required_before_intake",
    "DAT-02": "opaque_object_key_and_quarantine_before_any_parser",
    "DAT-03": "fail_closed_malware_active_content_pan_and_prohibited_content_scan",
    "DAT-04": "accepted_raw_version_is_immutable_and_never_overwritten",
    "DAT-05": "company_scoped_storage_and_forced_rls",
    "DAT-06": "derived_output_has_complete_digest_lineage",
    "DAT-07": "external_ai_ocr_and_unselected_providers_forbidden",
    "STO-01": "separate_keys_and_access_paths_per_data_plane",
    "STO-02": "security_archive_and_delete_ledger_outside_ordinary_restore",
    "STO-03": "backup_region_and_window_blocked_until_a02_and_l01",
    "STO-04": "restore_reapplies_tombstones_and_reconciles_before_reopen",
    "OBS-01": "structured_allowlist_metadata_only",
    "OBS-02": "no_payload_amount_account_tax_id_filename_token_or_document_content",
    "OPS-01": "time_bounded_lab_with_destroy_and_inventory_reconciliation",
    "OPS-02": "incident_response_and_revocation_drill_before_intake",
    "OPS-03": "evidence_export_is_digest_only_and_independently_reviewed",
    "OPS-04": "support_access_disabled_unless_jit_dual_control",
}
ZONE_PURPOSES = {
    "Z-IN": "controlled_intake",
    "Z-Q": "untrusted_quarantine",
    "Z-P": "isolated_processing",
    "Z-E": "accepted_evidence",
    "Z-C": "control_plane",
    "Z-A": "security_archive_delete_ledger",
}
TEST_IDS = frozenset({f"LAB-T{value:02d}" for value in range(1, 13)})
PREREQUISITES = {
    "FNC-LEG-001": "review_pending",
    "L-01": "not_met",
    "A-02": "not_met",
    "S-01": "not_met",
    "SUPPLY-CHAIN": "not_met",
    "FNC-PLT-004": "not_started",
    "FNC-QA-001": "not_started",
}
GATE_IDS = frozenset({"S-01", "DRG-00", "DRG-01"})


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _finding(code: str, path: str, detail: str) -> Finding:
    return Finding(code, path, detail)


def canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_threats(threat: dict[str, Any]) -> set[str]:
    risks = threat.get("risks")
    if not isinstance(risks, list):
        return set()
    return {
        item["id"] for item in risks
        if isinstance(item, dict) and item.get("target_gate") == "DRG-00"
        and isinstance(item.get("id"), str)
    }


def validate(model: dict[str, Any], sources: dict[str, dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    required_top = {
        "schema_version", "task_id", "status", "data_ceiling",
        "real_data_authorized", "deployment_enabled", "source_contracts",
        "unresolved_selection", "trust_zones", "control_catalog",
        "threat_coverage", "acceptance_tests", "prerequisites",
        "human_review", "gate_claims",
    }
    if set(model) != required_top:
        findings.append(_finding("LAB-SCHEMA", "$", "top-level fields drifted"))
    if model.get("schema_version") != "1.0.0" or model.get("task_id") != "FNC-SEC-003":
        findings.append(_finding("LAB-IDENTITY", "$", "unsupported model identity"))
    if model.get("status") != "design_review_pending":
        findings.append(_finding("LAB-STATUS", "$.status", "design cannot self-approve"))
    if (model.get("data_ceiling") != "synthetic_only"
            or model.get("real_data_authorized") is not False
            or model.get("deployment_enabled") is not False):
        findings.append(_finding("LAB-REAL-DATA", "$", "design cannot deploy or authorize real data"))

    if set(sources) != set(SOURCE_PATHS):
        findings.append(_finding("LAB-SOURCES", "sources", "source set is incomplete"))
    contracts = model.get("source_contracts")
    if not isinstance(contracts, list):
        findings.append(_finding("LAB-SOURCE-CONTRACT", "$.source_contracts", "source contracts must be a list"))
        contracts = []
    contract_ids = [str(item.get("id")) for item in contracts if isinstance(item, dict)]
    if set(contract_ids) != set(SOURCE_PATHS) or len(contract_ids) != len(SOURCE_PATHS):
        findings.append(_finding("LAB-SOURCE-COVERAGE", "$.source_contracts", "source coverage drifted"))
    for index, item in enumerate(contracts):
        path = f"$.source_contracts[{index}]"
        if not isinstance(item, dict) or set(item) != {"id", "path", "canonical_sha256"}:
            findings.append(_finding("LAB-SOURCE-SCHEMA", path, "source contract fields drifted"))
            continue
        identifier = item.get("id")
        if identifier not in SOURCE_PATHS or item.get("path") != SOURCE_PATHS.get(identifier):
            findings.append(_finding("LAB-SOURCE-PATH", path, "source path drifted"))
        elif identifier not in sources or item.get("canonical_sha256") != canonical_digest(sources[identifier]):
            findings.append(_finding("LAB-SOURCE-FRESHNESS", path, "source digest is stale"))

    expected_selection = {
        "provider": None, "region": None, "managed_idp": None,
        "kms_or_hsm": None, "secrets_manager": None,
        "private_endpoints": [], "egress_allowlist": [],
    }
    if model.get("unresolved_selection") != expected_selection:
        findings.append(_finding(
            "LAB-PREMATURE-SELECTION", "$.unresolved_selection",
            "provider, region, identity and endpoints need A-02 and human review"))

    zones = model.get("trust_zones")
    if not isinstance(zones, list):
        findings.append(_finding("LAB-ZONES", "$.trust_zones", "zones must be a list"))
        zones = []
    zone_ids = [str(item.get("id")) for item in zones if isinstance(item, dict)]
    if set(zone_ids) != set(ZONE_PURPOSES) or len(zone_ids) != len(ZONE_PURPOSES):
        findings.append(_finding("LAB-ZONE-COVERAGE", "$.trust_zones", "trust zones drifted"))
    for index, item in enumerate(zones):
        path = f"$.trust_zones[{index}]"
        if not isinstance(item, dict) or set(item) != {
            "id", "purpose", "public_ip", "ingress", "egress", "persistent_data",
        }:
            findings.append(_finding("LAB-ZONE-SCHEMA", path, "zone fields drifted"))
            continue
        if item.get("purpose") != ZONE_PURPOSES.get(item.get("id")):
            findings.append(_finding("LAB-ZONE-PURPOSE", path, "zone purpose drifted"))
        if item.get("public_ip") is not False:
            findings.append(_finding("LAB-PUBLIC-NETWORK", path, "public IP is forbidden"))
        if item.get("egress") != "deny_all":
            findings.append(_finding("LAB-EGRESS", path, "every current zone must deny egress"))

    controls = model.get("control_catalog")
    if not isinstance(controls, list):
        findings.append(_finding("LAB-CONTROLS", "$.control_catalog", "controls must be a list"))
        controls = []
    control_ids = [str(item.get("id")) for item in controls if isinstance(item, dict)]
    if set(control_ids) != CONTROL_IDS or len(control_ids) != len(CONTROL_IDS):
        findings.append(_finding("LAB-CONTROL-COVERAGE", "$.control_catalog", "required controls drifted"))
    for index, item in enumerate(controls):
        path = f"$.control_catalog[{index}]"
        if not isinstance(item, dict) or set(item) != {
            "id", "domain", "requirement", "implemented", "evidence_state",
        }:
            findings.append(_finding("LAB-CONTROL-SCHEMA", path, "control fields drifted"))
            continue
        identifier = item.get("id")
        if item.get("requirement") != CRITICAL_REQUIREMENTS.get(identifier):
            findings.append(_finding("LAB-CONTROL-SEMANTICS", path, "control requirement was weakened or changed"))
        if item.get("implemented") is not False or item.get("evidence_state") != "not_run":
            findings.append(_finding("LAB-PREMATURE-EVIDENCE", path, "design has no implementation evidence"))

    expected_threats = _expected_threats(sources.get("THREAT", {}))
    if not expected_threats:
        findings.append(_finding("LAB-THREAT-SOURCE", "sources.THREAT", "no DRG-00 threats discovered"))
    coverage = model.get("threat_coverage")
    if not isinstance(coverage, list):
        findings.append(_finding("LAB-THREATS", "$.threat_coverage", "threat coverage must be a list"))
        coverage = []
    threat_ids = [str(item.get("threat_id")) for item in coverage if isinstance(item, dict)]
    if set(threat_ids) != expected_threats or len(threat_ids) != len(expected_threats):
        findings.append(_finding("LAB-THREAT-COVERAGE", "$.threat_coverage", "dynamic DRG-00 threats are uncovered"))
    for index, item in enumerate(coverage):
        path = f"$.threat_coverage[{index}]"
        if not isinstance(item, dict) or set(item) != {"threat_id", "control_ids", "evidence_state"}:
            findings.append(_finding("LAB-THREAT-SCHEMA", path, "threat mapping fields drifted"))
            continue
        ids = item.get("control_ids")
        if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
                or not set(ids).issubset(CONTROL_IDS)):
            findings.append(_finding("LAB-THREAT-CONTROLS", path, "threat controls are empty, duplicated or unknown"))
        if item.get("evidence_state") != "not_run":
            findings.append(_finding("LAB-PREMATURE-THREAT-EVIDENCE", path, "threat evidence has not run"))

    tests = model.get("acceptance_tests")
    if not isinstance(tests, list):
        findings.append(_finding("LAB-TESTS", "$.acceptance_tests", "test plan must be a list"))
        tests = []
    test_ids = [str(item.get("id")) for item in tests if isinstance(item, dict)]
    if set(test_ids) != TEST_IDS or len(test_ids) != len(TEST_IDS):
        findings.append(_finding("LAB-TEST-COVERAGE", "$.acceptance_tests", "acceptance plan drifted"))
    for index, item in enumerate(tests):
        if (not isinstance(item, dict) or set(item) != {"id", "assertion", "state"}
                or not isinstance(item.get("assertion"), str) or len(item["assertion"]) < 30
                or item.get("state") != "not_run"):
            findings.append(_finding("LAB-PREMATURE-TEST", f"$.acceptance_tests[{index}]", "test is incomplete or claims evidence"))

    prerequisites = model.get("prerequisites")
    if not isinstance(prerequisites, list):
        findings.append(_finding("LAB-PREREQUISITES", "$.prerequisites", "prerequisites must be a list"))
        prerequisites = []
    prereq_ids = [str(item.get("id")) for item in prerequisites if isinstance(item, dict)]
    if set(prereq_ids) != set(PREREQUISITES) or len(prereq_ids) != len(PREREQUISITES):
        findings.append(_finding("LAB-PREREQ-COVERAGE", "$.prerequisites", "prerequisite set drifted"))
    for index, item in enumerate(prerequisites):
        if (not isinstance(item, dict) or set(item) != {"id", "state", "satisfied"}
                or item.get("state") != PREREQUISITES.get(item.get("id"))
                or item.get("satisfied") is not False):
            findings.append(_finding("LAB-PREMATURE-PREREQ", f"$.prerequisites[{index}]", "prerequisite is not satisfied"))

    expected_review = {
        "state": "pending_independent_review", "security_reviewer_id": None,
        "privacy_reviewer_id": None, "architecture_reviewer_id": None,
        "evidence_ref": None, "reviewed_at": None,
    }
    if model.get("human_review") != expected_review:
        findings.append(_finding("LAB-PREMATURE-REVIEW", "$.human_review", "independent review remains pending"))

    claims = model.get("gate_claims")
    if not isinstance(claims, list):
        findings.append(_finding("LAB-GATES", "$.gate_claims", "gate claims must be a list"))
        claims = []
    claim_ids = [str(item.get("id")) for item in claims if isinstance(item, dict)]
    if set(claim_ids) != GATE_IDS or len(claim_ids) != len(GATE_IDS):
        findings.append(_finding("LAB-GATE-COVERAGE", "$.gate_claims", "gate inventory drifted"))
    for index, item in enumerate(claims):
        if (not isinstance(item, dict) or set(item) != {"id", "status", "authorized"}
                or item.get("status") != "not_met" or item.get("authorized") is not False):
            findings.append(_finding("LAB-PREMATURE-GATE", f"$.gate_claims[{index}]", "design cannot meet a gate"))

    region = sources.get("REGION", {})
    default_posture = region.get("default_posture") if isinstance(region, dict) else None
    candidates = region.get("candidate_locations") if isinstance(region, dict) else None
    if (region.get("human_acceptance") is not False
            or not isinstance(default_posture, dict)
            or default_posture.get("real_data") != "forbidden"
            or default_posture.get("external_egress") != "deny"
            or not isinstance(candidates, list)
            or any(item.get("selected") is not False for item in candidates if isinstance(item, dict))):
        findings.append(_finding("LAB-A02-SOURCE", "sources.REGION", "A-02 source no longer has closed posture"))
    privacy = sources.get("PRIVACY", {})
    privacy_gates = {
        item.get("id"): item for item in privacy.get("gates", []) if isinstance(item, dict)
    }
    if (privacy.get("data_ceiling") != "synthetic_only"
            or privacy_gates.get("DRG-00", {}).get("status") != "not_met"):
        findings.append(_finding("LAB-PRIVACY-SOURCE", "sources.PRIVACY", "privacy source no longer blocks real data"))
    retention = sources.get("RETENTION", {})
    if (retention.get("status") != "review_pending"
            or retention.get("real_data_authorized") is not False):
        findings.append(_finding("LAB-RETENTION-SOURCE", "sources.RETENTION", "L-01 source posture drifted"))
    return sorted(set(findings))


def report(model: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings = validate(model, sources)
    expected_threats = _expected_threats(sources.get("THREAT", {}))
    return {
        "ok": not findings,
        "model_valid": not findings,
        "design_ready_for_independent_review": not findings,
        "implemented": False,
        "deployment_enabled": False,
        "real_data_authorized": False,
        "provider_selected": False,
        "region_selected": False,
        "managed_idp_selected": False,
        "control_count": len(CONTROL_IDS),
        "trust_zone_count": len(ZONE_PURPOSES),
        "drg00_threat_count": len(expected_threats),
        "acceptance_test_count": len(TEST_IDS),
        "passed_test_count": 0,
        "satisfied_prerequisite_count": 0,
        "aggregate_score": None,
        "findings": [item.as_dict() for item in findings],
    }
