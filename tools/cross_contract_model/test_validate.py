from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.cross_contract_model.validate import validate_model

ROOT = Path(__file__).parents[2]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class CrossContractModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load("docs/architecture/cross-contract-vocabulary.json")
        self.boundaries = load("docs/architecture/module-boundaries.json")
        self.dfd = load("docs/architecture/dfd-flows.json")
        self.canonical = load("docs/domain/canonical-model.json")
        self.lineage = load("docs/domain/lineage-model.json")
        self.adr = (ROOT / "docs/adr/ADR-023-engine-release.md").read_text(encoding="utf-8")

    def codes(
        self,
        model: dict | None = None,
        boundaries: dict | None = None,
        dfd: dict | None = None,
        canonical: dict | None = None,
        lineage: dict | None = None,
        adr: str | None = None,
    ) -> set[str]:
        errors = validate_model(
            model or self.model,
            boundaries or self.boundaries,
            dfd or self.dfd,
            canonical or self.canonical,
            lineage or self.lineage,
            self.adr if adr is None else adr,
        )
        return {error.code for error in errors}

    def mutate_mapping(self, mapping_id: str) -> tuple[dict, dict]:
        model = copy.deepcopy(self.model)
        mapping = next(item for item in model["store_contract"]["mappings"]
                       if item["id"] == mapping_id)
        return model, mapping

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual(set(), self.codes())

    def test_TST_XCON_001_all_boundary_stores_are_mapped_once(self) -> None:
        model = copy.deepcopy(self.model)
        model["store_contract"]["mappings"].pop(0)
        self.assertIn("XCON-BOUNDARY-COVERAGE", self.codes(model=model))

    def test_TST_XCON_002_all_dfd_stores_are_mapped_once(self) -> None:
        model, mapping = self.mutate_mapping("STORE-VAULT")
        mapping["dfd_store_ids"] = []
        self.assertIn("XCON-DFD-COVERAGE", self.codes(model=model))

    def test_duplicate_mapping_id_is_rejected(self) -> None:
        model = copy.deepcopy(self.model)
        model["store_contract"]["mappings"][1]["id"] = \
            model["store_contract"]["mappings"][0]["id"]
        self.assertIn("XCON-STORE-ID", self.codes(model=model))

    def test_TST_XCON_003_active_store_requires_real_persistence(self) -> None:
        model, mapping = self.mutate_mapping("STORE-VALKEY")
        mapping["usage_state"] = "active"
        self.assertIn("XCON-STORE-USAGE", self.codes(model=model))

    def test_inactive_store_cannot_gain_persistence_silently(self) -> None:
        dfd = copy.deepcopy(self.dfd)
        dfd["flows"][0]["persistence"].append({"store": "temporal"})
        self.assertIn("XCON-STORE-USAGE", self.codes(dfd=dfd))

    def test_no_authority_store_cannot_become_active(self) -> None:
        model, mapping = self.mutate_mapping("STORE-VALKEY")
        mapping["usage_state"] = "active"
        dfd = copy.deepcopy(self.dfd)
        dfd["flows"][0]["persistence"].append({"store": "valkey"})
        self.assertIn("XCON-STORE-AUTHORITY", self.codes(model=model, dfd=dfd))

    def test_TST_XCON_004_object_zones_cannot_lose_isolation(self) -> None:
        model, mapping = self.mutate_mapping("STORE-OBJECT-ZONES")
        mapping["zone_isolation_required"] = False
        self.assertIn("XCON-ZONE-ISOLATION", self.codes(model=model))

    def test_dfd_only_vault_stays_pending(self) -> None:
        model, mapping = self.mutate_mapping("STORE-VAULT")
        mapping["decision_state"] = "proposed"
        self.assertIn("XCON-STORE-UNRESOLVED", self.codes(model=model))

    def test_store_decision_cannot_be_agent_accepted(self) -> None:
        model, mapping = self.mutate_mapping("STORE-TEMPORAL")
        mapping["decision_state"] = "accepted"
        self.assertIn("XCON-STORE-DECISION", self.codes(model=model))

    def test_inactive_persistence_effect_must_block(self) -> None:
        model = copy.deepcopy(self.model)
        model["store_contract"]["inactive_store_persistence_effect"] = "warn"
        self.assertIn("XCON-INACTIVE-EFFECT", self.codes(model=model))

    def test_TST_XCON_005_canonical_classes_equal_shared_subset(self) -> None:
        model = copy.deepcopy(self.model)
        model["classification_contract"]["shared_domain_classes"].remove("secret")
        self.assertIn("XCON-CLASS-CANONICAL", self.codes(model=model))

    def test_dfd_edge_classes_are_exact(self) -> None:
        model = copy.deepcopy(self.model)
        model["classification_contract"]["dfd_edge_only_classes"] = ["prohibited"]
        self.assertIn("XCON-CLASS-DFD", self.codes(model=model))

    def test_classification_rank_drift_is_rejected(self) -> None:
        dfd = copy.deepcopy(self.dfd)
        next(item for item in dfd["classifications"] if item["id"] == "secret")["rank"] = 2
        self.assertIn("XCON-CLASS-RANK", self.codes(dfd=dfd))

    def test_public_or_prohibited_cannot_classify_canonical_entity(self) -> None:
        canonical = copy.deepcopy(self.canonical)
        canonical["entities"][0]["classification"] = "public"
        self.assertIn("XCON-CLASS-ENTITY", self.codes(canonical=canonical))

    def test_prohibited_cannot_persist_or_egress(self) -> None:
        model = copy.deepcopy(self.model)
        model["classification_contract"]["prohibited_persistence"] = "approved_stores"
        self.assertIn("XCON-PROHIBITED", self.codes(model=model))

    def test_secret_remains_vault_only(self) -> None:
        model = copy.deepcopy(self.model)
        model["classification_contract"]["secret_persistence"] = "encrypted_scoped"
        self.assertIn("XCON-SECRET", self.codes(model=model))

    def test_TST_XCON_006_personal_axis_stays_orthogonal_pending_and_closed(self) -> None:
        for field, value in (
            ("state", "accepted"),
            ("orthogonal_to_operational_classification", False),
            ("unknown_external_egress", "allowed"),
            ("agent_may_define_taxonomy", True),
        ):
            with self.subTest(field=field):
                model = copy.deepcopy(self.model)
                model["classification_contract"]["personal_data_axis"][field] = value
                self.assertIn("XCON-PERSONAL-AXIS", self.codes(model=model))

    def test_release_fields_must_match_lineage_exactly(self) -> None:
        model = copy.deepcopy(self.model)
        model["engine_release_profile"]["required_fields"].remove("source_tree_clean")
        self.assertIn("XCON-RELEASE-FIELDS", self.codes(model=model))

    def test_floating_release_versions_stay_forbidden(self) -> None:
        model = copy.deepcopy(self.model)
        model["engine_release_profile"]["floating_versions_forbidden"].remove("latest")
        self.assertIn("XCON-RELEASE-FLOATING", self.codes(model=model))

    def test_agent_cannot_approve_release(self) -> None:
        model = copy.deepcopy(self.model)
        model["engine_release_profile"]["agent_can_approve_release"] = True
        self.assertIn("XCON-RELEASE-AUTHORITY", self.codes(model=model))

    def test_unverifiable_release_must_block(self) -> None:
        model = copy.deepcopy(self.model)
        model["engine_release_profile"]["unverifiable_release_effect"] = "warn"
        self.assertIn("XCON-RELEASE-AUTHORITY", self.codes(model=model))

    def test_ADR_023_must_name_extended_profile_fields(self) -> None:
        adr = self.adr.replace("source_tree_clean", "source-tree-clean")
        self.assertIn("XCON-ADR-PROFILE", self.codes(adr=adr))

    def test_decisions_remain_proposed(self) -> None:
        model = copy.deepcopy(self.model)
        model["decision_states"]["DR-ARC-001"] = "accepted"
        self.assertIn("XCON-DECISION", self.codes(model=model))

    def test_gate_cannot_be_marked_met(self) -> None:
        model = copy.deepcopy(self.model)
        model["gates"][0]["status"] = "met"
        self.assertIn("XCON-GATE", self.codes(model=model))

    def test_required_test_cannot_be_removed(self) -> None:
        model = copy.deepcopy(self.model)
        model["required_tests"].pop()
        self.assertIn("XCON-TESTS", self.codes(model=model))

    def test_unknown_top_level_key_is_rejected(self) -> None:
        model = copy.deepcopy(self.model)
        model["silent_extension"] = True
        self.assertIn("XCON-TOP-LEVEL", self.codes(model=model))

    def test_validator_is_deterministic_and_offline(self) -> None:
        first = validate_model(self.model, self.boundaries, self.dfd, self.canonical,
                               self.lineage, self.adr)
        second = validate_model(copy.deepcopy(self.model), self.boundaries, self.dfd,
                                self.canonical, self.lineage, self.adr)
        self.assertEqual(first, second)
        source = (ROOT / "tools/cross_contract_model/validate.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "urllib", "socket", "subprocess", "os.environ", "datetime"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
