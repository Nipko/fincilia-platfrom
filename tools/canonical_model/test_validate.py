from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.canonical_model.validate import validate_model

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/domain/canonical-model.json"
ARCHITECTURE_PATH = ROOT / "docs/architecture/module-boundaries.json"


class CanonicalModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.architecture = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))

    def _codes(self, model: dict, architecture: dict | None = None) -> set[str]:
        return {error.code for error in validate_model(model, architecture or self.architecture)}

    def _entity(self, model: dict, entity_id: str) -> dict:
        return next(entity for entity in model["entities"] if entity["id"] == entity_id)

    def _field(self, model: dict, entity_id: str, field_name: str) -> dict:
        entity = self._entity(model, entity_id)
        return next(field for field in entity["fields"] if field["name"] == field_name)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.architecture))

    def test_float_money_storage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        money = next(item for item in mutated["logical_types"] if item["id"] == "money_decimal")
        money["storage"] = "double precision"
        self.assertIn("DOM-MONEY-TYPE", self._codes(mutated))

    def test_financial_entity_without_company_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "money_movement")["company_scoped"] = False
        self.assertIn("DOM-FINANCE-SCOPE", self._codes(mutated))

    def test_nullable_company_id_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._field(mutated, "money_movement", "company_id")["nullable"] = True
        self.assertIn("DOM-COMPANY-FIELD", self._codes(mutated))

    def test_cross_company_fk_without_scope_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        relation = self._entity(mutated, "money_movement")["relationships"][0]
        relation["company_scoped_fk"] = False
        self.assertIn("DOM-COMPOSITE-FK", self._codes(mutated))

    def test_cascade_delete_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "source_record")["relationships"][0]["on_delete"] = "cascade"
        self.assertIn("DOM-DELETE-CASCADE", self._codes(mutated))

    def test_dedupe_fingerprint_unique_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        movement = self._entity(mutated, "money_movement")
        movement["unique_constraints"].append({"id": "uq_bad", "fields": ["company_id", "dedupe_fingerprint"], "kind": "hard_idempotency"})
        self.assertIn("DOM-UNSAFE-UNIQUE", self._codes(mutated))

    def test_amount_date_reference_composite_unique_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        movement = self._entity(mutated, "money_movement")
        movement["unique_constraints"].append({"id": "uq_bad_candidate", "fields": ["company_id", "amount", "accounting_date", "direction"], "kind": "hard_idempotency"})
        self.assertIn("DOM-UNSAFE-UNIQUE", self._codes(mutated))

    def test_source_record_cannot_become_financial_authority(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "source_record")["authoritative_financial_state"] = True
        self.assertIn("DOM-SOURCE-AUTHORITY", self._codes(mutated))

    def test_evidence_link_must_connect_source_and_movement(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "movement_evidence_link")["relationships"].pop()
        self.assertIn("DOM-EVIDENCE-LINK-TARGETS", self._codes(mutated))

    def test_json_without_schema_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._field(mutated, "raw_record", "raw_values").pop("schema_ref")
        self.assertIn("DOM-JSON-CONTRACT", self._codes(mutated))

    def test_json_without_size_limit_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._field(mutated, "source_record", "source_payload")["max_bytes"] = 0
        self.assertIn("DOM-JSON-CONTRACT", self._codes(mutated))

    def test_clear_account_identifier_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._field(mutated, "financial_account", "identifier_token")["type"] = "text"
        self.assertIn("DOM-ACCOUNT-TOKEN", self._codes(mutated))

    def test_missing_date_semantic_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        movement = self._entity(mutated, "money_movement")
        movement["fields"] = [field for field in movement["fields"] if field["name"] != "value_date"]
        self.assertIn("DOM-REQUIRED-FIELD", self._codes(mutated))

    def test_settlement_component_is_required(self) -> None:
        mutated = copy.deepcopy(self.model)
        settlement = self._entity(mutated, "settlement")
        settlement["fields"] = [field for field in settlement["fields"] if field["name"] != "withholding_amount"]
        self.assertIn("DOM-REQUIRED-FIELD", self._codes(mutated))

    def test_ledger_direction_is_required(self) -> None:
        mutated = copy.deepcopy(self.model)
        line = self._entity(mutated, "ledger_line")
        line["fields"] = [field for field in line["fields"] if field["name"] != "debit_credit"]
        self.assertIn("DOM-REQUIRED-FIELD", self._codes(mutated))

    def test_core_fact_requires_engine_release(self) -> None:
        mutated = copy.deepcopy(self.model)
        movement = self._entity(mutated, "money_movement")
        movement["fields"] = [field for field in movement["fields"] if field["name"] != "engine_release_id"]
        self.assertIn("DOM-REQUIRED-FIELD", self._codes(mutated))

    def test_owner_mismatch_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "money_movement")["owner_module"] = "clean"
        self.assertIn("DOM-OWNER-MISMATCH", self._codes(mutated))

    def test_architecture_without_entity_owner_is_rejected(self) -> None:
        architecture = copy.deepcopy(self.architecture)
        finance = next(module for module in architecture["modules"] if module["id"] == "finance")
        finance["owns"].remove("movement_evidence_link")
        self.assertIn("DOM-OWNER-MISSING", self._codes(self.model, architecture))

    def test_financial_entity_without_lineage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._entity(mutated, "account_balance")["lineage_required"] = False
        self.assertIn("DOM-FINANCE-LINEAGE", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
