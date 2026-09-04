from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import report


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "docs/legal/subprocessor-register.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fincilia-subprocessor-register")
    parser.add_argument("command", choices=("validate", "report"))
    parser.add_argument("--model", type=Path, default=MODEL)
    args = parser.parse_args(argv)
    try:
        model = json.loads(args.model.read_text(encoding="utf-8"))
        public = (ROOT / model["public_disclosure_path"]).read_text(encoding="utf-8")
        payload = report(model, public)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "operational_error": type(error).__name__}, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
