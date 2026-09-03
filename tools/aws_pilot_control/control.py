from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from tools.aws_private_pilot.model import (
    CONTRACT_PATH,
    load_json,
    validate_contract,
    validate_plan,
    validate_sources,
)
from tools.aws_image_publication.model import (
    CONTRACT_PATH as PUBLICATION_CONTRACT_PATH,
    load_json as load_publication_json,
    validate_contract as validate_publication_contract,
    validate_plan as validate_publication_plan,
    validate_sources as validate_publication_sources,
)


ROOT = Path(__file__).resolve().parents[2]
INFRA_ROOT = ROOT / "infra" / "aws" / "private-pilot"
RESOURCE_NAME = "fincilia-private-pilot"
SERVICE_NAMES = (
    "fincilia-private-pilot-application",
    "fincilia-private-pilot-worker",
)
FOUNDATION_REQUIRED_ADDRESSES = frozenset({
    "aws_cloudtrail.pilot",
    "aws_cognito_user_pool.pilot",
    "aws_cognito_user_pool_client.web",
    "aws_cognito_user_pool_domain.pilot",
    "aws_db_instance.pilot",
    "aws_ecr_repository.runtime[\"api\"]",
    "aws_ecr_repository.runtime[\"web\"]",
    "aws_ecr_repository.runtime[\"worker\"]",
    "aws_ecs_cluster.pilot",
    "aws_iam_openid_connect_provider.github",
    "aws_iam_role.application",
    "aws_iam_role.execution",
    "aws_iam_role.github_ecr_publisher",
    "aws_iam_role.migrator",
    "aws_iam_role.worker",
    "aws_kms_key.audit",
    "aws_kms_key.database",
    "aws_kms_key.evidence",
    "aws_kms_key.gate",
    "aws_kms_key.quarantine",
    "aws_s3_bucket.alb_logs",
    "aws_s3_bucket.audit",
    "aws_s3_bucket.objects[\"derived\"]",
    "aws_s3_bucket.objects[\"exports\"]",
    "aws_s3_bucket.objects[\"quarantine\"]",
    "aws_s3_bucket.objects[\"raw\"]",
    "aws_secretsmanager_secret.application",
    "aws_secretsmanager_secret.google",
    "aws_secretsmanager_secret.migrator",
    "aws_secretsmanager_secret.worker",
    "aws_vpc.pilot",
    "aws_vpc_endpoint.s3",
    "terraform_data.account_guard",
})
RUNTIME_REQUIRED_ADDRESSES = frozenset({
    "aws_ecs_service.application[0]",
    "aws_ecs_service.worker[0]",
    "aws_ecs_task_definition.application[0]",
    "aws_ecs_task_definition.migrator[0]",
    "aws_ecs_task_definition.worker[0]",
    "aws_elasticache_replication_group.pilot[0]",
    "aws_lb.pilot[0]",
    "aws_lb_listener.https[0]",
    "aws_nat_gateway.application[0]",
    "aws_wafv2_web_acl.pilot[0]",
})
ALLOWED_REGIONS = {"sa-east-1"}
EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_EXTERNAL_FAILURE = 3


class ControlError(RuntimeError):
    """Fallo cerrado que puede mostrarse sin exponer salida sensible."""


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> Result: ...


class SubprocessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> Result:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        return Result(completed.returncode, completed.stdout, completed.stderr)


