"""Control seguro de secretos, bootstrap y migraciones del private-pilot."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from typing import Any, Callable
from urllib.parse import quote


REGION = "sa-east-1"
DATABASE_ID = "fincilia-private-pilot"
SECRET_NAMES = {
    "roles": "fincilia/private-pilot/database-roles-v1",
    "application": "fincilia/private-pilot/application-runtime-v1",
    "worker": "fincilia/private-pilot/worker-runtime-v1",
    "migrator": "fincilia/private-pilot/migrator-runtime-v1",
}
ROLE_FIELDS = (
    "FINCILIA_DB_APP_PASSWORD",
    "FINCILIA_DB_WORKER_PASSWORD",
    "FINCILIA_DB_MIGRATOR_PASSWORD",
)
APP_KEY_FIELDS = (
    "FINCILIA_AUTH_SIGNING_KEY",
    "FINCILIA_AUTHORIZATION_CONTEXT_HMAC_KEY",
    "FINCILIA_IDENTIFIER_TOKENIZATION_KEY",
    "FINCILIA_IDENTITY_BINDING_HMAC_KEY",
    "FINCILIA_OAUTH_TRANSACTION_KEY",
)
GATE_FIELDS = (
    "FINCILIA_IDENTITY_GATE_ATTESTATION",
    "FINCILIA_IDENTITY_GATE_SIGNATURE",
    "FINCILIA_DATA_GATE_ATTESTATION",
    "FINCILIA_DATA_GATE_SIGNATURE",
)
SAFE_SELECTOR = re.compile(r"^[A-Za-z0-9_+./=@:-]{1,256}$")
SAFE_HOST = re.compile(r"^[a-z0-9.-]{1,253}$")
MAX_RESPONSE = 512 * 1024


class BootstrapControlError(RuntimeError):
    """La operacion no puede probarse segura o termino con error."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


