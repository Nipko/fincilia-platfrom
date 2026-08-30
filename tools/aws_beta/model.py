from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "platform" / "aws-closed-beta.json"
INFRA_ROOT = ROOT / "infra" / "aws" / "beta"

REQUIRED_TAGS = {
    "Project": "Fincilia",
    "Environment": "closed-beta",
    "DataClass": "synthetic_only",
    "ManagedBy": "OpenTofu",
    "Task": "FNC-BET-001",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def validate_contract(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact = {
        "task_id": "FNC-BET-001",
        "gate": "BETA-01",
        "data_ceiling": "synthetic_only",
        "real_data_authorized": False,
        "external_ai_authorized": False,
        "google_oidc_enabled": False,
        "region": "sa-east-1",
    }
    for key, expected in exact.items():
        if model.get(key) != expected:
            errors.append(f"{key} debe ser {expected!r}")
    entry = model.get("public_entry", {})
    if entry.get("ingress_tcp_ports") != [80, 443]:
        errors.append("solo 80/443 pueden ser ingress publico")
    if entry.get("admin_access") != "ssm_only" or entry.get("ssh_enabled") is not False:
        errors.append("la administracion debe ser SSM-only sin SSH")
    identity = model.get("identity", {})
    if identity.get("registration") != "one_use_invitation":
        errors.append("el registro debe exigir invitacion de un uso")
    if identity.get("known_demo_users_seeded") is not False:
        errors.append("la beta no puede sembrar usuarios conocidos")
    secrets = model.get("secrets", {})
    if secrets.get("generated_on_instance") is not True:
        errors.append("los secretos deben generarse en el host")
    if secrets.get("stored_in_terraform_state") is not False:
        errors.append("los secretos no pueden entrar al estado IaC")
    backups = model.get("backups", {})
    if backups.get("restore_check") != "weekly_disposable_postgresql":
        errors.append("se requiere restore-check semanal desechable")
    if model.get("observability", {}).get("budget_is_hard_cap") is not False:
        errors.append("el budget es una alerta, no un hard cap")
    allowed = set(model.get("allowed_resource_types", []))
    forbidden = set(model.get("forbidden_resource_types", []))
    if allowed & forbidden:
        errors.append("allowlist y denylist de recursos se solapan")
    gates = {item.get("id"): item.get("status") for item in model.get("gate_claims", [])}
    for gate in ("BETA-01", "DRG-00", "DRG-01", "GA-01"):
        if gates.get(gate) != "not_met":
            errors.append(f"{gate} debe permanecer not_met")
    return errors


def source_text() -> str:
    suffixes = {".tf", ".tftpl", ".sh", ".service", ".timer", ".conf"}
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(INFRA_ROOT.rglob("*"))
        if path.is_file() and path.suffix in suffixes
    )


def validate_sources(sources: str | None = None) -> list[str]:
    sources = source_text() if sources is None else sources
    errors: list[str] = []
    required = (
        'instance_type                        = "t3.small"',
        'ami                                  = "ami-0ae4c9718ffae6ca6"',
        'volume_size           = 24',
        'encrypted             = true',
        'http_tokens                 = "required"',
        'from_port   = 80',
        'from_port   = 443',
        'FINCILIA_WEB_SECURE_COOKIES: "true"',
        'FINCILIA_REGISTRATION_INVITE_REQUIRED: "true"',
        'FINCILIA_REAL_DATA_ENABLED: "false"',
        'FINCILIA_AI_GATEWAY_ENABLED: "false"',
        'python -m db.seed.beta',
        'from fincilia_platform.probes import ensure_buckets',
        'created = ensure_buckets(settings)',
        'ignore_changes = [user_data]',
        'fincilia-beta-deploy.lock',
        'ReleaseDeploymentSuccess',
        "psql -U postgres -d fincilia_restore",
        "-Atqc 'SELECT 1'",
        'CREATE ROLE fincilia_app NOLOGIN',
        'CREATE ROLE fincilia_identity NOLOGIN',
        'python -m db.admin.invitations create',
        'sha256sum -c manifest.sha256',
        'RestoreCheckSuccess',
        'alarm_description   = "No se observo restore-check exitoso durante siete dias."',
        'evaluation_periods  = 7',
        'datapoints_to_alarm = 7',
        'BackupSuccess',
        'chmod 0600 runtime.env',
        '/fincilia/closed-beta/runtime-env-v1',
        'admin off',
    )
    for token in required:
        if token not in sources:
            errors.append(f"fuente no contiene control: {token}")
    forbidden = (
        'key_name =',
        'from_port   = 22',
        'FINCILIA_REAL_DATA_ENABLED=true',
        'FINCILIA_REAL_DATA_ENABLED: "true"',
        'FINCILIA_AI_GATEWAY_ENABLED: "true"',
        'python -m db.seed.local',
        'fincilia_local_' + 'admin_only',
        'fincilia_local_' + 'app_only',
        'ports: ["5432:',
        'ports: ["6379:',
        'ports: ["9000:',
        'resource "aws_route53_record"',
        'resource "aws_secretsmanager_secret"',
        'resource "aws_ssm_parameter"',
    )
    for token in forbidden:
        if token in sources:
            errors.append(f"fuente contiene patron prohibido: {token}")

    compose = (INFRA_ROOT / "runtime" / "compose.yaml.tftpl").read_text(encoding="utf-8")
    image_lines = [line.strip() for line in compose.splitlines() if line.strip().startswith("image:")]
    for line in image_lines:
        value = line.split(":", 1)[1].strip()
        if value in ("${api_image}", "${web_image}", "${worker_image}"):
            continue
        if not re.search(r"@sha256:[0-9a-f]{64}$", value):
            errors.append(f"imagen no fijada por digest: {value}")
    if compose.count('FINCILIA_REGISTRATION_INVITE_REQUIRED: "true"') != 2:
        errors.append("API y web deben exigir invitacion en la beta")
    if compose.count('FINCILIA_REAL_DATA_ENABLED: "false"') < 3:
        errors.append("API, worker y migrator deben mantener datos reales apagados")
    if compose.count('ports: ["80:80", "443:443"]') != 1:
        errors.append("solo Caddy debe publicar 80/443")
    return errors


def validate_plan(plan: dict[str, Any], model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = set(model["allowed_resource_types"])
    forbidden = set(model["forbidden_resource_types"])
    managed = [item for item in plan.get("resource_changes", [])
               if item.get("mode", "managed") == "managed"]
    if not managed:
        return ["plan sin recursos administrados"]
    counts: dict[str, int] = {}
    for item in managed:
        address = item.get("address", "<sin-address>")
        resource_type = item.get("type")
        counts[resource_type] = counts.get(resource_type, 0) + 1
        actions = item.get("change", {}).get("actions", [])
        after = item.get("change", {}).get("after") or {}
        if resource_type not in allowed or resource_type in forbidden:
            errors.append(f"{address}: tipo no permitido {resource_type}")
        if "delete" in actions and "create" not in actions:
            errors.append(f"{address}: borrado sin reemplazo no autorizado")
        if actions not in (["create"], ["no-op"], ["update"], ["delete", "create"]):
            errors.append(f"{address}: acciones no permitidas {actions}")
        if resource_type == "aws_instance":
            if after.get("instance_type") != "t3.small":
                errors.append(f"{address}: instance_type debe ser t3.small")
            if after.get("ami") != "ami-0ae4c9718ffae6ca6":
                errors.append(f"{address}: AMI no fijada")
            if after.get("key_name") not in (None, ""):
                errors.append(f"{address}: key pair prohibido")
            if after.get("monitoring") is not False:
                errors.append(f"{address}: detailed monitoring no autorizado")
            if after.get("instance_initiated_shutdown_behavior") != "stop":
                errors.append(f"{address}: shutdown debe detener la instancia")
            root = (after.get("root_block_device") or [{}])[0]
            if (root.get("encrypted") is not True or root.get("volume_size") != 24
                    or root.get("volume_type") != "gp3"):
                errors.append(f"{address}: EBS debe estar cifrado y medir 24 GiB")
            metadata = (after.get("metadata_options") or [{}])[0]
            if (metadata.get("http_tokens") != "required"
                    or metadata.get("http_put_response_hop_limit") != 1):
                errors.append(f"{address}: IMDSv2 requerido")
            credits = (after.get("credit_specification") or [{}])[0]
            if credits.get("cpu_credits") != "standard":
                errors.append(f"{address}: creditos CPU deben ser standard")
            tags = dict(after.get("tags") or {})
            tags.update(after.get("tags_all") or {})
            for key, value in REQUIRED_TAGS.items():
                if tags.get(key) != value:
                    errors.append(f"{address}: tag {key} debe ser {value}")
        elif resource_type == "aws_security_group":
            ingress = after.get("ingress", [])
            ports = sorted(rule.get("from_port") for rule in ingress)
            if ports != [80, 443]:
                errors.append(f"{address}: ingress debe ser exactamente 80/443")
            for rule in ingress:
                if (rule.get("protocol") != "tcp"
                        or rule.get("from_port") != rule.get("to_port")
                        or rule.get("cidr_blocks") != ["0.0.0.0/0"]
                        or rule.get("ipv6_cidr_blocks") not in (None, [])):
                    errors.append(f"{address}: regla ingress no canonica")
    required_counts = {
        "aws_instance": 1,
        "aws_eip": 1,
        "aws_eip_association": 1,
        "aws_security_group": 1,
        "aws_iam_role": 1,
        "aws_iam_instance_profile": 1,
        "aws_budgets_budget": 1,
        "aws_cloudwatch_metric_alarm": 3,
    }
    for resource_type, expected in required_counts.items():
        actual = counts.get(resource_type, 0)
        if actual != expected:
            errors.append(
                f"plan debe contener {expected} {resource_type}; contiene {actual}")
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
