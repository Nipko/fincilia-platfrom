from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs" / "product" / "web-functional-status.json"
DIMENSIONS = ("implementation", "synthetic_acceptance", "production_operability")


def load_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("functional status root must be an object")
    return value


def calculate(model: dict[str, Any]) -> dict[str, int]:
    scoring = model.get("scoring", {})
    capabilities = model.get("capabilities", [])
    result: dict[str, int] = {}
    for dimension in DIMENSIONS:
        factors = scoring.get(dimension, {})
        points = sum(
            item.get("weight", 0) * factors.get(item.get(dimension), -1000)
            for item in capabilities
        )
        result[f"{dimension}_percent"] = round(points)
    return result


def _evidence_path(raw: object) -> Path | None:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return None
    return resolved


def validate(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if model.get("task_id") != "FNC-GAT-008" or model.get("scope") != "web_platform":
        errors.append("STATUS-SCOPE")
    if model.get("data_ceiling") != "synthetic_only":
        errors.append("STATUS-DATA-CEILING")
    if model.get("excluded_from_denominator") != ["mobile_application"]:
        errors.append("STATUS-MOBILE-SCOPE")
    gates = model.get("gate_claims", {})
    if gates != {"DRG-00": "not_met", "DRG-01": "not_met", "GA-01": "not_met"}:
        errors.append("STATUS-GATES")

    scoring = model.get("scoring", {})
    expected_states = {
        "implementation": {"complete", "partial", "absent"},
        "synthetic_acceptance": {"synthetic_e2e", "component_verified", "blocked"},
        "production_operability": {"production_verified", "design_and_tests", "blocked"},
    }
    for dimension, states in expected_states.items():
        factors = scoring.get(dimension, {})
        if set(factors) != states or any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                or value < 0 or value > 1 for value in factors.values()):
            errors.append(f"STATUS-SCORING:{dimension}")

    capabilities = model.get("capabilities", [])
    identifiers: set[str] = set()
    total_weight = 0
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("STATUS-CAPABILITIES")
        capabilities = []
    for item in capabilities:
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            errors.append("STATUS-CAPABILITY-ID")
        else:
            identifiers.add(identifier)
        weight = item.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            errors.append(f"STATUS-WEIGHT:{identifier}")
        else:
            total_weight += weight
        for dimension, states in expected_states.items():
            if item.get(dimension) not in states:
                errors.append(f"STATUS-STATE:{identifier}:{dimension}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"STATUS-EVIDENCE:{identifier}")
        else:
            for raw in evidence:
                path = _evidence_path(raw)
                if path is None or not path.exists():
                    errors.append(f"STATUS-EVIDENCE:{identifier}")
        if not isinstance(item.get("remaining"), str) or not item["remaining"].strip():
            errors.append(f"STATUS-REMAINING:{identifier}")
        if item.get("production_operability") == "production_verified":
            errors.append(f"STATUS-PREMATURE-PRODUCTION:{identifier}")
    if total_weight != 100:
        errors.append("STATUS-WEIGHT-TOTAL")
    try:
        calculated = calculate(model)
    except TypeError:
        errors.append("STATUS-CALCULATION")
    else:
        if model.get("reported_progress") != calculated:
            errors.append("STATUS-STALE-PROGRESS")
    return sorted(set(errors))


def report(model: dict[str, Any]) -> dict[str, Any]:
    errors = validate(model)
    return {
        "ok": not errors,
        "errors": errors,
        "progress": calculate(model) if not errors else None,
        "capability_count": len(model.get("capabilities", [])),
        "data_ceiling": model.get("data_ceiling"),
        "excluded": model.get("excluded_from_denominator", []),
    }
