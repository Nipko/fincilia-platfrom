"""CLI offline y determinista de FNC-PRV-002."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import report

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "docs/privacy/retention-deletion-matrix.json"
PRIVACY = ROOT / "docs/privacy/privacy-map.json"


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fincilia-retention-matrix")
    parser.add_argument("command", choices=("validate", "report"))
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--privacy", type=Path, default=PRIVACY)
    args = parser.parse_args(argv)
    try:
        payload = report(_load(args.model), _load(args.privacy))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"ok": False, "operational_error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
