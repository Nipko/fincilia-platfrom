from __future__ import annotations

import json

from .model import load_model, report


def main() -> int:
    result = report(load_model())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
