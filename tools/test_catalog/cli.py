"""CLI del catálogo ejecutable de pruebas (FNC-QA-004).

    python -m tools.test_catalog.cli discover
    python -m tools.test_catalog.cli validate
    python -m tools.test_catalog.cli report
    python -m tools.test_catalog.cli project --format json

JSON por stdout, errores por stderr, salida ordenada y determinista.
`--root` se acepta solo si resuelve dentro de un árbol existente y sin traversal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.test_catalog.reconcile import (
    discover,
    load_model,
    project,
    reconcile,
    validate_model,
)

DEFAULT_MODEL = Path("docs/testing/test-catalog-model.json")


def _use_utf8_streams() -> None:
    """La salida es UTF-8 aunque la consola declare otra cosa.

    Sin esto, una consola cp1252 aborta con `UnicodeEncodeError` en cuanto un
    detalle de procedencia contiene un caracter fuera de su tabla, y el comando
    dejaria de ser determinista entre entornos.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _fail(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False,
                     indent=2, sort_keys=True), file=sys.stderr)
    return 2


def resolve_root(raw: Path) -> Path | None:
    """Acepta una raíz solo si existe, es un directorio y no es un symlink."""
    if ".." in raw.parts:
        return None
    if raw.is_symlink():
        return None
    candidate = raw.resolve()
    if not candidate.is_dir():
        return None
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia executable test catalogue")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--root", type=Path, default=Path("."))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("discover", help="stable inventory of identifiers and provenance")
    subparsers.add_parser("validate", help="model validity plus repository reconciliation")
    subparsers.add_parser("report", help="counts by state, finding, severity, owner and gate")
    projection = subparsers.add_parser("project", help="machine-readable catalogue proposal")
    projection.add_argument("--format", dest="output_format", default="json", choices=["json"])

    args = parser.parse_args(argv)
    _use_utf8_streams()
    root = resolve_root(args.root)
    if root is None:
        return _fail(f"root {str(args.root)!r} is absent, not a directory, "
                     "a symlink or contains a traversal segment")
    try:
        model = load_model(args.model)
    except (OSError, json.JSONDecodeError) as error:
        return _fail(f"model could not be loaded: {type(error).__name__}")

    structural = validate_model(model)

    if args.command == "validate":
        inventory = discover(model, root)
        result = reconcile(model, inventory)
        blocking = result["blocking_finding_ids"]
        payload = {
            "model_valid": not structural,
            "model_errors": [error.as_dict() for error in structural],
            "repository_reconciliation_findings": len(result["findings"]),
            "blocking_finding_ids": blocking,
            "counts_by_finding": result["counts_by_finding"],
            "counts_by_severity": result["counts_by_severity"],
            # `model valid` y `repository has findings` son hechos distintos.
            "ok": not structural and not blocking,
        }
        _emit(payload)
        return 0 if payload["ok"] else 1

    if structural:
        _emit({"model_valid": False,
               "model_errors": [error.as_dict() for error in structural], "ok": False})
        return 1

    inventory = discover(model, root)

    if args.command == "discover":
        _emit({**inventory, "model_valid": True, "ok": True})
        return 0

    result = reconcile(model, inventory)

    if args.command == "report":
        by_owner: dict[str, int] = {}
        by_gate: dict[str, int] = {}
        for finding in result["findings"]:
            by_owner[finding["owner_role"]] = by_owner.get(finding["owner_role"], 0) + 1
            by_gate[finding["gate"]] = by_gate.get(finding["gate"], 0) + 1
        _emit({
            "model_valid": True,
            "scanned_file_count": result["scanned_file_count"],
            "identifier_count": len(result["identifiers"]),
            "counts_by_state": result["counts_by_state"],
            "counts_by_finding": result["counts_by_finding"],
            "counts_by_severity": result["counts_by_severity"],
            "counts_by_owner": dict(sorted(by_owner.items())),
            "counts_by_gate": dict(sorted(by_gate.items())),
            "blocking_finding_ids": result["blocking_finding_ids"],
            "narrative_ranges_not_expanded": result["narrative_ranges_not_expanded"],
            "findings": result["findings"],
            "aggregate_score_as_gate": False,
            "ok": True,
        })
        return 0

    _emit({**project(model, result), "model_valid": True, "ok": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
