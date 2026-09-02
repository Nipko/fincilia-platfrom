from __future__ import annotations

import copy
import json
import unittest

from .model import (
    CONTROL_IDS,
    FOUNDER_ID,
    ROOT,
    SUPPLY_CHAIN_EVIDENCE,
    load_model,
    report,
    validate,
    validate_supply_chain_evidence,
)


class Drg01ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_model()

    def codes(self, candidate: dict) -> set[str]:
        return {item.code for item in validate(candidate)}

    def test_repository_model_is_valid_and_closed(self) -> None:
        payload = report(self.model)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertEqual(13, payload["blocker_count"])
        self.assertEqual(["DRG-00", "DRG-01"], [item["id"] for item in payload["gates"]])
        technical = {
            item["id"]: item["state"] for item in self.model["controls"]
            if item["id"].startswith("G00-") and item["kind"] == "automated"
        }
        self.assertEqual({
            "G00-ISOLATED-ENV": "pending", "G00-INVENTORY": "passed",
            "G00-DELETE": "passed", "G00-DRILL": "passed",
            "G00-SUPPLY-CHAIN": "passed",
        }, technical)

    def supply_evidence(self) -> dict:
        return json.loads((ROOT / SUPPLY_CHAIN_EVIDENCE).read_text(encoding="utf-8"))

    def test_supply_chain_evidence_is_bound_to_current_release_inputs(self) -> None:
        self.assertEqual([], validate_supply_chain_evidence(self.supply_evidence()))

    def test_supply_chain_evidence_mutations_bite(self) -> None:
        mutations = (
            ("DRG-SUPPLY-RUN", lambda item: item["run"].update({"signer_workflow": "other"})),
            ("DRG-SUPPLY-ATTESTATION", lambda item: item["attestations"][0].update(
                {"signature_verified_outside_runner": False})),
            ("DRG-SUPPLY-SOURCE", lambda item: item["source_inputs"][0].update(
                {"sha256": "0" * 64})),
            ("DRG-SUPPLY-REVIEW", lambda item: item["independent_review"].update(
                {"state": "accepted"})),
            ("DRG-SUPPLY-DIGEST", lambda item: item.update(
                {"evidence_sha256": "0" * 64})),
        )
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                candidate = self.supply_evidence()
                mutate(candidate)
                codes = {finding.code for finding in validate_supply_chain_evidence(candidate)}
                self.assertIn(expected, codes)

    def test_supply_chain_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"]
                       if item["id"] == "G00-SUPPLY-CHAIN")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG-SUPPLY-REF", self.codes(candidate))

    def test_scope_widening_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["pilot_scope"]["maximum_companies"] = 2
        self.assertIn("DRG-SCOPE", self.codes(candidate))

    def test_external_ai_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["pilot_scope"]["disabled_capabilities"].remove("external_ai")
        self.assertIn("DRG-SCOPE", self.codes(candidate))

    def test_missing_control_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["controls"].pop()
        self.assertIn("DRG-COVERAGE", self.codes(candidate))

    def test_wrong_control_kind_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["controls"][0]["kind"] = "automated"
        self.assertIn("DRG-CONTROL-KIND", self.codes(candidate))

    def test_founder_cannot_review_himself(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = candidate["controls"][0]
        control.update({"state": "accepted", "reviewer_id": FOUNDER_ID,
                        "reviewed_at": "2026-08-28",
                        "evidence_refs": ["docs/security/DRG01_READINESS.md"]})
        self.assertIn("DRG-SOD", self.codes(candidate))

    def test_fake_technical_pass_without_evidence_bites_derivation(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-IDENTITY")
        control["state"] = "passed"
        self.assertIn("DRG-EVIDENCE", self.codes(candidate))
        self.assertFalse(report(candidate)["real_data_authorized"])

    def test_unknown_evidence_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-IDENTITY")
        control.update({"state": "passed", "evidence_refs": ["docs/missing-evidence.json"]})
        self.assertIn("DRG-EVIDENCE", self.codes(candidate))

    def test_adjudicated_drg01_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-XTENANT")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG01-TECH-REF", self.codes(candidate))

    def test_rights_incident_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-RIGHTS-IR")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG01-RIGHTS-IR-REF", self.codes(candidate))

    def test_drg00_technical_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"]
                       if item["id"] == "G00-DRILL")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG-TECH-REF", self.codes(candidate))

    def test_drg01_cannot_open_before_drg00(self) -> None:
        candidate = copy.deepcopy(self.model)
        for control in candidate["controls"]:
            if control["gate"] == "DRG-01" and control["kind"] == "automated":
                control.update({"state": "passed", "evidence_refs": ["docs/security/DRG01_READINESS.md"]})
            elif control["gate"] == "DRG-01" and control["kind"] == "human":
                control.update({"state": "accepted", "evidence_refs": ["docs/security/DRG01_READINESS.md"],
                                "reviewer_id": "INDEPENDENT-TEST", "reviewed_at": "2026-08-28"})
        self.assertFalse(report(candidate)["real_data_authorized"])

    def test_control_inventory_matches_gate_partition(self) -> None:
        expected = set().union(*CONTROL_IDS.values())
        self.assertEqual(expected, {item["id"] for item in self.model["controls"]})


if __name__ == "__main__":
    unittest.main()
