from __future__ import annotations

import json

from .drill import load_evidence, run_drill, validate_evidence


def main() -> int:
    expected = run_drill()
    errors = validate_evidence(load_evidence())
    print(json.dumps({
        "ok": not errors,
        "errors": errors,
        "tests": expected["test_count"],
        "evidence_sha256": expected["evidence_sha256"],
        "real_data_authorized": False,
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
