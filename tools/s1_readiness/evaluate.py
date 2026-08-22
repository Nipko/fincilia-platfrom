"""Agregacion fail-closed de readiness S1 (FNC-GAT-003).

La regla de composicion es **conjuntiva**: S1-READY solo puede estar `met` si
todos sus requisitos estan satisfechos. `unknown`, `pending`, `stale`,
`not_executed` y `contradiction` **no** cuentan como satisfechos. Un validador en
verde acredita un contrato ejecutable, no una aprobacion humana, y ningun agente
puede convertir lo primero en lo segundo.

Cuando dos fuentes estructuradas dicen cosas distintas del mismo sujeto, se
reporta contradiccion. Elegir en silencio seria inventar autoridad.
"""

from __future__ import annotations

import subprocess  # nosec B404 - argv list, shell=False, allowlisted local modules only
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.s1_readiness.sources import (
    Observation,
    extract_adr_readiness,
    extract_decisions,
    extract_document_flags,
    extract_gates,
    extract_owner_slots,
    extract_task_cards,
    is_assigned,
    is_met,
    read_json,
    resolve_inside,
    sha256_file,
)

CATEGORIES = (
    "machine_pass", "machine_fail", "not_executed", "pending_human",
    "blocked_dependency", "stale_evidence", "contradiction",
)
SATISFYING_CATEGORIES = frozenset({"machine_pass"})

ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE",
                 "LANG", "LC_ALL")
SHELL_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "\n", "*", "~")


class EvaluationError(Exception):
    """La evaluacion no puede realizarse con seguridad."""


def build_environment(parent: dict[str, str] | None = None) -> dict[str, str]:
    import os
    source = os.environ if parent is None else parent
    env = {name: source[name] for name in ENV_ALLOWLIST if name in source}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# --------------------------------------------------------------------------- #
# Recoleccion de observaciones
# --------------------------------------------------------------------------- #

def collect(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    observations: list[Observation] = []
    manifest: list[dict[str, str]] = []
    unreadable: list[dict[str, str]] = []

    for source in contract.get("sources", []) or []:
        relative = str(source.get("path", ""))
        kind = str(source.get("kind", "json"))
        if kind != "json":
            continue
        document, digest, reason = read_json(root, relative)
        if document is None:
            unreadable.append({"path": relative, "reason": reason})
            continue
        manifest.append({"path": relative, "sha256": digest, "kind": kind})
        observations += extract_document_flags(document, relative, digest)
        for key in source.get("gates_keys", []) or []:
            observations += extract_gates(document, str(key), relative, digest)
        for key in source.get("decisions_keys", []) or []:
            observations += extract_decisions(document, str(key), relative, digest)
        if source.get("adr_readiness"):
            observations += extract_adr_readiness(document, relative, digest)

    task_glob = str(contract.get("task_cards_glob", ""))
    if task_glob:
        task_observations, task_unreadable = extract_task_cards(root, task_glob)
        observations += task_observations
        unreadable += task_unreadable

    phase_path = str(contract.get("phase_path", ""))
    if phase_path:
        slots, reason = extract_owner_slots(root, phase_path)
        if reason:
            unreadable.append({"path": phase_path, "reason": reason})
        else:
            resolved = resolve_inside(root, phase_path)
            manifest.append({"path": phase_path,
                             "sha256": sha256_file(resolved) if resolved else "",
                             "kind": "front_matter"})
            observations += slots

    return {
        "observations": sorted(set(observations)),
        "source_manifest": sorted(manifest, key=lambda item: item["path"]),
        "unreadable_sources": sorted(unreadable, key=lambda item: item["path"]),
    }


def index_observations(observations: list[Observation]) -> dict[tuple[str, str, str], list[Observation]]:
    index: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    for observation in observations:
        index[(observation.subject_kind, observation.subject_id,
               observation.field_name)].append(observation)
    return index


def contradiction_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("subject_kind")), str(item.get("subject_id")),
            str(item.get("field")))


