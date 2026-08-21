from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.dfd_model.validate import validate_model

MODEL_PATH = Path(__file__).parents[2] / "docs/architecture/dfd-flows.json"


class DfdModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def _codes(self, model: dict) -> set[str]:
        return {error.code for error in validate_model(model)}

    def _flow(self, model: dict, flow_id: str) -> dict:
        return next(flow for flow in model["flows"] if flow["id"] == flow_id)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model))

    def test_missing_zone_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["trust_zones"].pop()
        self.assertIn("DFD-ZONES", self._codes(mutated))

    def test_prohibited_data_in_flow_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F02")["data_classes"].append("prohibited")
        self.assertIn("DFD-PROHIBITED-DATA", self._codes(mutated))

    def test_financial_flow_without_verified_company_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F02")["company_scope"] = "not_applicable_until_resource_resolution"
        self.assertIn("DFD-FINANCIAL-SCOPE", self._codes(mutated))

    def test_sensitive_field_in_log_allowlist_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F06")["allowed_log_fields"].append("amount")
        self.assertIn("DFD-LOG-FIELD-FORBIDDEN", self._codes(mutated))

    def test_ai_egress_cannot_bypass_z5(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F08")["path"].remove("Z5")
        self.assertIn("DFD-EGRESS-ZONE", self._codes(mutated))

    def test_ai_cannot_receive_financial_sensitive_class(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F08")["data_classes"].append("financial_sensitive")
        self.assertIn("DFD-AI-CLASS", self._codes(mutated))

    def test_worker_cannot_gain_egress(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F04")["egress"] = {"mode": "approved_gateway", "gateway": "direct"}
        self.assertIn("DFD-WORKER-EGRESS", self._codes(mutated))

    def test_worker_cannot_publish_canonical_state(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F04")["authoritative_effect"] = "canonical_write"
        self.assertIn("DFD-WORKER-AUTHORITY", self._codes(mutated))

    def test_delete_ledger_cannot_move_into_ordinary_store(self) -> None:
        mutated = copy.deepcopy(self.model)
        flow = self._flow(mutated, "F11")
        flow["persistence"] = [item for item in flow["persistence"] if item["store"] != "security_archive"]
        self.assertIn("DFD-DELETE-LEDGER", self._codes(mutated))

    def test_restore_must_fail_closed(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F12")["degraded_mode"] = "serve_restored_state_immediately"
        self.assertIn("DFD-RESTORE-FAIL-CLOSED", self._codes(mutated))

    def test_revocation_requires_authorization_version(self) -> None:
        mutated = copy.deepcopy(self.model)
        flow = self._flow(mutated, "F13")
        flow["persistence"][0]["form"] = "engagement_and_grant"
        self.assertIn("DFD-REVOCATION-VERSION", self._codes(mutated))

    def test_unknown_control_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._flow(mutated, "F01")["controls"].append("C-UNKNOWN")
        self.assertIn("DFD-FLOW-REFERENCE", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
