"""Registro y validacion del contrato de la CLI de desarrollo (FNC-PLT-007).

La CLI no inventa comandos: los lee de `docs/platform/developer-cli.json` y los
cruza contra un allowlist cerrado que vive en el codigo. Un registro que pudiera
introducir un modulo nuevo seria un ejecutor de comandos disfrazado de
configuracion, asi que el contrato solo puede **elegir** entre lo permitido, no
**ampliarlo**.

Funciones puras. Sin red, reloj, entorno completo, Git ni aleatoriedad.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK = "FNC-PLT-007"

# Unico proyecto de Compose que esta CLI puede tocar.
ALLOWED_COMPOSE_PROJECT = "fincilia-local"
ALLOWED_COMPOSE_FILE = "infra/local/compose.yaml"

# Allowlist cerrado de modulos ejecutables. El contrato elige de aqui; no amplia.
ALLOWED_MODULES = frozenset({
    "tools.adr_readiness.validate",
    "tools.architecture_model.validate",
    "tools.brand_clearance.validate",
    "tools.budget_model.validate",
    "tools.canonical_model.validate",
    "tools.completeness_model.validate",
    "tools.connector_model.validate",
    "tools.cross_contract_model.validate",
    "tools.dfd_model.validate",
    "tools.event_model.validate",
    "tools.golden_harness.cli",
    "tools.idempotency_model.validate",
    "tools.lineage_model.validate",
    "tools.local_stack.validate",
    "tools.migration_readiness.validate",
    "tools.migration_spike.cli",
    "tools.mutation_harness.cli",
    "tools.privacy_model.validate",
    "tools.provider_evaluation.validate",
    "tools.quality_strategy.validate",
    "tools.region_decision.validate",
    "tools.research_protocol.validate",
    "tools.runtime_config.validate",
    "tools.supply_chain.cli",
    "tools.synthetic_corpus.cli",
    "tools.test_catalog.cli",
    "tools.threat_model.validate",
    "tools.ux_contract.validate",
    "tools.work_graph.validate",
    "tools.workspace_contract.validate",
    "tools.wsl_runtime.validate",
    "unittest",
})

# Comandos externos permitidos, sin argumentos libres.
ALLOWED_EXTERNAL = frozenset({"docker"})

VALIDATE_GROUPS = ("core", "security", "data", "qa")
TEST_GROUPS = ("unit", "golden", "mutation")
CLASSIFICATIONS = ("read_only", "local_reversible")

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_INVALID_USAGE = 2
EXIT_DEPENDENCY_MISSING = 3
EXIT_TIMEOUT = 4

EXIT_CODES = {
    "ok": EXIT_OK,
    "check_failed": EXIT_CHECK_FAILED,
    "invalid_usage": EXIT_INVALID_USAGE,
    "dependency_missing": EXIT_DEPENDENCY_MISSING,
    "timeout": EXIT_TIMEOUT,
}

SHELL_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "\n", "*", "~")
MAX_TIMEOUT_SECONDS = 3600
MAX_OUTPUT_BYTES = 4_194_304
ACCEPTED_TOKENS = frozenset({"accepted", "approved", "met", "resolved", "closed", "signed"})


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def safe_relative(raw: str) -> bool:
    if raw in ("", "."):
        return raw == "."
    if raw.startswith(("/", "\\")):
        return False
    if len(raw) > 1 and raw[1] == ":":
        return False
    return ".." not in Path(raw).parts


def resolve_inside(root: Path, relative: str) -> Path | None:
    if not safe_relative(relative):
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    if candidate.is_symlink():
        return None
    return candidate


def validate_contract(contract: dict[str, Any], root: Path) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if contract.get("schema_version") != 1:
        fail("DVC-SCHEMA", "schema_version", "schema_version must equal 1")
    if contract.get("task_id") != REQUIRED_TASK:
        fail("DVC-TASK", "task_id", f"task_id must be {REQUIRED_TASK}")
    if contract.get("status") != "review_pending":
        fail("DVC-STATUS", "status", "the contract stays review_pending")
    if contract.get("human_acceptance") != "pending":
        fail("DVC-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if contract.get("data_ceiling") != "synthetic_only":
        fail("DVC-DATA-CEILING", "data_ceiling", "expected synthetic_only")
    if contract.get("writes_gate_or_status") is not False:
        fail("DVC-AUTHORITY", "writes_gate_or_status",
             "this CLI never changes a gate, a status or a document")
    if contract.get("installs_or_updates_dependencies") is not False:
        fail("DVC-AUTHORITY", "installs_or_updates_dependencies",
             "this CLI does not install, update or purge anything")
    if contract.get("aggregate_score_as_gate") is not False:
        fail("DVC-SCORE", "aggregate_score_as_gate",
             "an aggregate score is never a verdict")

    exit_codes = contract.get("exit_codes", {})
    if exit_codes != EXIT_CODES:
        fail("DVC-EXIT-CODES", "exit_codes",
             f"exit codes must be exactly {EXIT_CODES}")

    environment = contract.get("environment_policy", {})
    if not isinstance(environment, dict):
        fail("DVC-ENV", "environment_policy", "environment_policy must be an object")
    else:
        allowlist = environment.get("env_allowlist")
        if not isinstance(allowlist, list) or not allowlist:
            fail("DVC-ENV", "environment_policy.env_allowlist",
                 "declare exactly which variables are inherited")
        else:
            for name in allowlist:
                upper = str(name).upper()
                if any(token in upper for token in
                       ("PROXY", "TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL")):
                    fail("DVC-ENV-LEAK", "environment_policy.env_allowlist",
                         f"{name!r} would inherit a proxy, a token or a credential")
        for field in ("inherits_proxies", "inherits_tokens", "inherits_credentials",
                      "shell"):
            if environment.get(field) is not False:
                fail("DVC-ENV", f"environment_policy.{field}",
                     f"{field} must be false")

    stack = contract.get("stack", {})
    if stack.get("compose_project") != ALLOWED_COMPOSE_PROJECT:
        fail("DVC-COMPOSE-PROJECT", "stack.compose_project",
             f"this CLI only ever touches {ALLOWED_COMPOSE_PROJECT!r}")
    if stack.get("compose_file") != ALLOWED_COMPOSE_FILE:
        fail("DVC-COMPOSE-FILE", "stack.compose_file",
             f"this CLI only ever uses {ALLOWED_COMPOSE_FILE!r}")
    for field in ("removes_volumes", "removes_orphans", "purges_data", "seeds_real_data",
                  "runs_product_migrations"):
        if stack.get(field) is not False:
            fail("DVC-STACK-DESTRUCTIVE", f"stack.{field}",
                 f"{field} must be false; this CLI never destroys local data")
    if stack.get("lock_required") is not True:
        fail("DVC-STACK-LOCK", "stack.lock_required",
             "two mutating stack commands must not run at once")

    degradation = contract.get("degradation", {})
    if degradation.get("doctor_requires_docker") is not False:
        fail("DVC-DEGRADATION", "degradation.doctor_requires_docker",
             "doctor must keep working without Docker")
    if degradation.get("missing_tool_is_diagnosis_not_traceback") is not True:
        fail("DVC-DEGRADATION", "degradation.missing_tool_is_diagnosis_not_traceback",
             "a missing tool produces a stable diagnosis, never a traceback")

    checks = contract.get("checks", []) or []
    if not checks:
        fail("DVC-CHECKS", "checks", "the registry declares no check at all")
    seen: set[str] = set()
    for index, check in enumerate(checks):
        location = f"checks[{check.get('id', index)}]"
        for field in ("id", "group", "kind", "module", "argv", "cwd", "timeout_seconds",
                      "max_output_bytes", "classification", "owner_role"):
            if check.get(field) in (None, "", []):
                fail("DVC-CHECK-FIELDS", f"{location}.{field}", f"a check needs {field}")
        identifier = str(check.get("id", ""))
        if identifier in seen:
            fail("DVC-CHECK-DUPLICATE", location, "duplicate check id")
        seen.add(identifier)

        module = str(check.get("module", ""))
        if module not in ALLOWED_MODULES:
            fail("DVC-MODULE-ALLOWLIST", f"{location}.module",
                 f"module {module!r} is not allowlisted")

        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or \
                not all(isinstance(item, str) for item in argv):
            fail("DVC-ARGV-LIST", f"{location}.argv",
                 "argv must be a non-empty list of strings")
        else:
            if argv[0] != "-m":
                fail("DVC-ARGV-FORM", f"{location}.argv",
                     "argv must start with -m; a command string is never accepted")
            elif len(argv) > 1 and argv[1] != module:
                fail("DVC-ARGV-FORM", f"{location}.argv",
                     "argv must run exactly the declared module")
            for item in argv:
                if any(token in item for token in SHELL_TOKENS):
                    fail("DVC-ARGV-SHELL", f"{location}.argv",
                         f"argv element {item!r} contains shell syntax")

        cwd = str(check.get("cwd", "."))
        if resolve_inside(root, cwd) is None:
            fail("DVC-CWD", f"{location}.cwd",
                 f"cwd {cwd!r} is absolute, traverses or is a symlink")

        group = str(check.get("group", ""))
        kind = str(check.get("kind", ""))
        if kind == "validate" and group not in VALIDATE_GROUPS:
            fail("DVC-GROUP", f"{location}.group",
                 f"unknown validate group {group!r}")
        if kind == "test" and group not in TEST_GROUPS:
            fail("DVC-GROUP", f"{location}.group", f"unknown test group {group!r}")
        if kind not in ("validate", "test"):
            fail("DVC-KIND", f"{location}.kind", f"unknown check kind {kind!r}")

        timeout = check.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
            fail("DVC-TIMEOUT", f"{location}.timeout_seconds",
                 "a check needs a positive bounded timeout")
        cap = check.get("max_output_bytes")
        if not isinstance(cap, int) or cap <= 0 or cap > MAX_OUTPUT_BYTES:
            fail("DVC-OUTPUT-CAP", f"{location}.max_output_bytes",
                 "a check needs a bounded output limit")

        classification = str(check.get("classification", ""))
        if classification not in CLASSIFICATIONS:
            fail("DVC-CLASSIFICATION", f"{location}.classification",
                 f"unknown classification {classification!r}")
        if kind in ("validate", "test") and classification != "read_only":
            fail("DVC-CLASSIFICATION", f"{location}.classification",
                 "a validate or test check only ever reads")

        requires = check.get("requires", []) or []
        for dependency in requires:
            if dependency not in {item.get("id") for item in
                                  contract.get("dependencies", []) or []}:
                fail("DVC-DEPENDENCY", f"{location}.requires",
                     f"undeclared dependency {dependency!r}")

    for index, dependency in enumerate(contract.get("dependencies", []) or []):
        location = f"dependencies[{dependency.get('id', index)}]"
        for field in ("id", "kind", "required", "probe_argv", "diagnosis"):
            if dependency.get(field) in (None, "", []):
                fail("DVC-DEPENDENCY", f"{location}.{field}",
                     f"a dependency needs {field}")
        probe = dependency.get("probe_argv") or []
        if probe and probe[0] not in ALLOWED_EXTERNAL:
            fail("DVC-DEPENDENCY-ALLOWLIST", f"{location}.probe_argv",
                 f"probe binary {probe[0]!r} is not allowlisted")
        for item in probe:
            if any(token in str(item) for token in SHELL_TOKENS):
                fail("DVC-ARGV-SHELL", f"{location}.probe_argv",
                     f"probe element {item!r} contains shell syntax")

    for index, gate in enumerate(contract.get("gates", []) or []):
        location = f"gates[{index}]"
        if gate.get("status") != "not_met":
            fail("DVC-GATE", f"{location}.status", "an agent cannot mark a gate as met")
        if str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("DVC-GATE", f"{location}.acceptance",
                 "an agent cannot record gate acceptance")

    if not contract.get("anti_promises"):
        fail("DVC-ANTI-PROMISES", "anti_promises",
             "state plainly what this CLI does not do")

    return sorted(set(findings))


def checks_for(contract: dict[str, Any], kind: str, group: str) -> list[dict[str, Any]]:
    """Selecciona checks de forma determinista y ordenada por id."""
    selected = [check for check in contract.get("checks", []) or []
                if check.get("kind") == kind
                and (group == "all" or check.get("group") == group)]
    return sorted(selected, key=lambda check: str(check.get("id", "")))


def known_groups(contract: dict[str, Any], kind: str) -> list[str]:
    return sorted({str(check.get("group")) for check in contract.get("checks", []) or []
                   if check.get("kind") == kind})


VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