def triage_contradictions(contract: dict[str, Any], index: dict, contradictions: list[dict],
                          gate: str) -> dict[str, list[dict[str, Any]]]:
    """Separa contradicciones en bloqueantes, enrutadas a otro gate y sin enrutar.

    La relevancia se declara **explicitamente** en el contrato. Derivarla de que
    exista o no cierto requisito la volveria invisible: bastaria retirar un
    requisito para que una contradiccion dejara de bloquear sin que nadie lo
    decidiera.

    Una contradiccion que no es relevante para este gate **no desaparece**. O bien
    esta enrutada a un owner y a su propio gate, o bloquea. El silencio no es una
    resolucion.
    """
    relevance = contract.get("contradiction_relevance", {})
    relevant_gates = {str(gate)} | {str(item) for item in relevance.get("gates", []) or []}
    relevant_owners = {str(item) for item in relevance.get("owner_slots", []) or []}
    if relevance.get("owner_slots_from_requirements"):
        relevant_owners |= {
            str(item.get("ref")) for item in contract.get("requirements", []) or []
            if item.get("kind") == "nominal_owner" and item.get("ref")}
    required_adrs = {
        subject_id for (subject_kind, subject_id, field_name), group in index.items()
        if subject_kind == "adr" and field_name == "required_for_s1"
        and any(observation.value == "true" for observation in group)}
    relevant_decisions = {
        subject_id for (subject_kind, subject_id, field_name), group in index.items()
        if subject_kind == "decision" and field_name == "blocks_gate"
        and any(observation.value == gate for observation in group)}

    routed = {contradiction_key(item): item
              for item in contract.get("acknowledged_contradictions", []) or []}

    blocking: list[dict[str, Any]] = []
    acknowledged: list[dict[str, Any]] = []
    unrouted: list[dict[str, Any]] = []
    for item in contradictions:
        kind, subject = item["subject_kind"], item["subject_id"]
        is_relevant = (
            (kind == "gate" and subject in relevant_gates)
            or (kind == "decision" and subject in relevant_decisions)
            or (kind == "adr" and subject in required_adrs)
            or (kind == "owner_slot" and subject in relevant_owners)
        )
        if is_relevant:
            blocking.append(item)
            continue
        acknowledgement = routed.get(contradiction_key(item))
        if acknowledgement is None:
            unrouted.append(item)
            continue
        acknowledged.append({**item,
                             "routed_to_owner": acknowledgement.get("owner_role"),
                             "blocks_gate": acknowledgement.get("gate"),
                             "reason": acknowledgement.get("reason")})
    return {"blocking": blocking, "acknowledged": acknowledged, "unrouted": unrouted}


