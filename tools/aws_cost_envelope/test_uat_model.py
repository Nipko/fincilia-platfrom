from __future__ import annotations

import copy
import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch

from .cli import main as cli_main
from .uat_model import MODEL_PATH, validate


MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8"))


class AwsUatCostDecisionTests(unittest.TestCase):
    def codes(self, model: dict | None = None) -> set[str]:
        return {item.code for item in validate(model or MODEL)}

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate(MODEL))

    def test_region_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["region"] = "us-east-1"
        self.assertIn("UATC-IDENTITY", self.codes(model))

    def test_hours_bite(self) -> None:
        model = copy.deepcopy(MODEL); model["monthly_hours"] = 720
        self.assertIn("UATC-BOUNDARY", self.codes(model))

    def test_rate_coverage_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["regional_rates"].pop()
        self.assertIn("UATC-RATE-COVERAGE", self.codes(model))

    def test_rate_value_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["regional_rates"][0]["unit_usd"] = "0"
        self.assertIn("UATC-RATE", self.codes(model))

    def test_price_list_sku_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["regional_rates"][0]["sku"] = None
        self.assertIn("UATC-SKU", self.codes(model))

    def test_component_arithmetic_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["monthly_scenarios"]["current_uat"]["components"][0]["subtotal_usd"] = "1"
        self.assertIn("UATC-ARITHMETIC", self.codes(model))

    def test_current_total_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["monthly_scenarios"]["current_uat"]["fixed_subtotal_usd"] = "30"
        self.assertIn("UATC-TOTAL", self.codes(model))

    def test_warm_total_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["monthly_scenarios"]["private_pilot_warm_services_active"]["fixed_subtotal_usd"] = "0"
        self.assertIn("UATC-TOTAL", self.codes(model))

    def test_recommendation_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["decision"]["recommendation"] = "apply_private_pilot"
        self.assertIn("UATC-RECOMMENDATION", self.codes(model))

    def test_budget_authorization_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["decision"]["budget_change_authorized"] = True
        self.assertIn("UATC-AUTHORIZATION", self.codes(model))

    def test_apply_authorization_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["decision"]["private_pilot_apply_authorized"] = True
        self.assertIn("UATC-AUTHORIZATION", self.codes(model))

    def test_real_data_authorization_bites(self) -> None:
        model = copy.deepcopy(MODEL); model["decision"]["real_data_authorized"] = True
        self.assertIn("UATC-AUTHORIZATION", self.codes(model))

    def test_review_cannot_self_accept(self) -> None:
        model = copy.deepcopy(MODEL); model["decision"]["independent_review_pending"] = False
        self.assertIn("UATC-REVIEW", self.codes(model))

    def test_uat_validate_cli_is_green(self) -> None:
        output = io.StringIO()
        with patch.object(sys, "argv", ["aws-cost-envelope", "uat-validate"]), contextlib.redirect_stdout(output):
            self.assertEqual(0, cli_main())
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_uat_report_cli_is_redacted_and_exact(self) -> None:
        output = io.StringIO()
        with patch.object(sys, "argv", ["aws-cost-envelope", "uat-report"]), contextlib.redirect_stdout(output):
            self.assertEqual(0, cli_main())
        report = json.loads(output.getvalue())
        self.assertEqual("34.258000", report["current_account_fixed_monthly_usd"])
        self.assertEqual("319.264000", report["private_pilot_warm_active_fixed_monthly_usd"])
        self.assertNotIn("account", output.getvalue().lower().replace("current_account", ""))


if __name__ == "__main__":
    unittest.main()
