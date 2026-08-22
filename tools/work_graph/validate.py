from __future__ import annotations

import json
from pathlib import Path

from .model import validate_repository


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report, findings = validate_repository(root)
    print(json.dumps({"ok": not findings, "report": report, "errors": [item.as_dict() for item in findings]}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

