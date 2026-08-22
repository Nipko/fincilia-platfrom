"""CLI del arnés de mutaciones (FNC-QA-005).

    python -m tools.mutation_harness.cli list
    python -m tools.mutation_harness.cli verify
    python -m tools.mutation_harness.cli run
    python -m tools.mutation_harness.cli run --mutation MUTATION_ID
    python -m tools.mutation_harness.cli report

Salida JSON determinista. Un superviviente de riesgo crítico produce exit
distinto de cero. `equivalent_pending_review` nunca cuenta como `killed`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.mutation_harness.registry import (
    load_registry,
    registry_digest,
    source_tree_digests_paths,
    validate_registry,
)
from tools.mutation_harness.runner import run_mutation, source_tree_digests

DEFAULT_REGISTRY = Path("docs/testing/mutation-harness.json")
BLOCKING_SEVERITIES = {"critical", "high"}


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def command_list(registry: dict, _root: Path) -> tuple[dict, int]:
    rows = [{
        "mutation_id": m.get("mutation_id"),
        "validator": m.get("validator"),
        "operator": m.get("operator"),
        "risk_refs": m.get("risk_refs", []),
        "control_refs": m.get("control_refs", []),
        "state": m.get("state"),
        "owner_role": m.get("owner_role"),
        "gate": m.get("gate"),
        "expectation_kind": m.get("expectation", {}).get("kind"),
    } for m in registry.get("mutations", [])]
    return {"mutations": sorted(rows, key=lambda r: str(r["mutation_id"])),
            "count": len(rows),
            "declared_gaps": registry.get("declared_gaps", []),
            "registry_digest": registry_digest(registry), "ok": True}, 0


def command_verify(registry: dict, root: Path) -> tuple[dict, int]:
    errors = validate_registry(registry, root)
    return {"errors": [e.as_dict() for e in errors],
            "mutations": len(registry.get("mutations", [])),
            "validators": len(registry.get("validators", [])),
            "registry_digest": registry_digest(registry),
            "ok": not errors}, 0 if not errors else 1


def severity_of(registry: dict, risk_refs: list[str]) -> str:
    severities = registry.get("risk_severity", {})
    ranked = [severities.get(risk, "unknown") for risk in risk_refs]
    for level in ("critical", "high", "medium", "low"):
        if level in ranked:
            return level
    return "unknown"


def command_run(registry: dict, root: Path, selected: str | None) -> tuple[dict, int]:
    errors = validate_registry(registry, root)
    if errors:
        return {"errors": [error.as_dict() for error in errors], "ok": False,
                "reason": "registry verification failed; nothing was executed"}, 1

    mutations = registry.get("mutations", [])
    if selected is not None:
        mutations = [m for m in mutations if m.get("mutation_id") == selected]
        if not mutations:
            return {"ok": False, "selected": selected, "results": [],
                    "reason": f"no mutation matches {selected!r}"}, 1

    watched = source_tree_digests_paths(registry)
    before = source_tree_digests(root, watched)
    results = [run_mutation(mutation, registry, root) for mutation in mutations]
    after = source_tree_digests(root, watched)

    survivors = [r for r in results if r["outcome"] == "survived"]
    blocking_survivors = sorted(
        r["mutation_id"] for r in survivors
        if severity_of(registry, r.get("risk_refs", [])) in BLOCKING_SEVERITIES)
    unresolved = sorted(r["mutation_id"] for r in results
                        if r["outcome"] in {"invalid", "error", "equivalent_pending_review"})

    payload = {
        "registry_digest": registry_digest(registry),
        "executed": len(results),
        "outcomes": {outcome: sum(1 for r in results if r["outcome"] == outcome)
                     for outcome in sorted({r["outcome"] for r in results})},
        "survivors": sorted(r["mutation_id"] for r in survivors),
        "blocking_survivors": blocking_survivors,
        "unresolved": unresolved,
        "source_tree_unchanged": before == after,
        "results": sorted(results, key=lambda r: str(r["mutation_id"])),
        "ok": not blocking_survivors and not unresolved and before == after,
    }
    return payload, 0 if payload["ok"] else 1


def command_report(registry: dict, root: Path) -> tuple[dict, int]:
    payload, _ = command_run(registry, root, None)
    if "results" not in payload:
        return payload, 1
    by_risk: dict[str, dict[str, int]] = {}
    by_control: dict[str, dict[str, int]] = {}
    for result in payload["results"]:
        for risk in result.get("risk_refs", []):
            bucket = by_risk.setdefault(risk, {})
            bucket[result["outcome"]] = bucket.get(result["outcome"], 0) + 1
        for control in result.get("control_refs", []):
            bucket = by_control.setdefault(control, {})
            bucket[result["outcome"]] = bucket.get(result["outcome"], 0) + 1
    report = {
        "registry_digest": payload["registry_digest"],
        "executed": payload["executed"],
        "outcomes": payload["outcomes"],
        "by_risk": dict(sorted(by_risk.items())),
        "by_control": dict(sorted(by_control.items())),
        "survivors": payload["survivors"],
        "blocking_survivors": payload["blocking_survivors"],
        "unresolved": payload["unresolved"],
        "declared_gaps": registry.get("declared_gaps", []),
        "source_tree_unchanged": payload["source_tree_unchanged"],
        "single_pass_score": None,
        "note": "No hay nota unica. Un mutation score alto no acredita seguridad, "
                "exactitud contable ni infraestructura real.",
        "ok": payload["ok"],
    }
    return report, 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia mutation harness")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--root", type=Path, default=Path("."))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list declared mutations and gaps")
    subparsers.add_parser("verify", help="validate the registry without executing anything")
    run_parser = subparsers.add_parser("run", help="verify and then execute mutations")
    run_parser.add_argument("--mutation", dest="mutation", default=None)
    subparsers.add_parser("report", help="outcomes by risk and control, without a single score")

    args = parser.parse_args(argv)
    _use_utf8_streams()
    root = args.root.resolve()
    registry = load_registry(args.registry)

    if args.command == "list":
        payload, code = command_list(registry, root)
    elif args.command == "verify":
        payload, code = command_verify(registry, root)
    elif args.command == "report":
        payload, code = command_report(registry, root)
    else:
        payload, code = command_run(registry, root, args.mutation)

    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
