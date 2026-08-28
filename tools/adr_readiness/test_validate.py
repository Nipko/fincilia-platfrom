from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from .validate import ROOT, validate_repository


MODEL = json.loads((ROOT / "docs/architecture/adr-readiness.json").read_text(encoding="utf-8"))


class AdrReadinessTest(unittest.TestCase):
    def assert_bites(self, mutated: dict, code: str) -> None:
        _, findings = validate_repository(ROOT, mutated)
        self.assertIn(code, {finding.code for finding in findings})

    def mutate(self) -> dict:
        return copy.deepcopy(MODEL)

    def test_repository_model_is_valid(self) -> None:
        report, findings = validate_repository()
        self.assertEqual([], findings)
        self.assertEqual("not_met", report["gate"])
        # Toda ADR que sigue en `Proposed` tiene que registrarse `blocked`: el
        # validador lo exige y evita que un spike o una beta condicionada
        # cuenten como decision de produccion.
        self.assertEqual(
            [
                "ADR-012", "ADR-020", "ADR-026", "ADR-027", "ADR-028",
                "ADR-029", "ADR-030", "ADR-031",
            ],
            report["blocked"],
        )

    def test_agent_acceptance_bites(self) -> None:
        model = self.mutate(); model["agent_may_accept"] = True
        self.assert_bites(model, "ADR-RDY-HUMAN")

    def test_human_acceptance_bites(self) -> None:
        model = self.mutate(); model["human_acceptance"] = "accepted"
        self.assert_bites(model, "ADR-RDY-HUMAN")

    def test_gate_promotion_bites(self) -> None:
        model = self.mutate(); model["release_rule"]["state"] = "met"
        self.assert_bites(model, "ADR-RDY-GATE")

    def test_gate_control_removal_bites(self) -> None:
        model = self.mutate(); model["release_rule"]["requires_independent_reviews"] = False
        self.assert_bites(model, "ADR-RDY-GATE")

    def test_real_data_ceiling_bites(self) -> None:
        model = self.mutate(); model["data_ceiling"] = "real_allowed"
        self.assert_bites(model, "ADR-RDY-DATA")

    def test_missing_core_adr_bites(self) -> None:
        model = self.mutate(); model["required_s1_adrs"].remove("ADR-009")
        self.assert_bites(model, "ADR-RDY-CORE")

    def test_unregistered_discovered_adr_bites(self) -> None:
        model = self.mutate(); model["adrs"] = model["adrs"][:-1]
        self.assert_bites(model, "ADR-RDY-COVERAGE")

    def test_duplicate_adr_bites(self) -> None:
        model = self.mutate(); model["adrs"].append(copy.deepcopy(model["adrs"][0]))
        self.assert_bites(model, "ADR-RDY-DUPLICATE")

    def test_unknown_record_key_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["surprise"] = True
        self.assert_bites(model, "ADR-RDY-RECORD")

    def test_bad_path_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["path"] = "docs/../docs/adr/ADR-001-modular-monolith-workers.md"
        self.assert_bites(model, "ADR-RDY-PATH")

    def test_external_path_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["path"] = "../outside.md"
        self.assert_bites(model, "ADR-RDY-PATH")

    def test_proposed_cannot_be_conditional(self) -> None:
        model = self.mutate()
        next(item for item in model["adrs"] if item["id"] == "ADR-020")["readiness"] = "conditional"
        self.assert_bites(model, "ADR-RDY-PROPOSED")

    def test_unassigned_owner_needs_blocker(self) -> None:
        model = self.mutate()
        record = next(item for item in model["adrs"] if item["id"] == "ADR-026")
        record["blockers"].remove("named_owner_assignment")
        self.assert_bites(model, "ADR-RDY-OWNER")

    def test_missing_evidence_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["evidence"] = []
        self.assert_bites(model, "ADR-RDY-EVIDENCE")

    def test_unknown_evidence_path_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["evidence"] = ["docs/missing.json"]
        self.assert_bites(model, "ADR-RDY-EVIDENCE")

    def test_owner_reviewer_overlap_bites(self) -> None:
        model = self.mutate(); model["adrs"][0]["reviewers"].append("Architecture")
        self.assert_bites(model, "ADR-RDY-SOD")

    def test_conditional_without_blocker_bites(self) -> None:
        model = self.mutate()
        record = next(item for item in model["adrs"] if item["id"] == "ADR-014")
        record["blockers"] = []
        self.assert_bites(model, "ADR-RDY-BLOCKER")

    def test_decision_cannot_be_agent_closed(self) -> None:
        model = self.mutate()
        model["decisions"][0]["state"] = "accepted"
        self.assert_bites(model, "ADR-RDY-DECISION")

    def test_unknown_top_level_key_bites(self) -> None:
        model = self.mutate(); model["extra"] = True
        self.assert_bites(model, "ADR-RDY-SCHEMA")


if __name__ == "__main__":
    unittest.main()
