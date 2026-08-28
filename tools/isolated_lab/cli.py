"""CLI offline del diseño de laboratorio aislado."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import report

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "docs/security/isolated-real-data-lab.json"
DEFAULT_SOURCES = {
    "THREAT": ROOT / "docs/security/threat-model.json",
    "PRIVACY": ROOT / "docs/privacy/privacy-map.json",
    "REGION": ROOT / "docs/architecture/region-transmission-decision.json",
    "RETENTION": ROOT / "docs/privacy/retention-deletion-matrix.json",
}


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fincilia-isolated-lab")
    parser.add_argument("command", choices=("validate", "report"))
    parser.add_argument("--model", type=Path, default=MODEL)
    for identifier, path in DEFAULT_SOURCES.items():
        parser.add_argument(f"--{identifier.lower()}", type=Path, default=path)
    args = parser.parse_args(argv)
    try:
        sources = {
            identifier: _load(getattr(args, identifier.lower()))
            for identifier in DEFAULT_SOURCES
        }
        payload = report(_load(args.model), sources)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"ok": False, "operational_error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
