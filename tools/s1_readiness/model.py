"""Validacion del contrato de readiness S1 (FNC-GAT-003).

Comprueba la estructura del registro: que las fuentes sean estructuradas y esten
dentro del arbol, que los checks sean allowlisted y con argv en lista, que cada
requisito tenga owner, revisores y gate, y que el contrato no se declare a si
mismo aceptado.

Un contrato valido no dice que S1 este listo. Son dos hechos distintos y el CLI
los reporta por separado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.s1_readiness.evaluate import CATEGORIES, SHELL_TOKENS
from tools.s1_readiness.sources import resolve_inside

REQUIRED_TASK = "FNC-GAT-003"
TARGET_GATE = "S1-READY"

REQUIREMENT_KINDS = (
    "machine_check", "human_decision", "nominal_owner", "gate", "adr", "adr_set",
    "decision_set", "no_contradiction", "evidence_freshness",
)
# Requisitos que se resuelven descubriendo un conjunto, no citando un id concreto.
SET_KINDS = ("adr_set", "decision_set", "no_contradiction", "evidence_freshness")
ALLOWED_MODULE_PREFIX = "tools."
ACCEPTED_TOKENS = frozenset({"accepted", "approved", "met", "resolved", "closed", "signed"})
# Modulos que exigen contenedores: `evaluate` no los ejecuta por defecto.
CONTAINER_MODULES = ("tools.migration_spike.cli", "tools.local_stack.compose")


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_contract(contract: dict[str, Any], root: Path) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if contract.get("schema_version") != 1:
        fail("S1R-SCHEMA", "schema_version", "schema_version must equal 1")
    if contract.get("task_id") != REQUIRED_TASK:
        fail("S1R-TASK", "task_id", f"task_id must be {REQUIRED_TASK}")
    if contract.get("status") != "review_pending":
        fail("S1R-STATUS", "status", "the aggregator stays review_pending")
    if contract.get("human_acceptance") != "pending":
        fail("S1R-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if contract.get("data_ceiling") != "synthetic_only":
        fail("S1R-DATA-CEILING", "data_ceiling", "expected synthetic_only")
    if contract.get("target_gate") != TARGET_GATE:
        fail("S1R-TARGET", "target_gate", f"the target gate is {TARGET_GATE}")
    if contract.get("initial_gate_status") != "not_met":
        fail("S1R-INITIAL", "initial_gate_status",
             "the gate starts not_met and only a human can change that")
    if contract.get("agent_may_accept") is not False:
        fail("S1R-AUTHORITY", "agent_may_accept",
             "an agent can never accept a gate")
    if contract.get("writes_central_state") is not False:
        fail("S1R-AUTHORITY", "writes_central_state",
             "this aggregator never writes CURRENT_PHASE, backlog, gates or decisions")
    if contract.get("aggregate_score_as_gate") is not False:
        fail("S1R-SCORE", "aggregate_score_as_gate",
             "a count or a percentage never approves a gate")
    if contract.get("runs_containers_in_evaluate") is not False:
        fail("S1R-CONTAINERS", "runs_containers_in_evaluate",
             "`evaluate` does not start containers; heavy checks consume declared evidence")

    aggregation = contract.get("aggregation", {})
    if aggregation.get("rule") != "conjunctive_fail_closed":
        fail("S1R-AGGREGATION", "aggregation.rule",
             "aggregation is conjunctive and fail-closed")
    satisfying = aggregation.get("satisfying_categories")
    if satisfying != ["machine_pass"]:
        fail("S1R-AGGREGATION", "aggregation.satisfying_categories",
             "only machine_pass satisfies a requirement; pending, unknown, stale, "
             "not_executed and contradiction never do")
    declared_categories = contract.get("categories", [])
    if sorted(declared_categories) != sorted(CATEGORIES):
        fail("S1R-CATEGORIES", "categories",
             f"categories must be exactly {sorted(CATEGORIES)}")

    precedence = contract.get("source_precedence", [])
    if not precedence or precedence[0] != "structured_json":
        fail("S1R-PRECEDENCE", "source_precedence",
             "structured JSON outranks narrative Markdown; the repository says so and "
             "this aggregator must not invert it")
    if "narrative_markdown" in precedence and \
            precedence.index("narrative_markdown") < len(precedence) - 1:
        fail("S1R-PRECEDENCE", "source_precedence",
             "narrative Markdown is the lowest precedence, never above a model")

    freshness = contract.get("freshness_policy", {})
    if "max_age_days" not in freshness:
        fail("S1R-FRESHNESS", "freshness_policy.max_age_days",
             "declare the freshness policy explicitly")
    elif freshness.get("max_age_days") is not None:
        fail("S1R-FRESHNESS", "freshness_policy.max_age_days",
             "no human has decided a maximum age; inventing a number would fabricate "
             "policy. Freshness is measured by digest, not by clock.")
    if freshness.get("measured_by") != "source_digest":
        fail("S1R-FRESHNESS", "freshness_policy.measured_by",
             "freshness is measured by comparing source digests")

    sources = contract.get("sources", []) or []
    if not sources:
        fail("S1R-SOURCES", "sources", "the aggregator declares no source of truth")
    seen_paths: set[str] = set()
    for index, source in enumerate(sources):
        location = f"sources[{source.get('path', index)}]"
        relative = str(source.get("path", ""))
        if resolve_inside(root, relative) is None:
            fail("S1R-PATH-UNSAFE", location,
                 "path is absolute, traverses, escapes the tree or is a symlink")
            continue
        if not (root / relative).is_file():
            fail("S1R-SOURCE-MISSING", location, "declared source does not exist")
        if relative in seen_paths:
            fail("S1R-SOURCE-DUPLICATE", location, "duplicate source")
        seen_paths.add(relative)
        if source.get("kind") not in ("json", "front_matter"):
            fail("S1R-SOURCE-KIND", location,
                 "only structured sources are read; prose is quoted, never trusted")
        if not (source.get("gates_keys") or source.get("decisions_keys")
                or source.get("adr_readiness") or source.get("flags_only")):
            fail("S1R-SOURCE-KEYS", location,
                 "declare which structured key this source contributes")

    checks = contract.get("machine_checks", []) or []
    if not checks:
        fail("S1R-CHECKS", "machine_checks", "the aggregator declares no machine check")
    check_ids: set[str] = set()
    for index, check in enumerate(checks):
        location = f"machine_checks[{check.get('id', index)}]"
        identifier = str(check.get("id", ""))
        if identifier in check_ids:
            fail("S1R-CHECK-DUPLICATE", location, "duplicate check id")
        check_ids.add(identifier)
        for field in ("id", "argv", "cwd", "timeout_seconds", "max_output_bytes",
                      "owner_role", "covers"):
            if check.get(field) in (None, "", []):
                fail("S1R-CHECK-FIELDS", f"{location}.{field}", f"a check needs {field}")
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or \
                not all(isinstance(item, str) for item in argv):
            fail("S1R-ARGV-LIST", f"{location}.argv",
                 "argv must be a non-empty list of strings")
        else:
            if argv[0] != "-m":
                fail("S1R-ARGV-FORM", f"{location}.argv",
                     "only `-m <module>` invocations are allowed")
            elif not str(argv[1]).startswith(ALLOWED_MODULE_PREFIX):
                fail("S1R-MODULE-ALLOWLIST", f"{location}.argv",
                     f"module {argv[1]!r} is outside the local tools namespace")
            elif any(str(argv[1]).startswith(module) for module in CONTAINER_MODULES) \
                    and "validate" not in argv:
                fail("S1R-CONTAINERS", f"{location}.argv",
                     "a container-dependent module may only be invoked in its structural "
                     "mode inside evaluate")
            for item in argv:
                if any(token in item for token in SHELL_TOKENS):
                    fail("S1R-ARGV-SHELL", f"{location}.argv",
                         f"argv element {item!r} contains shell syntax")
        cwd = str(check.get("cwd", "."))
        if cwd != "." and resolve_inside(root, cwd) is None:
            fail("S1R-CWD", f"{location}.cwd", f"cwd {cwd!r} is unsafe")
        timeout = check.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0 or timeout > 3600:
            fail("S1R-TIMEOUT", f"{location}.timeout_seconds",
                 "a check needs a positive bounded timeout")

    requirements = contract.get("requirements", []) or []
    if not requirements:
        fail("S1R-REQUIREMENTS", "requirements",
             "an aggregator with no requirement would approve everything")
    requirement_ids = {str(item.get("id", "")) for item in requirements}
    for index, requirement in enumerate(requirements):
        location = f"requirements[{requirement.get('id', index)}]"
        for field in ("id", "kind", "owner_role", "reviewer_roles", "gate", "explanation"):
            if requirement.get(field) in (None, "", []):
                fail("S1R-REQUIREMENT-FIELDS", f"{location}.{field}",
                     f"a requirement needs {field}")
        kind = str(requirement.get("kind", ""))
        if kind not in REQUIREMENT_KINDS:
            fail("S1R-REQUIREMENT-KIND", f"{location}.kind",
                 f"unknown requirement kind {kind!r}")
        if kind not in SET_KINDS and not requirement.get("ref"):
            fail("S1R-REQUIREMENT-FIELDS", f"{location}.ref",
                 "this requirement kind needs a ref")
        if kind == "machine_check" and str(requirement.get("ref")) not in check_ids:
            fail("S1R-REQUIREMENT-REF", f"{location}.ref",
                 f"machine check {requirement.get('ref')!r} is not declared")
        owner = requirement.get("owner_role")
        reviewers = requirement.get("reviewer_roles") or []
        if owner and owner in set(reviewers):
            fail("S1R-REQUIREMENT-OWNER", f"{location}.reviewer_roles",
                 "owner cannot be its own reviewer")
        for dependency in requirement.get("depends_on", []) or []:
            if dependency not in requirement_ids:
                fail("S1R-DEPENDENCY", f"{location}.depends_on",
                     f"unknown requirement {dependency!r}")
            if dependency == requirement.get("id"):
                fail("S1R-DEPENDENCY", f"{location}.depends_on",
                     "a requirement cannot depend on itself")

    covered = {str(item) for check in checks for item in check.get("covers", []) or []}
    for critical in contract.get("critical_coverage", []) or []:
        if str(critical) not in covered:
            fail("S1R-COVERAGE-OMISSION", "critical_coverage",
                 f"{critical!r} is declared critical but no machine check covers it; "
                 "removing a critical check is an omission, not an improvement")

    for dynamic in ("adr_set", "decision_set"):
        if not any(str(item.get("kind")) == dynamic for item in requirements):
            fail("S1R-REQUIREMENTS", "requirements",
                 f"the aggregator must declare a {dynamic} requirement so that a new ADR "
                 "or a new open decision is discovered instead of silently omitted")

    if not any(str(item.get("kind")) == "no_contradiction" for item in requirements):
        fail("S1R-REQUIREMENTS", "requirements",
             "the aggregator must require that no two structured sources contradict")

    for index, baseline in enumerate(contract.get("evidence_baseline", []) or []):
        location = f"evidence_baseline[{index}]"
        relative = str(baseline.get("path", ""))
        if resolve_inside(root, relative) is None:
            fail("S1R-PATH-UNSAFE", location, "baseline path is unsafe")
        for field in ("path", "sha256", "produced_by"):
            if not baseline.get(field):
                fail("S1R-EVIDENCE-FIELDS", f"{location}.{field}",
                     f"declared evidence needs {field}")

    for index, gate in enumerate(contract.get("gates", []) or []):
        location = f"gates[{index}]"
        if gate.get("status") != "not_met":
            fail("S1R-GATE", f"{location}.status", "an agent cannot mark a gate as met")
        if str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("S1R-GATE", f"{location}.acceptance",
                 "an agent cannot record gate acceptance")

    if not contract.get("anti_promises"):
        fail("S1R-ANTI-PROMISES", "anti_promises",
             "state plainly what this aggregator does not prove")

    return sorted(set(findings))
