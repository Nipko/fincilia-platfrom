from __future__ import annotations

import argparse
import json

from .model import load, validate
from .uat_model import load as load_uat
from .uat_model import validate as validate_uat


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia AWS cost envelopes")
    parser.add_argument(
        "command",
        choices=("validate", "report", "uat-validate", "uat-report"),
        nargs="?",
        default="validate",
    )
    args = parser.parse_args()
    if args.command.startswith("uat-"):
        model = load_uat()
        findings = validate_uat(model)
        if args.command == "uat-validate":
            print(json.dumps({"ok": not findings, "errors": [item.as_dict() for item in findings]}, sort_keys=True))
        else:
            scenarios = model["monthly_scenarios"]
            print(json.dumps({
                "ok": not findings,
                "region": model["region"],
                "current_uat_fixed_monthly_usd": scenarios["current_uat"]["fixed_subtotal_usd"],
                "current_account_fixed_monthly_usd": scenarios["current_account_fixed_total_usd"],
                "private_pilot_cold_fixed_monthly_usd": scenarios["private_pilot_cold"]["fixed_subtotal_usd"],
                "private_pilot_warm_stopped_fixed_monthly_usd": scenarios["private_pilot_warm_services_stopped"]["fixed_subtotal_usd"],
                "private_pilot_warm_active_fixed_monthly_usd": scenarios["private_pilot_warm_services_active"]["fixed_subtotal_usd"],
                "excluded_variable_usage_count": len(model["excluded_variable_usage"]),
                "recommendation": model["decision"]["recommendation"],
                "apply_authorized": False,
                "real_data_authorized": False,
                "errors": [item.as_dict() for item in findings],
            }, sort_keys=True))
        return 0 if not findings else 1

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
