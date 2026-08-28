from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida contrato y plan AWS T0")
    parser.add_argument("--plan", type=Path, help="Plan JSON producido por tofu show -json")
    args = parser.parse_args()
    result = validate(args.plan)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
