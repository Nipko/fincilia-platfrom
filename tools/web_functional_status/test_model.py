from __future__ import annotations

import copy
import unittest

from .model import calculate, load_model, validate


class WebFunctionalStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_model()

    def assert_bites(self, mutate, expected: str) -> None:
        candidate = copy.deepcopy(self.model)
        mutate(candidate)
        self.assertIn(expected, validate(candidate))

    def test_canonical_inventory_is_valid_and_reproducible(self) -> None:
        self.assertEqual([], validate(self.model))
        self.assertEqual({
            "implementation_percent": 88,
            "synthetic_acceptance_percent": 59,
            "production_operability_percent": 28,
        }, calculate(self.model))

    def test_weights_cannot_hide_scope(self) -> None:
        self.assert_bites(
            lambda value: value["capabilities"][0].update(weight=1),
            "STATUS-WEIGHT-TOTAL")

    def test_mobile_cannot_enter_web_denominator_silently(self) -> None:
        self.assert_bites(
            lambda value: value.update(excluded_from_denominator=[]),
            "STATUS-MOBILE-SCOPE")

    def test_data_ceiling_cannot_be_promoted(self) -> None:
        self.assert_bites(
            lambda value: value.update(data_ceiling="real_data"),
            "STATUS-DATA-CEILING")

    def test_gate_cannot_be_accepted_by_inventory(self) -> None:
        self.assert_bites(
            lambda value: value["gate_claims"].update({"DRG-00": "met"}),
            "STATUS-GATES")

    def test_production_verified_is_rejected_while_ga_is_closed(self) -> None:
        self.assert_bites(
            lambda value: value["capabilities"][0].update(
                production_operability="production_verified"),
            "STATUS-PREMATURE-PRODUCTION:identity_onboarding")

    def test_missing_evidence_fails_closed(self) -> None:
        self.assert_bites(
            lambda value: value["capabilities"][0].update(
                evidence=["docs/does-not-exist.md"]),
            "STATUS-EVIDENCE:identity_onboarding")

    def test_traversal_evidence_fails_closed(self) -> None:
        self.assert_bites(
            lambda value: value["capabilities"][0].update(
                evidence=["docs/../CURRENT_PHASE.md"]),
            "STATUS-EVIDENCE:identity_onboarding")

    def test_reported_percentage_cannot_drift(self) -> None:
        self.assert_bites(
            lambda value: value["reported_progress"].update(
                implementation_percent=99),
            "STATUS-STALE-PROGRESS")

    def test_unknown_state_fails_closed(self) -> None:
        self.assert_bites(
            lambda value: value["capabilities"][0].update(
                implementation="almost_done"),
            "STATUS-STATE:identity_onboarding:implementation")


if __name__ == "__main__":
    unittest.main()
