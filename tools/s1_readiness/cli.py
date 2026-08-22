"""CLI del agregador de readiness S1 (FNC-GAT-003).

    python -m tools.s1_readiness.cli validate
    python -m tools.s1_readiness.cli evaluate
    python -m tools.s1_readiness.cli explain [--owner ROLE] [--gate GATE]
    python -m tools.s1_readiness.cli graph

Codigos de salida, estables y deliberadamente distintos:

  0   la evaluacion es valida y el gate esta `met`
  10  la evaluacion es valida y el gate esta `not_met`  <- resultado normal hoy
  1   la evaluacion NO es valida: contrato invalido, fuente ilegible, check sin
      ejecutar o ciclo de dependencias
  2   uso invalido

Exit 0 nunca significa "gate aprobado por conveniencia": significa que todos los
requisitos, incluidas las aprobaciones humanas, estan satisfechos en una fuente
autoritativa.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.s1_readiness.evaluate import aggregate
from tools.s1_readiness.model import validate_contract

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = Path("docs/implementation/s1-readiness.json")

EXIT_GATE_MET = 0
EXIT_INVALID_EVALUATION = 1
EXIT_USAGE = 2
EXIT_GATE_NOT_MET = 10

EXIT_MEANING = {
    "0": "evaluation valid and gate met",
    "10": "evaluation valid and gate not_met",
    "1": "evaluation invalid",
    "2": "invalid usage",
}


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def resolve_root(raw: str | None) -> Path:
    if raw is None:
        return REPOSITORY_ROOT
    candidate = Path(raw)
    if ".." in candidate.parts:
        raise ValueError("root must not traverse with '..'")
    if candidate.is_symlink():
        raise ValueError("root must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise ValueError(f"root is not an existing directory: {raw}")
    return resolved


def _evaluation_exit(report: dict[str, Any]) -> int:
    if not report["evaluation_valid"]:
        return EXIT_INVALID_EVALUATION
    return EXIT_GATE_MET if report["gate_status"] == "met" else EXIT_GATE_NOT_MET


def command_validate(contract: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    errors = validate_contract(contract, root)
    payload = {
        "command": "validate",
        "contract_valid": not errors,
        "errors": [item.as_dict() for item in errors],
        "note": "La validez del contrato no dice nada sobre el estado del gate. "
                "Eso lo dice `evaluate`.",
        "ok": not errors,
    }
    return payload, EXIT_GATE_MET if not errors else EXIT_INVALID_EVALUATION


def command_evaluate(contract: dict[str, Any], root: Path,
                     verbose: bool) -> tuple[dict[str, Any], int]:
    errors = validate_contract(contract, root)
    if errors:
        return {"command": "evaluate", "evaluation_valid": False,
                "contract_errors": [item.as_dict() for item in errors],
                "gate_status": "not_met", "gate_acceptance": "pending_human",
                "reason": "the contract is invalid; nothing was evaluated"}, \
            EXIT_INVALID_EVALUATION

    report = aggregate(contract, root)
    if not verbose:
        for requirement in report["requirements"]:
            requirement["evidence"] = requirement["evidence"][:1]
    report["command"] = "evaluate"
    report["exit_code_meaning"] = EXIT_MEANING
    report["agent_may_accept"] = False
    return report, _evaluation_exit(report)


def command_explain(contract: dict[str, Any], root: Path,
                    owner: str | None, gate: str | None) -> tuple[dict[str, Any], int]:
    errors = validate_contract(contract, root)
    if errors:
        return {"command": "explain", "evaluation_valid": False,
                "contract_errors": [item.as_dict() for item in errors],
                "reason": "the contract is invalid; nothing was evaluated"}, \
            EXIT_INVALID_EVALUATION

    report = aggregate(contract, root)
    canonical = report["blockers"]
    shown = canonical
    if owner:
        shown = [row for row in shown if str(row["owner_role"]).lower() == owner.lower()]
    if gate:
        shown = [row for row in shown if str(row["gate"]).lower() == gate.lower()]

    payload = {
        "command": "explain",
        "filter": {"owner": owner, "gate": gate},
        "target_gate": report["target_gate"],
        "gate_status": report["gate_status"],
        "evaluation_valid": report["evaluation_valid"],
        # El filtro es una VISTA. El total canonico viaja siempre, para que
        # filtrar por owner no pueda hacer desaparecer un blocker del resultado.
        "canonical_blocker_count": len(canonical),
        "filtered_out_count": len(canonical) - len(shown),
        "shown_blocker_count": len(shown),
        "blockers": [{
            "id": row["id"], "kind": row["kind"], "ref": row["ref"],
            "category": row["category"], "owner_role": row["owner_role"],
            "reviewer_roles": row["reviewer_roles"], "gate": row["gate"],
            "explanation": row["explanation"],
        } for row in shown],
        "owners_with_blockers": sorted({str(row["owner_role"]) for row in canonical}),
        "gates_with_blockers": sorted({str(row["gate"]) for row in canonical}),
        "contradictions": report["contradictions"],
        "note": "Un filtro es una vista, no el resultado canonico: el total sigue "
                "arriba para que filtrar no pueda esconder un blocker.",
        "ok": report["evaluation_valid"] and not canonical,
    }
    return payload, _evaluation_exit(report)


def command_graph(contract: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    errors = validate_contract(contract, root)
    if errors:
        return {"command": "graph", "ok": False,
                "errors": [item.as_dict() for item in errors]}, EXIT_INVALID_EVALUATION

    nodes = []
    edges = []
    for requirement in contract.get("requirements", []) or []:
        identifier = str(requirement.get("id"))
        nodes.append({
            "id": identifier,
            "kind": requirement.get("kind"),
            "ref": requirement.get("ref", ""),
            "owner_role": requirement.get("owner_role"),
            "gate": requirement.get("gate"),
        })
        for dependency in sorted(requirement.get("depends_on", []) or []):
            edges.append({"from": dependency, "to": identifier})

    from tools.s1_readiness.evaluate import detect_cycles
    cycles = detect_cycles([
        {"id": node["id"],
         "depends_on": [edge["from"] for edge in edges if edge["to"] == node["id"]]}
        for node in nodes
    ])
    known_gates = {str(gate.get("id")) for gate in contract.get("gates", []) or []}
    unknown_gates = sorted({str(node["gate"]) for node in nodes
                            if str(node["gate"]) not in known_gates})

    payload = {
        "command": "graph",
        "target_gate": contract.get("target_gate"),
        "nodes": sorted(nodes, key=lambda node: node["id"]),
        "edges": sorted(edges, key=lambda edge: (edge["from"], edge["to"])),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "dependency_cycles": cycles,
        "unknown_gates": unknown_gates,
        "acyclic": not cycles,
        "ok": not cycles and not unknown_gates,
    }
    return payload, EXIT_GATE_MET if payload["ok"] else EXIT_INVALID_EVALUATION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia S1 readiness aggregator")
    parser.add_argument("--root", default=None)
    parser.add_argument("--contract", default=None)
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="contract and registry structure")
    subparsers.add_parser("evaluate", help="run allowlisted checks and aggregate")
    explain_parser = subparsers.add_parser("explain", help="actionable blockers")
    explain_parser.add_argument("--owner", default=None)
    explain_parser.add_argument("--gate", default=None)
    subparsers.add_parser("graph", help="machine-readable dependency graph")

    args = parser.parse_args(argv)
    _use_utf8_streams()

    try:
        root = resolve_root(args.root)
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return EXIT_USAGE

    contract_path = Path(args.contract) if args.contract else (root / DEFAULT_CONTRACT)
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": f"unreadable contract: {error}"}),
              file=sys.stderr)
        return EXIT_USAGE

    if args.command == "validate":
        payload, code = command_validate(contract, root)
    elif args.command == "evaluate":
        payload, code = command_evaluate(contract, root, args.verbose)
    elif args.command == "explain":
        payload, code = command_explain(contract, root, args.owner, args.gate)
    else:
        payload, code = command_graph(contract, root)

    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
