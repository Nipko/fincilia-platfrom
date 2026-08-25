from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.founder_governance.validate import MODEL_PATH, ROOT, load_json, validate


class FounderGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = load_json(MODEL_PATH)

    def codes(self, model: dict, root: Path = ROOT) -> set[str]:
        return {error.code for error in validate(model, root)}

    def mutated(self) -> dict:
        return copy.deepcopy(self.model)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate(self.model))

    def test_requires_one_founder(self) -> None:
        model = self.mutated()
        model["human_principals"].append({"id": "OTHER", "kind": "natural_person"})
        self.assertIn("GOV-SINGLE-PRINCIPAL", self.codes(model))

    def test_requires_all_role_slots(self) -> None:
        model = self.mutated()
        model["required_role_slots"].pop()
        self.assertIn("GOV-ROLE-SET", self.codes(model))

    def test_rejects_duplicate_role(self) -> None:
        model = self.mutated()
        model["role_assignments"].append(copy.deepcopy(model["role_assignments"][0]))
        self.assertIn("GOV-ROLE-DUPLICATE", self.codes(model))

    def test_rejects_other_principal_assignment(self) -> None:
        model = self.mutated()
        model["role_assignments"][0]["principal_id"] = "OTHER"
        self.assertIn("GOV-FOUNDER-ASSIGNMENT", self.codes(model))

    def test_rejects_non_provisional_assignment(self) -> None:
        model = self.mutated()
        model["role_assignments"][0]["provisional"] = False
        self.assertIn("GOV-FOUNDER-ASSIGNMENT", self.codes(model))

    def test_rejects_fake_independent_review(self) -> None:
        model = self.mutated()
        model["single_person_governance"]["counts_as_independent_review"] = True
        self.assertIn("GOV-NO-FAKE-INDEPENDENCE", self.codes(model))

    def test_rejects_fake_sod(self) -> None:
        model = self.mutated()
        model["single_person_governance"]["separation_of_duties_satisfied"] = True
        self.assertIn("GOV-NO-FAKE-INDEPENDENCE", self.codes(model))

    def test_required_gate_cannot_be_removed_from_forbidden_list(self) -> None:
        model = self.mutated()
        model["single_person_governance"]["forbidden_promotions"].remove("DRG-00")
        self.assertIn("GOV-FORBIDDEN-PROMOTION", self.codes(model))

    def test_independence_control_cannot_be_satisfied(self) -> None:
        model = self.mutated()
        model["independence_controls"][0]["state"] = "satisfied"
        self.assertIn("GOV-INDEPENDENCE-STATE", self.codes(model))

    def test_source_rejects_traversal(self) -> None:
        model = self.mutated()
        model["decision_sources"][0] = "docs/../docs/privacy/privacy-map.json"
        self.assertIn("GOV-SOURCE-PATH", self.codes(model))

    def test_source_rejects_absolute_path(self) -> None:
        model = self.mutated()
        model["decision_sources"][0] = str((ROOT / "docs/privacy/privacy-map.json").resolve())
        self.assertIn("GOV-SOURCE-PATH", self.codes(model))

    def test_dynamic_new_s1_decision_must_enter_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            source = root / "docs/source.json"
            source.write_text(json.dumps({"unresolved_decisions": [{
                "id": "UD-NEW", "blocks": ["S1-READY"], "owner_role": "Legal",
                "reviewer_roles": ["Privacy"], "state": "pending_human"
            }]}), encoding="utf-8")
            (root / "CURRENT_PHASE.md").write_text("\n".join(
                f"{field}: Founder" for field in (
                    "integration_owner", "product_owner", "accounting_owner",
                    "architecture_owner", "security_owner", "privacy_owner", "legal_owner"
                )
            ), encoding="utf-8")
            model = self.mutated()
            model["decision_sources"] = ["docs/source.json"]
            self.assertIn("GOV-PACKET-COVERAGE", self.codes(model, root))

    def test_packet_cannot_add_non_blocking_decision(self) -> None:
        model = self.mutated()
        model["decision_packet"].append(copy.deepcopy(model["decision_packet"][0]) | {"id": "UD-EXTRA"})
        self.assertIn("GOV-PACKET-COVERAGE", self.codes(model))

    def test_packet_roles_must_match_source(self) -> None:
        model = self.mutated()
        model["decision_packet"][0]["owner_role"] = "Founder"
        self.assertIn("GOV-PACKET-ROLES", self.codes(model))

    def test_packet_requires_independent_human(self) -> None:
        model = self.mutated()
        model["decision_packet"][0]["independent_review_state"] = "satisfied"
        self.assertIn("GOV-PACKET-INDEPENDENCE", self.codes(model))

    def test_packet_recommendation_is_required(self) -> None:
        model = self.mutated()
        model["decision_packet"][0]["recommendation"] = ""
        self.assertIn("GOV-PACKET-EVIDENCE", self.codes(model))

    def test_gate_cannot_be_promoted(self) -> None:
        model = self.mutated()
        model["gate_state"]["S1-READY"] = "met"
        self.assertIn("GOV-GATE-FAIL-CLOSED", self.codes(model))

    def test_current_phase_requires_founder_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in self.model["decision_sources"]:
                target = root / source
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")
            phase = (ROOT / "CURRENT_PHASE.md").read_text(encoding="utf-8-sig")
            (root / "CURRENT_PHASE.md").write_text(phase.replace("security_owner: Founder", "security_owner: UNASSIGNED"), encoding="utf-8")
            self.assertIn("GOV-PHASE-OWNER", self.codes(self.model, root))


if __name__ == "__main__":
    unittest.main()