class AwsJson:
    """AWS CLI sin shell; payloads y secretos viajan solamente por stdin."""

    def __init__(self, *, profile: str, region: str = REGION,
                 runner: Runner = subprocess.run) -> None:
        if not SAFE_SELECTOR.fullmatch(profile) or region != REGION:
            raise ValueError("invalid AWS selector")
        self.profile = profile
        self.region = region
        self._runner = runner

    def invoke(self, service: str, operation: str, payload: dict[str, Any], *,
               missing_is_empty: bool = False, timeout: int = 60) -> dict[str, Any]:
        if any(not SAFE_SELECTOR.fullmatch(value) for value in (service, operation)):
            raise ValueError("invalid AWS operation")
        operation_parts = (
            ["wait", "tasks-stopped"]
            if service == "ecs" and operation == "wait-tasks-stopped"
            else [operation]
        )
        arguments = [
            "aws", service, *operation_parts,
            "--profile", self.profile,
            "--region", self.region,
        ]
        stdin_value: str | None = None
        if service == "secretsmanager" and operation == "put-secret-value":
            if (
                set(payload) != {"SecretId", "SecretString", "VersionStages"}
                or not isinstance(payload["SecretId"], str)
                or not SAFE_SELECTOR.fullmatch(payload["SecretId"])
                or not isinstance(payload["SecretString"], str)
                or payload["VersionStages"] != ["AWSCURRENT"]
            ):
                raise BootstrapControlError("secret write shape was invalid")
            arguments.extend([
                "--secret-id", payload["SecretId"],
                "--secret-string", "file:///dev/stdin",
                "--version-stages", "AWSCURRENT",
            ])
            stdin_value = payload["SecretString"]
        else:
            if "SecretString" in payload or "SecretBinary" in payload:
                raise BootstrapControlError("secret material cannot enter argv")
            arguments.extend([
                "--cli-input-json", json.dumps(payload, separators=(",", ":")),
            ])
        arguments.extend(["--output", "json", "--no-cli-pager"])
        try:
            completed = self._runner(
                arguments,
                input=stdin_value,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
                env={**os.environ, "AWS_PAGER": ""},
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BootstrapControlError("AWS operation failed") from error
        if completed.returncode != 0:
            if missing_is_empty and "ResourceNotFoundException" in completed.stderr:
                return {}
            raise BootstrapControlError("AWS operation failed")
        if len(completed.stdout.encode("utf-8")) > MAX_RESPONSE:
            raise BootstrapControlError("AWS response exceeded its limit")
        if not completed.stdout.strip():
            return {}
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise BootstrapControlError("AWS response was invalid") from error
        if not isinstance(value, dict):
            raise BootstrapControlError("AWS response was invalid")
        return value


def _secret_value(aws: AwsJson, name: str) -> dict[str, str]:
    response = aws.invoke(
        "secretsmanager", "get-secret-value", {"SecretId": name},
        missing_is_empty=True,
    )
    raw = response.get("SecretString")
    if raw is None:
        return {}
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 64 * 1024:
        raise BootstrapControlError("stored secret was invalid")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BootstrapControlError("stored secret was invalid") from error
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise BootstrapControlError("stored secret was invalid")
    return value


def _put_secret(aws: AwsJson, name: str, value: dict[str, str]) -> None:
    aws.invoke("secretsmanager", "put-secret-value", {
        "SecretId": name,
        "SecretString": json.dumps(value, separators=(",", ":")),
        "VersionStages": ["AWSCURRENT"],
    })


def _new_secret() -> str:
    return secrets.token_urlsafe(48)


def _preserve_or_generate(current: dict[str, str], field: str) -> str:
    value = current.get(field, "")
    return value if len(value.encode("utf-8")) >= 32 else _new_secret()


def _database_endpoint(aws: AwsJson) -> tuple[str, int, str]:
    response = aws.invoke("rds", "describe-db-instances", {
        "DBInstanceIdentifier": DATABASE_ID,
    })
    instances = response.get("DBInstances")
    if not isinstance(instances, list) or len(instances) != 1:
        raise BootstrapControlError("private database is not uniquely available")
    instance = instances[0]
    if not isinstance(instance, dict):
        raise BootstrapControlError("private database controls do not match")
    endpoint = instance.get("Endpoint", {})
    host = endpoint.get("Address") if isinstance(endpoint, dict) else None
    port = endpoint.get("Port") if isinstance(endpoint, dict) else None
    database = instance.get("DBName") if isinstance(instance, dict) else None
    if (
        not isinstance(host, str)
        or not SAFE_HOST.fullmatch(host)
        or port != 5432
        or database != "fincilia_pilot"
        or instance.get("PubliclyAccessible") is not False
        or instance.get("StorageEncrypted") is not True
        or instance.get("DBInstanceStatus") != "available"
    ):
        raise BootstrapControlError("private database controls do not match")
    return host, port, database


def _dsn(*, role: str, password: str, host: str, port: int, database: str) -> str:
    return (
        f"postgresql://{quote(role, safe='')}:{quote(password, safe='')}@"
        f"{host}:{port}/{database}?sslmode=require&connect_timeout=10"
    )


def prepare_runtime_secrets(aws: AwsJson) -> dict[str, object]:
    host, port, database = _database_endpoint(aws)
    current_roles = _secret_value(aws, SECRET_NAMES["roles"])
    passwords = {
        field: _preserve_or_generate(current_roles, field)
        for field in ROLE_FIELDS
    }
    if len(set(passwords.values())) != len(passwords):
        raise BootstrapControlError("stored role credentials are not independent")

    current_app = _secret_value(aws, SECRET_NAMES["application"])
    current_worker = _secret_value(aws, SECRET_NAMES["worker"])
    current_migrator = _secret_value(aws, SECRET_NAMES["migrator"])
    app = {
        "FINCILIA_DATABASE_URL": _dsn(
            role="fincilia_app", password=passwords["FINCILIA_DB_APP_PASSWORD"],
            host=host, port=port, database=database,
        ),
        **{
            field: _preserve_or_generate(current_app, field)
            for field in APP_KEY_FIELDS
        },
        **{
            field: current_app.get(field, "disabled") or "disabled"
            for field in GATE_FIELDS
        },
    }
    worker = {
        "FINCILIA_DATABASE_URL": _dsn(
            role="fincilia_worker",
            password=passwords["FINCILIA_DB_WORKER_PASSWORD"],
            host=host, port=port, database=database,
        ),
        "FINCILIA_DATA_GATE_ATTESTATION": (
            current_worker.get("FINCILIA_DATA_GATE_ATTESTATION", "disabled")
            or "disabled"
        ),
        "FINCILIA_DATA_GATE_SIGNATURE": (
            current_worker.get("FINCILIA_DATA_GATE_SIGNATURE", "disabled")
            or "disabled"
        ),
    }
    migrator = {
        "FINCILIA_MIGRATOR_URL": _dsn(
            role="fincilia_migrator",
            password=passwords["FINCILIA_DB_MIGRATOR_PASSWORD"],
            host=host, port=port, database=database,
        )
    }

    _put_secret(aws, SECRET_NAMES["roles"], passwords)
    _put_secret(aws, SECRET_NAMES["application"], app)
    _put_secret(aws, SECRET_NAMES["worker"], worker)
    _put_secret(aws, SECRET_NAMES["migrator"], migrator)
    return {
        "ok": True,
        "secret_containers": sorted(SECRET_NAMES),
        "credentials_generated": not bool(current_roles),
        "credentials_exposed": False,
        "gate_values_accepted": False,
        "real_data_authorized": False,
    }


def read_tofu_output(*, directory: Path, profile: str,
                     runner: Runner = subprocess.run) -> dict[str, Any]:
    resolved = directory.resolve()
    if (
        resolved.name != "private-pilot"
        or resolved.parent.name != "aws"
        or not SAFE_SELECTOR.fullmatch(profile)
    ):
        raise BootstrapControlError("unexpected OpenTofu directory")
    try:
        completed = runner(
            ["tofu", f"-chdir={resolved}", "output", "-json", "database_bootstrap"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, check=False, shell=False,
            env={**os.environ, "AWS_PROFILE": profile, "AWS_REGION": REGION},
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise BootstrapControlError("OpenTofu output failed") from error
    if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > MAX_RESPONSE:
        raise BootstrapControlError("OpenTofu output failed")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BootstrapControlError("OpenTofu output was invalid") from error
    required = {
        "task_definition_arn", "migration_definition_arn", "subnet_ids",
        "security_group_id", "cluster_arn", "runtime_plane_enabled",
        "services_desired_count", "real_data_authorized",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise BootstrapControlError("OpenTofu output fields drifted")
    if value["real_data_authorized"] is not False:
        raise BootstrapControlError("bootstrap cannot authorize real data")
    if value["runtime_plane_enabled"] is not True or value["services_desired_count"] != 0:
        raise BootstrapControlError("bootstrap requires warm infrastructure at zero")
    if not isinstance(value["subnet_ids"], list) or not value["subnet_ids"]:
        raise BootstrapControlError("OpenTofu subnet selectors are invalid")
    selectors = [
        value["task_definition_arn"], value["migration_definition_arn"],
        value["security_group_id"], value["cluster_arn"], *value["subnet_ids"],
    ]
    if any(not isinstance(item, str) or not SAFE_SELECTOR.fullmatch(item)
           for item in selectors):
        raise BootstrapControlError("OpenTofu selectors are invalid")
    return value


def _run_one_task(aws: AwsJson, topology: dict[str, Any], *,
                  definition_field: str, started_by: str) -> None:
    network = {
        "awsvpcConfiguration": {
            "subnets": topology["subnet_ids"],
            "securityGroups": [topology["security_group_id"]],
            "assignPublicIp": "DISABLED",
        }
    }
    launched = aws.invoke("ecs", "run-task", {
        "cluster": topology["cluster_arn"],
        "taskDefinition": topology[definition_field],
        "launchType": "FARGATE",
        "networkConfiguration": network,
        "count": 1,
        "enableExecuteCommand": False,
        "startedBy": started_by,
    })
    failures = launched.get("failures", [])
    tasks = launched.get("tasks", [])
    if failures or not isinstance(tasks, list) or len(tasks) != 1:
        raise BootstrapControlError("ECS refused the one-off task")
    task_arn = tasks[0].get("taskArn") if isinstance(tasks[0], dict) else None
    if not isinstance(task_arn, str) or not SAFE_SELECTOR.fullmatch(task_arn):
        raise BootstrapControlError("ECS task identity was invalid")
    wait_input = {"cluster": topology["cluster_arn"], "tasks": [task_arn]}
    aws.invoke("ecs", "wait-tasks-stopped", wait_input, timeout=900)
    described = aws.invoke("ecs", "describe-tasks", wait_input)
    stopped = described.get("tasks", [])
    if not isinstance(stopped, list) or len(stopped) != 1:
        raise BootstrapControlError("ECS stopped task was not observable")
    containers = stopped[0].get("containers", []) if isinstance(stopped[0], dict) else []
    if (
        not isinstance(containers, list)
        or len(containers) != 1
        or containers[0].get("exitCode") != 0
    ):
        raise BootstrapControlError("ECS one-off task failed")


def bootstrap_and_migrate(aws: AwsJson, topology: dict[str, Any]) -> dict[str, object]:
    _run_one_task(
        aws, topology, definition_field="task_definition_arn",
        started_by="fincilia-role-bootstrap-v1",
    )
    _run_one_task(
        aws, topology, definition_field="migration_definition_arn",
        started_by="fincilia-schema-migrator-v1",
    )
    return {
        "ok": True,
        "stages": ["roles_bootstrapped", "migrations_applied"],
        "task_identifiers_exposed": False,
        "real_data_authorized": False,
    }
