from __future__ import annotations

import argparse
import json

from .model import load, validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the private-pilot AWS cost envelope")
    parser.add_argument("command", choices=("validate", "report"), nargs="?", default="validate")
    args = parser.parse_args()
    model = load()
    findings = validate(model)
    if args.command == "validate":
        print(json.dumps({"ok": not findings, "errors": [item.as_dict() for item in findings]}, sort_keys=True))
    else:
        print(json.dumps({
            "ok": not findings,
            "mode": model["plan_reference"]["mode"],
            "planned_creates": model["plan_reference"]["actions"]["create"],
            "known_floor_monthly_usd": model["known_priced_floor"]["subtotal_monthly_usd"],
            "complete_monthly_estimate_usd": model["decision_state"]["complete_monthly_estimate_usd"],
            "unpriced_cold_component_count": len(model["unpriced_cold_components"]),
            "warm_cost_driver_count": len(model["warm_only_cost_drivers"]),
            "apply_authorized": False,
            "real_data_authorized": False,
            "errors": [item.as_dict() for item in findings],
        }, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
