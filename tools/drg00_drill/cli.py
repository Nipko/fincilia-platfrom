from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import ROOT, run_drill


DEFAULT_OUTPUT = ROOT / "docs/implementation/evidence/FNC-QA-001.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="fincilia-drg00-drill")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = run_drill()
    except Exception as error:  # noqa: BLE001 - evidencia fail-closed
        print(json.dumps({"ok": False, "error": type(error).__name__}, sort_keys=True))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True, "test_count": report["test_count"],
        "passed_count": report["passed_count"],
        "evidence_sha256": report["evidence_sha256"],
        "output": args.output.relative_to(ROOT).as_posix(),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