def detect_contradictions(observations: list[Observation],
                          ignored_fields: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Dos fuentes estructuradas que dicen cosas distintas del mismo sujeto."""
    contradictions: list[dict[str, Any]] = []
    for key, group in sorted(index_observations(observations).items()):
        kind, subject, field_name = key
        if field_name in ignored_fields:
            continue
        values = {item.value for item in group if item.value != ""}
        if len(values) <= 1:
            continue
        contradictions.append({
            "subject_kind": kind,
            "subject_id": subject,
            "field": field_name,
            "values": sorted(values),
            "sources": sorted({f"{item.source_path}{item.locator}" for item in group}),
            "resolution": "pending_human",
            "note": "Dos fuentes estructuradas discrepan. Elegir una en silencio seria "
                    "inventar autoridad, asi que el agregador reporta y bloquea.",
        })
    return contradictions


# --------------------------------------------------------------------------- #
# Checks de maquina
# --------------------------------------------------------------------------- #

def run_machine_check(check: dict[str, Any], root: Path,
                      env: dict[str, str] | None = None) -> dict[str, Any]:
    argv = list(check.get("argv", []))
    identifier = str(check.get("id", ""))
    for item in argv:
        if any(token in str(item) for token in SHELL_TOKENS):
            return {"id": identifier, "status": "refused", "exit_code": None,
                    "detail": f"argv element {item!r} contains shell syntax"}
    if not argv or argv[0] != "-m":
        return {"id": identifier, "status": "refused", "exit_code": None,
                "detail": "only `-m <module>` invocations are allowed"}
    cwd = str(check.get("cwd", "."))
    working = root if cwd == "." else resolve_inside(root, cwd)
    if working is None or not working.is_dir():
        return {"id": identifier, "status": "refused", "exit_code": None,
                "detail": f"cwd {cwd!r} is unsafe or missing"}
    environment = {**(env if env is not None else build_environment()),
                   "PYTHONPATH": str(root.resolve())}
    timeout = int(check.get("timeout_seconds", 300))
    cap = int(check.get("max_output_bytes", 262_144))
    try:
        completed = subprocess.run(  # nosec B603 - argv list, shell=False, allowlisted
            [sys.executable, *argv], cwd=str(working), env=environment,
            capture_output=True, shell=False, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"id": identifier, "status": "timeout", "exit_code": None,
                "detail": f"exceeded {timeout}s; a timeout is never a pass"}
    except (OSError, ValueError) as error:
        return {"id": identifier, "status": "not_executed", "exit_code": None,
                "detail": f"could not start: {type(error).__name__}"}
    truncated = len(completed.stdout) > cap or len(completed.stderr) > cap
    if truncated:
        return {"id": identifier, "status": "truncated", "exit_code": completed.returncode,
                "detail": "output truncated; the result could not be read"}
    expected = check.get("expected_exit_code", 0)
    if completed.returncode == expected:
        return {"id": identifier, "status": "passed", "exit_code": completed.returncode,
                "detail": ""}
    tail = (completed.stderr[:cap] or completed.stdout[:cap]).decode("utf-8", "replace")
    return {"id": identifier, "status": "failed", "exit_code": completed.returncode,
            "detail": tail.strip()[-300:]}


# --------------------------------------------------------------------------- #
# Evaluacion de requisitos
# --------------------------------------------------------------------------- #

def _observation_value(index: dict, kind: str, subject: str, field_name: str) -> str:
    group = index.get((kind, subject, field_name), [])
    values = sorted({item.value for item in group})
    return values[0] if len(values) == 1 else ("" if not values else "|".join(values))


def evaluate_requirements(contract: dict[str, Any], root: Path,
                          collected: dict[str, Any],
                          check_results: dict[str, dict[str, Any]],
                          contradictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = index_observations(collected["observations"])
    contradicted = {(item["subject_kind"], item["subject_id"]) for item in contradictions}
    results: dict[str, dict[str, Any]] = {}

    for requirement in contract.get("requirements", []) or []:
        identifier = str(requirement.get("id", ""))
        kind = str(requirement.get("kind", ""))
        ref = str(requirement.get("ref", ""))
        row: dict[str, Any] = {
            "id": identifier,
            "kind": kind,
            "ref": ref,
            "owner_role": requirement.get("owner_role", "UNASSIGNED"),
            "reviewer_roles": requirement.get("reviewer_roles", []),
            "gate": requirement.get("gate", "S1-READY"),
            "depends_on": sorted(requirement.get("depends_on", []) or []),
            "evidence": [],
        }

        if kind == "machine_check":
            outcome = check_results.get(ref)
            if outcome is None:
                row.update(category="not_executed",
                           explanation="the check was never executed, and an unexecuted "
                                       "check is not a pass")
            elif outcome["status"] == "passed":
                row.update(category="machine_pass",
                           explanation="the validator exited with its declared code")
            elif outcome["status"] in ("timeout", "truncated", "not_executed", "refused"):
                row.update(category="not_executed",
                           explanation=f"{outcome['status']}: {outcome['detail']}")
            else:
                row.update(category="machine_fail",
                           explanation=outcome["detail"] or "the validator failed")
            if outcome is not None:
                row["evidence"].append({
                    "command": "python " + " ".join(
                        str(item) for item in
                        next((c.get("argv", []) for c in contract.get("machine_checks", [])
                              if c.get("id") == ref), [])),
                    "exit_code": outcome["exit_code"],
                    "result": outcome["status"],
                    "runtime_version": ".".join(str(p) for p in sys.version_info[:3]),
                })

        elif kind == "human_decision":
            if ("decision", ref) in contradicted:
                row.update(category="contradiction",
                           explanation="two structured sources disagree about this decision")
            else:
                value = _observation_value(index, "decision", ref, "status")
                if not value:
                    row.update(category="pending_human",
                               explanation="no structured source records this decision; "
                                           "absence is never approval")
                elif is_met(value):
                    row.update(category="machine_pass",
                               explanation=f"approved in an authoritative source ({value})")
                else:
                    row.update(category="pending_human",
                               explanation=f"declared {value!r}; only a human approval in "
                                           "an authoritative source satisfies this")
                row["evidence"] += [item.as_dict() for item in
                                    index.get(("decision", ref, "status"), [])]

        elif kind == "nominal_owner":
            value = _observation_value(index, "owner_slot", ref, "assigned_to")
            if is_assigned(value):
                row.update(category="machine_pass",
                           explanation=f"assigned to {value}")
            else:
                row.update(category="pending_human",
                           explanation=f"{ref} is {value or 'absent'}; a gate cannot be "
                                       "approved by nobody")
            row["evidence"] += [item.as_dict() for item in
                                index.get(("owner_slot", ref, "assigned_to"), [])]

        elif kind == "gate":
            if ("gate", ref) in contradicted:
                row.update(category="contradiction",
                           explanation="two structured sources disagree about this gate")
            else:
                value = _observation_value(index, "gate", ref, "status")
                if not value:
                    row.update(category="pending_human",
                               explanation="no structured source declares this gate")
                elif is_met(value):
                    row.update(category="machine_pass",
                               explanation=f"declared {value} in an authoritative source")
                else:
                    row.update(category="pending_human",
                               explanation=f"declared {value!r}")
                row["evidence"] += [item.as_dict() for item in
                                    index.get(("gate", ref, "status"), [])]

        elif kind == "adr":
            value = _observation_value(index, "adr", ref, "readiness")
            required = _observation_value(index, "adr", ref, "required_for_s1")
            if not value:
                row.update(category="pending_human",
                           explanation="the ADR is not inventoried in adr-readiness.json")
            elif value == "ready":
                row.update(category="machine_pass", explanation="readiness is ready")
            else:
                row.update(category="pending_human",
                           explanation=f"readiness is {value!r}"
                                       f"{' and it is required for S1' if required else ''}")
            row["evidence"] += [item.as_dict() for item in
                                index.get(("adr", ref, "readiness"), [])]

        elif kind == "adr_set":
            # Conjunto DINAMICO: se descubre de required_s1_adrs, no se copia una
            # lista paralela que quedaria vieja en cuanto alguien anadiera un ADR.
            required = sorted({observation.subject_id
                               for (subject_kind, subject_id, field_name), group
                               in index.items()
                               if subject_kind == "adr" and field_name == "required_for_s1"
                               for observation in group if observation.value == "true"})
            not_ready = [identifier for identifier in required
                         if _observation_value(index, "adr", identifier, "readiness")
                         != "ready"]
            if not required:
                row.update(category="not_executed",
                           explanation="no source declares which ADR are required for S1")
            elif not_ready:
                row.update(category="pending_human",
                           explanation=f"{len(not_ready)} of {len(required)} required ADR "
                                       f"are not ready: {', '.join(not_ready)}")
            else:
                row.update(category="machine_pass",
                           explanation=f"all {len(required)} required ADR are ready")
            row["evidence"] = [{"required_s1_adrs": required, "not_ready": not_ready}]

        elif kind == "decision_set":
            target_gate = str(requirement.get("gate", contract.get("target_gate", "S1-READY")))
            # Una decision abierta solo bloquea este gate cuando su fuente lo dice
            # expresamente. Descubrir todas las decisiones del programa y hacerlas
            # bloquear S1 mezclaria gates posteriores (DRG, A-02, GA) con el
            # arranque sintetico de Sprint 1.
            decisions = sorted({subject_id
                                for (subject_kind, subject_id, field_name), group
                                in index.items()
                                if subject_kind == "decision" and field_name == "blocks_gate"
                                and any(observation.value == target_gate
                                        for observation in group)})
            unresolved = [identifier for identifier in decisions
                          if not is_met(_observation_value(index, "decision", identifier,
                                                           "status"))]
            if unresolved:
                row.update(category="pending_human",
                           explanation=f"{len(unresolved)} of {len(decisions)} discovered "
                                       "human decisions are still unresolved")
            else:
                row.update(category="machine_pass",
                           explanation=f"all {len(decisions)} discovered decisions are "
                                       "resolved in an authoritative source")
            row["evidence"] = [{"discovered": len(decisions),
                                "unresolved": unresolved[:40]}]

        elif kind == "no_contradiction":
            triage = triage_contradictions(contract, index, contradictions, row["gate"])
            blocking_contradictions = triage["blocking"]
            unrouted = triage["unrouted"]
            if blocking_contradictions or unrouted:
                row.update(
                    category="contradiction",
                    explanation=(
                        f"{len(blocking_contradictions)} contradictions relevant to "
                        f"{row['gate']} and {len(unrouted)} contradictions that nobody "
                        "routed to an owner remain unresolved"))
            else:
                row.update(category="machine_pass",
                           explanation=(
                               f"no contradiction relevant to {row['gate']} remains, and "
                               f"the {len(triage['acknowledged'])} observed elsewhere are "
                               "routed to a named owner and still block their own gate"))
            row["evidence"] = [{
                "blocking_contradictions": blocking_contradictions,
                "unrouted_contradictions": unrouted,
                "acknowledged_elsewhere": triage["acknowledged"],
            }]

        elif kind == "evidence_freshness":
            stale = [item for item in contract.get("evidence_baseline", []) or []
                     if _digest_of(root, str(item.get("path", ""))) != item.get("sha256")]
            if stale:
                row.update(category="stale_evidence",
                           explanation="the recorded digest no longer matches: "
                                       + ", ".join(str(item.get("path")) for item in stale))
            else:
                row.update(category="machine_pass",
                           explanation="every baseline digest still matches its source")

        else:
            row.update(category="not_executed",
                       explanation=f"unknown requirement kind {kind!r}")

        results[identifier] = row

    # Dependencias: un requisito cuyo predecesor no esta satisfecho queda bloqueado.
    for identifier, row in results.items():
        if row["category"] in SATISFYING_CATEGORIES:
            unmet = [dependency for dependency in row["depends_on"]
                     if results.get(dependency, {}).get("category")
                     not in SATISFYING_CATEGORIES]
            if unmet:
                row["category"] = "blocked_dependency"
                row["explanation"] = ("depends on unsatisfied requirements: "
                                      + ", ".join(sorted(unmet)))
    return [results[key] for key in sorted(results)]


def _digest_of(root: Path, relative: str) -> str:
    resolved = resolve_inside(root, relative)
    return sha256_file(resolved) if resolved and resolved.is_file() else ""


def detect_cycles(requirements: list[dict[str, Any]]) -> list[list[str]]:
    """Un grafo con ciclos no se puede evaluar: se reporta, no se rompe al azar."""
    graph = {row["id"]: list(row.get("depends_on", [])) for row in requirements}
    cycles: list[list[str]] = []
    state: dict[str, int] = {}

    def visit(node: str, trail: list[str]) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            start = trail.index(node)
            cycles.append(trail[start:] + [node])
            return
        state[node] = 1
        for neighbour in graph.get(node, []):
            if neighbour in graph:
                visit(neighbour, trail + [neighbour])
        state[node] = 2

    for node in sorted(graph):
        visit(node, [node])
    return [list(cycle) for cycle in sorted({tuple(cycle) for cycle in cycles})]


def aggregate(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    """Evaluacion completa. Conjuntiva y fail-closed."""
    collected = collect(contract, root)
    ignored = tuple(contract.get("contradiction_ignored_fields", []) or ())
    contradictions = detect_contradictions(collected["observations"], ignored)

    env = build_environment()
    check_results = {
        str(check.get("id")): run_machine_check(check, root, env)
        for check in contract.get("machine_checks", []) or []
    }

    requirements = evaluate_requirements(contract, root, collected, check_results,
                                         contradictions)
    cycles = detect_cycles(requirements)
    triage = triage_contradictions(
        contract, index_observations(collected["observations"]), contradictions,
        str(contract.get("target_gate", "S1-READY")))

    blockers = [row for row in requirements
                if row["category"] not in SATISFYING_CATEGORIES]
    counts = {category: sum(1 for row in requirements if row["category"] == category)
              for category in CATEGORIES
              if any(row["category"] == category for row in requirements)}

    evaluation_valid = (
        not collected["unreadable_sources"]
        and not cycles
        and not any(row["category"] == "not_executed" for row in requirements)
    )
    gate_met = evaluation_valid and not blockers

    return {
        "target_gate": contract.get("target_gate", "S1-READY"),
        "gate_status": "met" if gate_met else "not_met",
        "gate_acceptance": "pending_human",
        "evaluation_valid": evaluation_valid,
        "aggregation_rule": "conjunctive_fail_closed",
        "counts_by_category": counts,
        "requirement_count": len(requirements),
        "blocker_count": len(blockers),
        "requirements": requirements,
        "blockers": blockers,
        "contradictions": contradictions,
        "contradiction_triage": triage,
        "dependency_cycles": cycles,
        "machine_check_results": [check_results[key] for key in sorted(check_results)],
        "source_manifest": collected["source_manifest"],
        "unreadable_sources": collected["unreadable_sources"],
        "observation_count": len(collected["observations"]),
        "aggregate_score": None,
        "note": "Un validador en verde acredita un contrato ejecutable, no una "
                "aprobacion humana. Este agregador no puede convertir lo primero en "
                "lo segundo.",
    }
