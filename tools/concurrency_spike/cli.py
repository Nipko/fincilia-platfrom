"""CLI del spike FNC-DB-004."""

from __future__ import annotations

import argparse
import json

from .runner import RunnerError, run
from .validate import load_model, validate_model


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    execute = sub.add_parser("run")
    execute.add_argument("--repeat", type=int, default=2)
    sub.add_parser("report")
    args = parser.parse_args()
    if args.command == "validate":
        findings = validate_model(load_model())
        payload = {"ok": not findings, "errors": findings}
    elif args.command == "report":
        model = load_model()
        payload = {"task_id": model["task_id"], "status": model["status"],
                   "human_acceptance": model["human_acceptance"],
                   "tests": [case["id"] for case in model["cases"]],
                   "product_effect": "none"}
    else:
        try:
            payload = run(repeat=args.repeat)
        except RunnerError as error:
            payload = {"ok": False, "status": "invalid_request", "detail": str(error)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
