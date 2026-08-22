from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tools.connector_model.validate import validate_model

ROOT = Path(__file__).resolve().parents[2]


def _load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class ConnectorModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = _load("docs/contracts/connectors/connector-contract.json")
        cls.schema = _load("docs/contracts/connectors/connector-manifest.schema.json")
        cls.completeness = _load("docs/domain/completeness-balances.json")
        cls.idempotency = _load("docs/domain/idempotency-dedupe.json")
        cls.events = _load("docs/architecture/events-retries.json")
        cls.privacy = _load("docs/privacy/privacy-map.json")

    def _codes(self, model=None, schema=None, completeness=None, idempotency=None, events=None, privacy=None) -> set[str]:
        return {error.code for error in validate_model(
            model if model is not None else self.model,
            schema if schema is not None else self.schema,
            completeness if completeness is not None else self.completeness,
            idempotency if idempotency is not None else self.idempotency,
            events if events is not None else self.events,
            privacy if privacy is not None else self.privacy,
        )}

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual(set(), self._codes())

    def test_connector_must_remain_read_only(self) -> None:
        model = copy.deepcopy(self.model); model["mode"] = "read_write"
        self.assertIn("CON-SCOPE", self._codes(model=model))

    def test_platform_cannot_receive_credentials(self) -> None:
        model = copy.deepcopy(self.model); model["platform_receives_bank_credentials"] = True
        self.assertIn("CON-CREDENTIALS", self._codes(model=model))

    def test_region_must_be_required_by_manifest(self) -> None:
        schema = copy.deepcopy(self.schema); schema["required"].remove("region")
        self.assertIn("CON-MANIFEST-SECTIONS", self._codes(schema=schema))

    def test_manifest_rejects_unknown_fields(self) -> None:
        schema = copy.deepcopy(self.schema); schema["additionalProperties"] = True
        self.assertIn("CON-MANIFEST-CLOSED", self._codes(schema=schema))

    def test_unknown_capability_is_not_supported(self) -> None:
        model = copy.deepcopy(self.model); model["capability_contract"]["unknown_is_not_supported"] = False
        self.assertIn("CON-CAPABILITY-UNKNOWN", self._codes(model=model))

    def test_write_capability_defaults_forbidden(self) -> None:
        model = copy.deepcopy(self.model); model["capability_contract"]["write_capabilities_default"] = "allowed"
        self.assertIn("CON-WRITE", self._codes(model=model))

    def test_bank_password_cannot_be_removed_from_denylist(self) -> None:
        model = copy.deepcopy(self.model); model["authorization_contract"]["forbidden_inputs"].remove("bank_password")
        self.assertIn("CON-AUTH-FORBIDDEN", self._codes(model=model))

    def test_secret_must_be_vault_reference(self) -> None:
        model = copy.deepcopy(self.model); model["authorization_contract"]["secret_storage"] = "database_ciphertext"
        self.assertIn("CON-SECRET-STORAGE", self._codes(model=model))

    def test_revocation_cannot_be_disabled(self) -> None:
        model = copy.deepcopy(self.model); model["authorization_contract"]["revocation_supported"] = False
        self.assertIn("CON-AUTH", self._codes(model=model))

    def test_cursor_scope_requires_company_and_account(self) -> None:
        model = copy.deepcopy(self.model); model["sync_contract"]["cursor_scope"].remove("company_id")
        self.assertIn("CON-CURSOR-SCOPE", self._codes(model=model))

    def test_empty_page_is_not_completeness(self) -> None:
        model = copy.deepcopy(self.model); model["sync_contract"]["empty_page_means_complete"] = True
        self.assertIn("CON-EMPTY-PAGE", self._codes(model=model))

    def test_pending_cannot_alias_posted(self) -> None:
        model = copy.deepcopy(self.model); model["sync_contract"]["pending_never_aliases_posted"] = False
        self.assertIn("CON-SYNC", self._codes(model=model))

    def test_provider_identity_starts_unverified(self) -> None:
        model = copy.deepcopy(self.model); model["identity_contract"]["default_assurance"] = "verified"
        self.assertIn("CON-IDENTITY", self._codes(model=model))

    def test_cross_source_similarity_is_candidate_only(self) -> None:
        model = copy.deepcopy(self.model); model["identity_contract"]["cross_source_dedupe_candidate_only"] = False
        self.assertIn("CON-DEDUPE", self._codes(model=model))

    def test_completeness_requires_closing_balance(self) -> None:
        model = copy.deepcopy(self.model); model["completeness_contract"]["required_controls"].remove("closing_balance")
        self.assertIn("CON-COMPLETENESS-CONTROLS", self._codes(model=model))

    def test_missing_control_becomes_unknown(self) -> None:
        model = copy.deepcopy(self.model); model["completeness_contract"]["unavailable_required_control"] = "match"
        self.assertIn("CON-COMPLETENESS-UNKNOWN", self._codes(model=model))

    def test_pagination_alone_is_not_proof(self) -> None:
        model = copy.deepcopy(self.model); model["completeness_contract"]["pagination_exhaustion_alone_is_proof"] = True
        self.assertIn("CON-COMPLETENESS-PROOF", self._codes(model=model))

    def test_adapter_cannot_retry(self) -> None:
        model = copy.deepcopy(self.model); model["retry_contract"]["adapter_retries"] = True
        self.assertIn("CON-RETRY-OWNER", self._codes(model=model))

    def test_unknown_outcome_reconciles_before_retry(self) -> None:
        model = copy.deepcopy(self.model); model["retry_contract"]["unknown_outcome"] = "retry"
        self.assertIn("CON-RETRY-SAFETY", self._codes(model=model))

    def test_signature_occurs_before_inbox(self) -> None:
        model = copy.deepcopy(self.model); model["webhook_contract"]["signature_before_inbox"] = False
        self.assertIn("CON-WEBHOOK", self._codes(model=model))

    def test_same_webhook_id_different_payload_suspends(self) -> None:
        model = copy.deepcopy(self.model); model["webhook_contract"]["same_id_different_payload"] = "ack"
        self.assertIn("CON-WEBHOOK-CONFLICT", self._codes(model=model))

    def test_file_fallback_is_permanent(self) -> None:
        model = copy.deepcopy(self.model); model["fallback_contract"]["permanent_not_temporary"] = False
        self.assertIn("CON-FALLBACK", self._codes(model=model))

    def test_feed_failure_cannot_block_file(self) -> None:
        model = copy.deepcopy(self.model); model["fallback_contract"]["feed_failure_does_not_block_file"] = False
        self.assertIn("CON-FALLBACK", self._codes(model=model))

    def test_degraded_feed_never_assumes_zero(self) -> None:
        model = copy.deepcopy(self.model); model["degraded_contract"]["never_assume_zero_or_complete"] = False
        self.assertIn("CON-DEGRADED", self._codes(model=model))

    def test_schema_drift_blocks_publication(self) -> None:
        model = copy.deepcopy(self.model); model["degraded_contract"]["schema_drift_blocks_publication"] = False
        self.assertIn("CON-DEGRADED", self._codes(model=model))

    def test_ssrf_control_cannot_be_disabled(self) -> None:
        model = copy.deepcopy(self.model); model["security_contract"]["ssrf_private_ranges_and_redirects_blocked"] = False
        self.assertIn("CON-SECURITY", self._codes(model=model))

    def test_worker_cannot_access_internet_directly(self) -> None:
        model = copy.deepcopy(self.model); model["security_contract"]["worker_direct_internet_forbidden"] = False
        self.assertIn("CON-SECURITY", self._codes(model=model))

    def test_region_decision_remains_pending(self) -> None:
        model = copy.deepcopy(self.model); model["legal_cost_contract"]["region_state"] = "accepted"
        self.assertIn("CON-LEGAL-PENDING", self._codes(model=model))

    def test_production_requires_legal_and_cost_approval(self) -> None:
        model = copy.deepcopy(self.model); model["legal_cost_contract"]["no_production_before_approval"] = False
        self.assertIn("CON-COST-PENDING", self._codes(model=model))

    def test_gate_cannot_be_accepted_by_agent(self) -> None:
        model = copy.deepcopy(self.model); model["certification_gates"][0]["state"] = "accepted"
        self.assertIn("CON-GATE-PENDING", self._codes(model=model))

    def test_gate_owner_and_reviewer_are_independent(self) -> None:
        model = copy.deepcopy(self.model); model["certification_gates"][0]["reviewer"] = model["certification_gates"][0]["owner"]
        self.assertIn("CON-GATE-PENDING", self._codes(model=model))

    def test_required_connector_test_cannot_be_removed(self) -> None:
        model = copy.deepcopy(self.model); model["required_tests"].pop()
        self.assertIn("CON-TESTS", self._codes(model=model))

    def test_dom004_provider_default_alignment(self) -> None:
        idem = copy.deepcopy(self.idempotency); idem["provider_identity_contract"]["default_state"] = "verified"
        self.assertIn("CON-DOM004", self._codes(idempotency=idem))

    def test_arc004_adapter_retry_alignment(self) -> None:
        events = copy.deepcopy(self.events); events["retry_policy_contract"]["adapter_schedules_retry"] = True
        self.assertIn("CON-ARC004", self._codes(events=events))


if __name__ == "__main__":
    unittest.main()
