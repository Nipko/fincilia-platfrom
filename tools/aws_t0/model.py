from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "platform" / "aws-t0-deployment.json"
INFRA_ROOT = ROOT / "infra" / "aws"
T0_SOURCE_ROOTS = (
    INFRA_ROOT / "bootstrap",
    INFRA_ROOT / "t0",
)

REQUIRED_TAGS = {
    "Project": "Fincilia",
    "Environment": "t0-synthetic",
    "DataClass": "synthetic_only",
    "ManagedBy": "OpenTofu",
    "Task": "FNC-PLT-010",
}

TAGGABLE_TYPES = {
    "aws_cloudtrail",
    "aws_ecr_repository",
    "aws_iam_role",
    "aws_internet_gateway",
    "aws_s3_bucket",
    "aws_security_group",
    "aws_subnet",
    "aws_vpc",
    "aws_vpc_endpoint",
}

FORBIDDEN_SOURCE_TOKENS = {
    'resource "aws_instance"': "EC2",
    'resource "aws_db_instance"': "RDS",
    'resource "aws_nat_gateway"': "NAT",
    'resource "aws_lb"': "ALB/NLB",
    'resource "aws_ecs_': "ECS/Fargate",
    'resource "aws_kms_key"': "customer-managed KMS",
    'resource "aws_secretsmanager_secret"': "Secrets Manager",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} debe contener un objeto JSON")
    return value


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("task_id") != "FNC-PLT-010":
        errors.append("contract.task_id debe ser FNC-PLT-010")
    if contract.get("data_ceiling") != "synthetic_only":
        errors.append("contract.data_ceiling debe ser synthetic_only")
    if contract.get("real_data_authorized") is not False:
        errors.append("contract.real_data_authorized debe ser false")
    if contract.get("external_ai_authorized") is not False:
        errors.append("contract.external_ai_authorized debe ser false")
    if contract.get("region") != "sa-east-1":
        errors.append("contract.region debe ser sa-east-1")

    scope = contract.get("apply_scope", {})
    if scope.get("runtime_enabled") is not False:
        errors.append("apply_scope.runtime_enabled debe ser false")
    allowed = scope.get("allowed_resource_types", [])
    forbidden = scope.get("forbidden_resource_types", [])
    if not allowed or len(allowed) != len(set(allowed)):
        errors.append("allowed_resource_types debe ser una lista unica y no vacia")
    if not forbidden or len(forbidden) != len(set(forbidden)):
        errors.append("forbidden_resource_types debe ser una lista unica y no vacia")
    overlap = set(allowed) & set(forbidden)
    if overlap:
        errors.append(f"tipos simultaneamente permitidos y prohibidos: {sorted(overlap)}")

    cost = contract.get("cost_control", {})
    if cost.get("gross_monthly_budget_usd") != 5:
        errors.append("gross_monthly_budget_usd debe permanecer en 5 para T0")
    if cost.get("organizations_forbidden") is not True:
        errors.append("AWS Organizations debe permanecer prohibido")
    if cost.get("control_tower_forbidden") is not True:
        errors.append("Control Tower debe permanecer prohibido")
    return errors


def validate_sources(root: Path | None = None) -> list[str]:
    errors: list[str] = []
    roots = (root,) if root is not None else T0_SOURCE_ROOTS
    sources = sorted(path for source_root in roots for path in source_root.rglob("*.tf"))
    if not sources:
        return ["no se encontraron fuentes OpenTofu"]
    merged = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for token, label in FORBIDDEN_SOURCE_TOKENS.items():
        if token in merged:
            errors.append(f"fuente contiene recurso prohibido {label}: {token}")
    for required in (
        'required_version = "= 1.12.6"',
        'version = "= 6.59.0"',
        'use_lockfile = true',
        'data "aws_caller_identity" "current"',
        'data "aws_region" "current"',
        'DataClass   = "synthetic_only"',
        'resource "aws_budgets_budget"',
        'resource "aws_cognito_user_pool_client" "google_web"',
        'supported_identity_providers         = ["Google"]',
        'callback_urls                        = ["https://fincilia.com/api/auth/callback/cognito"]',
        'logout_urls                          = ["https://fincilia.com/entrar"]',
    ):
        if required not in merged:
            errors.append(f"fuente no contiene control requerido: {required}")
    return errors


def _iter_managed_changes(plan: dict[str, Any]):
    for change in plan.get("resource_changes", []):
        if change.get("mode", "managed") == "managed":
            yield change


def validate_plan(plan: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("format_version") is None:
        errors.append("plan carece de format_version")
    scope = contract["apply_scope"]
    allowed = set(scope["allowed_resource_types"])
    forbidden = set(scope["forbidden_resource_types"])
    changes = list(_iter_managed_changes(plan))
    if not changes:
        errors.append("plan no contiene resource_changes administrados")

    for item in changes:
        address = item.get("address", "<sin-address>")
        resource_type = item.get("type")
        actions = item.get("change", {}).get("actions", [])
        if resource_type in forbidden:
            errors.append(f"{address}: tipo prohibido {resource_type}")
        if resource_type not in allowed:
            errors.append(f"{address}: tipo no allowlisted {resource_type}")
        if actions not in (["create"], ["no-op"]):
            errors.append(f"{address}: acciones no permitidas {actions}")

        if resource_type in TAGGABLE_TYPES and actions == ["create"]:
            after = item.get("change", {}).get("after") or {}
            tags = dict(after.get("tags") or {})
            tags.update(after.get("tags_all") or {})
            for key, value in REQUIRED_TAGS.items():
                if tags.get(key) != value:
                    errors.append(f"{address}: tag {key} debe ser {value}")
    return errors


def validate(plan_path: Path | None = None) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    errors = validate_contract(contract)
    errors.extend(validate_sources())
    if plan_path is not None:
        try:
            plan = load_json(plan_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"no se pudo leer el plan: {exc}")
        else:
            errors.extend(validate_plan(plan, contract))
    return {"ok": not errors, "errors": errors}
