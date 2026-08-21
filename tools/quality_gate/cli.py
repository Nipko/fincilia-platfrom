from __future__ import annotations

import argparse
import json
from pathlib import Path

from .repo_policy import scan_repository


def main() -> int:
    parser = argparse.ArgumentParser(description="Fincilia repository policy gate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan_repository(args.root.resolve())
    print(
        json.dumps(
            {
                "findings": [finding.as_dict() for finding in findings],
                "ok": not findings,
                "tracked_scope": "git-index",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
