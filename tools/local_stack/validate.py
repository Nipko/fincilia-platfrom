from __future__ import annotations

import json
from pathlib import Path

from .model import validate_repository


def main() -> int:
    findings = validate_repository(Path(__file__).resolve().parents[2])
    print(json.dumps({"ok": not findings, "errors": [item.as_dict() for item in findings]}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

