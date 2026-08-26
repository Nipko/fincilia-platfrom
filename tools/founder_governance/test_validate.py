from __future__ import annotations

import copy
import json
import unittest

from .validate import MODEL, ROOT, validate_model, validate_repository


MODEL_DATA = json.loads((ROOT / MODEL).read_text(encoding="utf-8"))


class FounderGovernanceTest(unittest.TestCase):
    def codes(self, model: dict) -> set[str]:
        return {finding.code for finding in validate_model(model)}

    def test_repository_is_valid(self) -> None:
        report, findings = validate_repository()
        self.assertEqual([], findings)
        self.assertEqual(10, report["approved_decisions"])
        self.assertEqual("pending_distinct_humans", report["independent_review"])

    def test_founder_never_becomes_independent_reviewer(self) -> None:
        model = copy.deepcopy(MODEL_DATA)
        model["independent_review"]["founder_counts_as_independent_reviewer"] = True
        self.assertIn("FG-SOD", self.codes(model))

    def test_decision_package_cannot_silently_shrink(self) -> None:
        model = copy.deepcopy(MODEL_DATA)
        model["approved_decisions"].pop()
        self.assertIn("FG-DECISIONS", self.codes(model))

    def test_adr_026_cannot_enter_the_package(self) -> None:
        model = copy.deepcopy(MODEL_DATA)
        model["approved_adrs"].append("ADR-026")
        self.assertIn("FG-ADRS", self.codes(model))

    def test_approval_cannot_open_real_data(self) -> None:
        model = copy.deepcopy(MODEL_DATA)
        model["limits"]["real_financial_data_authorized"] = True
        self.assertIn("FG-LIMITS", self.codes(model))


if __name__ == "__main__":
    unittest.main()
