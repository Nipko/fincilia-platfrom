from __future__ import annotations

import copy
import json
import unittest

from .model import MODEL_PATH, validate


MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8"))


class AwsCostEnvelopeTests(unittest.TestCase):
    def codes(self, model: dict | None = None) -> set[str]:
        return {item.code for item in validate(model or MODEL)}

    def mutate(self, path: list[str], value: object) -> dict:
        model = copy.deepcopy(MODEL)
        target = model
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return model

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate(MODEL))

    def test_plan_digest_bites(self) -> None:
        self.assertIn("ACE-PLAN", self.codes(self.mutate(["plan_reference", "sha256"], "0" * 64)))

    def test_action_count_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["plan_reference"]["actions"]["create"] = 141
        self.assertIn("ACE-ACTIONS", self.codes(model))

    def test_resource_total_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["resource_type_counts"]["aws_subnet"] = 8
        self.assertIn("ACE-COUNT-TOTAL", self.codes(model))

    def test_kms_count_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["resource_type_counts"]["aws_kms_key"] = 4; model["resource_type_counts"]["aws_subnet"] = 8
        self.assertIn("ACE-COUNT-DRIVER", self.codes(model))

    def test_floor_cannot_claim_complete_estimate(self) -> None:
        self.assertIn("ACE-FLOOR-NONCLAIM", self.codes(self.mutate(["known_priced_floor", "not_a_complete_monthly_estimate"], False)))

    def test_unit_price_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["known_priced_floor"]["components"][0]["unit_monthly_usd"] = "0.00"
        self.assertIn("ACE-PRICE", self.codes(model))

    def test_floor_total_bites(self) -> None:
        self.assertIn("ACE-FLOOR-TOTAL", self.codes(self.mutate(["known_priced_floor", "subtotal_monthly_usd"], "5.00")))

    def test_primary_source_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["sources"][0]["url"] = "https://example.com/price"
        self.assertIn("ACE-SOURCE", self.codes(model))

    def test_unpriced_component_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["unpriced_cold_components"].pop()
        self.assertIn("ACE-UNPRICED", self.codes(model))

    def test_warm_driver_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["warm_only_cost_drivers"].pop()
        self.assertIn("ACE-WARM", self.codes(model))

    def test_credits_are_not_zero_cost(self) -> None:
        self.assertIn("ACE-CREDIT-NONCLAIM", self.codes(self.mutate(["account_program_facts", "credits_are_not_zero_cost"], False)))

    def test_apply_authorization_bites(self) -> None:
        self.assertIn("ACE-AUTHORIZATION", self.codes(self.mutate(["decision_state", "apply_authorized"], True)))

    def test_real_data_authorization_bites(self) -> None:
        self.assertIn("ACE-AUTHORIZATION", self.codes(self.mutate(["decision_state", "real_data_authorized"], True)))

    def test_false_monthly_precision_bites(self) -> None:
        self.assertIn("ACE-FALSE-PRECISION", self.codes(self.mutate(["decision_state", "complete_monthly_estimate_usd"], "10.00")))

    def test_missing_pre_apply_decision_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["decision_state"]["required_before_apply"].pop()
        self.assertIn("ACE-DECISIONS", self.codes(model))


if __name__ == "__main__":
    unittest.main()
