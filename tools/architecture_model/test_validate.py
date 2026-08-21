from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.architecture_model.validate import validate_model

MODEL_PATH = Path(__file__).parents[2] / "docs/architecture/module-boundaries.json"


class ArchitectureModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def _codes(self, model: dict) -> set[str]:
        return {error.code for error in validate_model(model)}

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model))

    def test_duplicate_entity_owner_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["modules"][0]["owns"].append("company")
        self.assertIn("ARC-ENTITY-MULTIPLE-OWNERS", self._codes(mutated))

    def test_unknown_dependency_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["modules"][0]["allowed_dependencies"].append("unknown_module")
        self.assertIn("ARC-DEPENDENCY-UNKNOWN", self._codes(mutated))

    def test_dependency_cycle_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        tenancy = next(module for module in mutated["modules"] if module["id"] == "tenancy")
        tenancy["allowed_dependencies"].append("access")
        self.assertIn("ARC-DEPENDENCY-CYCLE", self._codes(mutated))

    def test_analytics_cannot_claim_financial_authority(self) -> None:
        mutated = copy.deepcopy(self.model)
        analytics = next(module for module in mutated["modules"] if module["id"] == "analytics")
        analytics["authoritative_financial_state"] = True
        self.assertIn("ARC-FINANCIAL-AUTHORITY-FORBIDDEN", self._codes(mutated))

    def test_cache_cannot_become_authoritative(self) -> None:
        mutated = copy.deepcopy(self.model)
        valkey = next(store for store in mutated["stores"] if store["id"] == "valkey")
        valkey["authority_scope"] = "financial_state"
        self.assertIn("ARC-STORE-AUTHORITY", self._codes(mutated))

    def test_required_invariant_is_enforced(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["global_invariants"] = [
            item for item in mutated["global_invariants"] if item["id"] != "ARC-WORKER-MANIFEST"
        ]
        self.assertIn("ARC-INVARIANT-REQUIRED", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
