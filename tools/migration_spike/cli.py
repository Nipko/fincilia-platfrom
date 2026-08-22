"""CLI del spike de migraciones (FNC-DB-002).

    python -m tools.migration_spike.cli validate
    python -m tools.migration_spike.cli plan
    python -m tools.migration_spike.cli run --suite all
    python -m tools.migration_spike.cli report

`plan` jamas muta nada. `run` solo opera el proyecto `fincilia-db-spike`.
`report` no inventa evidencia: si no hubo ejecucion, lo dice.

Codigos de salida:
  0  todo correcto
  1  algun caso fallo, o el contrato/manifiesto es invalido
  2  uso invalido o fichero ilegible
  3  no hay runtime de contenedores: los casos de PostgreSQL quedan not_executed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.migration_spike.contract import validate_contract
from tools.migration_spike.manifest import (
    load_manifest,
    plan,
    plan_digest,
    validate_manifest,
)
from tools.migration_spike.runner import SpikeLab, SpikeRunnerError, probe_adapter
from tools.migration_spike.suite import CASE_CATALOGUE, runtime_cases, static_cases

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = Path("docs/database/migration-spike.json")
DEFAULT_SPIKE = Path("spikes/FNC-DB-002")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_RUNTIME = 3


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


def load_all(root: Path, contract_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    spike_root = root / str(contract.get("spike_root", DEFAULT_SPIKE))
    manifest = load_manifest(root / str(contract.get("manifest_path")))
    return contract, manifest, spike_root


def structural_findings(contract: dict[str, Any], manifest: dict[str, Any],
                        root: Path, spike_root: Path) -> dict[str, Any]:
    contract_errors = validate_contract(contract, root)
    manifest_errors = validate_manifest(manifest, spike_root)
    return {
        "contract_errors": [item.as_dict() for item in contract_errors],
        "manifest_errors": [item.as_dict() for item in manifest_errors],
        "structural_valid": not contract_errors and not manifest_errors,
    }


def command_validate(contract, manifest, root, spike_root) -> tuple[dict[str, Any], int]:
    payload = structural_findings(contract, manifest, root, spike_root)
    payload["ok"] = payload["structural_valid"]
    payload["note"] = ("La validez estructural no dice que el spike haya corrido. "
                       "Eso lo dice `run`.")
    return payload, EXIT_OK if payload["ok"] else EXIT_FAILED


def command_plan(contract, manifest, root, spike_root) -> tuple[dict[str, Any], int]:
    structural = structural_findings(contract, manifest, root, spike_root)
    steps = plan(manifest)
    payload = {
        **structural,
        "compose_project": manifest.get("compose_project"),
        "plan": steps,
        "plan_digest": plan_digest(steps),
        "step_count": len(steps),
        "mutates_anything": False,
        "note": "Plan canonico ordenado por version. Este comando no toca la base de datos.",
        "ok": structural["structural_valid"],
    }
    return payload, EXIT_OK if payload["ok"] else EXIT_FAILED


def _not_executed(reason: str) -> list[dict[str, Any]]:
    return [{
        "case_id": entry["case_id"], "invariant": entry["invariant"],
        "expectation": entry["expectation"], "outcome": "not_executed",
        "detail": reason, "executions": [],
    } for entry in CASE_CATALOGUE if entry["kind"] == "runtime"]


def command_run(contract, manifest, root, spike_root, *, suite: str,
                keep: bool, verbose: bool) -> tuple[dict[str, Any], int]:
    structural = structural_findings(contract, manifest, root, spike_root)
    if not structural["structural_valid"]:
        return {**structural, "ok": False, "results": [],
                "reason": "structural validation failed; the laboratory was not started"}, \
            EXIT_FAILED

    adapter = probe_adapter()
    lab: SpikeLab | None = None
    lifecycle: list[dict[str, Any]] = []
    if adapter is not None:
        try:
            lab = SpikeLab(adapter, spike_root,
                           compose_file=str(manifest.get("compose_file", "compose.yaml")),
                           project=str(manifest.get("compose_project")),
                           database=str(manifest.get("database")))
        except SpikeRunnerError as error:
            return {**structural, "ok": False, "results": [],
                    "reason": f"the laboratory refused to start: {error}"}, EXIT_FAILED

    results = [item.as_dict(include_output=verbose)
               for item in static_cases(manifest, spike_root, lab, adapter)]

    if suite in ("all", "runtime"):
        if lab is None:
            results += _not_executed(
                "no container runtime answered; the PostgreSQL invariants were not "
                "executed and nothing was simulated")
        else:
            config = lab.config()
            lifecycle.append(config.as_dict(include_output=verbose))
            if config.status != "completed" or config.exit_code != 0:
                results += _not_executed(
                    f"`compose config` failed ({config.status}/{config.exit_code}); "
                    "the laboratory was never started")
            else:
                results += [item.as_dict(include_output=verbose)
                            for item in runtime_cases(lab, manifest)]
                if not keep:
                    lifecycle.append(lab.down().as_dict(include_output=verbose))

    outcomes = {name: sum(1 for item in results if item["outcome"] == name)
                for name in sorted({item["outcome"] for item in results})}
    failed = [item["case_id"] for item in results if item["outcome"] in ("fail", "error")]
    pending = [item["case_id"] for item in results if item["outcome"] == "not_executed"]

    payload = {
        **structural,
        "runtime_adapter": (adapter or {}).get("id", "none"),
        "docker_server_version": (adapter or {}).get("server_version", ""),
        "compose_project": manifest.get("compose_project"),
        "plan_digest": plan_digest(plan(manifest)),
        "outcomes": outcomes,
        "failed_cases": sorted(failed),
        "not_executed_cases": sorted(pending),
        "results": results,
        "lifecycle": lifecycle,
        "adr_002_accepted": False,
        "note": "Un spike verde prueba invariantes, no selecciona herramienta ni acepta "
                "ADR-002.",
        "ok": not failed and not pending,
    }
    if failed:
        return payload, EXIT_FAILED
    if pending:
        return payload, EXIT_NO_RUNTIME
    return payload, EXIT_OK


def command_report(contract, manifest, root, spike_root) -> tuple[dict[str, Any], int]:
    """El informe no ejecuta nada y no inventa evidencia."""
    structural = structural_findings(contract, manifest, root, spike_root)
    adapter = probe_adapter()
    declared = {str(case.get("case_id")): case for case in contract.get("cases", []) or []}
    rows = []
    for entry in CASE_CATALOGUE:
        case = declared.get(entry["case_id"], {})
        rows.append({
            "case_id": entry["case_id"],
            "invariant": entry["invariant"],
            "kind": entry["kind"],
            "matrix_ref": entry["matrix_ref"],
            "owner_role": case.get("owner_role", "UNASSIGNED"),
            "gate": case.get("gate", "ADR-002-MIGRATIONS"),
            "declared_evidence_state": case.get("evidence_state", "not_executed"),
            "evidence_ref": case.get("evidence_ref", ""),
        })
    payload = {
        **structural,
        "runtime_available": adapter is not None,
        "runtime_adapter": (adapter or {}).get("id", "none"),
        "cases": rows,
        "tooling_decision": contract.get("tooling_decision", {}),
        "gates": contract.get("gates", []),
        "limits": contract.get("limits", []),
        "anti_promises": contract.get("anti_promises", []),
        "aggregate_score": None,
        "note": "Este informe describe lo declarado y si hay runtime disponible. "
                "La evidencia de ejecucion la produce `run`, no este comando.",
        "ok": structural["structural_valid"],
    }
    return payload, EXIT_OK if payload["ok"] else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia migration invariant spike")
    parser.add_argument("--root", default=None)
    parser.add_argument("--contract", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="contract and manifest structure")
    subparsers.add_parser("plan", help="canonical plan; never mutates anything")
    run_parser = subparsers.add_parser("run", help="operate the spike laboratory")
    run_parser.add_argument("--suite", choices=("all", "runtime", "static"), default="all")
    run_parser.add_argument("--keep", action="store_true",
                            help="leave the laboratory running after the suite")
    run_parser.add_argument("--verbose", action="store_true",
                            help="include bounded output tails in the manifest")
    subparsers.add_parser("report", help="declared cases, gates and limits")

    args = parser.parse_args(argv)
    _use_utf8_streams()

    try:
        root = resolve_root(args.root)
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return EXIT_USAGE

    contract_path = Path(args.contract) if args.contract else (root / DEFAULT_CONTRACT)
    try:
        contract, manifest, spike_root = load_all(root, contract_path)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        print(json.dumps({"ok": False, "error": f"unreadable contract or manifest: {error}"}),
              file=sys.stderr)
        return EXIT_USAGE

    if args.command == "validate":
        payload, code = command_validate(contract, manifest, root, spike_root)
    elif args.command == "plan":
        payload, code = command_plan(contract, manifest, root, spike_root)
    elif args.command == "report":
        payload, code = command_report(contract, manifest, root, spike_root)
    else:
        payload, code = command_run(contract, manifest, root, spike_root,
                                    suite=args.suite, keep=args.keep, verbose=args.verbose)

    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
