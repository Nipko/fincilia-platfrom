from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_TIERS = {"TIER-0-SYNTHETIC", "TIER-1-DRG00", "TIER-2-PRODUCTION"}
REQUIRED_SERVICES = {
    "COGNITO",
    "S3",
    "RDS",
    "EC2",
    "ECR",
    "CLOUDTRAIL",
    "S3_GATEWAY_ENDPOINT",
    "KMS",
    "SECRETS_MANAGER",
    "FARGATE",
    "NAT_GATEWAY",
    "ALB",
}
PAID_FROM_START = {"KMS", "SECRETS_MANAGER", "FARGATE", "NAT_GATEWAY", "ALB"}
FORBIDDEN_T0 = {"FARGATE", "NAT_GATEWAY", "ALB"}
REQUIRED_T0_EXCLUSIONS = {
    "DRG-00",
    "DRG-01",
    "production_availability",
    "legal_suitability",
    "real_data_security",
}


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def validate(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    direction = model.get("founder_direction", {})
    if direction.get("preferred_provider_for_evaluation") != "AWS":
        fail("AFT-DIRECTION", "founder_direction", "AWS must remain an evaluation preference only")
    if direction.get("preferred_region_for_evaluation") != "sa-east-1":
        fail("AFT-REGION", "founder_direction", "the evaluated region must be sa-east-1")
    if direction.get("final_a02_selection") is not False:
        fail("AFT-A02", "founder_direction.final_a02_selection", "cost evaluation cannot accept A-02")
    for field in ("deployment_authorized", "real_data_authorized"):
        if direction.get(field) is not False:
            fail("AFT-AUTHORIZATION", f"founder_direction.{field}", f"{field} must stay false")
    if direction.get("cloud_spend_authorized_usd") != 0:
        fail("AFT-SPEND", "founder_direction.cloud_spend_authorized_usd", "no cloud spend is authorized")

    program = model.get("free_tier_program", {})
    if program.get("free_plan_duration_months_max") != 6:
        fail("AFT-FREE-DURATION", "free_tier_program", "the current Free Plan maximum is six months")
    if program.get("free_plan_ends_when_credits_depleted") is not True:
        fail("AFT-CREDIT-BOUND", "free_tier_program", "credit depletion must end the Free Plan")
    if program.get("joining_aws_organizations_ends_free_plan") is not True:
        fail("AFT-ORG-EXIT", "free_tier_program", "Organizations must be recorded as ending Free Plan")
    if program.get("account_creation_date") is not None or program.get("account_plan") is not None:
        fail("AFT-ACCOUNT-EVIDENCE", "free_tier_program", "unknown account facts cannot be invented")
    if program.get("eligibility_state") != "unknown_requires_account_evidence":
        fail("AFT-ELIGIBILITY", "free_tier_program", "eligibility must remain unknown until account evidence")

    workload = model.get("fincilia_workload", {})
    if workload.get("external_ai_enabled") is not False:
        fail("AFT-AI", "fincilia_workload.external_ai_enabled", "external AI must remain disabled")
    if workload.get("initial_research_file_limit") != 10:
        fail("AFT-FILE-COUNT", "fincilia_workload", "initial research is limited to ten files")
    expected_bytes = workload.get("initial_research_file_limit", 0) * workload.get("max_file_bytes", 0)
    if workload.get("maximum_initial_input_bytes") != expected_bytes:
        fail("AFT-VOLUME", "fincilia_workload.maximum_initial_input_bytes", "input bound must be derived exactly")
    if set(workload.get("formats_allowed_for_initial_research", [])) != {"csv", "xlsx"}:
        fail("AFT-FORMATS", "fincilia_workload.formats_allowed_for_initial_research", "only CSV and XLSX are allowed")
    if "pdf" not in workload.get("formats_forbidden_for_initial_research", []):
        fail("AFT-PDF", "fincilia_workload.formats_forbidden_for_initial_research", "PDF must remain forbidden")
    if workload.get("arm64_compatibility_verified") is not False or workload.get("measured_cloud_memory_profile") is not False:
        fail("AFT-SIZING", "fincilia_workload", "unmeasured compatibility or sizing cannot be claimed")

    sources = {source.get("id"): source for source in model.get("sources", [])}
    if len(sources) != len(model.get("sources", [])):
        fail("AFT-SOURCE-DUPLICATE", "sources", "source IDs must be unique")
    for source_id, source in sources.items():
        if source.get("authority") != "AWS" or not str(source.get("url", "")).startswith("https://"):
            fail("AFT-SOURCE", str(source_id), "only HTTPS primary AWS sources are allowed")

    services = model.get("service_assessments", [])
    service_by_id = {service.get("id"): service for service in services}
    if set(service_by_id) != REQUIRED_SERVICES or len(services) != len(REQUIRED_SERVICES):
        fail("AFT-SERVICE-COVERAGE", "service_assessments", "required services must appear exactly once")
    for service_id, service in service_by_id.items():
        source_ids = service.get("source_ids", [])
        if not source_ids or any(source_id not in sources for source_id in source_ids):
            fail("AFT-SERVICE-SOURCE", service_id, "service evidence must reference known sources")
        if service_id in PAID_FROM_START and not str(service.get("free_character", "")).startswith("paid"):
            fail("AFT-PAID-CLAIM", service_id, "billable service cannot be described as free")

    tiers = model.get("launch_tiers", [])
    tier_by_id = {tier.get("id"): tier for tier in tiers}
    if set(tier_by_id) != REQUIRED_TIERS or len(tiers) != len(REQUIRED_TIERS):
        fail("AFT-TIER-COVERAGE", "launch_tiers", "T0, T1 and T2 are required exactly once")
    t0 = tier_by_id.get("TIER-0-SYNTHETIC", {})
    if t0.get("data_ceiling") != "synthetic_only" or t0.get("duration_days_max") != 30:
        fail("AFT-T0-BOUND", "TIER-0-SYNTHETIC", "T0 must be synthetic and expire within 30 days")
    if t0.get("account_topology") != "standalone_not_in_Organizations":
        fail("AFT-T0-ACCOUNT", "TIER-0-SYNTHETIC", "T0 must not claim a governed production account")
    if set(t0.get("forbidden_services", [])) != FORBIDDEN_T0:
        fail("AFT-T0-COST-TRAPS", "TIER-0-SYNTHETIC", "Fargate, NAT and ALB must be forbidden in T0")
    if set(t0.get("not_evidence_for", [])) != REQUIRED_T0_EXCLUSIONS:
        fail("AFT-T0-NONCLAIMS", "TIER-0-SYNTHETIC", "T0 non-claims must remain explicit")
    if tier_by_id.get("TIER-1-DRG00", {}).get("cash_zero_feasible") != "no":
        fail("AFT-DRG00-FREE", "TIER-1-DRG00", "DRG-00 cannot be promised as cash-zero")
    if tier_by_id.get("TIER-2-PRODUCTION", {}).get("cash_zero_feasible") != "no":
        fail("AFT-PROD-FREE", "TIER-2-PRODUCTION", "production cannot be promised as cash-zero")

    cost = model.get("cost_control", {})
    if cost.get("current_spend_authorization_usd") != 0:
        fail("AFT-COST-AUTH", "cost_control", "current spend authorization must remain zero")
    if cost.get("calculator_quote_required_before_deployment") is not True:
        fail("AFT-CALCULATOR", "cost_control", "a regional calculator export is mandatory")
    if cost.get("monthly_estimate_usd") is not None:
        fail("AFT-FALSE-PRECISION", "cost_control.monthly_estimate_usd", "unmeasured monthly cost must stay null")
    required_cost_inputs = {
        "account_creation_date_and_plan",
        "credit_balance_and_expiry",
        "measured_image_sizes_and_memory",
        "AWS_Pricing_Calculator_export_for_sa_east_1",
        "Founder_monthly_hard_cap",
        "budget_alerts_and_cost_anomaly_detection",
        "resource_expiry_tags_and_destroy_runbook",
    }
    if set(cost.get("required_before_any_paid_plan", [])) != required_cost_inputs:
        fail("AFT-COST-INPUTS", "cost_control.required_before_any_paid_plan", "all cost inputs are mandatory")

    verdict = model.get("verdict", {})
    if verdict.get("can_start_on_aws_free_tier") is not True or verdict.get("scope") != "synthetic_cloud_spike_only":
        fail("AFT-VERDICT", "verdict", "AWS Free Tier is valid only for the synthetic spike")
    if verdict.get("can_run_DRG00_entirely_on_always_free_allowances") is not False:
        fail("AFT-VERDICT-DRG00", "verdict", "DRG-00 must not be called always-free")
    if verdict.get("can_run_production_entirely_on_free_tier") is not False:
        fail("AFT-VERDICT-PROD", "verdict", "production must not be called free-tier viable")

    return sorted(set(findings))


def validate_repository(root: Path) -> list[Finding]:
    path = root / "docs/architecture/aws-free-tier-evaluation.json"
    return validate(json.loads(path.read_text(encoding="utf-8")))
