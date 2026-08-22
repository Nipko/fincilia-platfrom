"""Validacion del contrato del spike (FNC-DB-002).

Comprueba `docs/database/migration-spike.json`: que declare hipotesis y limites,
que no seleccione herramienta, que no acepte ADR-002 y que la limpieza siga
confinada al proyecto de Compose del spike.

Un contrato valido no significa que el spike haya corrido. Son dos hechos
distintos y el CLI los reporta por separado.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.migration_spike.manifest import resolve_inside
from tools.migration_spike.suite import CASE_CATALOGUE

REQUIRED_TASK = "FNC-DB-002"
REQUIRED_PROJECT = "fincilia-db-spike"
OCI_DIGEST = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$")
FLOATING_TAGS = ("latest", "main", "head", "stable", "current", "edge", "nightly")
ACCEPTED_TOKENS = frozenset({"accepted", "approved", "met", "resolved", "closed", "signed",
                             "done", "selected"})
EXECUTION_STATES = ("not_executed", "passed", "failed", "error", "skipped")


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
        fail("MSC-SCHEMA", "schema_version", "schema_version must equal 1")
    if contract.get("task_id") != REQUIRED_TASK:
        fail("MSC-TASK", "task_id", f"task_id must be {REQUIRED_TASK}")
    if contract.get("status") != "review_pending":
        fail("MSC-STATUS", "status", "the spike stays review_pending")
    if contract.get("human_acceptance") != "pending":
        fail("MSC-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if contract.get("data_ceiling") != "synthetic_only":
        fail("MSC-DATA-CEILING", "data_ceiling", "expected synthetic_only")
    if contract.get("is_production_decision") is not False:
        fail("MSC-SCOPE", "is_production_decision",
             "a spike proves invariants; it does not promote anything to product")
    if contract.get("product_migrations_allowed") is not False:
        fail("MSC-SCOPE", "product_migrations_allowed",
             "this spike never touches db/migrations")
    if contract.get("modifies_shared_infrastructure") is not False:
        fail("MSC-SCOPE", "modifies_shared_infrastructure",
             "the spike must not modify infra/local, CI or productive roles")

    tooling = contract.get("tooling_decision", {})
    if not isinstance(tooling, dict):
        fail("MSC-TOOLING", "tooling_decision", "tooling_decision must be an object")
    else:
        if tooling.get("selected_tool") is not None:
            fail("MSC-TOOLING", "tooling_decision.selected_tool",
                 "the spike does not select a migration tool")
        if tooling.get("state") != "pending_human":
            fail("MSC-TOOLING", "tooling_decision.state",
                 "the tooling decision stays pending_human")
        if tooling.get("adr") != "ADR-002":
            fail("MSC-TOOLING", "tooling_decision.adr", "the decision belongs to ADR-002")
        if str(tooling.get("adr_state", "")).lower() in ACCEPTED_TOKENS:
            fail("MSC-ADR-ACCEPTED", "tooling_decision.adr_state",
                 "an agent cannot accept ADR-002, and passing this spike does not accept it")
        for field in ("owner_role", "reviewer_roles"):
            if not tooling.get(field):
                fail("MSC-TOOLING", f"tooling_decision.{field}",
                     f"the tooling decision needs {field}")

    environment = contract.get("environment", {})
    if not isinstance(environment, dict):
        fail("MSC-ENVIRONMENT", "environment", "environment must be an object")
    else:
        image = str(environment.get("postgres_image", ""))
        if not OCI_DIGEST.match(image):
            fail("MSC-IMAGE-PIN", "environment.postgres_image",
                 "the PostgreSQL artifact must be pinned by digest")
        if any(f":{tag}@" in image or image.endswith(f":{tag}") for tag in FLOATING_TAGS):
            fail("MSC-IMAGE-PIN", "environment.postgres_image",
                 "the image tag floats")
        if environment.get("compose_project") != REQUIRED_PROJECT:
            fail("MSC-PROJECT", "environment.compose_project",
                 f"the spike operates only on {REQUIRED_PROJECT!r}")
        if environment.get("publishes_host_port") is not False:
            fail("MSC-PORT", "environment.publishes_host_port",
                 "the spike is reached through compose exec; an open port is unused surface")
        if environment.get("network_internal") is not True:
            fail("MSC-NETWORK", "environment.network_internal",
                 "the laboratory network denies external routing")
        if not environment.get("healthcheck"):
            fail("MSC-HEALTHCHECK", "environment.healthcheck",
                 "the service declares a healthcheck")
        roles = environment.get("roles", {})
        for role in ("bootstrap", "migrator", "runtime"):
            if not roles.get(role):
                fail("MSC-ROLES", f"environment.roles.{role}",
                     "bootstrap, migrator and runtime are three separate roles")
        if len({roles.get("bootstrap"), roles.get("migrator"), roles.get("runtime")}) < 3:
            fail("MSC-ROLES", "environment.roles",
                 "the three roles must be genuinely different")

    policy = contract.get("migration_policy", {})
    for field, expected in (("transaction_per_migration", True),
                            ("destructive_down_migrations", False),
                            ("automatic_historical_rollback", False),
                            ("applied_file_edit_allowed", False),
                            ("startup_auto_migrate", False),
                            ("runtime_role_can_migrate", False),
                            ("runtime_role_owns_tables", False),
                            ("advisory_lock_serialises_migrators", True),
                            ("server_side_applied_at", True)):
        if policy.get(field) is not expected:
            fail("MSC-POLICY", f"migration_policy.{field}",
                 f"{field} must be {str(expected).lower()}")

    expand = contract.get("expand_contract", {})
    if not isinstance(expand, dict) or expand.get("proven_by_this_spike") is not False:
        fail("MSC-EXPAND", "expand_contract.proven_by_this_spike",
             "expand/contract is declared policy; one expand step does not prove N/N+1 "
             "compatibility for a real application")
    if not expand.get("policy"):
        fail("MSC-EXPAND", "expand_contract.policy", "declare the expand/contract policy")

    cleanup = contract.get("cleanup", {})
    if cleanup.get("scope") != REQUIRED_PROJECT:
        fail("MSC-CLEANUP", "cleanup.scope",
             f"cleanup is confined to {REQUIRED_PROJECT!r}")
    if cleanup.get("removes_foreign_volumes") is not False:
        fail("MSC-CLEANUP", "cleanup.removes_foreign_volumes",
             "the runner never removes a volume outside its own project")

    declared_cases = contract.get("cases", []) or []
    declared_ids = {str(case.get("case_id")) for case in declared_cases}
    catalogue_ids = {entry["case_id"] for entry in CASE_CATALOGUE}
    if declared_ids != catalogue_ids:
        fail("MSC-CASES", "cases",
             f"the contract and the runner disagree on the case set; "
             f"missing {sorted(catalogue_ids - declared_ids)}, "
             f"extra {sorted(declared_ids - catalogue_ids)}")
    for case in declared_cases:
        location = f"cases[{case.get('case_id')}]"
        for field in ("case_id", "invariant", "expectation", "owner_role", "gate",
                      "evidence_state"):
            if not case.get(field):
                fail("MSC-CASES", f"{location}.{field}", f"a case needs {field}")
        if case.get("evidence_state") not in EXECUTION_STATES:
            fail("MSC-EVIDENCE-STATE", f"{location}.evidence_state",
                 f"unknown execution state {case.get('evidence_state')!r}")
        if case.get("evidence_state") == "passed" and not case.get("evidence_ref"):
            fail("MSC-EVIDENCE-FABRICATED", f"{location}.evidence_ref",
                 "a case cannot be recorded as passed without pointing at the run that "
                 "produced the evidence")

    for index, gate in enumerate(contract.get("gates", []) or []):
        location = f"gates[{index}]"
        if gate.get("status") != "not_met":
            fail("MSC-GATE", f"{location}.status", "an agent cannot mark a gate as met")
        if str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("MSC-GATE", f"{location}.acceptance",
                 "an agent cannot record gate acceptance")

    for index, limit in enumerate(contract.get("limits", []) or []):
        if not str(limit).strip():
            fail("MSC-LIMITS", f"limits[{index}]", "an empty limit states nothing")
    if not contract.get("hypotheses"):
        fail("MSC-HYPOTHESES", "hypotheses", "declare what this spike is trying to learn")
    if not contract.get("limits"):
        fail("MSC-LIMITS", "limits", "declare what this spike cannot show")
    if not contract.get("anti_promises"):
        fail("MSC-ANTI-PROMISES", "anti_promises",
             "state plainly what a green run does not prove")

    for key in ("spike_root", "manifest_path"):
        relative = str(contract.get(key, ""))
        if resolve_inside(root, relative) is None:
            fail("MSC-PATH-UNSAFE", key,
                 f"{key} is absolute, traverses or escapes the repository")
        elif not (root / relative).exists():
            fail("MSC-PATH-MISSING", key, f"{key} does not exist: {relative}")

    return sorted(set(findings))
