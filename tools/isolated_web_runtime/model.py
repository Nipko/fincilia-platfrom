"""Validacion fail-closed del runtime web desechable.

Este modulo no ejecuta Docker. Comprueba que el contrato, Compose y ambos
entrypoints mantengan separadas la regresion automatizada y la demo persistente.
Las comprobaciones deliberadamente redundantes protegen la unica operacion
destructiva de la rebanada: eliminar los volumenes del proyecto E2E exacto.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


REQUIRED_PHASES = (
    "validate_constants",
    "preclean",
    "build",
    "dependencies",
    "migrate",
    "synthetic_seed",
    "acceptance_fixture",
    "applications",
    "readiness",
    "isolation_probe",
    "chromium",
    "axe",
    "cleanup",
    "absence_probe",
)
EXPECTED_ENTRYPOINTS = {
    "windows_orchestrator": "infra/local/test-web-isolated.ps1",
    "wsl_lifecycle": "infra/local/test-web-isolated.sh",
    "compose_file": "infra/local/compose.yaml",
}
DISPOSABLE_PROJECT = "fincilia-e2e"
PERSISTENT_PROJECT = "fincilia-local"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate_contract(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if model.get("task_id") != "FNC-QA-009":
        findings.append(Finding("IWR-TASK", "contract must belong to FNC-QA-009"))
    if model.get("data_ceiling") != "synthetic_only":
        findings.append(Finding("IWR-DATA", "runtime must remain synthetic_only"))

    entrypoints = model.get("entrypoints")
    if entrypoints != EXPECTED_ENTRYPOINTS:
        findings.append(Finding(
            "IWR-ENTRYPOINT",
            "entrypoints are not the three repository-owned allowlisted paths",
        ))

    persistent = model.get("persistent_runtime", {})
    disposable = model.get("disposable_runtime", {})
    if persistent.get("project") != PERSISTENT_PROJECT:
        findings.append(Finding("IWR-PERSISTENT-PROJECT", "persistent project drifted"))
    if disposable.get("project") != DISPOSABLE_PROJECT:
        findings.append(Finding("IWR-DISPOSABLE-PROJECT", "disposable project drifted"))
    if persistent.get("project") == disposable.get("project"):
        findings.append(Finding("IWR-PROJECT-COLLISION", "projects must be disjoint"))
    if disposable.get("accepts_resource_name_input") is not False:
        findings.append(Finding(
            "IWR-RESOURCE-INPUT",
            "resource names must be closed constants, never caller input",
        ))

    for resource in ("volumes", "networks"):
        durable = set(_as_list(persistent.get(resource)))
        ephemeral = set(_as_list(disposable.get(resource)))
        if len(durable) != 2 or len(ephemeral) != 2:
            findings.append(Finding(
                "IWR-RESOURCE-COUNT", f"both runtimes need exactly two {resource}",
            ))
        overlap = sorted(durable & ephemeral)
        if overlap:
            findings.append(Finding(
                "IWR-RESOURCE-COLLISION", f"shared {resource}: {overlap}",
            ))
        if any(not str(item).startswith("fincilia_e2e_") for item in ephemeral):
            findings.append(Finding(
                "IWR-RESOURCE-NAME", f"disposable {resource} lack fincilia_e2e_ prefix",
            ))

    durable_ports = set(_as_list(persistent.get("published_ports")))
    port_map = disposable.get("published_ports", {})
    if not isinstance(port_map, dict) or set(port_map) != {
        "web", "api", "object", "object_console"
    }:
        findings.append(Finding("IWR-PORT-MAP", "four named disposable ports are required"))
        ephemeral_ports: list[Any] = []
    else:
        ephemeral_ports = list(port_map.values())
    if len(ephemeral_ports) != len(set(ephemeral_ports)):
        findings.append(Finding("IWR-PORT-COLLISION", "disposable ports must be unique"))
    if durable_ports & set(ephemeral_ports):
        findings.append(Finding("IWR-PORT-COLLISION", "a disposable port reuses the demo"))
    if any(not isinstance(port, int) or not 1024 <= port <= 65535
           for port in ephemeral_ports):
        findings.append(Finding("IWR-PORT-RANGE", "disposable ports must be valid integers"))
    if disposable.get("bind_address") != "127.0.0.1":
        findings.append(Finding("IWR-LOOPBACK", "published ports must bind to loopback"))

    for field in ("precleans_exact_project", "removes_volumes_on_cleanup",
                  "removes_orphans_on_cleanup"):
        if disposable.get(field) is not True:
            findings.append(Finding("IWR-CLEANUP", f"{field} must be true"))

    execution = model.get("execution", {})
    if tuple(_as_list(execution.get("phases"))) != REQUIRED_PHASES:
        findings.append(Finding(
            "IWR-PHASES", "execution phases are missing, reordered or duplicated",
        ))
    if execution.get("browser_base_url") != "http://127.0.0.1:53100":
        findings.append(Finding("IWR-BASE-URL", "browser must target isolated web port"))
    if execution.get("api_base_url") != "http://127.0.0.1:58180":
        findings.append(Finding("IWR-API-URL", "test helpers must target isolated API port"))
    if execution.get("npm_scripts") != ["test:e2e", "test:a11y"]:
        findings.append(Finding("IWR-SUITES", "Chromium and Axe are both mandatory"))
    if execution.get("playwright_workers") != 1:
        findings.append(Finding("IWR-WORKERS", "shared synthetic fixtures require one worker"))
    for field in ("cleanup_in_finally", "cleanup_after_success", "cleanup_after_failure"):
        if execution.get(field) is not True:
            findings.append(Finding("IWR-CLEANUP", f"{field} must be true"))
    if execution.get("repeatable_runs_required") != 2:
        findings.append(Finding("IWR-REPEAT", "acceptance requires two clean runs"))
    return sorted(set(findings))


def validate_scripts(shell: str, powershell: str, compose: str) -> list[Finding]:
    findings: list[Finding] = []
    shell_required = (
        "PROJECT=fincilia-e2e",
        "PGDATA_VOLUME=fincilia_e2e_pgdata",
        "OBJECTDATA_VOLUME=fincilia_e2e_objectdata",
        "PRIVATE_NETWORK=fincilia_e2e_private",
        "EDGE_NETWORK=fincilia_e2e_edge",
        'EXPECTED_PROJECT=fincilia-e2e',
        'compose down --volumes --remove-orphans',
        'python -m db.seed.local',
        '/checks/e2e_fixture.py',
        '/health/ready',
        'assert_isolated',
        'assert_absent',
    )
    for marker in shell_required:
        if marker not in shell:
            findings.append(Finding("IWR-SHELL", f"WSL lifecycle is missing {marker!r}"))
    if re.search(r"PROJECT=\$|PROJECT=\$\{|PROJECT=\"\$", shell):
        findings.append(Finding("IWR-PROJECT-INPUT", "project cannot come from environment/input"))
    if 'fincilia_local_pgdata' in shell or 'fincilia_local_objectdata' in shell:
        findings.append(Finding(
            "IWR-PERSISTENT-TARGET", "disposable helper names a persistent volume",
        ))
    if 'fincilia_local_private' in shell or 'fincilia_local_edge' in shell:
        findings.append(Finding(
            "IWR-PERSISTENT-TARGET", "disposable helper names a persistent network",
        ))

    ps_required = (
        "finally",
        "test:e2e",
        "test:a11y",
        "http://127.0.0.1:53100",
        "http://127.0.0.1:58180",
        "FINCILIA_E2E_API_URL",
        "test-web-isolated.sh",
        "'down'",
        "'assert-clean'",
    )
    for marker in ps_required:
        if marker not in powershell:
            findings.append(Finding("IWR-POWERSHELL", f"orchestrator is missing {marker!r}"))
    if re.search(r"(?im)^\s*\[string\]\s*\$Project\b", powershell):
        findings.append(Finding("IWR-PROJECT-INPUT", "PowerShell cannot accept a project"))

    compose_required = (
        "${FINCILIA_LOCAL_PGDATA_VOLUME:-fincilia_local_pgdata}",
        "${FINCILIA_LOCAL_OBJECTDATA_VOLUME:-fincilia_local_objectdata}",
        "${FINCILIA_LOCAL_PRIVATE_NETWORK:-fincilia_local_private}",
        "${FINCILIA_LOCAL_EDGE_NETWORK:-fincilia_local_edge}",
    )
    for marker in compose_required:
        if marker not in compose:
            findings.append(Finding(
                "IWR-COMPOSE-OVERRIDE", f"Compose lacks safe override {marker!r}",
            ))
    return sorted(set(findings))


def validate_repository(root: Path) -> list[Finding]:
    contract_path = root / "docs/platform/isolated-web-runtime.json"
    shell_path = root / "infra/local/test-web-isolated.sh"
    ps_path = root / "infra/local/test-web-isolated.ps1"
    compose_path = root / "infra/local/compose.yaml"
    missing = [path.relative_to(root).as_posix() for path in
               (contract_path, shell_path, ps_path, compose_path) if not path.is_file()]
    if missing:
        return [Finding("IWR-MISSING", f"missing repository paths: {missing}")]
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return [Finding("IWR-JSON", f"invalid contract JSON: {error}")]
    return sorted(set(
        validate_contract(contract)
        + validate_scripts(
            shell_path.read_text(encoding="utf-8"),
            ps_path.read_text(encoding="utf-8-sig"),
            compose_path.read_text(encoding="utf-8"),
        )
    ))
