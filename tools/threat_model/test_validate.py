from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.threat_model.validate import validate_model

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/security/threat-model.json"
DFD_PATH = ROOT / "docs/architecture/dfd-flows.json"


class ThreatModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.dfd = json.loads(DFD_PATH.read_text(encoding="utf-8"))

    def _codes(self, model: dict) -> set[str]:
        return {error.code for error in validate_model(model, self.dfd, ROOT)}

    def _risk(self, model: dict, risk_id: str) -> dict:
        return next(risk for risk in model["risks"] if risk["id"] == risk_id)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.dfd, ROOT))

    def test_incorrect_score_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["inherent"]["score"] = 24
        self.assertIn("TM-SCORE-FORMULA", self._codes(mutated))

    def test_incorrect_severity_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["inherent"]["severity"] = "high"
        self.assertIn("TM-SCORE-SEVERITY", self._codes(mutated))

    def test_agent_cannot_accept_residual_risk(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["acceptance"] = "accepted"
        self.assertIn("TM-HUMAN-ACCEPTANCE", self._codes(mutated))

    def test_risk_cannot_be_marked_closed(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["status"] = "closed"
        self.assertIn("TM-RISK-OPEN", self._codes(mutated))

    def test_cross_company_control_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["controls"].remove("C-RLS")
        self.assertIn("TM-SCENARIO-CONTROL", self._codes(mutated))

    def test_ai_gateway_control_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-010")["controls"].remove("C-EGRESS")
        self.assertIn("TM-SCENARIO-CONTROL", self._codes(mutated))

    def test_restore_control_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-014")["controls"].remove("C-DELETE")
        self.assertIn("TM-SCENARIO-CONTROL", self._codes(mutated))

    def test_missing_dfd_threat_coverage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        for risk in mutated["risks"]:
            risk["dfd_threats"] = [threat for threat in risk["dfd_threats"] if threat != "T08"]
        self.assertIn("TM-DFD-THREAT-COVERAGE", self._codes(mutated))

    def test_missing_flow_coverage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        for risk in mutated["risks"]:
            risk["flows"] = [flow for flow in risk["flows"] if flow != "F08"]
        self.assertIn("TM-DFD-FLOW-COVERAGE", self._codes(mutated))

    def test_unknown_control_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-003")["controls"].append("C-UNKNOWN")
        self.assertIn("TM-RISK-REFERENCE-UNKNOWN", self._codes(mutated))

    def test_missing_evidence_path_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._risk(mutated, "TM-001")["evidence"][0]["path"] = "missing/evidence.test"
        self.assertIn("TM-EVIDENCE-MISSING", self._codes(mutated))

    def test_owner_cannot_be_only_reviewer(self) -> None:
        mutated = copy.deepcopy(self.model)
        risk = self._risk(mutated, "TM-001")
        risk["reviewer_roles"] = [risk["owner_role"]]
        self.assertIn("TM-INDEPENDENT-REVIEW", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
