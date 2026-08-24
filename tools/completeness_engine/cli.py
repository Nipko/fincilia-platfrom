"""CLI de la especificacion ejecutable de completitud (FNC-DOM-006).

    python -m tools.completeness_engine.cli statement <fixture.json>
    python -m tools.completeness_engine.cli close <fixture.json>
    python -m tools.completeness_engine.cli fixtures

JSON ordenado por stdout, errores operativos por stderr. No toca la base de datos,
no consulta el reloj y no acepta nada: solo aplica el contrato a datos sinteticos.

Codigos de salida:
  0  el fixture cumple lo que declara esperar
  1  el fixture no cumple, o el cierre no esta listo
  2  uso invalido o fichero ilegible
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from tools.completeness_engine.engine import (
    compute_statement,
    evaluate_close_readiness,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path("tests/golden/completeness")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def resolve_inside(root: Path, relative: str) -> Path | None:
    """Rechaza absolutas, unidades de Windows, `..` y symlinks."""
    if not relative or relative.startswith(("/", "\\")):
        return None
    if len(relative) > 1 and relative[1] == ":":
        return None
    if ".." in Path(relative).parts:
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


def load_fixture(root: Path, relative: str) -> dict[str, Any]:
    resolved = resolve_inside(root, relative)
    if resolved is None or not resolved.is_file():
        raise ValueError(f"fixture is missing, absolute, traversing or a symlink: "
                         f"{relative}")
    return json.loads(resolved.read_text(encoding="utf-8"))


def command_statement(document: dict[str, Any]) -> tuple[dict[str, Any], int]:
    outcome = compute_statement(document["statement"], document.get("items", []) or [])
    payload = outcome.as_dict()
    expected = document.get("expected")
    if expected:
        mismatches = {
            key: {"expected": value, "observed": payload.get(key)}
            for key, value in expected.items() if payload.get(key) != value
        }
        payload["expected"] = expected
        payload["mismatches"] = mismatches
        payload["ok"] = not mismatches
    else:
        payload["ok"] = not outcome.findings
    payload["note"] = ("Solo cuentan los items confirmed, y `balanced` exige cero "
                       "exacto.")
    return payload, EXIT_OK if payload["ok"] else EXIT_FAILED


def command_close(document: dict[str, Any]) -> tuple[dict[str, Any], int]:
    as_of = date.fromisoformat(str(document["as_of"]))
    outcome = evaluate_close_readiness(document, as_of)
    payload = outcome.as_dict()
    payload["company_id"] = document.get("company_id")
    payload["period"] = [document.get("period_start"), document.get("period_end")]
    payload["as_of"] = document.get("as_of")
    payload["ok"] = outcome.ready
    payload["note"] = ("Cobertura de matching no es completitud, y un cierre listo no "
                       "es un cierre autorizado: en E0 el cierre de producto sigue "
                       "deshabilitado.")
    return payload, EXIT_OK if outcome.ready else EXIT_FAILED


def command_fixtures(root: Path) -> tuple[dict[str, Any], int]:
    directory = resolve_inside(root, FIXTURE_ROOT.as_posix())
    files = sorted(item.relative_to(root).as_posix()
                   for item in (directory.glob("*.json") if directory else [])
                   if item.is_file() and not item.is_symlink())
    return {"fixtures": files, "count": len(files),
            "data_classification": "synthetic_only", "ok": bool(files)}, \
        EXIT_OK if files else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fincilia completeness and balance executable specification")
    parser.add_argument("--root", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    statement_parser = subparsers.add_parser("statement", help="compute one statement")
    statement_parser.add_argument("fixture")
    close_parser = subparsers.add_parser("close", help="evaluate close readiness")
    close_parser.add_argument("fixture")
    subparsers.add_parser("fixtures", help="list synthetic fixtures")

    args = parser.parse_args(argv)
    _use_utf8_streams()

    root = REPOSITORY_ROOT if args.root is None else Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"ok": False, "error": f"root is not a directory: {args.root}"}),
              file=sys.stderr)
        return EXIT_USAGE

    if args.command == "fixtures":
        payload, code = command_fixtures(root)
        _emit(payload)
        return code

    try:
        document = load_fixture(root, args.fixture)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return EXIT_USAGE

    try:
        if args.command == "statement":
            payload, code = command_statement(document)
        else:
            payload, code = command_close(document)
    except (KeyError, ValueError) as error:
        print(json.dumps({"ok": False, "error": f"malformed fixture: {error}"}),
              file=sys.stderr)
        return EXIT_USAGE

    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
