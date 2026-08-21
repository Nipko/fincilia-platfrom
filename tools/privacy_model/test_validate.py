"""Pruebas del validador del mapa de privacidad (FNC-PRV-001).

Las negativas mutan una copia profunda del modelo real del repositorio: si una
regla se debilita, la prueba correspondiente deja de fallar y el hueco se ve.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.privacy_model.validate import validate_model

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/privacy/privacy-map.json"
DFD_PATH = ROOT / "docs/architecture/dfd-flows.json"
THREAT_PATH = ROOT / "docs/security/threat-model.json"
VALIDATOR_PATH = ROOT / "tools/privacy_model/validate.py"


class PrivacyModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.dfd = json.loads(DFD_PATH.read_text(encoding="utf-8"))
        self.threats = json.loads(THREAT_PATH.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    # utilidades
    # ------------------------------------------------------------------ #

    def _codes(self, model: dict) -> set[str]:
        return {error.code for error in validate_model(model, self.dfd, self.threats, ROOT)}

    def _activity(self, model: dict, activity_id: str) -> dict:
        return next(a for a in model["processing_activities"] if a["id"] == activity_id)

    def _store(self, model: dict, store_id: str) -> dict:
        return next(s for s in model["stores"] if s["id"] == store_id)

    def _policy(self, model: dict, policy_id: str) -> dict:
        return next(p for p in model["retention_policies"] if p["id"] == policy_id)

    def _recipient(self, model: dict, recipient_id: str) -> dict:
        return next(r for r in model["recipient_registry"] if r["id"] == recipient_id)

    # ------------------------------------------------------------------ #
    # positivas
    # ------------------------------------------------------------------ #

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.dfd, self.threats, ROOT))

    def test_every_dfd_flow_is_covered(self) -> None:
        covered: set[str] = set()
        for activity in self.model["processing_activities"]:
            covered.update(activity["source_flows"])
        expected = {flow["id"] for flow in self.dfd["flows"]}
        self.assertEqual(expected, expected & covered)
        self.assertEqual(set(), covered - expected)

    def test_every_dfd_retention_policy_is_modelled(self) -> None:
        expected = {
            persistence["retention_policy_id"]
            for flow in self.dfd["flows"]
            for persistence in flow["persistence"]
        }
        modelled = {policy["id"] for policy in self.model["retention_policies"]}
        self.assertEqual(set(), expected - modelled)

    def test_every_dfd_store_is_modelled_and_referenced(self) -> None:
        modelled = {store["id"] for store in self.model["stores"]}
        referenced: set[str] = set()
        for activity in self.model["processing_activities"]:
            referenced.update(activity["stores"])
        expected = set(self.dfd["stores"])
        self.assertEqual(set(), expected - modelled)
        self.assertEqual(set(), expected - referenced)

    def test_declared_evidence_paths_exist(self) -> None:
        missing = []
        for activity in self.model["processing_activities"]:
            for item in activity.get("evidence", []):
                if not (ROOT / item["path"]).exists():
                    missing.append(item["path"])
        self.assertEqual([], missing)

    def test_validator_is_deterministic(self) -> None:
        first = validate_model(copy.deepcopy(self.model), self.dfd, self.threats, ROOT)
        second = validate_model(copy.deepcopy(self.model), self.dfd, self.threats, ROOT)
        self.assertEqual(first, second)

    def test_validator_does_not_depend_on_network_or_clock(self) -> None:
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        for forbidden in ("import time", "import datetime", "from datetime",
                          "import urllib", "import socket", "import requests",
                          "import random", "os.environ"):
            self.assertNotIn(forbidden, source,
                             f"the validator must stay deterministic: found {forbidden!r}")

    # ------------------------------------------------------------------ #
    # negativas: techos de fase
    # ------------------------------------------------------------------ #

    def test_external_ai_cannot_be_enabled_globally(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["external_ai_enabled"] = True
        self.assertIn("PRV-EXTERNAL-AI-GLOBAL", self._codes(mutated))

    def test_external_ai_cannot_be_enabled_per_activity(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-19")["external_ai"]["enabled"] = True
        self.assertIn("PRV-EXTERNAL-AI-ACTIVITY", self._codes(mutated))

    def test_region_cannot_be_marked_resolved(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["region_decision"] = "resolved_region_placeholder"
        self.assertIn("PRV-REGION-DECISION", self._codes(mutated))

    def test_activity_region_cannot_be_marked_resolved(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-03")["region_state"] = "resolved_region_placeholder"
        self.assertIn("PRV-REGION-DECISION", self._codes(mutated))

    def test_legal_validation_cannot_be_accepted(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["legal_validation"] = "accepted"
        self.assertIn("PRV-LEGAL-VALIDATION", self._codes(mutated))

    def test_legal_basis_cannot_be_accepted_per_activity(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-03")["legal_basis_state"] = "accepted"
        self.assertIn("PRV-LEGAL-BASIS", self._codes(mutated))

    def test_gate_cannot_be_marked_as_met(self) -> None:
        mutated = copy.deepcopy(self.model)
        next(g for g in mutated["gates"] if g["id"] == "DRG-00")["status"] = "met"
        self.assertIn("PRV-GATE-STATUS", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: cobertura
    # ------------------------------------------------------------------ #

    def test_missing_flow_coverage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-19")
        activity["source_flows"] = [f for f in activity["source_flows"] if f != "F08"]
        self.assertIn("PRV-FLOW-COVERAGE", self._codes(mutated))

    def test_missing_retention_policy_used_by_dfd_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_policies"] = [
            p for p in mutated["retention_policies"] if p["id"] != "L-01-CLOSE"
        ]
        self.assertIn("PRV-RETENTION-COVERAGE", self._codes(mutated))

    def test_missing_mandatory_privacy_risk_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        for activity in mutated["processing_activities"]:
            activity["threat_refs"] = [t for t in activity["threat_refs"] if t != "TM-010"]
        self.assertIn("PRV-RISK-COVERAGE", self._codes(mutated))

    def test_unknown_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-01")["threat_refs"].append("TM-999")
        self.assertIn("PRV-THREAT-REFERENCE", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: clasificación y alcance
    # ------------------------------------------------------------------ #

    def test_financial_activity_cannot_lose_company_scope(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-03")["company_scope"] = "not_applicable_until_resource_resolution"
        self.assertIn("PRV-FINANCIAL-SCOPE", self._codes(mutated))

    def test_prohibited_class_cannot_appear(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-04")["classifications"].append("prohibited")
        self.assertIn("PRV-PROHIBITED-CLASS", self._codes(mutated))

    def test_secret_cannot_be_persisted_in_business_stores(self) -> None:
        by_store = copy.deepcopy(self.model)
        self._store(by_store, "postgresql")["allowed_classifications"].append("secret")
        self.assertIn("PRV-SECRET-STORE", self._codes(by_store))

        by_activity = copy.deepcopy(self.model)
        self._activity(by_activity, "PA-01")["classifications"].append("secret")
        self.assertIn("PRV-SECRET-STORE", self._codes(by_activity))

        by_raw = copy.deepcopy(self.model)
        self._store(by_raw, "object_storage_raw")["allowed_classifications"].append("secret")
        self.assertIn("PRV-SECRET-STORE", self._codes(by_raw))

    # ------------------------------------------------------------------ #
    # negativas: destinatarios externos
    # ------------------------------------------------------------------ #

    def test_external_recipient_without_contract_state_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._recipient(mutated, "REC-IDP")["contract_state"] = ""
        self.assertIn("PRV-RECIPIENT-STATE", self._codes(mutated))

    def test_external_recipient_without_region_state_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._recipient(mutated, "REC-AI")["region_state"] = ""
        self.assertIn("PRV-RECIPIENT-STATE", self._codes(mutated))

    def test_external_recipient_cannot_be_pre_accepted(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._recipient(mutated, "REC-CLOUD")["role_state"] = "accepted"
        self.assertIn("PRV-RECIPIENT-STATE", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: retención
    # ------------------------------------------------------------------ #

    def test_invented_textual_duration_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._policy(mutated, "L-01-RAW")["expiry_trigger"] = "purge 90 days after acceptance"
        self.assertIn("PRV-RETENTION-DURATION", self._codes(mutated))

    def test_invented_numeric_duration_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._policy(mutated, "L-01-FINANCIAL")["retention_days"] = 3650
        self.assertIn("PRV-RETENTION-DURATION", self._codes(mutated))

    def test_duration_state_cannot_be_settled(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._policy(mutated, "L-01-AUDIT")["duration_state"] = "decided"
        self.assertIn("PRV-RETENTION-DURATION", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: borrado, ledger y restore
    # ------------------------------------------------------------------ #

    def test_delete_ledger_cannot_move_to_postgresql(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["ledger_store"] = "postgresql"
        self._policy(mutated, "L-01-DELETE-LEDGER")["stores"] = ["postgresql"]
        self.assertIn("PRV-DELETE-LEDGER-STORE", self._codes(mutated))

    def test_delete_ledger_cannot_enter_ordinary_restore(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["ledger_outside_ordinary_restore"] = False
        self.assertIn("PRV-DELETE-LEDGER-STORE", self._codes(mutated))

    def test_restore_cannot_reopen_before_tombstones(self) -> None:
        mutated = copy.deepcopy(self.model)
        machine = mutated["deletion_state_machine"]
        machine["restore_requires_tombstone_reapplication_before_service_reopen"] = False
        self.assertIn("PRV-RESTORE-TOMBSTONE", self._codes(mutated))

    def test_raw_cannot_be_overwritten_to_delete(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["raw_overwrite_to_delete"] = True
        self.assertIn("PRV-RESTORE-TOMBSTONE", self._codes(mutated))

    def test_requested_cannot_transition_directly_to_completed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["transitions"].append(
            {"from": "requested", "to": "completed"}
        )
        self.assertIn("PRV-DELETE-SHORTCUT", self._codes(mutated))

    def test_deletion_state_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        machine = mutated["deletion_state_machine"]
        machine["states"] = [s for s in machine["states"] if s != "backup_pending"]
        self.assertIn("PRV-DELETE-STATES", self._codes(mutated))

    def test_legal_hold_cannot_be_silent(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["legal_hold_silent_activation"] = True
        self.assertIn("PRV-LEGAL-HOLD", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: autoridad, logs y gobierno
    # ------------------------------------------------------------------ #

    def test_valkey_cannot_become_financial_authority(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._store(mutated, "valkey")["financial_authority"] = True
        self.assertIn("PRV-STORE-AUTHORITY", self._codes(mutated))

    def test_analytics_projection_cannot_declare_authority(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._store(mutated, "analytics_projection")["authority"] = "authoritative_operational"
        self.assertIn("PRV-STORE-AUTHORITY", self._codes(mutated))

    def test_log_allowlist_cannot_include_denied_fields(self) -> None:
        for field in ("amount", "token", "ocr_text"):
            mutated = copy.deepcopy(self.model)
            self._activity(mutated, "PA-01")["allowed_log_fields"].append(field)
            self.assertIn("PRV-LOG-DENYLIST", self._codes(mutated), f"field {field}")

    def test_owner_cannot_be_its_only_reviewer(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-01")
        activity["reviewer_roles"] = [activity["owner_role"]]
        self.assertIn("PRV-OWNER-INDEPENDENCE", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas: export, portafolio y soporte
    # ------------------------------------------------------------------ #

    def test_export_cannot_lose_authorization_version_binding(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-09")
        activity["minimization_controls"] = [
            c for c in activity["minimization_controls"] if c != "authorization_version_bound"
        ]
        self.assertIn("PRV-EXPORT-CONTROLS", self._codes(mutated))

    def test_portability_cannot_lose_manifest_and_hash(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-16")
        activity["minimization_controls"] = [
            c for c in activity["minimization_controls"] if c != "export_manifest_and_hash"
        ]
        self.assertIn("PRV-EXPORT-CONTROLS", self._codes(mutated))

    def test_portfolio_cannot_use_cache_as_candidate_source(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-21")
        activity["minimization_controls"] = [
            "consolidated_cache_candidate_source" if c == "authoritative_candidate_enumeration" else c
            for c in activity["minimization_controls"]
        ]
        self.assertIn("PRV-PORTFOLIO-CONTROLS", self._codes(mutated))

    def test_support_cannot_lose_jit_or_expiration(self) -> None:
        mutated = copy.deepcopy(self.model)
        activity = self._activity(mutated, "PA-13")
        activity["minimization_controls"] = [
            c for c in activity["minimization_controls"]
            if c not in {"just_in_time_grant_only", "time_bounded_expiration"}
        ]
        self.assertIn("PRV-SUPPORT-CONTROLS", self._codes(mutated))

    def test_missing_evidence_path_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-01")["evidence"].append(
            {"id": "EV-MISSING", "status": "planned", "path": "docs/privacy/does-not-exist.md"}
        )
        self.assertIn("PRV-EVIDENCE-PATH", self._codes(mutated))

    # ------------------------------------------------------------------ #
    # negativas añadidas por revisión de integración
    # ------------------------------------------------------------------ #

    def test_rights_workflow_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["rights_workflows"].pop()
        self.assertIn("PRV-CATALOG-COVERAGE", self._codes(mutated))

    def test_dpia_trigger_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dpia_triggers"].pop()
        self.assertIn("PRV-CATALOG-COVERAGE", self._codes(mutated))

    def test_catalog_duplicate_id_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_policies"].append(copy.deepcopy(mutated["retention_policies"][0]))
        self.assertIn("PRV-CATALOG-DUPLICATE", self._codes(mutated))

    def test_rights_legal_state_cannot_be_accepted(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["rights_workflows"][0]["sla_state"] = "accepted"
        self.assertIn("PRV-RIGHTS-PENDING", self._codes(mutated))

    def test_unknown_activity_classification_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-01")["classifications"].append("personal_unknown")
        self.assertIn("PRV-CLASSIFICATION-REFERENCE", self._codes(mutated))

    def test_activity_evidence_cannot_be_empty(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._activity(mutated, "PA-01")["evidence"] = []
        self.assertIn("PRV-ACTIVITY-COLLECTION", self._codes(mutated))

    def test_store_class_cannot_be_allowed_and_forbidden(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._store(mutated, "postgresql")["allowed_classifications"].append("secret")
        self.assertIn("PRV-STORE-CLASS-CONFLICT", self._codes(mutated))

    def test_delete_required_path_cannot_be_shortened(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["deletion_state_machine"]["completed_requires_path_through"].remove("backup_pending")
        self.assertIn("PRV-DELETE-REQUIRED-PATH", self._codes(mutated))

    def test_unreachable_deletion_state_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        machine = mutated["deletion_state_machine"]
        machine["transitions"] = [item for item in machine["transitions"] if item["to"] != "tombstoned"]
        self.assertIn("PRV-DELETE-REACHABILITY", self._codes(mutated))

    def test_retention_policy_requires_independent_reviewer(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_policies"][0]["reviewer_roles"] = []
        self.assertIn("PRV-REVIEWER-MISSING", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
