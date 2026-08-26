from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/platform/wsl-local-runtime.json"
SCRIPT = ROOT / "infra/local/fincilia-local.ps1"


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_contract(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    expected = {
        "schema_version": 1,
        "task_id": "FNC-PLT-009",
        "status": "review_pending",
        "human_acceptance": "pending",
        "data_ceiling": "synthetic_only",
        "entrypoint": "infra/local/fincilia-local.ps1",
        "default_distribution": "Ubuntu",
        "compose_project": "fincilia-local",
        "compose_file": "infra/local/compose.yaml",
    }
    for field, value in expected.items():
        if document.get(field) != value:
            fail("WSL-CONTRACT", field, f"expected {value!r}")

    if document.get("actions") != {
        "doctor": "read_only", "up": "local_reversible",
        "status": "read_only", "down": "local_reversible",
    }:
        fail("WSL-ACTIONS", "actions", "actions and classifications are closed")

    keepalive = document.get("keepalive", {})
    if keepalive.get("windows_binary") != "wsl.exe" or \
            keepalive.get("linux_argv") != ["sleep", "infinity"]:
        fail("WSL-KEEPALIVE", "keepalive", "the keepalive argv is fixed")
    for field in ("validates_pid_command_line", "stops_only_recorded_process"):
        if keepalive.get(field) is not True:
            fail("WSL-PID-SCOPE", f"keepalive.{field}", f"{field} must be true")
    if keepalive.get("window_style") != "hidden":
        fail("WSL-NO-WINDOW", "keepalive.window_style", "keepalive must be hidden")
    if set(keepalive.get("state_fields", [])) != {
            "pid", "distribution", "project", "started_at"}:
        fail("WSL-STATE-MINIMIZATION", "keepalive.state_fields",
             "state fields must remain minimal")

    lifecycle = document.get("lifecycle", {})
    for field in ("lock_required", "preserves_volumes"):
        if lifecycle.get(field) is not True:
            fail("WSL-LIFECYCLE", f"lifecycle.{field}", f"{field} must be true")
    for field in ("removes_orphans", "terminates_distribution",
                  "modifies_wsl_configuration", "installs_or_updates_dependencies"):
        if lifecycle.get(field) is not False:
            fail("WSL-DESTRUCTIVE", f"lifecycle.{field}", f"{field} must be false")
    if lifecycle.get("up_script") != "infra/local/up.sh":
        fail("WSL-UP-SCRIPT", "lifecycle.up_script", "up must reuse the reviewed script")
    wait = lifecycle.get("waits_for_docker_seconds")
    if not isinstance(wait, int) or not 10 <= wait <= 120:
        fail("WSL-BOUNDED-WAIT", "lifecycle.waits_for_docker_seconds",
             "Docker wait must be bounded between 10 and 120 seconds")

    if document.get("exit_codes") != {
            "ok": 0, "command_failed": 1, "dependency_missing": 3}:
        fail("WSL-EXIT-CODES", "exit_codes", "exit codes are part of the contract")
    status_output = document.get("status_output", {})
    if set(status_output.get("fields", [])) != {"service", "state", "health", "ports"}:
        fail("WSL-STATUS-MINIMIZATION", "status_output.fields",
             "status may expose only service, state, health and ports")
    for field in ("includes_labels", "includes_environment"):
        if status_output.get(field) is not False:
            fail("WSL-STATUS-MINIMIZATION", f"status_output.{field}",
                 f"{field} must be false")
    gate = document.get("gate", {})
    if gate != {"id": "S1-READY", "status": "not_met", "effect": "none"}:
        fail("WSL-GATE", "gate", "the wrapper cannot move S1-READY")
    if not document.get("security_invariants"):
        fail("WSL-INVARIANTS", "security_invariants", "security limits must be explicit")
    return sorted(set(findings))


def validate_script(text: str) -> list[Finding]:
    findings: list[Finding] = []

    def require(code: str, needle: str, message: str) -> None:
        if needle not in text:
            findings.append(Finding(code, "entrypoint", message))

    require("WSL-SCRIPT-STRICT", "Set-StrictMode -Version Latest", "strict mode missing")
    require("WSL-SCRIPT-DISTRO", "ValidatePattern('^[A-Za-z0-9._-]{1,64}$')",
            "distribution is not syntactically bounded")
    require("WSL-SCRIPT-HIDDEN", "-WindowStyle Hidden", "keepalive opens a window")
    require("WSL-SCRIPT-KEEPALIVE", "'sleep', 'infinity'", "keepalive argv changed")
    require("WSL-SCRIPT-PID", "Get-CimInstance Win32_Process",
            "recorded PID command line is not revalidated")
    require("WSL-SCRIPT-PROJECT", "$Project = 'fincilia-local'",
            "compose project is not fixed")
    require("WSL-SCRIPT-COMPOSE", "$ComposeFile = 'infra/local/compose.yaml'",
            "compose file is not fixed")
    require("WSL-SCRIPT-ROOT", "'--cd', $RepositoryRoot", "workspace is not argv-bound")
    require("WSL-SCRIPT-LOCK", "[IO.FileMode]::CreateNew", "lifecycle has no atomic lock")
    require("WSL-SCRIPT-UP", "@('sh', 'infra/local/up.sh')",
            "up does not reuse the reviewed lifecycle")
    require("WSL-SCRIPT-DOWN", "$Project, 'down'", "down is not project-scoped")
    require("WSL-SCRIPT-STATUS", "services = @($services | Sort-Object service)",
            "status output is not reduced to the closed service view")

    forbidden = {
        "--volumes": "volume deletion",
        "--remove-orphans": "cross-project orphan removal",
        "docker system prune": "global Docker pruning",
        "wsl --shutdown": "global WSL shutdown",
        "wsl --terminate": "distribution termination",
        "Remove-Item -Recurse": "recursive deletion",
        "Invoke-Expression": "dynamic command execution",
        "services_json": "raw Compose status output",
    }
    lowered = text.lower()
    for needle, meaning in forbidden.items():
        if needle.lower() in lowered:
            findings.append(Finding("WSL-SCRIPT-DESTRUCTIVE", "entrypoint",
                                    f"script contains {meaning}"))
    return sorted(set(findings))


def validate_repository(root: Path = ROOT) -> list[Finding]:
    contract_path = root / CONTRACT.relative_to(ROOT)
    script_path = root / SCRIPT.relative_to(ROOT)
    findings: list[Finding] = []
    if not contract_path.is_file():
        return [Finding("WSL-CONTRACT-MISSING", str(contract_path), "contract is missing")]
    if not script_path.is_file():
        return [Finding("WSL-SCRIPT-MISSING", str(script_path), "entrypoint is missing")]
    try:
        document = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [Finding("WSL-CONTRACT-INVALID", str(contract_path), type(error).__name__)]
    findings.extend(validate_contract(document))
    findings.extend(validate_script(script_path.read_text(encoding="utf-8")))
    return sorted(set(findings))


def main() -> int:
    findings = validate_repository()
    print(json.dumps({"ok": not findings, "errors": [item.as_dict() for item in findings]},
                     indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
