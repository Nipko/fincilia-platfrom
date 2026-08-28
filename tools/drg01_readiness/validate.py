from __future__ import annotations

import json

from .model import load_model, report


def main() -> int:
    payload = report(load_model())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
