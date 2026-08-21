from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.completeness_model.validate import validate_model

ROOT = Path(__file__).parents[2]


class CompletenessModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads((ROOT / "docs/domain/completeness-balances.json").read_text(encoding="utf-8"))
        self.canonical = json.loads((ROOT / "docs/domain/canonical-model.json").read_text(encoding="utf-8"))
        self.architecture = json.loads((ROOT / "docs/architecture/module-boundaries.json").read_text(encoding="utf-8"))
        self.threats = json.loads((ROOT / "docs/security/threat-model.json").read_text(encoding="utf-8"))

    def _codes(self, model: dict, canonical: dict | None = None, architecture: dict | None = None) -> set[str]:
        return {error.code for error in validate_model(model, canonical or self.canonical, architecture or self.architecture, self.threats)}

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.canonical, self.architecture, self.threats))

    def test_float_money_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["money_type"] = "float"
        self.assertIn("CMP-MONEY", self._codes(mutated))

    def test_missing_control_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["control_types"].pop()
        self.assertIn("CMP-CONTROL-TYPES", self._codes(mutated))

    def test_unavailable_control_cannot_be_treated_as_match(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["control_types"][0]["unavailable_outcome"] = "match"
        self.assertIn("CMP-CONTROL-UNKNOWN", self._codes(mutated))

    def test_unknown_cannot_be_removed_from_precedence(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["assessment_contract"]["derivation_precedence"].pop(1)
        self.assertIn("CMP-DERIVATION", self._codes(mutated))

    def test_exception_cannot_be_derived_automatically(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["assessment_contract"]["accepted_exception_is_derived"] = True
        self.assertIn("CMP-EXCEPTION-DERIVATION", self._codes(mutated))

    def test_not_applicable_requires_predeclared_expectation(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["assessment_contract"]["not_applicable_rule"] = "operator_can_skip"
        self.assertIn("CMP-NOT-APPLICABLE", self._codes(mutated))

    def test_unknown_cannot_feed_close(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["eligibility"]["unknown"]["close_input"] = True
        self.assertIn("CMP-FAIL-CLOSED-ELIGIBILITY", self._codes(mutated))

    def test_mismatch_cannot_feed_certified_report(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["eligibility"]["mismatch"]["certified_report_input"] = True
        self.assertIn("CMP-FAIL-CLOSED-ELIGIBILITY", self._codes(mutated))

    def test_auto_match_cannot_be_enabled_in_e0(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["eligibility"]["verified"]["auto_match"] = True
        self.assertIn("CMP-AUTO-MATCH", self._codes(mutated))

    def test_balance_is_not_completeness_proof(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["account_balance_contract"]["source_observation_not_completeness_proof"] = False
        self.assertIn("CMP-BALANCE-NOT-PROOF", self._codes(mutated))

    def test_statement_formula_cannot_change_sign(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reconciliation_statement_contract"]["formula"]["unexplained_difference"] = "books_closing_balance - adjusted_bank_balance"
        self.assertIn("CMP-STATEMENT-FORMULA", self._codes(mutated))

    def test_balanced_requires_exact_zero(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reconciliation_statement_contract"]["balanced_requires_exact_zero"] = False
        self.assertIn("CMP-STATEMENT-GUARD", self._codes(mutated))

    def test_accepted_difference_cannot_be_named_balanced(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reconciliation_statement_contract"]["accepted_difference_never_named_balanced"] = False
        self.assertIn("CMP-STATEMENT-GUARD", self._codes(mutated))

    def test_proposed_item_cannot_count(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reconciling_item_contract"]["only_state_counted"] = "proposed"
        self.assertIn("CMP-ITEM-MONEY", self._codes(mutated))

    def test_item_requires_sod_and_lineage(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reconciling_item_contract"]["confirmed_requires"].remove("sod_check")
        self.assertIn("CMP-ITEM-DECISION", self._codes(mutated))

    def test_exception_requires_expiry(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["accepted_exception_contract"]["expiry_required"] = False
        self.assertIn("CMP-EXCEPTION-GUARD", self._codes(mutated))

    def test_expired_exception_cannot_allow_close(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["accepted_exception_contract"]["expired_exception_allows_new_close"] = True
        self.assertIn("CMP-EXCEPTION-FAIL-CLOSED", self._codes(mutated))

    def test_matching_coverage_cannot_replace_completeness(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["close_readiness_gate"]["matching_coverage_is_not_completeness"] = False
        self.assertIn("CMP-CLOSE-GUARD", self._codes(mutated))

    def test_product_close_cannot_be_enabled_in_e0(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["close_readiness_gate"]["product_close_enabled_in_e0"] = True
        self.assertIn("CMP-E0-DISABLED", self._codes(mutated))

    def test_missing_close_condition_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["close_readiness_gate"]["required_conditions"].pop()
        self.assertIn("CMP-CLOSE-CONDITIONS", self._codes(mutated))

    def test_architecture_owner_mismatch_is_rejected(self) -> None:
        architecture = copy.deepcopy(self.architecture)
        reconciliation = next(module for module in architecture["modules"] if module["id"] == "reconciliation")
        reconciliation["owns"].remove("completeness_assessment")
        self.assertIn("CMP-ARCHITECTURE-OWNER", self._codes(self.model, architecture=architecture))

    def test_owner_and_reviewer_must_be_independent(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reviewer_roles"].append("Accounting")
        self.assertIn("CMP-INDEPENDENT-REVIEW", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