def safe_environment(profile: str, region: str) -> dict[str, str]:
    allowed = (
        "PATH",
        "HOME",
        "USERPROFILE",
        "SystemRoot",
        "WSLENV",
        "WSL_DISTRO_NAME",
        "SSL_CERT_FILE",
        "AWS_CA_BUNDLE",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    user_bin = str(Path.home() / ".local" / "bin")
    environment["PATH"] = os.pathsep.join(
        item for item in (user_bin, environment.get("PATH", "")) if item
    )
    environment.update({
        "AWS_PROFILE": profile,
        "AWS_REGION": region,
        "AWS_DEFAULT_REGION": region,
        "AWS_PAGER": "",
        "TF_INPUT": "0",
        "TF_IN_AUTOMATION": "1",
    })
    return environment


def _json(result: Result, operation: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise ControlError(f"{operation} fallo; revise la sesion y permisos AWS")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ControlError(f"{operation} no devolvio JSON valido") from exc
    if not isinstance(payload, dict):
        raise ControlError(f"{operation} devolvio una forma inesperada")
    return payload


class PilotController:
    def __init__(
        self,
        *,
        account_id: str,
        profile: str = "fincilia-sandbox",
        region: str = "sa-east-1",
        runner: Runner | None = None,
        root: Path = ROOT,
    ) -> None:
        if len(account_id) != 12 or not account_id.isdigit():
            raise ControlError("account-id debe contener exactamente 12 digitos")
        if region not in ALLOWED_REGIONS:
            raise ControlError("la unica region autorizada es sa-east-1")
        if not profile or any(char.isspace() for char in profile):
            raise ControlError("profile AWS invalido")
        self.account_id = account_id
        self.profile = profile
        self.region = region
        self.runner = runner or SubprocessRunner()
        self.root = root
        self.infra_root = root / "infra" / "aws" / "private-pilot"
        self.environment = safe_environment(profile, region)

    def _run(
        self,
        argv: Sequence[str],
        *,
        timeout: int = 120,
        operation: str,
        expect_json: bool = False,
    ) -> Result | dict[str, Any]:
        result = self.runner.run(
            argv,
            cwd=self.root,
            env=self.environment,
            timeout=timeout,
        )
        return _json(result, operation) if expect_json else result

    def guard_identity(self) -> dict[str, str]:
        identity = self._run(
            ("aws", "sts", "get-caller-identity", "--output", "json"),
            operation="verificacion de identidad",
            expect_json=True,
        )
        assert isinstance(identity, dict)
        observed = str(identity.get("Account", ""))
        if observed != self.account_id:
            raise ControlError("la sesion AWS no corresponde a la cuenta autorizada")
        return {"account": observed, "profile": self.profile, "region": self.region}

    def _aws_json(self, service: str, *arguments: str) -> dict[str, Any]:
        payload = self._run(
            ("aws", service, *arguments, "--region", self.region, "--output", "json"),
            operation=f"consulta {service}",
            expect_json=True,
        )
        assert isinstance(payload, dict)
        return payload

    def status(self) -> dict[str, Any]:
        identity = self.guard_identity()
        rds = self._describe_optional(
            "rds", "describe-db-instances", "--db-instance-identifier", RESOURCE_NAME,
            collection="DBInstances", state_field="DBInstanceStatus",
        )
        services = self._describe_services()
        nat = self._aws_json(
            "ec2",
            "describe-nat-gateways",
            "--filter",
            "Name=tag:Environment,Values=private-pilot",
            "Name=state,Values=pending,available,deleting",
        )
        load_balancers = self._describe_optional(
            "elbv2", "describe-load-balancers", "--names", RESOURCE_NAME,
            collection="LoadBalancers", state_field="State",
        )
        cache = self._describe_optional(
            "elasticache", "describe-replication-groups",
            "--replication-group-id", RESOURCE_NAME,
            collection="ReplicationGroups", state_field="Status",
        )
        runtime_count = (
            len(nat.get("NatGateways", []))
            + int(load_balancers != "absent")
            + int(cache != "absent")
            + sum(int(item["status"] != "absent") for item in services)
        )
        state_inventory = self._state_inventory()
        addresses = set(state_inventory["addresses"])
        missing_foundation = sorted(FOUNDATION_REQUIRED_ADDRESSES - addresses)
        missing_runtime = sorted(RUNTIME_REQUIRED_ADDRESSES - addresses)
        foundation_state = (
            "absent" if not addresses else
            "complete" if not missing_foundation else
            "partial"
        )
        runtime_state = (
            "absent" if not addresses.intersection(RUNTIME_REQUIRED_ADDRESSES) else
            "complete" if not missing_runtime else
            "partial"
        )
        blockers = []
        if missing_foundation:
            blockers.append("foundation_not_applied")
        if missing_runtime:
            blockers.append("runtime_plane_not_applied")
        blockers.extend((
            "release_not_admitted_to_target",
            "target_environment_drill_not_observed",
            "independent_security_review_pending",
        ))
        return {
            "ok": True,
            "command": "status",
            "identity": identity,
            "mode": "cold" if runtime_count == 0 else "warm_or_transitioning",
            "database": rds,
            "database_stop_limit_days": 7,
            "services": services,
            "runtime": {
                "nat_gateways": len(nat.get("NatGateways", [])),
                "load_balancer": load_balancers,
                "cache": cache,
            },
            "state_inventory": {
                "resource_count": len(addresses),
                "foundation": {
                    "state": foundation_state,
                    "required_count": len(FOUNDATION_REQUIRED_ADDRESSES),
                    "missing": missing_foundation,
                },
                "runtime_plane": {
                    "state": runtime_state,
                    "required_count": len(RUNTIME_REQUIRED_ADDRESSES),
                    "missing": missing_runtime,
                },
            },
            "isolated_environment_control": {
                "id": "G00-ISOLATED-ENV",
                "state": "pending",
                "blockers": blockers,
                "agent_observation_is_not_gate_acceptance": True,
            },
            "real_data_authorized": False,
        }

    def _state_inventory(self) -> dict[str, Any]:
        """Return only OpenTofu addresses; never serialize state values.

        The remote state is the ownership inventory for this dedicated
        environment. Reading full state would expose endpoints and sensitive
        outputs, so this probe deliberately invokes ``state list`` only.
        """
        result = self._run(
            ("tofu", f"-chdir={self.infra_root}", "state", "list", "-no-color"),
            timeout=300,
            operation="inventario de estado OpenTofu",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            lowered = f"{result.stdout}\n{result.stderr}".lower()
            if "no state file was found" in lowered or "no state" in lowered:
                return {"addresses": []}
            raise ControlError(
                "inventario de estado OpenTofu fallo; no se asumira ausencia"
            )
        addresses = []
        for line in result.stdout.splitlines():
            address = line.strip()
            if not address:
                continue
            if any(char.isspace() for char in address) or len(address) > 240:
                raise ControlError("inventario OpenTofu devolvio una forma inesperada")
            addresses.append(address)
        if len(addresses) != len(set(addresses)):
            raise ControlError("inventario OpenTofu contiene direcciones duplicadas")
        return {"addresses": sorted(addresses)}

    def _describe_optional(
        self,
        service: str,
        *arguments: str,
        collection: str,
        state_field: str,
    ) -> str:
        result = self._run(
            ("aws", service, *arguments, "--region", self.region, "--output", "json"),
            operation=f"consulta {service}",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            lowered = result.stderr.lower()
            if "notfound" in lowered or "not found" in lowered:
                return "absent"
            raise ControlError(f"consulta {service} fallo; no se asumira ausencia")
        payload = _json(result, f"consulta {service}")
        items = payload.get(collection, [])
        if not items:
            return "absent"
        state = items[0].get(state_field, "unknown")
        if isinstance(state, dict):
            state = state.get("Code", "unknown")
        return str(state)

    def _describe_services(self) -> list[dict[str, Any]]:
        result = self._run(
            (
                "aws", "ecs", "describe-services", "--cluster", RESOURCE_NAME,
                "--services", *SERVICE_NAMES, "--region", self.region, "--output", "json",
            ),
            operation="consulta ECS",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            lowered = result.stderr.lower()
            if "clusternotfound" in lowered:
                return [
                    {"name": name, "status": "absent", "desired": 0, "running": 0}
                    for name in SERVICE_NAMES
                ]
            raise ControlError("consulta ECS fallo; no se asumira ausencia")
        payload = _json(result, "consulta ECS")
        found = {item.get("serviceName"): item for item in payload.get("services", [])}
        return [
            {
                "name": name,
                "status": str(found.get(name, {}).get("status", "absent")).lower(),
                "desired": int(found.get(name, {}).get("desiredCount", 0)),
                "running": int(found.get(name, {}).get("runningCount", 0)),
            }
            for name in SERVICE_NAMES
        ]

    def plan(self, mode: str) -> dict[str, Any]:
        if mode not in {"cold", "warm"}:
            raise ControlError("mode debe ser cold o warm")
        self.guard_identity()
        plan_path = self.infra_root / ".terraform" / f"pilot-{mode}.tfplan"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        enabled = "true" if mode == "warm" else "false"
        plan = self._run(
            (
                "tofu", f"-chdir={self.infra_root}", "plan", "-input=false",
                "-lock-timeout=60s", f"-var=runtime_plane_enabled={enabled}",
                f"-out={plan_path}",
            ),
            timeout=900,
            operation=f"plan {mode}",
        )
        assert isinstance(plan, Result)
        if plan.returncode != 0:
            raise ControlError(f"plan {mode} fallo; no se aplico ningun cambio")
        shown = self._run(
            ("tofu", f"-chdir={self.infra_root}", "show", "-json", str(plan_path)),
            timeout=300,
            operation=f"lectura de plan {mode}",
            expect_json=True,
        )
        assert isinstance(shown, dict)
        contract = load_json(CONTRACT_PATH)
        publication_contract = load_publication_json(PUBLICATION_CONTRACT_PATH)
        errors = (
            validate_contract(contract)
            + validate_sources()
            + validate_plan(shown, contract)
            + validate_publication_contract(publication_contract)
            + validate_publication_sources()
            + validate_publication_plan(shown)
        )
        if errors:
            raise ControlError("el plan fue rechazado por el contrato de seguridad")
        action_counts: dict[str, int] = {}
        for item in shown.get("resource_changes", []):
            action = "/".join(item.get("change", {}).get("actions", []))
            action_counts[action] = action_counts.get(action, 0) + 1
        return {
            "ok": True,
            "command": "plan",
            "mode": mode,
            "validated": True,
            "actions": dict(sorted(action_counts.items())),
            "plan_file": plan_path,
        }

    def apply_mode(self, mode: str, *, apply: bool) -> dict[str, Any]:
        if not apply:
            raise ControlError("la mutacion requiere --apply")
        alb_arn: str | None = None
        if mode == "cold":
            self.guard_identity()
            self._scale_services_to_zero()
            alb_arn = self._load_balancer_arn()
            if alb_arn is not None:
                self._set_alb_deletion_protection(alb_arn, enabled=False)
        try:
            report = self.plan(mode)
            apply_result = self._run(
                (
                    "tofu", f"-chdir={self.infra_root}", "apply", "-input=false",
                    "-auto-approve",
                    f"-var=runtime_plane_enabled={'true' if mode == 'warm' else 'false'}",
                    str(report["plan_file"]),
                ),
                timeout=1800,
                operation=f"apply {mode}",
            )
            assert isinstance(apply_result, Result)
            if apply_result.returncode != 0:
                raise ControlError(
                    f"apply {mode} fallo; revise el estado antes de reintentar"
                )
        except ControlError:
            if alb_arn is not None:
                self._set_alb_deletion_protection(alb_arn, enabled=True)
            raise
        database_action = self._start_database() if mode == "warm" else self._stop_database()
        return {
            "ok": True,
            "command": mode,
            "mode": mode,
            "infrastructure_applied": True,
            "database_action": database_action,
            "services_desired_count": 0,
            "real_data_authorized": False,
            "note": (
                "Infraestructura temporal lista; las tareas siguen detenidas."
                if mode == "warm"
                else "Plano temporal retirado; almacenamiento persistente conservado."
            ),
        }

    def _load_balancer_arn(self) -> str | None:
        result = self._run(
            (
                "aws", "elbv2", "describe-load-balancers", "--names", RESOURCE_NAME,
                "--region", self.region, "--output", "json",
            ),
            operation="consulta ALB",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            if "notfound" in result.stderr.lower():
                return None
            raise ControlError("consulta ALB fallo; cold fue detenido")
        payload = _json(result, "consulta ALB")
        load_balancers = payload.get("LoadBalancers", [])
        if not load_balancers:
            return None
        arn = load_balancers[0].get("LoadBalancerArn")
        if not isinstance(arn, str) or not arn.startswith("arn:aws:elasticloadbalancing:"):
            raise ControlError("ALB devolvio una identidad inesperada")
        return arn

    def _set_alb_deletion_protection(self, arn: str, *, enabled: bool) -> None:
        result = self._run(
            (
                "aws", "elbv2", "modify-load-balancer-attributes",
                "--load-balancer-arn", arn,
                "--attributes", f"Key=deletion_protection.enabled,Value={str(enabled).lower()}",
                "--region", self.region, "--no-cli-pager",
            ),
            operation="proteccion de borrado ALB",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            if enabled and "notfound" in result.stderr.lower():
                return
            state = "reactivar" if enabled else "desactivar"
            raise ControlError(f"no se pudo {state} la proteccion de borrado del ALB")

    def _scale_services_to_zero(self) -> None:
        active_services = [
            service for service in self._describe_services()
            if service["status"] != "absent"
        ]
        for service in active_services:
            result = self._run(
                (
                    "aws", "ecs", "update-service", "--cluster", RESOURCE_NAME,
                    "--service", service["name"], "--desired-count", "0",
                    "--region", self.region, "--no-cli-pager",
                ),
                operation="escala ECS a cero",
            )
            assert isinstance(result, Result)
            if result.returncode != 0:
                raise ControlError("no se pudo escalar ECS a cero; cold fue detenido")
        if active_services:
            result = self._run(
                (
                    "aws", "ecs", "wait", "services-stable", "--cluster", RESOURCE_NAME,
                    "--services", *(item["name"] for item in active_services),
                    "--region", self.region,
                ),
                timeout=900,
                operation="espera ECS",
            )
            assert isinstance(result, Result)
            if result.returncode != 0:
                raise ControlError("ECS no llego a cero de forma estable; cold fue detenido")

    def _database_state(self) -> str:
        return self._describe_optional(
            "rds", "describe-db-instances", "--db-instance-identifier", RESOURCE_NAME,
            collection="DBInstances", state_field="DBInstanceStatus",
        )

    def _stop_database(self) -> str:
        state = self._database_state()
        if state in {"absent", "stopped", "stopping"}:
            return state
        if state != "available":
            raise ControlError(f"RDS esta {state}; no se solicitara stop automaticamente")
        result = self._run(
            (
                "aws", "rds", "stop-db-instance", "--db-instance-identifier",
                RESOURCE_NAME, "--region", self.region, "--no-cli-pager",
            ),
            operation="stop RDS",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            raise ControlError("no se pudo solicitar stop de RDS")
        return "stop_requested"

    def _start_database(self) -> str:
        state = self._database_state()
        if state in {"available", "starting", "creating"}:
            return state
        if state != "stopped":
            raise ControlError(f"RDS esta {state}; no se solicitara start automaticamente")
        result = self._run(
            (
                "aws", "rds", "start-db-instance", "--db-instance-identifier",
                RESOURCE_NAME, "--region", self.region, "--no-cli-pager",
            ),
            operation="start RDS",
        )
        assert isinstance(result, Result)
        if result.returncode != 0:
            raise ControlError("no se pudo solicitar start de RDS")
        return "start_requested"
