"""Pruebas de la estrategia de pruebas ejecutable (FNC-QA-002).

Las negativas mutan una copia profunda del modelo real: si una regla se debilita,
la prueba correspondiente deja de fallar y el hueco queda visible.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.quality_strategy.validate import (
    discover_test_ids,
    missing_sources,
    validate_model,
)

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/testing/test-strategy.json"
THREAT_PATH = ROOT / "docs/security/threat-model.json"
ARCHITECTURE_PATH = ROOT / "docs/architecture/module-boundaries.json"
VALIDATOR_PATH = ROOT / "tools/quality_strategy/validate.py"


class QualityStrategyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.threats = json.loads(THREAT_PATH.read_text(encoding="utf-8"))
        self.architecture = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))
        self.sources = self.model["id_policy"]["discovery_sources"]
        self.discovered = discover_test_ids(ROOT, self.sources)

    def _codes(self, model: dict, discovered: set[str] | None = None,
               absent: list[str] | None = None) -> set[str]:
        return {e.code for e in validate_model(
            model, self.threats, self.architecture,
            self.discovered if discovered is None else discovered, absent)}

    def _row(self, model: dict, risk_id: str) -> dict:
        return next(r for r in model["risk_control_matrix"] if r["risk_id"] == risk_id)

    def _layer(self, model: dict, layer_id: str) -> dict:
        return next(l for l in model["layers"] if l["id"] == layer_id)

    # ================================================================== #
    # Positivas
    # ================================================================== #

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.threats, self.architecture,
                                            self.discovered, []))

    def test_every_threat_model_risk_is_in_the_matrix(self) -> None:
        expected = {risk["id"] for risk in self.threats["risks"]}
        declared = {row["risk_id"] for row in self.model["risk_control_matrix"]}
        self.assertEqual(expected, declared)

    def test_test_ids_are_discovered_dynamically(self) -> None:
        self.assertGreater(len(self.discovered), 40)
        used = {t for row in self.model["risk_control_matrix"] for t in row["test_ids"]}
        self.assertLessEqual(used, self.discovered)
        self.assertFalse(self.model["id_policy"]["parallel_fixed_list_maintained"])

    def test_declared_discovery_sources_exist(self) -> None:
        self.assertEqual([], missing_sources(ROOT, self.sources))

    def test_validator_is_deterministic_and_offline(self) -> None:
        first = validate_model(copy.deepcopy(self.model), self.threats, self.architecture,
                               self.discovered, [])
        second = validate_model(copy.deepcopy(self.model), self.threats, self.architecture,
                                self.discovered, [])
        self.assertEqual(first, second)
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        for forbidden in ("import time", "import datetime", "from datetime", "import urllib",
                          "import socket", "import requests", "import random", "os.environ"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_every_gap_declares_owner_gate_and_reason(self) -> None:
        for row in self.model["risk_control_matrix"]:
            if row["coverage_state"] == "gap_declared":
                self.assertTrue(row.get("gap_owner_role"), row["risk_id"])
                self.assertTrue(row.get("gap_gate"), row["risk_id"])
                self.assertTrue(row.get("gap_reason"), row["risk_id"])
                self.assertTrue(row.get("blocks_gate"), row["risk_id"])

    # ================================================================== #
    # Negativas 1-20 del encargo
    # ================================================================== #

    def test_neg_01_critical_risk_without_case_or_evidence(self) -> None:
        without_tests = copy.deepcopy(self.model)
        self._row(without_tests, "TM-007")["test_ids"] = []
        self.assertIn("QS-RISK-UNCOVERED", self._codes(without_tests))

        without_evidence = copy.deepcopy(self.model)
        self._row(without_evidence, "TM-001")["evidence_ref"] = ""
        self.assertIn("QS-RISK-UNCOVERED", self._codes(without_evidence))

        dropped = copy.deepcopy(self.model)
        dropped["risk_control_matrix"] = [r for r in dropped["risk_control_matrix"]
                                          if r["risk_id"] != "TM-014"]
        self.assertIn("QS-RISK-UNCOVERED", self._codes(dropped))

        unowned_gap = copy.deepcopy(self.model)
        self._row(unowned_gap, "TM-005")["gap_owner_role"] = ""
        self.assertIn("QS-RISK-GAP-UNOWNED", self._codes(unowned_gap))

    def test_neg_02_required_id_removed_or_duplicated(self) -> None:
        unknown = copy.deepcopy(self.model)
        self._row(unknown, "TM-008")["test_ids"].append("TST-DOES-999")
        self.assertIn("QS-ID-UNKNOWN", self._codes(unknown))

        duplicated_row = copy.deepcopy(self.model)
        duplicated_row["risk_control_matrix"].append(
            copy.deepcopy(self._row(duplicated_row, "TM-001")))
        self.assertIn("QS-ID-DUPLICATE", self._codes(duplicated_row))

        duplicated_test = copy.deepcopy(self.model)
        row = self._row(duplicated_test, "TM-009")
        row["test_ids"] = row["test_ids"] + [row["test_ids"][0]]
        self.assertIn("QS-ID-DUPLICATE", self._codes(duplicated_test))

    def test_neg_03_fixed_list_contradicts_catalogue_or_contracts(self) -> None:
        parallel = copy.deepcopy(self.model)
        parallel["id_policy"]["parallel_fixed_list_maintained"] = True
        self.assertIn("QS-FIXED-LIST-DRIFT", self._codes(parallel))

        # Una fuente declarada que no existe también es drift.
        self.assertIn("QS-DISCOVERY-SOURCE",
                      self._codes(self.model, absent=["docs/testing/does-not-exist.json"]))

        # Si el universo descubrible encoge, los IDs usados dejan de resolver.
        shrunk = self.discovered - {"TST-LIN-003"}
        self.assertIn("QS-ID-UNKNOWN", self._codes(self.model, discovered=shrunk))

    def test_neg_04_unit_test_used_as_postgresql_isolation_proof(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["security_testing"]["layer"] = "unit"
        self.assertIn("QS-LAYER-MISMATCH", self._codes(mutated))

    def test_neg_05_mock_used_as_real_integration(self) -> None:
        for layer_id in ("integration", "security", "e2e"):
            mutated = copy.deepcopy(self.model)
            mutated["double_policy"]["allowed_layers"] = \
                sorted(set(mutated["double_policy"]["allowed_layers"]) | {layer_id})
            mutated["double_policy"]["forbidden_layers"] = [
                l for l in mutated["double_policy"]["forbidden_layers"] if l != layer_id]
            self.assertIn("QS-DOUBLE-AS-INTEGRATION", self._codes(mutated), layer_id)

        counted = copy.deepcopy(self.model)
        counted["double_policy"]["double_counted_as_integration"] = True
        self.assertIn("QS-DOUBLE-AS-INTEGRATION", self._codes(counted))

        security_doubles = copy.deepcopy(self.model)
        security_doubles["security_testing"]["doubles_allowed"] = True
        self.assertIn("QS-DOUBLE-AS-INTEGRATION", self._codes(security_doubles))

    def test_neg_05b_integration_layer_cannot_be_relabelled_to_admit_doubles(self) -> None:
        # Ruta de escape mas sutil: en vez de permitir dobles en integration,
        # se marca la capa integration como si admitiera dobles. La prohibicion
        # por nombre de capa debe seguir cerrando la puerta.
        mutated = copy.deepcopy(self.model)
        self._layer(mutated, "integration")["test_doubles_allowed"] = True
        mutated["double_policy"]["allowed_layers"] = \
            sorted(set(mutated["double_policy"]["allowed_layers"]) | {"integration"})
        mutated["double_policy"]["forbidden_layers"] = [
            l for l in mutated["double_policy"]["forbidden_layers"] if l != "integration"]
        self.assertIn("QS-DOUBLE-AS-INTEGRATION", self._codes(mutated))

    def test_neg_06_skip_or_quarantine_of_protected_domain(self) -> None:
        for field in ("protected_domain_skip_allowed", "protected_domain_quarantine_allowed",
                      "skip_allowed", "silent_skip_allowed", "known_failure_counts_as_pass"):
            mutated = copy.deepcopy(self.model)
            mutated["flake_policy"][field] = True
            self.assertIn("QS-PROTECTED-SKIP", self._codes(mutated), field)

        dropped = copy.deepcopy(self.model)
        dropped["flake_policy"]["protected_control_domains"] = [
            d for d in dropped["flake_policy"]["protected_control_domains"]
            if d != "money_and_decimal"]
        self.assertIn("QS-PROTECTED-SKIP", self._codes(dropped))

    def test_neg_07_retry_hides_flakiness(self) -> None:
        for field in ("retry_allowed", "retry_masks_flake"):
            mutated = copy.deepcopy(self.model)
            mutated["flake_policy"][field] = True
            self.assertIn("QS-RETRY-MASKS-FLAKE", self._codes(mutated), field)

    def test_neg_08_waiver_without_owner_reviewer_reason_expiry_or_gate(self) -> None:
        for field in ("waiver_id", "owner_role", "reviewer_role", "reason", "expiry_gate"):
            mutated = copy.deepcopy(self.model)
            mutated["flake_policy"]["waiver_required_fields"] = [
                f for f in mutated["flake_policy"]["waiver_required_fields"] if f != field]
            self.assertIn("QS-WAIVER-FIELDS", self._codes(mutated), field)

        self_approved = copy.deepcopy(self.model)
        self_approved["flake_policy"]["waiver_self_approval_allowed"] = True
        self.assertIn("QS-WAIVER-FIELDS", self._codes(self_approved))

    def test_neg_09_average_coverage_hides_a_failing_field(self) -> None:
        for field in ("average_hides_failure", "aggregate_percentage_as_gate"):
            mutated = copy.deepcopy(self.model)
            mutated["coverage_policy"][field] = True
            self.assertIn("QS-AVERAGE-COVERAGE", self._codes(mutated), field)

        for field in ("per_field_enumeration_required", "per_company_enumeration_required",
                      "per_format_enumeration_required",
                      "structural_coverage_is_not_correctness"):
            mutated = copy.deepcopy(self.model)
            mutated["coverage_policy"][field] = False
            self.assertIn("QS-AVERAGE-COVERAGE", self._codes(mutated), field)

    def test_neg_10_float_or_approximate_comparison_for_money(self) -> None:
        for field in ("float_allowed", "approximate_comparison_allowed"):
            mutated = copy.deepcopy(self.model)
            mutated["accounting_testing"][field] = True
            self.assertIn("QS-MONEY-FLOAT", self._codes(mutated), field)

        representation = copy.deepcopy(self.model)
        representation["accounting_testing"]["money_representation"] = "float64"
        self.assertIn("QS-MONEY-FLOAT", self._codes(representation))

        oracle = copy.deepcopy(self.model)
        next(o for o in oracle["oracle_types"] if o["id"] == "exact")["money_safe"] = False
        self.assertIn("QS-MONEY-FLOAT", self._codes(oracle))

    def test_neg_11_snapshot_updated_automatically(self) -> None:
        mutated = copy.deepcopy(self.model)
        next(o for o in mutated["oracle_types"]
             if o["id"] == "adjudicated_snapshot")["auto_update_allowed"] = True
        self.assertIn("QS-SNAPSHOT-AUTOUPDATE", self._codes(mutated))

        unadjudicated = copy.deepcopy(self.model)
        next(o for o in unadjudicated["oracle_types"]
             if o["id"] == "adjudicated_snapshot")["requires_adjudication"] = False
        self.assertIn("QS-SNAPSHOT-AUTOUPDATE", self._codes(unadjudicated))

    def test_neg_12_expected_output_approved_by_the_code_author(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["ownership"]["expected_output_adjudicator_equals_code_author_allowed"] = True
        self.assertIn("QS-ADJUDICATION-SOD", self._codes(mutated))

    def test_neg_13_evidence_without_command_version_hash_or_result(self) -> None:
        for field in ("command", "runtime_version", "input_digests", "result",
                      "data_classification"):
            mutated = copy.deepcopy(self.model)
            mutated["evidence_contract"]["required_fields"] = [
                f for f in mutated["evidence_contract"]["required_fields"] if f != field]
            self.assertIn("QS-EVIDENCE-FIELDS", self._codes(mutated), field)

        leaking = copy.deepcopy(self.model)
        leaking["evidence_contract"]["payload_included"] = True
        self.assertIn("QS-EVIDENCE-FIELDS", self._codes(leaking))

        secrets = copy.deepcopy(self.model)
        secrets["evidence_contract"]["secrets_included"] = True
        self.assertIn("QS-EVIDENCE-FIELDS", self._codes(secrets))

    def test_neg_14_real_derived_or_uninventoried_fixture(self) -> None:
        for field, value in (("real_or_derived_allowed", True),
                             ("provenance_required", False),
                             ("manifest_required", False)):
            mutated = copy.deepcopy(self.model)
            mutated["data_and_fixture_policy"][field] = value
            self.assertIn("QS-FIXTURE-PROVENANCE", self._codes(mutated), field)

        classification = copy.deepcopy(self.model)
        classification["evidence_contract"]["data_classification_values"] = \
            ["synthetic_only", "real_derived"]
        self.assertIn("QS-FIXTURE-PROVENANCE", self._codes(classification))

    def test_neg_15_test_with_network_or_uncontrolled_clock(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["test_case_contract"]["network_access_allowed"] = True
        self.assertIn("QS-NETWORK-OR-CLOCK", self._codes(mutated))

        dropped = copy.deepcopy(self.model)
        dropped["test_case_contract"]["required_fields"] = [
            f for f in dropped["test_case_contract"]["required_fields"]
            if f != "deterministic"]
        self.assertIn("QS-CASE-FIELDS", self._codes(dropped))

    def test_neg_16_invented_or_accepted_performance_threshold(self) -> None:
        for field in ("thresholds_declared", "invented_threshold_allowed"):
            mutated = copy.deepcopy(self.model)
            mutated["performance_slo"][field] = True
            self.assertIn("QS-PERF-THRESHOLD", self._codes(mutated), field)

        accepted = copy.deepcopy(self.model)
        accepted["performance_slo"]["budget_state"] = "accepted"
        self.assertIn("QS-PERF-THRESHOLD", self._codes(accepted))

        unmeasured = copy.deepcopy(self.model)
        unmeasured["performance_slo"]["measurement_required_before_threshold"] = False
        self.assertIn("QS-PERF-THRESHOLD", self._codes(unmeasured))

    def test_neg_17_ai_evaluated_only_by_valid_json(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["ai_testing"]["json_validity_is_sufficient_oracle"] = True
        self.assertIn("QS-AI-SEMANTIC-ORACLE", self._codes(mutated))

        for oracle in ("semantic_field_accuracy", "abstention_rate",
                       "adversarial_prompt_injection", "redaction_recall"):
            dropped = copy.deepcopy(self.model)
            dropped["ai_testing"]["required_oracles"] = [
                o for o in dropped["ai_testing"]["required_oracles"] if o != oracle]
            self.assertIn("QS-AI-SEMANTIC-ORACLE", self._codes(dropped), oracle)

    def test_neg_18_model_without_abstention_redaction_or_fallback(self) -> None:
        for field in ("abstention_required", "redaction_fail_closed_required",
                      "fallback_required", "adjudicated_dataset_required",
                      "drift_monitoring_required"):
            mutated = copy.deepcopy(self.model)
            mutated["ai_testing"][field] = False
            self.assertIn("QS-AI-SAFETY", self._codes(mutated), field)

        authority = copy.deepcopy(self.model)
        authority["ai_testing"]["model_has_financial_authority"] = True
        self.assertIn("QS-AI-SAFETY", self._codes(authority))

        enabled = copy.deepcopy(self.model)
        enabled["ai_testing"]["external_ai_enabled"] = True
        self.assertIn("QS-AI-SAFETY", self._codes(enabled))

    def test_neg_19_accessibility_declared_by_component_existence(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["accessibility_testing"]["component_existence_counts_as_evidence"] = True
        self.assertIn("QS-A11Y-EVIDENCE", self._codes(mutated))

        claimed = copy.deepcopy(self.model)
        claimed["accessibility_testing"]["human_testing_claimed"] = True
        self.assertIn("QS-A11Y-EVIDENCE", self._codes(claimed))

        settled = copy.deepcopy(self.model)
        settled["accessibility_testing"]["human_testing_state"] = "done"
        self.assertIn("QS-A11Y-EVIDENCE", self._codes(settled))

    def test_neg_20_gate_marked_met_or_human_decision_closed(self) -> None:
        gate = copy.deepcopy(self.model)
        next(g for g in gate["gates"] if g["id"] == "S1-READY")["status"] = "met"
        self.assertIn("QS-GATE-STATUS", self._codes(gate))

        acceptance = copy.deepcopy(self.model)
        next(g for g in acceptance["gates"] if g["id"] == "DRG-00")["acceptance"] = "accepted"
        self.assertIn("QS-GATE-STATUS", self._codes(acceptance))

        decision = copy.deepcopy(self.model)
        decision["unresolved_decisions"][0]["state"] = "resolved"
        self.assertIn("QS-DECISION-STATE", self._codes(decision))

        residual = copy.deepcopy(self.model)
        self._row(residual, "TM-011")["acceptance"] = "accepted"
        self.assertIn("QS-RISK-ACCEPTANCE", self._codes(residual))

        human = copy.deepcopy(self.model)
        human["human_acceptance"] = "accepted"
        self.assertIn("QS-HUMAN-ACCEPTANCE", self._codes(human))

    # ================================================================== #
    # Refuerzos adicionales
    # ================================================================== #

    def test_layer_must_declare_what_it_cannot_prove(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._layer(mutated, "unit")["cannot_prove"] = ""
        self.assertIn("QS-LAYER-SCOPE", self._codes(mutated))

    def test_missing_layer_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["layers"] = [l for l in mutated["layers"] if l["id"] != "golden"]
        self.assertIn("QS-LAYER-COVERAGE", self._codes(mutated))

    def test_severity_drift_against_threat_model_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._row(mutated, "TM-001")["risk_severity"] = "low"
        self.assertIn("QS-RISK-SEVERITY", self._codes(mutated))

    def test_unknown_risk_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        row = copy.deepcopy(self._row(mutated, "TM-001"))
        row["risk_id"] = "TM-999"
        mutated["risk_control_matrix"].append(row)
        self.assertIn("QS-RISK-REFERENCE", self._codes(mutated))

    def test_lane_cannot_depend_on_a_later_lane(self) -> None:
        mutated = copy.deepcopy(self.model)
        lane = next(l for l in mutated["ci_lanes"] if l["id"] == "lane_static")
        lane["depends_on"] = ["lane_security"]
        self.assertIn("QS-LANE-ORDER", self._codes(mutated))

    def test_unknown_lane_dependency_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        next(l for l in mutated["ci_lanes"] if l["id"] == "lane_golden")["depends_on"] = ["lane_ghost"]
        self.assertIn("QS-LANE-REFERENCE", self._codes(mutated))

    def test_mutation_policy_cannot_be_disabled(self) -> None:
        for field, value in (("required", False),
                             ("surviving_mutant_effect", "informational"),
                             ("minimum_mutants_per_validator", 0)):
            mutated = copy.deepcopy(self.model)
            mutated["mutation_policy"][field] = value
            self.assertIn("QS-MUTATION", self._codes(mutated), field)

    def test_security_scenario_cannot_be_dropped(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["security_testing"]["required_scenarios"] = [
            s for s in mutated["security_testing"]["required_scenarios"] if s != "cross_company"]
        self.assertIn("QS-SECURITY-SCENARIOS", self._codes(mutated))

    def test_accounting_invariants_cannot_be_relaxed(self) -> None:
        for field in ("unknown_or_partial_blocks_close", "segregation_of_duties_required"):
            mutated = copy.deepcopy(self.model)
            mutated["accounting_testing"][field] = False
            self.assertIn("QS-ACCOUNTING", self._codes(mutated), field)

        dates = copy.deepcopy(self.model)
        dates["accounting_testing"]["semantic_dates_distinct"] = ["posted", "value"]
        self.assertIn("QS-ACCOUNTING", self._codes(dates))

    def test_owner_cannot_be_its_own_reviewer(self) -> None:
        row = copy.deepcopy(self.model)
        target = self._row(row, "TM-013")
        target["reviewer_roles"] = [target["owner_role"]]
        self.assertIn("QS-OWNER-INDEPENDENCE", self._codes(row))

        ownership = copy.deepcopy(self.model)
        ownership["ownership"]["author_is_sole_reviewer_allowed"] = True
        self.assertIn("QS-OWNER-INDEPENDENCE", self._codes(ownership))

    def test_unknown_module_in_pyramid_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["pyramid_by_module"].append({"module": "ghost_module", "boundary": "none"})
        self.assertIn("QS-MODULE-REFERENCE", self._codes(mutated))

    def test_required_gate_cannot_be_dropped(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["gates"] = [g for g in mutated["gates"] if g["id"] != "DRG-01"]
        self.assertIn("QS-GATE-COVERAGE", self._codes(mutated))

    def test_unknown_coverage_state_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._row(mutated, "TM-003")["coverage_state"] = "probably_fine"
        self.assertIn("QS-COVERAGE-STATE", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
