from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from .model import validate, validate_repository


ROOT = Path(__file__).resolve().parents[2]
MODEL = json.loads(
    (ROOT / "docs/architecture/aws-free-tier-evaluation.json").read_text(encoding="utf-8")
)


class AwsFreeTierTests(unittest.TestCase):
    def codes(self, model: dict | None = None) -> set[str]:
        return {finding.code for finding in validate(model or MODEL)}

    def mutate(self, path: list[str | int], value: object) -> dict:
        model = copy.deepcopy(MODEL)
        target: object = model
        for key in path[:-1]:
            target = target[key]  # type: ignore[index]
        target[path[-1]] = value  # type: ignore[index]
        return model

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], validate_repository(ROOT))

    def test_final_a02_selection_bites(self) -> None:
        model = self.mutate(["founder_direction", "final_a02_selection"], True)
        self.assertIn("AFT-A02", self.codes(model))

    def test_spend_authorization_bites(self) -> None:
        model = self.mutate(["founder_direction", "cloud_spend_authorized_usd"], 1)
        self.assertIn("AFT-SPEND", self.codes(model))

    def test_real_data_authorization_bites(self) -> None:
        model = self.mutate(["founder_direction", "real_data_authorized"], True)
        self.assertIn("AFT-AUTHORIZATION", self.codes(model))

    def test_account_facts_cannot_be_invented(self) -> None:
        model = self.mutate(["free_tier_program", "account_plan"], "free")
        self.assertIn("AFT-ACCOUNT-EVIDENCE", self.codes(model))

    def test_organizations_exit_bites(self) -> None:
        model = self.mutate(["free_tier_program", "joining_aws_organizations_ends_free_plan"], False)
        self.assertIn("AFT-ORG-EXIT", self.codes(model))

    def test_external_ai_bites(self) -> None:
        model = self.mutate(["fincilia_workload", "external_ai_enabled"], True)
        self.assertIn("AFT-AI", self.codes(model))

    def test_volume_must_be_derived(self) -> None:
        model = self.mutate(["fincilia_workload", "maximum_initial_input_bytes"], 1)
        self.assertIn("AFT-VOLUME", self.codes(model))

    def test_pdf_allowance_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        model["fincilia_workload"]["formats_forbidden_for_initial_research"].remove("pdf")
        self.assertIn("AFT-PDF", self.codes(model))

    def test_unverified_sizing_claim_bites(self) -> None:
        model = self.mutate(["fincilia_workload", "measured_cloud_memory_profile"], True)
        self.assertIn("AFT-SIZING", self.codes(model))

    def test_unknown_source_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        model["service_assessments"][0]["source_ids"] = ["UNKNOWN"]
        self.assertIn("AFT-SERVICE-SOURCE", self.codes(model))

    def test_duplicate_service_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        model["service_assessments"].append(copy.deepcopy(model["service_assessments"][0]))
        self.assertIn("AFT-SERVICE-COVERAGE", self.codes(model))

    def test_nat_cannot_be_described_as_free(self) -> None:
        model = copy.deepcopy(MODEL)
        service = next(item for item in model["service_assessments"] if item["id"] == "NAT_GATEWAY")
        service["free_character"] = "always_free"
        self.assertIn("AFT-PAID-CLAIM", self.codes(model))

    def test_t0_real_data_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        tier = next(item for item in model["launch_tiers"] if item["id"] == "TIER-0-SYNTHETIC")
        tier["data_ceiling"] = "real_research"
        self.assertIn("AFT-T0-BOUND", self.codes(model))

    def test_t0_nat_allowance_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        tier = next(item for item in model["launch_tiers"] if item["id"] == "TIER-0-SYNTHETIC")
        tier["forbidden_services"].remove("NAT_GATEWAY")
        self.assertIn("AFT-T0-COST-TRAPS", self.codes(model))

    def test_t0_cannot_claim_drg00_evidence(self) -> None:
        model = copy.deepcopy(MODEL)
        tier = next(item for item in model["launch_tiers"] if item["id"] == "TIER-0-SYNTHETIC")
        tier["not_evidence_for"].remove("DRG-00")
        self.assertIn("AFT-T0-NONCLAIMS", self.codes(model))

    def test_drg00_free_claim_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        tier = next(item for item in model["launch_tiers"] if item["id"] == "TIER-1-DRG00")
        tier["cash_zero_feasible"] = "yes"
        self.assertIn("AFT-DRG00-FREE", self.codes(model))

    def test_production_free_claim_bites(self) -> None:
        model = self.mutate(["verdict", "can_run_production_entirely_on_free_tier"], True)
        self.assertIn("AFT-VERDICT-PROD", self.codes(model))

    def test_unmeasured_monthly_price_bites(self) -> None:
        model = self.mutate(["cost_control", "monthly_estimate_usd"], 42)
        self.assertIn("AFT-FALSE-PRECISION", self.codes(model))

    def test_missing_calculator_export_bites(self) -> None:
        model = copy.deepcopy(MODEL)
        model["cost_control"]["required_before_any_paid_plan"].remove(
            "AWS_Pricing_Calculator_export_for_sa_east_1"
        )
        self.assertIn("AFT-COST-INPUTS", self.codes(model))


if __name__ == "__main__":
    unittest.main()
