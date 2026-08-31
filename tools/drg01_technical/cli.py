from __future__ import annotations

import json

from .model import build_evidence, load_evidence, validate_evidence


def main() -> int:
    expected = build_evidence()
    errors = validate_evidence(load_evidence())
    print(json.dumps({
        "ok": not errors,
        "errors": errors,
        "evidence_sha256": expected["evidence_sha256"],
        "technical_controls": sorted(expected["technical_controls"]),
        "tests_run": expected["executed_suite"]["tests_run"],
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
