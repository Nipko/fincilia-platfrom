from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tools.idempotency_model.validate import validate_model


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class IdempotencyModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = _load("docs/domain/idempotency-dedupe.json")
        cls.canonical = _load("docs/domain/canonical-model.json")
        cls.architecture = _load("docs/architecture/module-boundaries.json")
        cls.dfd = _load("docs/architecture/dfd-flows.json")

    def _codes(
        self,
        model: dict[str, Any] | None = None,
        canonical: dict[str, Any] | None = None,
        architecture: dict[str, Any] | None = None,
        dfd: dict[str, Any] | None = None,
    ) -> set[str]:
        return {
            item.code
            for item in validate_model(
                model or self.model,
                canonical or self.canonical,
                architecture or self.architecture,
                dfd or self.dfd,
            )
        }

    @staticmethod
    def _item(model: dict[str, Any], catalog: str, identifier: str) -> dict[str, Any]:
        return next(item for item in model[catalog] if item["id"] == identifier)

    @staticmethod
    def _entity(canonical: dict[str, Any], identifier: str) -> dict[str, Any]:
        return next(item for item in canonical["entities"] if item["id"] == identifier)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.canonical, self.architecture, self.dfd))

    def test_productive_merge_cannot_be_enabled(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["execution_mode"] = "productive_merge"
        self.assertIn("IDM-EXECUTION", self._codes(model=mutated))

    def test_identity_layer_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["identity_layers"].pop()
        self.assertIn("IDM-LAYERS", self._codes(model=mutated))

    def test_economic_event_cannot_gain_hard_identity(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "identity_layers", "economic_event")["hard_identity_allowed"] = True
        self.assertIn("IDM-ECONOMIC-HARD-ID", self._codes(model=mutated))

    def test_source_observation_requires_verified_contract(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "identity_layers", "source_observation")["hard_identity_allowed"] = True
        self.assertIn("IDM-SOURCE-ASSURANCE", self._codes(model=mutated))

    def test_artifact_key_requires_company_and_source(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-ARTIFACT-EXACT")["scope_fields"] = ["company_id"]
        self.assertIn("IDM-ARTIFACT-KEY", self._codes(model=mutated))

    def test_provider_key_cannot_store_raw_identifier(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-PROVIDER-EVENT")["identity_material"] = ["provider_event_id_raw"]
        self.assertIn("IDM-PROVIDER-KEY", self._codes(model=mutated))

    def test_provider_receipt_requires_payload_digest(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-PROVIDER-EVENT")["payload_digest"] = None
        self.assertIn("IDM-PROVIDER-DIGEST", self._codes(model=mutated))

    def test_same_key_different_payload_cannot_return_success(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-COMMAND")["same_key_different_payload"] = "return_success"
        self.assertIn("IDM-PAYLOAD-CONFLICT", self._codes(model=mutated))

    def test_processing_key_requires_engine_release(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-PROCESSING")["identity_material"].remove("engine_release_id")
        self.assertIn("IDM-PROCESSING-VERSION", self._codes(model=mutated))

    def test_publication_requires_atomic_outbox(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "hard_idempotency_rules", "IDEM-PUBLICATION")["atomic_mechanism"] = "eventual_outbox"
        self.assertIn("IDM-PUBLICATION-OUTBOX", self._codes(model=mutated))

    def test_provider_default_cannot_be_verified(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["provider_identity_contract"]["default_state"] = "verified"
        self.assertIn("IDM-PROVIDER-DEFAULT", self._codes(model=mutated))

    def test_provider_verification_evidence_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["provider_identity_contract"]["verified_requires"].pop()
        self.assertIn("IDM-PROVIDER-EVIDENCE", self._codes(model=mutated))

    def test_identifier_reuse_must_suspend_provider_contract(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["provider_identity_contract"]["suspended_on"].remove("identifier_reuse")
        self.assertIn("IDM-PROVIDER-SUSPEND", self._codes(model=mutated))

    def test_candidate_fingerprint_cannot_be_unique(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "candidate_rules", "CAND-MOVEMENT-SIMILARITY")["unique_constraint_forbidden"] = False
        self.assertIn("IDM-CANDIDATE-UNIQUE", self._codes(model=mutated))

    def test_candidate_cannot_have_automatic_effect(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "candidate_rules", "CAND-SOURCE-OVERLAP")["automatic_effect"] = "merge"
        self.assertIn("IDM-CANDIDATE-AUTO", self._codes(model=mutated))

    def test_business_composite_must_remain_forbidden(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "forbidden_hard_uniqueness", "NO-BUSINESS-COMPOSITE")["fields"].remove("reference")
        self.assertIn("IDM-BUSINESS-COMPOSITE", self._codes(model=mutated))

    def test_candidate_hash_cannot_be_called_anonymous(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["fingerprint_policy"]["hash_or_hmac_is_not_anonymization"] = False
        self.assertIn("IDM-FINGERPRINT-PRIVACY", self._codes(model=mutated))

    def test_application_precheck_cannot_be_authoritative(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["inbox_state_machine"]["application_precheck_is_authority"] = True
        self.assertIn("IDM-INBOX-PRECHECK", self._codes(model=mutated))

    def test_fencing_token_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["inbox_state_machine"]["lease_requires_fencing_token"] = False
        self.assertIn("IDM-INBOX-RETRY", self._codes(model=mutated))

    def test_dedupe_decision_requires_evidence(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dedupe_decision_contract"]["required_fields"].remove("evidence_refs")
        self.assertIn("IDM-DEDUPE-FIELDS", self._codes(model=mutated))

    def test_dedupe_history_cannot_be_overwritten(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dedupe_decision_contract"]["decision_history"] = "mutable_latest_only"
        self.assertIn("IDM-DEDUPE-HISTORY", self._codes(model=mutated))

    def test_dedupe_cannot_delete_source_evidence(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dedupe_decision_contract"]["source_evidence_deleted"] = True
        self.assertIn("IDM-DEDUPE-DESTRUCTIVE", self._codes(model=mutated))

    def test_auto_dedupe_cannot_be_enabled(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dedupe_decision_contract"]["automatic_same_event_decision_enabled"] = True
        self.assertIn("IDM-DEDUPE-DESTRUCTIVE", self._codes(model=mutated))

    def test_valkey_lock_cannot_become_correctness_primitive(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["concurrency_contract"]["correctness_primitives"].append("valkey_lock")
        self.assertIn("IDM-CONCURRENCY-PRIMITIVES", self._codes(model=mutated))

    def test_connector_cannot_own_retry_schedule(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["concurrency_contract"]["connector_schedules_retries"] = True
        self.assertIn("IDM-RETRY-OWNER", self._codes(model=mutated))

    def test_outbox_cannot_commit_after_domain_change(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["concurrency_contract"]["outbox_same_transaction_as_domain_change"] = False
        self.assertIn("IDM-OUTBOX", self._codes(model=mutated))

    def test_company_scope_cannot_come_from_client(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["security_contract"]["company_scope_source"] = "request_body_company_id"
        self.assertIn("IDM-COMPANY-SCOPE", self._codes(model=mutated))

    def test_raw_identifiers_cannot_be_logged(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["security_contract"]["raw_identifier_log_forbidden"] = False
        self.assertIn("IDM-SECURITY", self._codes(model=mutated))

    def test_money_movement_cannot_gain_business_unique_constraint(self) -> None:
        canonical = copy.deepcopy(self.canonical)
        self._entity(canonical, "money_movement")["unique_constraints"].append({
            "id": "uq_bad_business_key",
            "fields": ["company_id", "financial_account_id", "posting_date", "amount", "direction", "reference"],
            "kind": "hard_idempotency",
        })
        self.assertIn("IDM-CANONICAL-MOVEMENT-UNIQUE", self._codes(canonical=canonical))

    def test_canonical_fingerprint_cannot_be_unique_identity(self) -> None:
        canonical = copy.deepcopy(self.canonical)
        movement = self._entity(canonical, "money_movement")
        next(field for field in movement["fields"] if field["name"] == "dedupe_fingerprint")["value_rule"] = "hard_identity"
        self.assertIn("IDM-CANONICAL-FINGERPRINT", self._codes(canonical=canonical))

    def test_dfd_must_keep_duplicate_effect_threat(self) -> None:
        dfd = copy.deepcopy(self.dfd)
        dfd["threat_catalog"] = [item for item in dfd["threat_catalog"] if item["id"] != "T12"]
        self.assertIn("IDM-DFD-COVERAGE", self._codes(dfd=dfd))

    def test_required_concurrency_scenario_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["required_tests"] = [item for item in mutated["required_tests"] if item["id"] != "TST-IDEM-001"]
        self.assertIn("IDM-TEST-COVERAGE", self._codes(model=mutated))


if __name__ == "__main__":
    unittest.main()
