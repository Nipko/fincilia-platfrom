from __future__ import annotations

import json
import re
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
    if identity.get("native_mfa") != "required_by_user_pool":
        errors.append("Cognito debe exigir MFA a identidades nativas")
    if identity.get("federated_assurance") != \
            "delegated_to_google_not_asserted_by_fincilia":
        errors.append("el assurance federado debe permanecer delegado y no afirmado")
    if identity.get("native_self_service_signup") is not False:
        errors.append("SignUp nativo de Cognito debe permanecer cerrado")
    if identity.get("registration") != "public_google_self_service":
        errors.append("el alta administrada debe ser autoservicio publico con Google")

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

    lifecycle = model.get("cost_lifecycle", {})
    expected_lifecycle = {
        "default_mode": "cold",
        "cold_runtime_plane_enabled": False,
        "warm_runtime_plane_enabled": True,
        "warm_initial_desired_count": 0,
        "cold_rds_action": "request_stop_preserve_storage",
        "rds_stop_limit_days": 7,
        "mutations_require_apply_flag": True,
        "controller_can_accept_gates": False,
    }
    for field, expected in expected_lifecycle.items():
        if lifecycle.get(field) != expected:
            errors.append(f"cost_lifecycle.{field} debe ser {expected!r}")
    persistent = set(lifecycle.get("persistent_resource_types", []))
    runtime_only = set(lifecycle.get("runtime_only_resource_types", []))
    if not persistent or not runtime_only or persistent & runtime_only:
        errors.append("cost_lifecycle debe separar recursos persistentes y runtime")

    disabled = set(model.get("disabled_capabilities", []))
    required_disabled = {
        "external_ai", "payments", "email_ingest", "sftp", "api_connectors",
        "webhooks", "automatic_close",
    }
    if not required_disabled.issubset(disabled):
        errors.append("faltan capacidades prohibidas del piloto")

    observability = model.get("observability", {})
    if observability.get("alb_access_logs") is not True:
        errors.append("ALB access logs son obligatorios")
    if observability.get("alb_access_log_encryption") != \
            "SSE-S3_AWS_ALB_constraint":
        errors.append("ALB access logs deben declarar la restriccion SSE-S3 de AWS")
    if observability.get("audit_evidence_encryption") != \
            "SSE-KMS_customer_managed":
        errors.append("la evidencia de auditoria debe usar CMK")

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


def source_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(INFRA_ROOT.glob("*.tf"))
    )


def validate_sources(sources: str | None = None) -> list[str]:
    sources = source_text() if sources is None else sources
    errors: list[str] = []
    required = (
        'required_version = "= 1.12.6"',
        'version = "= 6.59.0"',
        'key          = "fincilia/private-pilot/foundation.tfstate"',
        'vpc_cidr = "10.60.0.0/16"',
        'worker-no-default-route',
        'variable "runtime_plane_enabled"',
        'default     = false',
        'for_each = var.runtime_plane_enabled ? toset([',
        'count = var.runtime_plane_enabled ? 1 : 0',
        'assign_public_ip = false',
        'condition     = var.service_desired_count == 0',
        'manage_master_user_password   = true',
        'publicly_accessible    = false',
        'deletion_protection       = true',
        'backup_retention_period    = 14',
        'key_usage                = "SIGN_VERIFY"',
        'customer_master_key_spec = "RSA_2048"',
        'FINCILIA_OBJECT_CREDENTIALS_SOURCE", value = "aws_workload_identity"',
        'FINCILIA_OIDC_ENABLED", value = "true"',
        'FINCILIA_OIDC_REGISTRATION_MODE", value = "public_google"',
        'allowed_oauth_flows                  = ["code"]',
        'allowed_oauth_scopes                 = ["openid", "email", "profile"]',
        'allow_admin_create_user_only = true',
        'data "aws_iam_policy_document" "alb_logs"',
        'sse_algorithm = "AES256"',
        'resource "aws_wafv2_web_acl_association" "pilot"',
        'resource "aws_cloudtrail" "pilot"',
        'variable "budget_alert_email"',
        'notification_type          = "ACTUAL"',
        'notification_type          = "FORECASTED"',
        'subscriber_email_addresses = [var.budget_alert_email]',
    )
    for token in required:
        if token not in sources:
            errors.append(f"fuente no contiene control: {token}")
    if sources.count('FINCILIA_REAL_DATA_ENABLED", value = "false"') != 4:
        errors.append(
            "API, worker, bootstrap y migrator deben declarar datos reales apagados"
        )
    if sources.count('assign_public_ip = false') != 2:
        errors.append("app y worker deben declarar assign_public_ip=false")
    if sources.count('user                   = "10001"') != 3:
        errors.append(
            "API, bootstrap y migrator deben ejecutar con el UID 10001 de su imagen"
        )
    if sources.count('user                   = "10002"') != 2:
        errors.append("web y worker deben ejecutar con el UID 10002 de sus imagenes")
    forbidden = (
        'FINCILIA_REAL_DATA_ENABLED", value = "true"',
        'FINCILIA_AI_GATEWAY_ENABLED", value = "true"',
        'FINCILIA_PAYMENTS_ENABLED", value = "true"',
        'FINCILIA_OBJECT_ACCESS_KEY',
        'FINCILIA_OBJECT_SECRET_KEY',
        'aws_access_key_id',
        'secret_string',
        'secret_binary',
        'resource "aws_cognito_identity_provider"',
        'allow_admin_create_user_only = false',
        'resource "aws_instance"',
        'resource "aws_key_pair"',
        'assign_public_ip = true',
        'from_port = 22',
        'from_port   = 22',
    )
    for token in forbidden:
        if token in sources:
            errors.append(f"fuente contiene patron prohibido: {token}")
    if re.search(
        r'resource\s+"aws_route"\s+"(?:worker|data)[^"]*"\s*\{[^}]*'
        r'destination_cidr_block\s*=\s*"0\.0\.0\.0/0"',
        sources,
        re.DOTALL,
    ):
        errors.append("worker/data no pueden recibir default route")
    return errors


