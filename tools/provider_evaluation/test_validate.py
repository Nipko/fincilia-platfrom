from __future__ import annotations

import copy
import json
import unittest

from .validate import ROOT, validate_repository


MODEL = json.loads((ROOT / "docs/integrations/provider-evaluation.json").read_text(encoding="utf-8"))


class ProviderEvaluationTest(unittest.TestCase):
    def mutated(self) -> dict:
        return copy.deepcopy(MODEL)

    def assert_bites(self, model: dict, code: str) -> None:
        _, findings = validate_repository(ROOT, model)
        self.assertIn(code, {finding.code for finding in findings})

    def candidate(self, model: dict, identifier: str) -> dict:
        return next(item for item in model["candidates"] if item["id"] == identifier)

    def test_repository_model_is_valid(self) -> None:
        report, findings = validate_repository()
        self.assertEqual([], findings)
        self.assertEqual(0, report["quotes_received"])
        self.assertIsNone(report["winner"])

    def test_production_enablement_bites(self) -> None:
        model = self.mutated(); model["production_connections_allowed"] = True
        self.assert_bites(model, "INT-DATA-GATE")

    def test_real_data_bites(self) -> None:
        model = self.mutated(); model["data_ceiling"] = "real"
        self.assert_bites(model, "INT-DATA-GATE")

    def test_agent_vendor_selection_bites(self) -> None:
        model = self.mutated(); model["agent_may_select_vendor"] = True
        self.assert_bites(model, "INT-HUMAN")

    def test_winner_selection_bites(self) -> None:
        model = self.mutated(); model["scoring"]["winner"] = "prometeo"
        self.assert_bites(model, "INT-WINNER")

    def test_bank_credential_capture_bites(self) -> None:
        model = self.mutated(); model["platform_never_receives_bank_credentials"] = False
        self.assert_bites(model, "INT-CREDENTIAL")

    def test_file_fallback_removal_bites(self) -> None:
        model = self.mutated(); model["permanent_fallback"] = "prometeo"
        self.assert_bites(model, "INT-FALLBACK")

    def test_file_kind_change_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "file_ingestion")["kind"] = "temporary"
        self.assert_bites(model, "INT-FALLBACK")

    def test_missing_candidate_bites(self) -> None:
        model = self.mutated(); model["candidates"] = model["candidates"][:-1]
        self.assert_bites(model, "INT-COVERAGE")

    def test_duplicate_candidate_bites(self) -> None:
        model = self.mutated(); model["candidates"].append(copy.deepcopy(model["candidates"][0]))
        self.assert_bites(model, "INT-COVERAGE")

    def test_premature_score_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "prometeo")["score"] = 92
        self.assert_bites(model, "INT-PREMATURE-SCORE")

    def test_prometeo_coverage_claim_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "prometeo")["business_coverage"] = "verified"
        self.assert_bites(model, "INT-COVERAGE-CLAIM")

    def test_bancolombia_coverage_claim_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "bancolombia_direct")["business_coverage"] = "verified"
        self.assert_bites(model, "INT-COVERAGE-CLAIM")

    def test_belvo_colombia_claim_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "belvo")["countries"] = ["CO"]
        self.assert_bites(model, "INT-BELVO")

    def test_non_official_source_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "prometeo")["sources"] = ["https://example.com/claim"]
        self.assert_bites(model, "INT-SOURCE")

    def test_missing_local_source_bites(self) -> None:
        model = self.mutated(); self.candidate(model, "file_ingestion")["sources"] = ["docs/missing.json"]
        self.assert_bites(model, "INT-SOURCE")

    def test_weight_drift_bites(self) -> None:
        model = self.mutated(); model["scoring"]["weights"]["total_cost"] = 50
        self.assert_bites(model, "INT-SCORING")

    def test_evidence_weakening_bites(self) -> None:
        model = self.mutated(); model["scoring"]["minimum_evidence"] = ["quote"]
        self.assert_bites(model, "INT-EVIDENCE")

    def test_fake_quote_bites(self) -> None:
        model = self.mutated(); model["rfq"]["received_quotes"] = 3
        self.assert_bites(model, "INT-QUOTE")

    def test_agent_outreach_bites(self) -> None:
        model = self.mutated(); model["rfq"]["outreach_authorized"] = True
        self.assert_bites(model, "INT-OUTREACH")

    def test_fx_scenarios_weakening_bites(self) -> None:
        model = self.mutated(); model["rfq"]["fx_scenarios_percent"] = [0]
        self.assert_bites(model, "INT-COST")

    def test_external_gate_promotion_bites(self) -> None:
        model = self.mutated(); model["gates"][1]["state"] = "met"
        self.assert_bites(model, "INT-GATE")

    def test_duplicate_gate_bites(self) -> None:
        model = self.mutated(); model["gates"][1]["id"] = "INT-G01"
        self.assert_bites(model, "INT-GATE")

    def test_unknown_top_level_key_bites(self) -> None:
        model = self.mutated(); model["surprise"] = True
        self.assert_bites(model, "INT-SCHEMA")


if __name__ == "__main__":
    unittest.main()
