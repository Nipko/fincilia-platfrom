from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_CONTROL_TYPES = {
    "record_count", "debit_total", "credit_total", "opening_balance", "closing_balance",
    "running_balance_continuity", "period_coverage", "page_section_coverage",
    "sequence_cursor", "provenance_integrity", "currency_consistency", "account_identity",
}
REQUIRED_TESTS = {"TST-CMP-001", "TST-CMP-002", "TST-BAL-001", "TST-BAL-002", "TST-EXC-001", "TST-CLOSE-001"}
REQUIRED_CLOSE_CONDITIONS = {
    "every_expected_source_has_assessment", "no_unhandled_mismatch_or_unknown",
    "statement_for_every_required_account_and_currency",
    "every_statement_balanced_or_explicit_exception_accepted",
    "no_hidden_unexplained_difference", "confirmed_items_have_evidence_and_sod",
    "all_published_fields_and_decisions_have_lineage",
    "engine_schema_reference_and_rule_versions_fixed",
    "authorization_revalidated_before_snapshot",
}
REQUIRED_EXCEPTION_FIELDS = {
    "scope", "reason", "owner_subject_id", "approved_by", "approved_at",
    "materiality_policy_id", "valid_from", "expires_at", "allowed_actions",
    "evidence_refs", "audit_event_id",
}
REQUIRED_BALANCE_FIELDS = {
    "company_id", "financial_account_id", "source_record_id", "balance_type", "amount",
    "currency_code", "as_of", "engine_release_id", "canonical_schema_version", "lineage_state",
}
REQUIRED_ASSESSMENT_SCOPE = {
    "company_id", "data_source_id", "source_expectation_id", "period_start", "period_end",
    "dataset_version_id", "engine_release_id",
}


@dataclass(frozen=True, order=True)
class CompletenessModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _architecture_owner(architecture: dict[str, Any], entity_id: str) -> str | None:
    for module in architecture.get("modules", []):
        if entity_id in module.get("owns", []):
            return module.get("id")
    return None


def _canonical_fields(canonical: dict[str, Any], entity_id: str) -> set[str]:
    for entity in canonical.get("entities", []):
        if entity.get("id") == entity_id:
            return {field.get("name") for field in entity.get("fields", []) if isinstance(field, dict)}
    return set()


