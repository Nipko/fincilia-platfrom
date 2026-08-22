"""CLI del baseline de cadena de suministro (FNC-SUP-001).

    python -m tools.supply_chain.cli discover
    python -m tools.supply_chain.cli validate
    python -m tools.supply_chain.cli report

JSON ordenado por stdout, errores operativos por stderr. `--root` y `--model` son
inyectables y quedan confinados al árbol. Nunca ejecuta lo que descubre.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.supply_chain.discovery import discover
from tools.supply_chain.rules import reconcile, validate_model

DEFAULT_MODEL = Path("docs/security/supply-chain.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def resolve_root(raw: str | None) -> Path:
    """Acepta un root solo si existe, es directorio, no es symlink y no traversa."""
    if raw is None:
        return REPOSITORY_ROOT
    candidate = Path(raw)
    if ".." in candidate.parts:
        raise ValueError("root must not traverse with '..'")
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise ValueError(f"root is not an existing directory: {raw}")
    if candidate.is_symlink():
        raise ValueError("root must not be a symlink")
    return resolved


def load_model(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia supply-chain baseline")
    parser.add_argument("--model", default=None, help="path to supply-chain.json")
    parser.add_argument("--root", default=None, help="tree to scan")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("discover", help="stable inventory of supply-chain components")
    subparsers.add_parser("validate", help="model validity plus repository reconciliation")
    subparsers.add_parser("report", help="blockers and gaps by risk, owner and gate")

    args = parser.parse_args(argv)
    _use_utf8_streams()

    try:
        root = resolve_root(args.root)
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 2

    model_path = Path(args.model) if args.model else (REPOSITORY_ROOT / DEFAULT_MODEL)
    try:
        model = load_model(model_path)
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": f"model unreadable: {error}"}), file=sys.stderr)
        return 2

    model_errors = validate_model(model)
    if model_errors and args.command != "validate":
        _emit({"ok": False, "model_valid": False,
               "model_errors": [item.as_dict() for item in model_errors],
               "reason": "the contract is invalid; nothing was scanned"})
        return 1

    if args.command == "validate":
        inventory = discover(model, root) if not model_errors else {}
        result = reconcile(model, root, inventory) if not model_errors else {}
        payload = {
            "model_valid": not model_errors,
            "model_errors": [item.as_dict() for item in model_errors],
            "repository_findings": result.get("finding_count", 0),
            "blocking_findings": result.get("blocking_count", 0),
            "counts_by_code": result.get("counts_by_code", {}),
            "findings": result.get("findings", []),
            "ok": not model_errors and not result.get("blocking_count", 0),
        }
        _emit(payload)
        return 0 if payload["ok"] else 1

    inventory = discover(model, root)

    if args.command == "discover":
        payload = dict(inventory)
        payload["ok"] = not inventory.get("unsafe_paths") and \
            not inventory.get("unscannable_files")
        _emit(payload)
        return 0 if payload["ok"] else 1

    result = reconcile(model, root, inventory)
    payload = {
        "scanned_file_count": inventory["scanned_file_count"],
        "component_count": inventory["component_count"],
        "counts_by_type": inventory["counts_by_type"],
        "counts_by_code": result["counts_by_code"],
        "counts_by_severity": result["counts_by_severity"],
        "counts_by_owner": result["counts_by_owner"],
        "counts_by_gate": result["counts_by_gate"],
        "counts_by_classification": result["counts_by_classification"],
        "blocking_findings": result["blocking_findings"],
        "declared_gaps": model.get("declared_gaps", []),
        "tm_005": model.get("tm_005", {}),
        "aggregate_score": None,
        "note": "No hay nota agregada: un porcentaje ocultaria justo el blocker. "
                "Un digest identifica el artefacto observado; no acredita a su autor.",
        "ok": result["blocking_count"] == 0,
    }
    _emit(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
