from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "platform" / "aws-private-pilot.json"
INFRA_ROOT = ROOT / "infra" / "aws" / "private-pilot"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def validate_contract(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact = {
        "task_id": "FNC-PLT-012",
        "gate": "DRG-01",
        "region": "sa-east-1",
        "data_ceiling": "synthetic_only_until_DRG-01",
        "real_data_authorized": False,
        "deployment_authorized": False,
        "external_ai_authorized": False,
    }
    for field, expected in exact.items():
        if model.get(field) != expected:
            errors.append(f"{field} debe ser {expected!r}")

    architecture = model.get("architecture", {})
    expected_architecture = {
        "vpc": "dedicated_private_pilot",
        "availability_zones": 2,
        "public_entry": "alb_https_acm_waf",
        "application_runtime": "ecs_fargate_private",
        "worker_runtime": "ecs_fargate_isolated_no_default_route",
        "database": "rds_postgresql_17_single_az_private",
        "cache": "elasticache_valkey_ephemeral_private",
        "object_store": "four_private_s3_zones",
        "operator_access": "ecs_exec_via_ssm_no_ssh",
    }
    for field, expected in expected_architecture.items():
        if architecture.get(field) != expected:
            errors.append(f"architecture.{field} debe ser {expected!r}")

    network = model.get("network", {})
    if network.get("alb_public_subnet_count") != 2:
        errors.append("ALB requiere exactamente dos subredes publicas")
    if network.get("worker_has_default_route") is not False:
        errors.append("worker no puede tener default route")
    if network.get("assign_public_ip") is not False:
        errors.append("las tareas no pueden recibir IP publica")
    if network.get("public_tcp_ports") != [80, 443]:
        errors.append("solo 80/443 pueden ser publicos")
    if network.get("ssh_enabled") is not False:
        errors.append("SSH debe permanecer deshabilitado")

    stores = model.get("data_stores", {})
    if stores.get("s3_zones") != ["quarantine", "raw", "derived", "exports"]:
        errors.append("las cuatro zonas S3 deben ser exactas y ordenadas")
    for field in (
        "bucket_versioning", "bucket_public_access_block", "bucket_tls_required",
        "rds_storage_encrypted", "rds_deletion_protection",
        "valkey_transit_encryption", "valkey_at_rest_encryption",
    ):
        if stores.get(field) is not True:
            errors.append(f"data_stores.{field} debe ser true")
    if stores.get("rds_publicly_accessible") is not False:
        errors.append("RDS no puede ser publico")
    if stores.get("rds_backup_retention_days", 0) < 14:
        errors.append("RDS debe conservar al menos 14 dias de backup")

    identity = model.get("identity", {})
    if identity.get("authorization_source") != \
            "PostgreSQL server-side memberships and roles":
        errors.append("Cognito no puede ser fuente de autorizacion financiera")
    if identity.get("oauth_flow") != "authorization_code_pkce_s256":
        errors.append("OIDC debe usar Authorization Code + PKCE S256")
    if identity.get("scopes") != ["openid", "email", "profile"]:
        errors.append("OIDC debe pedir solamente openid email profile")
    if identity.get("google_secret_in_iac") is not False:
        errors.append("el secreto Google no puede entrar a IaC")
    if identity.get("known_users_seeded") is not False:
        errors.append("el piloto no puede sembrar usuarios conocidos")

    secrets = model.get("secrets", {})
    if secrets.get("values_created_out_of_band") is not True or \
            secrets.get("values_in_iac_state") is not False:
        errors.append("los valores de secretos deben quedar fuera de IaC")
    if secrets.get("rds_master_password_managed_by_rds") is not True:
        errors.append("RDS debe administrar su password master en Secrets Manager")
    if secrets.get("application_static_aws_credentials") is not False:
        errors.append("las aplicaciones no pueden recibir credenciales AWS estaticas")

    activation = model.get("runtime_activation", {})
    if activation.get("initial_desired_count") != 0:
        errors.append("el primer despliegue debe tener capacidad cero")
    if activation.get("real_data_flag_in_iac") is not False:
        errors.append("IaC no puede ser la bandera de autorizacion de datos reales")
    for field in ("kms_signed_DRG00_required_for_identity",
                  "kms_signed_DRG01_required_for_real_data",
                  "human_gate_remains_external"):
        if activation.get(field) is not True:
            errors.append(f"runtime_activation.{field} debe ser true")

    disabled = set(model.get("disabled_capabilities", []))
    required_disabled = {
        "external_ai", "payments", "email_ingest", "sftp", "api_connectors",
        "webhooks", "automatic_close",
    }
    if not required_disabled.issubset(disabled):
        errors.append("faltan capacidades prohibidas del piloto")

    required = set(model.get("required_resource_types", []))
    forbidden = set(model.get("forbidden_resource_types", []))
    if not required or not forbidden or required & forbidden:
        errors.append("allowlist/denylist de recursos invalida")

    gates = {item.get("id"): item.get("status")
             for item in model.get("gate_claims", [])}
    for gate in ("DRG-00", "DRG-01", "GA-01"):
        if gates.get(gate) != "not_met":
            errors.append(f"{gate} debe permanecer not_met")
    return errors


def validate_plan(plan: dict[str, Any], model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(model["required_resource_types"])
    forbidden = set(model["forbidden_resource_types"])
    changes = [item for item in plan.get("resource_changes", [])
               if item.get("mode", "managed") == "managed"]
    if not changes:
        return ["plan sin recursos administrados"]
    present = {item.get("type") for item in changes}
    for resource_type in sorted(required - present):
        errors.append(f"plan no contiene recurso requerido {resource_type}")

    for item in changes:
        address = item.get("address", "<sin-address>")
        resource_type = item.get("type")
        actions = item.get("change", {}).get("actions", [])
        after = item.get("change", {}).get("after") or {}
        if resource_type in forbidden:
            errors.append(f"{address}: tipo prohibido {resource_type}")
        if "delete" in actions and "create" not in actions:
            errors.append(f"{address}: borrado sin reemplazo no autorizado")
        if resource_type == "aws_ecs_service":
            network = (after.get("network_configuration") or [{}])[0]
            if network.get("assign_public_ip") is not False:
                errors.append(f"{address}: assign_public_ip debe ser false")
            if after.get("desired_count") != 0:
                errors.append(f"{address}: foundation debe iniciar en desired_count 0")
        elif resource_type == "aws_db_instance":
            if after.get("publicly_accessible") is not False:
                errors.append(f"{address}: RDS no puede ser publico")
            if after.get("storage_encrypted") is not True:
                errors.append(f"{address}: RDS debe cifrar storage")
            if after.get("deletion_protection") is not True:
                errors.append(f"{address}: RDS debe proteger borrado")
            if after.get("backup_retention_period", 0) < 14:
                errors.append(f"{address}: backup retention menor a 14 dias")
            if after.get("manage_master_user_password") is not True:
                errors.append(f"{address}: password master debe administrarlo RDS")
        elif resource_type == "aws_elasticache_replication_group":
            if after.get("transit_encryption_enabled") is not True or \
                    after.get("at_rest_encryption_enabled") is not True:
                errors.append(f"{address}: Valkey debe cifrar transito y reposo")
        elif resource_type == "aws_s3_bucket":
            if after.get("force_destroy") is not False:
                errors.append(f"{address}: bucket no puede usar force_destroy")
        elif resource_type == "aws_kms_key":
            if after.get("enable_key_rotation") is not True:
                errors.append(f"{address}: KMS debe rotar")
            if after.get("deletion_window_in_days", 0) < 30:
                errors.append(f"{address}: KMS requiere ventana de borrado >= 30")
        elif resource_type == "aws_secretsmanager_secret":
            if "secret_string" in after or "secret_binary" in after:
                errors.append(f"{address}: valor de secreto no puede entrar al plan")
    return errors


def validate(plan_path: Path | None = None) -> dict[str, Any]:
    model = load_json(CONTRACT_PATH)
    errors = validate_contract(model)
    if plan_path is not None:
        try:
            errors.extend(validate_plan(load_json(plan_path), model))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"plan invalido: {exc}")
    return {
        "ok": not errors,
        "errors": errors,
        "report": {
            "contract_valid": not validate_contract(model),
            "deployment_authorized": False,
            "real_data_authorized": False,
        },
    }
