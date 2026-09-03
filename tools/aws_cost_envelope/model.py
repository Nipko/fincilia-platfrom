from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs" / "platform" / "aws-private-pilot-cost-envelope.json"
PLAN_EVIDENCE = ROOT / "docs" / "implementation" / "evidence" / "FNC-GAT-007-COLD-PLAN.json"

EXPECTED_ACTIONS = {"create": 142, "read": 11, "update": 0, "delete": 0}
EXPECTED_PLAN_SHA256 = "c99de724cfed0d804129d1ef62634c23054c4893bdc29cd265d1a8a938aaa914"
EXPECTED_PRICED_COMPONENTS = {
    "customer_managed_kms_keys": (5, Decimal("1.00"), "AWS-KMS-PRICE"),
    "declared_secrets_manager_secrets": (4, Decimal("0.40"), "AWS-SECRETS-PRICE"),
}
REQUIRED_UNPRICED = {
    "rds_db_t4g_micro_hours_after_credit_or_free_allowance",
    "rds_20_gb_gp3_storage_backup_and_io",
    "rds_managed_master_secret",
    "s3_storage_versioning_requests_and_kms_requests",
    "cloudtrail_s3_data_events",
    "cloudwatch_log_ingestion_storage_and_metrics",
    "ecr_image_storage_and_scanning",
    "cognito_monthly_active_users_above_allowance",
    "network_data_transfer_and_public_ipv4_if_any",
}
REQUIRED_WARM = {
    "one_nat_gateway_hour_and_data_processing",
    "six_interface_vpc_endpoints_hours_and_data",
    "one_application_load_balancer_hours_lcu_and_public_ipv4",
    "one_regional_waf_web_acl_three_rules_and_requests",
    "one_cache_t4g_micro_valkey_node",
    "fargate_vcpu_memory_and_ephemeral_storage_only_after_desired_count_above_zero",
    "additional_waf_and_runtime_log_ingestion",
}
REQUIRED_DECISIONS = {
    "refresh_temporary_aws_session",
    "obtain_complete_sa_east_1_quote",
    "price_cold_and_bounded_warm_hours",
    "set_founder_monthly_hard_cap",
    "regenerate_plan_if_source_or_cloud_changed",
    "obtain_exact_plan_digest_authorization",
    "obtain_independent_finance_platform_security_review",
}


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def load(path: Path = MODEL_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(model: dict[str, Any], *, root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if model.get("task_id") != "FNC-FIN-002" or model.get("region") != "sa-east-1":
        fail("ACE-IDENTITY", "root", "task and region must identify the private pilot")
    if model.get("data_ceiling") != "synthetic_only_until_gate":
        fail("ACE-DATA", "data_ceiling", "cost review cannot authorize real data")

    plan = model.get("plan_reference", {})
    if plan.get("mode") != "cold" or plan.get("sha256") != EXPECTED_PLAN_SHA256:
        fail("ACE-PLAN", "plan_reference", "the exact observed cold plan must be pinned")
    if plan.get("actions") != EXPECTED_ACTIONS:
        fail("ACE-ACTIONS", "plan_reference.actions", "plan actions must remain 142/11/0/0")
    evidence_path = root / str(plan.get("evidence", ""))
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("ACE-EVIDENCE", "plan_reference.evidence", "plan evidence must exist and be valid JSON")
    else:
        if evidence.get("plan_sha256") != plan.get("sha256") or evidence.get("planned_actions") != plan.get("actions"):
            fail("ACE-EVIDENCE", "plan_reference.evidence", "cost envelope and plan evidence drifted")

    counts = model.get("resource_type_counts", {})
    if not isinstance(counts, dict) or any(not isinstance(v, int) or v <= 0 for v in counts.values()):
        fail("ACE-COUNTS", "resource_type_counts", "resource counts must be positive integers")
    elif sum(counts.values()) != EXPECTED_ACTIONS["create"]:
        fail("ACE-COUNT-TOTAL", "resource_type_counts", "resource counts must sum to planned creates")
    for resource_type, expected in {"aws_kms_key": 5, "aws_secretsmanager_secret": 4, "aws_db_instance": 1}.items():
        if counts.get(resource_type) != expected:
            fail("ACE-COUNT-DRIVER", f"resource_type_counts.{resource_type}", "priced driver count drifted")

    sources = {item.get("id"): item for item in model.get("sources", [])}
    if len(sources) != len(model.get("sources", [])):
        fail("ACE-SOURCE-DUPLICATE", "sources", "source IDs must be unique")
    for source_id, source in sources.items():
        if source.get("authority") != "AWS" or not str(source.get("url", "")).startswith("https://aws.amazon.com/"):
            fail("ACE-SOURCE", f"sources.{source_id}", "only primary HTTPS AWS sources are allowed")

    floor = model.get("known_priced_floor", {})
    if floor.get("not_a_complete_monthly_estimate") is not True or floor.get("excludes_usage_requests") is not True:
        fail("ACE-FLOOR-NONCLAIM", "known_priced_floor", "known floor must not be presented as a complete estimate")
    components = floor.get("components", [])
    by_id = {item.get("id"): item for item in components}
    if set(by_id) != set(EXPECTED_PRICED_COMPONENTS) or len(components) != len(EXPECTED_PRICED_COMPONENTS):
        fail("ACE-PRICE-COVERAGE", "known_priced_floor.components", "only adjudicated priced components are allowed")
    subtotal = Decimal("0")
    for component_id, (quantity, unit, source_id) in EXPECTED_PRICED_COMPONENTS.items():
        item = by_id.get(component_id, {})
        try:
            item_unit = Decimal(str(item.get("unit_monthly_usd")))
            item_subtotal = Decimal(str(item.get("subtotal_monthly_usd")))
        except InvalidOperation:
            fail("ACE-PRICE-DECIMAL", component_id, "prices must be exact decimals")
            continue
        if item.get("quantity") != quantity or item_unit != unit or item_subtotal != unit * quantity:
            fail("ACE-PRICE", component_id, "quantity, unit price and subtotal must agree")
        if item.get("source_id") != source_id or source_id not in sources:
            fail("ACE-PRICE-SOURCE", component_id, "each price requires its exact primary source")
        subtotal += item_subtotal
    try:
        claimed_subtotal = Decimal(str(floor.get("subtotal_monthly_usd")))
    except InvalidOperation:
        claimed_subtotal = Decimal("-1")
    if claimed_subtotal != subtotal or subtotal != Decimal("6.60"):
        fail("ACE-FLOOR-TOTAL", "known_priced_floor.subtotal_monthly_usd", "known floor must add exactly")

    if set(model.get("unpriced_cold_components", [])) != REQUIRED_UNPRICED:
        fail("ACE-UNPRICED", "unpriced_cold_components", "all variable cold costs must remain visible")
    if set(model.get("warm_only_cost_drivers", [])) != REQUIRED_WARM:
        fail("ACE-WARM", "warm_only_cost_drivers", "all warm cost drivers must remain visible")

    program = model.get("account_program_facts", {})
    if program.get("evidence_source") != "founder_reported_not_cloud_reverified":
        fail("ACE-ACCOUNT-EVIDENCE", "account_program_facts", "founder-reported facts cannot be promoted to cloud evidence")
    if program.get("available_credits_usd") != "100.00" or program.get("credit_expiry_date") != "2027-02-28":
        fail("ACE-CREDITS", "account_program_facts", "reported credits and expiry drifted")
    if program.get("credits_are_not_a_hard_cap") is not True or program.get("credits_are_not_zero_cost") is not True:
        fail("ACE-CREDIT-NONCLAIM", "account_program_facts", "credits cannot be treated as a hard cap or zero cost")
    if any("account_id" in key.lower() for key in program):
        fail("ACE-ACCOUNT-ID", "account_program_facts", "account identifier must not be stored in cost evidence")

    decision = model.get("decision_state", {})
    for field in ("apply_authorized", "deployment_authorized", "real_data_authorized", "regional_price_quote_complete", "warm_plan_priced"):
        if decision.get(field) is not False:
            fail("ACE-AUTHORIZATION", f"decision_state.{field}", f"{field} must remain false")
    for field in ("complete_monthly_estimate_usd", "founder_monthly_hard_cap_usd"):
        if decision.get(field) is not None:
            fail("ACE-FALSE-PRECISION", f"decision_state.{field}", f"{field} must remain null")
    if set(decision.get("required_before_apply", [])) != REQUIRED_DECISIONS:
        fail("ACE-DECISIONS", "decision_state.required_before_apply", "all pre-apply decisions are mandatory")

    return sorted(set(findings))


def validate_repository(root: Path = ROOT) -> list[Finding]:
    return validate(load(root / MODEL_PATH.relative_to(ROOT)), root=root)