def validate_plan(plan: dict[str, Any], model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(model["required_resource_types"])
    forbidden = set(model["forbidden_resource_types"])
    lifecycle = model["cost_lifecycle"]
    runtime_only = set(lifecycle["runtime_only_resource_types"])
    persistent = set(lifecycle["persistent_resource_types"])
    changes = [item for item in plan.get("resource_changes", [])
               if item.get("mode", "managed") == "managed"]
    if not changes:
        return ["plan sin recursos administrados"]
    runtime_enabled = any(
        item.get("type") == "aws_nat_gateway"
        and item.get("change", {}).get("actions") != ["delete"]
        for item in changes
    )
    required_for_mode = required if runtime_enabled else required - runtime_only
    present = {
        item.get("type") for item in changes
        if item.get("change", {}).get("actions") != ["delete"]
    }
    planned_addresses = {str(item.get("address", "")) for item in changes}
    for resource_type in sorted(required_for_mode - present):
        errors.append(f"plan no contiene recurso requerido {resource_type}")

    for item in changes:
        address = item.get("address", "<sin-address>")
        resource_type = item.get("type")
        actions = item.get("change", {}).get("actions", [])
        after = item.get("change", {}).get("after") or {}
        after_unknown = item.get("change", {}).get("after_unknown") or {}
        if resource_type in forbidden:
            errors.append(f"{address}: tipo prohibido {resource_type}")
        delete_only = "delete" in actions and "create" not in actions
        if not runtime_enabled and resource_type in runtime_only and not delete_only:
            errors.append(f"{address}: recurso runtime presente en plan cold")
        if delete_only:
            runtime_address = (
                resource_type in runtime_only
                or address.startswith("aws_eip.nat")
                or address.startswith("aws_route.application_internet")
                or address.startswith("aws_vpc_endpoint.worker_interface")
                or address.startswith("aws_cloudwatch_log_group.waf")
                or address.startswith("aws_cloudwatch_metric_alarm.alb_5xx")
                or address.startswith("aws_cloudwatch_metric_alarm.waf_blocked")
                or address.startswith("aws_wafv2_web_acl_logging_configuration.pilot")
            )
            if runtime_enabled or not runtime_address:
                errors.append(f"{address}: borrado sin reemplazo no autorizado")
            if resource_type in persistent:
                errors.append(f"{address}: modo cold intenta borrar recurso persistente")
            continue
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
            # AWS provider 6.59 serializes at_rest_encryption_enabled as the
            # string "true" in a saved-plan JSON while transit encryption is
            # a JSON boolean. Fail closed for every other representation.
            if after.get("transit_encryption_enabled") is not True or \
                    after.get("at_rest_encryption_enabled") not in (True, "true"):
                errors.append(f"{address}: Valkey debe cifrar transito y reposo")
        elif resource_type == "aws_s3_bucket":
            if after.get("force_destroy") is not False:
                errors.append(f"{address}: bucket no puede usar force_destroy")
        elif resource_type == "aws_kms_key":
            if after.get("key_usage", "ENCRYPT_DECRYPT") == "SIGN_VERIFY":
                if after.get("customer_master_key_spec") != "RSA_2048":
                    errors.append(f"{address}: gate KMS debe usar RSA_2048")
                if after.get("enable_key_rotation") is not False:
                    errors.append(
                        f"{address}: KMS asimetrica no admite rotacion automatica")
            elif after.get("enable_key_rotation") is not True:
                errors.append(f"{address}: KMS simetrica debe rotar")
            if after.get("deletion_window_in_days", 0) < 30:
                errors.append(f"{address}: KMS requiere ventana de borrado >= 30")
        elif resource_type == "aws_secretsmanager_secret":
            if "secret_string" in after or "secret_binary" in after:
                errors.append(f"{address}: valor de secreto no puede entrar al plan")
        elif resource_type == "aws_lb":
            if after.get("internal") is not False or \
                    after.get("load_balancer_type") != "application":
                errors.append(f"{address}: entrada debe ser ALB publico")
            if after.get("enable_deletion_protection") is not True:
                errors.append(f"{address}: ALB debe proteger borrado")
            subnets = after.get("subnets")
            subnets_are_two = isinstance(subnets, list) and len(subnets) == 2
            if subnets is None and after_unknown.get("subnets") is True:
                # IDs created in this same plan are unknown until apply, so
                # OpenTofu omits `after.subnets`. Require the exact two indexed
                # public subnet resources rather than treating any unknown as
                # safe.
                subnets_are_two = {
                    "aws_subnet.public[0]", "aws_subnet.public[1]",
                }.issubset(planned_addresses) and not any(
                    address.startswith("aws_subnet.public[")
                    and address not in {
                        "aws_subnet.public[0]", "aws_subnet.public[1]",
                    }
                    for address in planned_addresses
                )
            if not subnets_are_two:
                errors.append(f"{address}: ALB requiere dos subredes")
            logs = (after.get("access_logs") or [{}])[0]
            if logs.get("enabled") is not True:
                errors.append(f"{address}: ALB access logs son obligatorios")
        elif resource_type == "aws_cognito_user_pool":
            if after.get("mfa_configuration") != "ON":
                errors.append(f"{address}: Cognito debe exigir MFA nativo")
            if after.get("deletion_protection") != "ACTIVE":
                errors.append(f"{address}: Cognito debe proteger borrado")
            admin = after.get("admin_create_user_config") or []
            if len(admin) != 1 or \
                    admin[0].get("allow_admin_create_user_only") is not True:
                errors.append(f"{address}: SignUp nativo debe estar cerrado")
        elif resource_type == "aws_cognito_user_pool_client":
            if after.get("generate_secret") is not False:
                errors.append(f"{address}: el cliente PKCE no lleva secreto en IaC")
            scopes = after.get("allowed_oauth_scopes") or []
            if after.get("allowed_oauth_flows") != ["code"] or \
                    len(scopes) != 3 or set(scopes) != {"openid", "email", "profile"}:
                errors.append(f"{address}: flujo/scopes OIDC no son minimos")
        elif resource_type == "aws_budgets_budget":
            if after.get("cost_filter"):
                errors.append(
                    f"{address}: el presupuesto bruto no puede depender de tags")
            notifications = after.get("notification") or []
            kinds = {entry.get("notification_type") for entry in notifications}
            subscribers = [
                mailbox
                for entry in notifications
                for mailbox in (entry.get("subscriber_email_addresses") or [])
            ]
            if kinds != {"ACTUAL", "FORECASTED"} or len(notifications) != 2:
                errors.append(
                    f"{address}: faltan alertas ACTUAL y FORECASTED")
            if len(subscribers) != 2 or any(
                    not isinstance(item, str) or not item for item in subscribers):
                errors.append(f"{address}: las alertas no tienen destinatario")
        elif resource_type == "aws_vpc":
            if after.get("cidr_block") != "10.60.0.0/16":
                errors.append(f"{address}: VPC no es la frontera dedicada")
        elif resource_type == "aws_subnet":
            if after.get("map_public_ip_on_launch") is not False:
                errors.append(f"{address}: subnet no puede autoasignar IP publica")
        elif resource_type == "aws_route":
            if ("worker" in address or "data" in address) and \
                    after.get("destination_cidr_block") == "0.0.0.0/0":
                errors.append(f"{address}: segmento aislado no admite default route")
        elif resource_type == "aws_vpc_security_group_ingress_rule":
            if after.get("cidr_ipv4") == "0.0.0.0/0" and (
                    after.get("from_port") not in (80, 443)
                    or after.get("to_port") != after.get("from_port")
                    or "alb" not in address):
                errors.append(f"{address}: ingress publico fuera de ALB 80/443")
    return errors


def validate(plan_path: Path | None = None) -> dict[str, Any]:
    model = load_json(CONTRACT_PATH)
    contract_errors = validate_contract(model)
    source_errors = validate_sources()
    errors = contract_errors + source_errors
    if plan_path is not None:
        try:
            errors.extend(validate_plan(load_json(plan_path), model))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"plan invalido: {exc}")
    return {
        "ok": not errors,
        "errors": errors,
        "report": {
            "contract_valid": not contract_errors,
            "sources_valid": not source_errors,
            "deployment_authorized": False,
            "real_data_authorized": False,
        },
    }
