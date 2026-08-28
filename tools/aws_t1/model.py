from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "platform" / "aws-t1-remote-lab.json"
INFRA_ROOT = ROOT / "infra" / "aws" / "t1"

REQUIRED_TAGS = {
    "Project": "Fincilia",
    "Environment": "t1-remote-lab",
    "DataClass": "synthetic_only",
    "ManagedBy": "OpenTofu",
    "Task": "FNC-PLT-011",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def validate_contract(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if model.get("task_id") != "FNC-PLT-011":
        errors.append("task_id debe ser FNC-PLT-011")
    if model.get("data_ceiling") != "synthetic_only":
        errors.append("data_ceiling debe ser synthetic_only")
    if model.get("real_data_authorized") is not False:
        errors.append("real_data_authorized debe ser false")
    if model.get("external_ai_authorized") is not False:
        errors.append("external_ai_authorized debe ser false")
    runtime = model.get("runtime", {})
    expected = {
        "instance_count": 1,
        "instance_type": "t3.small",
        "architecture": "x86_64",
        "root_volume_type": "gp3",
        "root_volume_gib": 16,
        "root_volume_encrypted": True,
        "cpu_credits": "standard",
        "instance_shutdown_behavior": "stop",
        "max_session_hours": 4,
        "ingress_rules": 0,
        "access": "ssm_port_forwarding_only",
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            errors.append(f"runtime.{key} debe ser {value!r}")
    allowed = model.get("allowed_resource_types", [])
    forbidden = model.get("forbidden_resource_types", [])
    if set(allowed) & set(forbidden):
        errors.append("allowlist y denylist no pueden solaparse")
    if model.get("cost_model", {}).get("hard_cost_cap") is not False:
        errors.append("el presupuesto es alerta, no hard cap; debe declararse")
    return errors


def validate_sources() -> list[str]:
    errors: list[str] = []
    source_suffixes = {".tf", ".tftpl", ".sh", ".sql", ".service", ".timer"}
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(INFRA_ROOT.rglob("*"))
        if path.is_file() and path.suffix in source_suffixes
    )
    required = (
        'instance_type                        = "t3.small"',
        'ami                                  = "ami-0ae4c9718ffae6ca6"',
        'cpu_credits = "standard"',
        'instance_initiated_shutdown_behavior = "stop"',
        'http_tokens                 = "required"',
        'http_put_response_hop_limit = 1',
        'volume_size           = 16',
        'encrypted             = true',
        'OnBootSec=4h',
        'FINCILIA_REAL_DATA_ENABLED=false',
        '127.0.0.1:53000:3000',
    )
    for token in required:
        if token not in sources:
            errors.append(f"fuente no contiene control: {token}")
    forbidden = (
        'resource "aws_db_instance"', 'resource "aws_eip"',
        'resource "aws_lb"', 'resource "aws_nat_gateway"',
        'resource "aws_ecs_', 'resource "aws_kms_key"',
        'resource "aws_secretsmanager_secret"', 'resource "aws_ssm_parameter"',
        'key_name =', '0.0.0.0:53000', 'FINCILIA_REAL_DATA_ENABLED=true',
    )
    for token in forbidden:
        if token in sources:
            errors.append(f"fuente contiene patron prohibido: {token}")
    return errors


def validate_plan(plan: dict[str, Any], model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = set(model["allowed_resource_types"])
    forbidden = set(model["forbidden_resource_types"])
    managed = [item for item in plan.get("resource_changes", [])
               if item.get("mode", "managed") == "managed"]
    if not managed:
        return ["plan sin recursos administrados"]
    instances = 0
    for item in managed:
        address = item.get("address", "<sin-address>")
        resource_type = item.get("type")
        actions = item.get("change", {}).get("actions", [])
        after = item.get("change", {}).get("after") or {}
        if resource_type not in allowed or resource_type in forbidden:
            errors.append(f"{address}: tipo no permitido {resource_type}")
        if actions not in (["create"], ["no-op"]):
            errors.append(f"{address}: acciones no permitidas {actions}")
        if resource_type == "aws_instance":
            instances += 1
            if after.get("instance_type") != "t3.small":
                errors.append(f"{address}: instance_type debe ser t3.small")
            if after.get("ami") != "ami-0ae4c9718ffae6ca6":
                errors.append(f"{address}: AMI no fijada")
            if after.get("key_name") is not None:
                errors.append(f"{address}: key pair prohibido")
            if after.get("monitoring") is not False:
                errors.append(f"{address}: detailed monitoring no autorizado")
            if after.get("instance_initiated_shutdown_behavior") != "stop":
                errors.append(f"{address}: shutdown debe detener")
            metadata = (after.get("metadata_options") or [{}])[0]
            if metadata.get("http_tokens") != "required" or metadata.get("http_put_response_hop_limit") != 1:
                errors.append(f"{address}: IMDSv2/hop limit incorrecto")
            root = (after.get("root_block_device") or [{}])[0]
            if root.get("encrypted") is not True or root.get("volume_type") != "gp3" or root.get("volume_size") != 16:
                errors.append(f"{address}: root EBS debe ser gp3 cifrado de 16 GiB")
            credits = (after.get("credit_specification") or [{}])[0]
            if credits.get("cpu_credits") != "standard":
                errors.append(f"{address}: creditos CPU deben ser standard")
            tags = dict(after.get("tags") or {})
            tags.update(after.get("tags_all") or {})
            for key, value in REQUIRED_TAGS.items():
                if tags.get(key) != value:
                    errors.append(f"{address}: tag {key} debe ser {value}")
    if instances != 1:
        errors.append(f"plan debe contener exactamente una instancia; contiene {instances}")
    return errors


def validate(plan_path: Path | None = None) -> dict[str, Any]:
    model = load_json(CONTRACT_PATH)
    errors = validate_contract(model) + validate_sources()
    if plan_path is not None:
        try:
            errors.extend(validate_plan(load_json(plan_path), model))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"plan invalido: {exc}")
    return {"ok": not errors, "errors": errors}
