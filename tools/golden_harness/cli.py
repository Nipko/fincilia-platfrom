"""CLI del golden harness (FNC-QA-003): list, verify y run.

    python -m tools.golden_harness.cli list
    python -m tools.golden_harness.cli verify
    python -m tools.golden_harness.cli run
    python -m tools.golden_harness.cli run --case CASE_ID

Salida JSON determinista. Código de salida distinto de cero ante cualquier fallo,
incluida una selección de caso que no exista.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.golden_harness.registry import (
    load_registry,
    registry_digest,
    validate_registry,
)
from tools.golden_harness.runner import run_case

DEFAULT_REGISTRY = Path("docs/testing/golden-harness.json")


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def command_list(registry: dict, _root: Path) -> tuple[dict, int]:
    cases = [
        {
            "case_id": case.get("case_id"),
            "suite": case.get("suite"),
            "state": case.get("state"),
            "owner_role": case.get("owner_role"),
            "consumer_gates": case.get("consumer_gates", []),
            "test_refs": case.get("test_refs", []),
        }
        for case in registry.get("cases", [])
    ]
    return {"cases": sorted(cases, key=lambda item: str(item["case_id"])),
            "count": len(cases),
            "registry_digest": registry_digest(registry),
            "ok": True}, 0


def command_verify(registry: dict, root: Path) -> tuple[dict, int]:
    errors = validate_registry(registry, root)
    payload = {
        "errors": [error.as_dict() for error in errors],
        "registry_digest": registry_digest(registry),
        "cases": len(registry.get("cases", [])),
        "ok": not errors,
    }
    return payload, 0 if not errors else 1


def command_run(registry: dict, root: Path, selected: str | None) -> tuple[dict, int]:
    errors = validate_registry(registry, root)
    if errors:
        return {"errors": [error.as_dict() for error in errors],
                "ok": False,
                "reason": "registry verification failed; nothing was executed"}, 1

    cases = registry.get("cases", [])
    if selected is not None:
        cases = [case for case in cases if case.get("case_id") == selected]
        if not cases:
            # Una selección vacía nunca es un éxito silencioso.
            return {"ok": False, "selected": selected, "results": [],
                    "reason": f"no case matches {selected!r}"}, 1

    results = [run_case(case, registry, root) for case in cases]
    failed = [result["case_id"] for result in results if not result["passed"]]
    payload = {
        "registry_digest": registry_digest(registry),
        "executed": len(results),
        "failed": sorted(failed),
        "results": sorted(results, key=lambda item: str(item["case_id"])),
        "ok": not failed,
    }
    return payload, 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia golden harness")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--root", type=Path, default=Path("."))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list adjudicated cases")
    subparsers.add_parser("verify", help="validate the registry without executing anything")
    run_parser = subparsers.add_parser("run", help="verify and then execute cases")
    run_parser.add_argument("--case", dest="case", default=None)

    args = parser.parse_args(argv)
    root = args.root.resolve()
    registry = load_registry(args.registry)

    if args.command == "list":
        payload, code = command_list(registry, root)
    elif args.command == "verify":
        payload, code = command_verify(registry, root)
    else:
        payload, code = command_run(registry, root, args.case)

    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
