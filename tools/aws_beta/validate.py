from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import ROOT, validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Fincilia closed beta")
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    report = validate(args.plan)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
