from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs" / "platform" / "aws-uat-cost-decision.json"

EXPECTED_RATES = {
    "ec2_t3_small": Decimal("0.0336000000"),
    "ebs_gp3": Decimal("0.1520000000"),
    "public_ipv4": Decimal("0.0050000000"),
    "rds_postgresql_db_t4g_micro": Decimal("0.0340000000"),
    "rds_postgresql_gp3": Decimal("0.2190000000"),
    "kms_customer_key": Decimal("1.0000000000"),
    "secrets_manager_secret": Decimal("0.4000000000"),
    "nat_gateway": Decimal("0.0930000000"),
    "interface_vpc_endpoint": Decimal("0.0210000000"),
    "application_load_balancer": Decimal("0.0340000000"),
    "application_load_balancer_lcu": Decimal("0.0110000000"),
    "waf_web_acl": Decimal("5.0000000000"),
    "waf_rule": Decimal("1.0000000000"),
    "waf_request": Decimal("0.0000006000"),
    "valkey_cache_t4g_micro": Decimal("0.0240000000"),
    "fargate_x86_vcpu": Decimal("0.0696000000"),
    "fargate_x86_memory": Decimal("0.0076000000"),
}
EXPECTED_TOTALS = {
    "current_uat": Decimal("31.826000"),
    "current_account_overhead": Decimal("2.432000"),
    "private_pilot_cold": Decimal("36.200000"),
    "private_pilot_warm_services_stopped": Decimal("257.360000"),
    "private_pilot_warm_services_active": Decimal("319.264000"),
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


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def validate(model: dict[str, Any], *, root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if model.get("task_id") != "FNC-FIN-003" or model.get("region") != "sa-east-1":
        fail("UATC-IDENTITY", "root", "task and region must remain exact")
    if model.get("monthly_hours") != 730 or model.get("data_ceiling") != "synthetic_only_until_gate":
        fail("UATC-BOUNDARY", "root", "730 hours and the synthetic ceiling are mandatory")

    evidence_path = root / str(model.get("live_evidence", ""))
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("UATC-EVIDENCE", "live_evidence", "redacted live evidence must exist")
        evidence = {}
    identity = evidence.get("identity", {})
    if identity.get("authenticated") is not True or identity.get("expected_account_match") is not True:
        fail("UATC-AUTH", "live_evidence.identity", "authenticated expected-account evidence is required")
    if identity.get("raw_identifiers_persisted") is not False:
        fail("UATC-REDACTION", "live_evidence.identity", "raw cloud identifiers are forbidden")
    inventory = evidence.get("live_inventory", {})
    expected_inventory = {
        "uat_running_instances": {"count": 1, "instance_type": "t3.small", "root_gp3_gb": 24},
        "stopped_lab_instances": {"count": 1, "instance_type": "t3.small", "root_gp3_gb": 16},
        "associated_elastic_ipv4": 1,
        "rds_instances": 0,
    }
    if inventory != expected_inventory:
        fail("UATC-INVENTORY", "live_evidence.live_inventory", "live inventory drifted")
    if evidence.get("mutations_executed") is not False or evidence.get("apply_executed") is not False:
        fail("UATC-READONLY", "live_evidence", "cost evidence must be read-only")
    if evidence.get("real_data_observed") is not False:
        fail("UATC-DATA", "live_evidence", "cost inspection cannot include real data")

    rates = model.get("regional_rates", [])
    by_rate = {item.get("id"): item for item in rates}
    if len(by_rate) != len(rates) or set(by_rate) != set(EXPECTED_RATES):
        fail("UATC-RATE-COVERAGE", "regional_rates", "the exact regional rate set is required")
    for rate_id, expected in EXPECTED_RATES.items():
        item = by_rate.get(rate_id, {})
        try:
            observed = _decimal(item.get("unit_usd"))
        except (InvalidOperation, ValueError):
            fail("UATC-RATE-DECIMAL", rate_id, "rate must be an exact decimal")
            continue
        if observed != expected:
            fail("UATC-RATE", rate_id, "regional rate drifted")
        if item.get("source_id") not in {"AWS-PRICE-LIST", "AWS-KMS-PRICE", "AWS-SECRETS-PRICE"}:
            fail("UATC-RATE-SOURCE", rate_id, "rate lacks its primary source")
        if item.get("source_id") == "AWS-PRICE-LIST" and not item.get("sku"):
            fail("UATC-SKU", rate_id, "Price List API rates require a SKU")

    scenarios = model.get("monthly_scenarios", {})

    def component_sum(section: dict[str, Any], key: str) -> Decimal:
        total = Decimal("0")
        for index, component in enumerate(section.get(key, [])):
            rate_id = component.get("rate_id")
            try:
                quantity = _decimal(component.get("quantity"))
                subtotal = _decimal(component.get("subtotal_usd"))
                expected_subtotal = EXPECTED_RATES[rate_id] * quantity
            except (InvalidOperation, ValueError, KeyError, TypeError):
                fail("UATC-COMPONENT", f"{key}[{index}]", "component is not calculable")
                continue
            if subtotal != expected_subtotal:
                fail("UATC-ARITHMETIC", f"{key}[{index}]", "component subtotal is incorrect")
            total += subtotal
        return total

    current = scenarios.get("current_uat", {})
    overhead = scenarios.get("current_account_overhead", {})
    cold = scenarios.get("private_pilot_cold", {})
    warm_stopped = scenarios.get("private_pilot_warm_services_stopped", {})
    warm_active = scenarios.get("private_pilot_warm_services_active", {})
    calculated = {
        "current_uat": component_sum(current, "components"),
        "current_account_overhead": component_sum(overhead, "components"),
        "private_pilot_cold": component_sum(cold, "components"),
    }
    calculated["private_pilot_warm_services_stopped"] = calculated["private_pilot_cold"] + component_sum(
        warm_stopped, "additional_components"
    )
    calculated["private_pilot_warm_services_active"] = calculated["private_pilot_warm_services_stopped"] + component_sum(
        warm_active, "additional_components"
    )
    for scenario_id, expected in EXPECTED_TOTALS.items():
        section = scenarios.get(scenario_id, {})
        try:
            claimed = _decimal(section.get("fixed_subtotal_usd"))
        except (InvalidOperation, ValueError):
            claimed = Decimal("-1")
        if calculated.get(scenario_id) != expected or claimed != expected:
            fail("UATC-TOTAL", f"monthly_scenarios.{scenario_id}", "scenario total is incorrect")
    if _decimal(scenarios.get("current_account_fixed_total_usd")) != Decimal("34.258000"):
        fail("UATC-ACCOUNT-TOTAL", "monthly_scenarios.current_account_fixed_total_usd", "account fixed total drifted")
    elif calculated["current_uat"] + calculated["current_account_overhead"] != Decimal("34.258000"):
        fail("UATC-ACCOUNT-ARITHMETIC", "monthly_scenarios", "account total does not add up")

    decision = model.get("decision", {})
    if decision.get("recommendation") != "retain_and_harden_existing_uat_single_host":
        fail("UATC-RECOMMENDATION", "decision.recommendation", "recommendation drifted")
    if decision.get("recommended_gross_budget_alert_usd") != "45.00" or decision.get("current_budget_usd") != "35.00":
        fail("UATC-BUDGET", "decision", "current and recommended alerts must remain explicit")
    for field in (
        "budget_change_authorized",
        "delete_stopped_lab_authorized",
        "private_pilot_apply_authorized",
        "deployment_authorized",
        "real_data_authorized",
        "production_promotion_authorized",
    ):
        if decision.get(field) is not False:
            fail("UATC-AUTHORIZATION", f"decision.{field}", "no cloud or data authorization was issued")
    if decision.get("independent_review_pending") is not True:
        fail("UATC-REVIEW", "decision.independent_review_pending", "independent review remains pending")

    source_ids = {source.get("id") for source in model.get("sources", [])}
    if {item.get("source_id") for item in rates} - source_ids:
        fail("UATC-SOURCES", "sources", "every rate source must be declared")
    return sorted(set(findings))


def validate_repository(root: Path = ROOT) -> list[Finding]:
    return validate(load(root / MODEL_PATH.relative_to(ROOT)), root=root)