def validate_model(
    model: dict[str, Any],
    canonical: dict[str, Any],
    architecture: dict[str, Any],
    threat_model: dict[str, Any],
) -> list[CompletenessModelError]:
    errors: list[CompletenessModelError] = []
    if model.get("schema_version") != 1:
        errors.append(CompletenessModelError("CMP-SCHEMA-VERSION", "$", "schema_version must equal 1"))
    if model.get("task_id") != "FNC-DOM-003":
        errors.append(CompletenessModelError("CMP-TASK", "task_id", "task_id must be FNC-DOM-003"))
    if model.get("status") != "review_pending" or model.get("human_acceptance") != "pending":
        errors.append(CompletenessModelError("CMP-ACCEPTANCE", "$", "model and human acceptance must remain pending"))
    if model.get("data_ceiling") != "synthetic_only":
        errors.append(CompletenessModelError("CMP-DATA-CEILING", "data_ceiling", "E0 permits synthetic_only"))
    if model.get("money_type") != "money_decimal" or model.get("float_forbidden") is not True:
        errors.append(CompletenessModelError("CMP-MONEY", "money_type", "exact decimal is required and float forbidden"))

    exact_sets = (
        ("assessment_states", {"verified", "mismatch", "unknown", "accepted_exception"}, "CMP-ASSESSMENT-STATES"),
        ("control_outcomes", {"match", "mismatch", "unknown", "not_applicable"}, "CMP-CONTROL-OUTCOMES"),
        ("statement_states", {"draft", "review_required", "balanced", "exception_accepted", "superseded"}, "CMP-STATEMENT-STATES"),
        ("reconciling_item_states", {"proposed", "confirmed", "rejected", "reversed"}, "CMP-ITEM-STATES"),
    )
    for field, expected, code in exact_sets:
        if set(model.get(field, [])) != expected or len(model.get(field, [])) != len(expected):
            errors.append(CompletenessModelError(code, field, "state set must be declared exactly once"))

    control_types = model.get("control_types")
    control_ids = _ids(control_types)
    if set(control_ids) != REQUIRED_CONTROL_TYPES or len(control_ids) != len(REQUIRED_CONTROL_TYPES):
        errors.append(CompletenessModelError("CMP-CONTROL-TYPES", "control_types", "required controls must be exact"))
    for control in control_types or []:
        if control.get("unavailable_outcome") != "unknown":
            errors.append(CompletenessModelError("CMP-CONTROL-UNKNOWN", f"control_types.{control.get('id')}", "unavailable required evidence must become unknown"))
        if control.get("id") in {"debit_total", "credit_total", "opening_balance", "closing_balance"} and control.get("value_type") != "money_decimal":
            errors.append(CompletenessModelError("CMP-CONTROL-MONEY", f"control_types.{control.get('id')}", "monetary control must use money_decimal"))

    assessment = model.get("assessment_contract", {})
    if assessment.get("entity") != "completeness_assessment" or assessment.get("owner_module") != "reconciliation":
        errors.append(CompletenessModelError("CMP-ASSESSMENT-OWNER", "assessment_contract", "assessment belongs to reconciliation"))
    if assessment.get("company_scoped") is not True or assessment.get("lineage_required") is not True:
        errors.append(CompletenessModelError("CMP-ASSESSMENT-SCOPE", "assessment_contract", "assessment must be company-scoped with lineage"))
    if set(assessment.get("scope_fields", [])) != REQUIRED_ASSESSMENT_SCOPE:
        errors.append(CompletenessModelError("CMP-ASSESSMENT-FIELDS", "assessment_contract.scope_fields", "assessment scope is incomplete"))
    derivation = assessment.get("derivation_precedence", [])
    expected_derivation = [
        ("any_required_control_mismatch", "mismatch"),
        ("no_mismatch_and_any_required_control_unknown", "unknown"),
        ("all_required_controls_match", "verified"),
    ]
    if [(item.get("when"), item.get("state")) for item in derivation] != expected_derivation:
        errors.append(CompletenessModelError("CMP-DERIVATION", "assessment_contract.derivation_precedence", "fail-closed precedence is invalid"))
    if assessment.get("accepted_exception_is_derived") is not False or assessment.get("base_state_preserved") is not True:
        errors.append(CompletenessModelError("CMP-EXCEPTION-DERIVATION", "assessment_contract", "accepted exception must be explicit and preserve base state"))
    if assessment.get("not_applicable_rule") != "must_be_predeclared_by_versioned_expectation_with_reason":
        errors.append(CompletenessModelError("CMP-NOT-APPLICABLE", "assessment_contract", "not_applicable must be predeclared with reason"))

    control_result = model.get("control_result_contract", {})
    if control_result.get("silent_skip_forbidden") is not True or control_result.get("monetary_tolerance_uses_decimal") is not True:
        errors.append(CompletenessModelError("CMP-CONTROL-RESULT", "control_result_contract", "silent skip is forbidden and tolerance uses decimal"))
    if control_result.get("lineage_required") is not True:
        errors.append(CompletenessModelError("CMP-CONTROL-LINEAGE", "control_result_contract", "control result requires lineage"))

    eligibility = model.get("eligibility", {})
    for state in {"verified", "mismatch", "unknown", "accepted_exception"}:
        if state not in eligibility:
            errors.append(CompletenessModelError("CMP-ELIGIBILITY", f"eligibility.{state}", "state eligibility is missing"))
            continue
        if eligibility[state].get("auto_match") is not False:
            errors.append(CompletenessModelError("CMP-AUTO-MATCH", f"eligibility.{state}", "auto-match must remain disabled in E0"))
    for state in {"mismatch", "unknown"}:
        values = eligibility.get(state, {})
        if values.get("match_suggestion") is not False or values.get("close_input") is not False or values.get("certified_report_input") is not False:
            errors.append(CompletenessModelError("CMP-FAIL-CLOSED-ELIGIBILITY", f"eligibility.{state}", "incomplete state must block downstream certification"))
    accepted = eligibility.get("accepted_exception", {})
    if accepted.get("close_input") != "conditional_valid_exception" or accepted.get("certified_report_input") != "conditional_disclosed_exception":
        errors.append(CompletenessModelError("CMP-EXCEPTION-DISCLOSURE", "eligibility.accepted_exception", "exception use must be conditional and disclosed"))

    balance = model.get("account_balance_contract", {})
    if balance.get("amount_type") != "money_decimal" or balance.get("currency_required") is not True:
        errors.append(CompletenessModelError("CMP-BALANCE-MONEY", "account_balance_contract", "balance requires exact money and currency"))
    if balance.get("source_observation_not_completeness_proof") is not True:
        errors.append(CompletenessModelError("CMP-BALANCE-NOT-PROOF", "account_balance_contract", "balance cannot prove completeness"))
    canonical_balance_fields = _canonical_fields(canonical, "account_balance")
    if not set(balance.get("required_fields", [])).issubset(canonical_balance_fields) or set(balance.get("required_fields", [])) != REQUIRED_BALANCE_FIELDS:
        errors.append(CompletenessModelError("CMP-BALANCE-FIELDS", "account_balance_contract.required_fields", "balance fields must match canonical model"))

    statement = model.get("reconciliation_statement_contract", {})
    expected_formula = {
        "adjusted_bank_balance": "bank_closing_balance + confirmed_additions_to_bank - confirmed_deductions_from_bank",
        "unexplained_difference": "adjusted_bank_balance - books_closing_balance",
    }
    if statement.get("formula") != expected_formula:
        errors.append(CompletenessModelError("CMP-STATEMENT-FORMULA", "reconciliation_statement_contract.formula", "statement formula is invalid"))
    for field in ("company_scoped", "single_currency", "same_company_account_period_required", "only_confirmed_items_count", "balanced_requires_exact_zero", "accepted_difference_never_named_balanced", "lineage_required"):
        if statement.get(field) is not True:
            errors.append(CompletenessModelError("CMP-STATEMENT-GUARD", f"reconciliation_statement_contract.{field}", "statement guard must be true"))
    if statement.get("amount_type") != "money_decimal" or statement.get("accepted_difference_state") != "exception_accepted":
        errors.append(CompletenessModelError("CMP-STATEMENT-MONEY", "reconciliation_statement_contract", "statement money/state contract is invalid"))

    item = model.get("reconciling_item_contract", {})
    if set(item.get("adjustment_sides", [])) != {"add_to_bank", "deduct_from_bank"}:
        errors.append(CompletenessModelError("CMP-ITEM-SIDE", "reconciling_item_contract", "adjustment side must be explicit"))
    if item.get("amount_type") != "money_decimal" or item.get("amount_rule") != "positive" or item.get("only_state_counted") != "confirmed":
        errors.append(CompletenessModelError("CMP-ITEM-MONEY", "reconciling_item_contract", "item must be positive decimal and only confirmed counts"))
    if set(item.get("confirmed_requires", [])) != {"approved_by", "approved_at", "sod_check", "lineage"} or item.get("reversal_creates_new_decision") is not True:
        errors.append(CompletenessModelError("CMP-ITEM-DECISION", "reconciling_item_contract", "confirmation and reversal contract is invalid"))

    exception = model.get("accepted_exception_contract", {})
    if set(exception.get("required_fields", [])) != REQUIRED_EXCEPTION_FIELDS:
        errors.append(CompletenessModelError("CMP-EXCEPTION-FIELDS", "accepted_exception_contract", "exception fields are incomplete"))
    for field in ("independent_approver_required", "expiry_required", "base_state_preserved", "must_be_disclosed_in_snapshot_and_report"):
        if exception.get(field) is not True:
            errors.append(CompletenessModelError("CMP-EXCEPTION-GUARD", f"accepted_exception_contract.{field}", "exception guard must be true"))
    if exception.get("auto_match_allowed") is not False or exception.get("expired_exception_allows_new_close") is not False:
        errors.append(CompletenessModelError("CMP-EXCEPTION-FAIL-CLOSED", "accepted_exception_contract", "exception cannot auto-match or survive expiry"))

    close_gate = model.get("close_readiness_gate", {})
    if set(close_gate.get("required_conditions", [])) != REQUIRED_CLOSE_CONDITIONS:
        errors.append(CompletenessModelError("CMP-CLOSE-CONDITIONS", "close_readiness_gate", "close conditions are incomplete"))
    for field in ("matching_coverage_is_not_completeness", "movement_matches_are_not_balance_reconciliation", "balanced_label_requires_zero"):
        if close_gate.get(field) is not True:
            errors.append(CompletenessModelError("CMP-CLOSE-GUARD", f"close_readiness_gate.{field}", "close guard must be true"))
    if close_gate.get("auto_match_enabled_in_e0") is not False or close_gate.get("product_close_enabled_in_e0") is not False:
        errors.append(CompletenessModelError("CMP-E0-DISABLED", "close_readiness_gate", "auto-match and product close remain disabled in E0"))

    if set(model.get("required_test_scenarios", [])) != REQUIRED_TESTS:
        errors.append(CompletenessModelError("CMP-TEST-SCENARIOS", "required_test_scenarios", "required scenarios must be exact"))
    known_risks = {risk.get("id") for risk in threat_model.get("risks", []) if isinstance(risk, dict)}
    risk_refs = set(model.get("risk_refs", []))
    if not {"TM-007", "TM-013"}.issubset(risk_refs) or not risk_refs.issubset(known_risks):
        errors.append(CompletenessModelError("CMP-RISK-REFS", "risk_refs", "required privacy/accounting risks must be valid"))
    owners = set(model.get("owner_roles", []))
    reviewers = set(model.get("reviewer_roles", []))
    if not owners or not reviewers or owners & reviewers:
        errors.append(CompletenessModelError("CMP-INDEPENDENT-REVIEW", "$", "owner and reviewer roles must be non-empty and independent"))

    expected_owners = {
        "completeness_assessment": "reconciliation",
        "completeness_control_result": "reconciliation",
        "reconciliation_statement": "reconciliation",
        "reconciling_item": "reconciliation",
        "account_balance": "finance",
    }
    for entity_id, owner in expected_owners.items():
        if _architecture_owner(architecture, entity_id) != owner:
            errors.append(CompletenessModelError("CMP-ARCHITECTURE-OWNER", f"architecture.{entity_id}", f"owner must be {owner}"))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Fincilia completeness and balance model")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/domain/completeness-balances.json"))
    parser.add_argument("--canonical", type=Path, default=Path("docs/domain/canonical-model.json"))
    parser.add_argument("--architecture", type=Path, default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--threat-model", type=Path, default=Path("docs/security/threat-model.json"))
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    canonical = json.loads(args.canonical.read_text(encoding="utf-8"))
    architecture = json.loads(args.architecture.read_text(encoding="utf-8"))
    threat_model = json.loads(args.threat_model.read_text(encoding="utf-8"))
    errors = validate_model(model, canonical, architecture, threat_model)
    print(json.dumps({"errors": [error.as_dict() for error in errors], "ok": not errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
