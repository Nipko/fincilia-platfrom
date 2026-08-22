"""Pruebas del contrato de linaje (FNC-DOM-005).

Tres bloques:

1. positivas sobre el modelo real del repositorio;
2. funciones puras: grafo sintético, cadena de overlays y reproduction key;
3. mutaciones sobre copia profunda que demuestran que el validador muerde.

Todos los identificadores son inequívocamente sintéticos.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.lineage_model.validate import (
    apply_overlay_chain,
    canonical_json,
    reproduction_key,
    validate_graph,
    validate_model,
)

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/domain/lineage-model.json"
CANONICAL_PATH = ROOT / "docs/domain/canonical-model.json"
ARCHITECTURE_PATH = ROOT / "docs/architecture/module-boundaries.json"
IDEMPOTENCY_PATH = ROOT / "docs/domain/idempotency-dedupe.json"
PRIVACY_PATH = ROOT / "docs/privacy/privacy-map.json"
DFD_PATH = ROOT / "docs/architecture/dfd-flows.json"
THREAT_PATH = ROOT / "docs/security/threat-model.json"
VALIDATOR_PATH = ROOT / "tools/lineage_model/validate.py"

C1 = "company_c1"
C2 = "company_c2"


def digest_of(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def synthetic_graph() -> dict:
    """Grafo mínimo completo: evidencia → registro → hecho → decisión → cierre."""
    nodes = [
        {"id": "node_artifact_v1", "type": "artifact_version", "company_id": C1},
        {"id": "node_locator_v1", "type": "raw_locator", "company_id": C1},
        {"id": "node_extracted_v1", "type": "extracted_field", "company_id": C1},
        {"id": "node_transformed_v1", "type": "transformed_value", "company_id": C1},
        {"id": "node_source_record_v1", "type": "source_record_field", "company_id": C1},
        {"id": "node_fact_v1", "type": "financial_fact_field", "company_id": C1},
        {"id": "node_decision_v1", "type": "decision", "company_id": C1},
        {"id": "node_report_v1", "type": "report_field", "company_id": C1},
        {"id": "node_close_v1", "type": "close_snapshot_field", "company_id": C1},
    ]
    chain = [
        ("node_artifact_v1", "node_locator_v1", "derived_from"),
        ("node_locator_v1", "node_extracted_v1", "derived_from"),
        ("node_extracted_v1", "node_transformed_v1", "derived_from"),
        ("node_transformed_v1", "node_source_record_v1", "derived_from"),
        ("node_source_record_v1", "node_fact_v1", "derived_from"),
        ("node_fact_v1", "node_decision_v1", "decided_using"),
        ("node_fact_v1", "node_report_v1", "derived_from"),
        ("node_decision_v1", "node_close_v1", "included_in_snapshot"),
    ]
    edges = [
        {"edge_id": f"edge_synthetic_{index:02d}", "company_id": C1,
         "from_node_id": source, "to_node_id": target, "operation": operation}
        for index, (source, target, operation) in enumerate(chain, start=1)
    ]
    return {"nodes": nodes, "edges": edges}


class LineageModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
        self.architecture = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))
        self.idempotency = json.loads(IDEMPOTENCY_PATH.read_text(encoding="utf-8"))
        self.privacy = json.loads(PRIVACY_PATH.read_text(encoding="utf-8"))
        self.dfd = json.loads(DFD_PATH.read_text(encoding="utf-8"))
        self.threats = json.loads(THREAT_PATH.read_text(encoding="utf-8"))

    def _codes(self, model: dict) -> set[str]:
        return {e.code for e in validate_model(
            model, self.canonical, self.architecture, self.idempotency, self.privacy,
            self.dfd, self.threats)}

    def _graph_codes(self, graph: dict) -> set[str]:
        return {e.code for e in validate_graph(graph, self.model)}

    def _node(self, model: dict, node_id: str) -> dict:
        return next(n for n in model["node_types"] if n["id"] == node_id)

    def _locator(self, model: dict, locator_id: str) -> dict:
        return next(l for l in model["locator_types"] if l["id"] == locator_id)

    def _path(self, model: dict, path_id: str) -> dict:
        return next(p for p in model["required_paths"] if p["id"] == path_id)

    # ================================================================== #
    # Positivas
    # ================================================================== #

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(
            self.model, self.canonical, self.architecture, self.idempotency, self.privacy,
            self.dfd, self.threats))

    def test_lineage_required_entities_are_derived_dynamically(self) -> None:
        expected = {e["id"] for e in self.canonical["entities"] if e.get("lineage_required")}
        declared = set(self.model["canonical_binding"]["entities_requiring_lineage"])
        self.assertEqual(expected, declared)
        self.assertFalse(self.model["canonical_binding"]["parallel_list_maintained"])

    def test_privacy_and_retention_references_exist(self) -> None:
        activities = {a["id"] for a in self.privacy["processing_activities"]}
        policies = {p["id"] for p in self.privacy["retention_policies"]}
        bound_activities = {b["activity_id"] for b in self.model["privacy_activity_bindings"]}
        bound_policies = {p["retention_policy_id"] for p in self.model["retention_binding"]["policies"]}
        self.assertLessEqual({"PA-03", "PA-06", "PA-07", "PA-08", "PA-09", "PA-15", "PA-17"},
                             bound_activities)
        self.assertLessEqual(bound_activities, activities)
        self.assertLessEqual({"L-01-DERIVED", "L-01-FINANCIAL", "L-01-AUDITABLE-DECISION",
                              "L-01-AUDIT", "L-01-DELETE-LEDGER", "L-01-BACKUP"}, bound_policies)
        self.assertLessEqual(bound_policies, policies)

    def test_node_owner_modules_exist_in_architecture(self) -> None:
        modules = {m["id"] for m in self.architecture["modules"]}
        for node in self.model["node_types"]:
            self.assertIn(node["owner_module"], modules, node["id"])

    def test_validator_is_deterministic_and_offline(self) -> None:
        first = validate_model(copy.deepcopy(self.model), self.canonical, self.architecture,
                               self.idempotency, self.privacy, self.dfd, self.threats)
        second = validate_model(copy.deepcopy(self.model), self.canonical, self.architecture,
                                self.idempotency, self.privacy, self.dfd, self.threats)
        self.assertEqual(first, second)
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        for forbidden in ("import time", "import datetime", "from datetime", "import urllib",
                          "import socket", "import requests", "import random", "os.environ"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_dfd_lineage_control_is_required_on_publication_and_close(self) -> None:
        mutated_dfd = copy.deepcopy(self.dfd)
        flow = next(flow for flow in mutated_dfd["flows"] if flow["id"] == "F05")
        flow["controls"] = [control for control in flow["controls"] if control != "C-LINEAGE"]
        errors = validate_model(self.model, self.canonical, self.architecture,
                                self.idempotency, self.privacy, mutated_dfd, self.threats)
        self.assertIn("LIN-DFD-FLOW", {error.code for error in errors})

    def test_TM_015_supply_chain_binding_is_required(self) -> None:
        mutated_threats = copy.deepcopy(self.threats)
        risk = next(risk for risk in mutated_threats["risks"] if risk["id"] == "TM-015")
        risk["controls"] = [control for control in risk["controls"] if control != "C-LINEAGE"]
        errors = validate_model(self.model, self.canonical, self.architecture,
                                self.idempotency, self.privacy, self.dfd, mutated_threats)
        self.assertIn("LIN-THREAT-BINDING", {error.code for error in errors})

    # ================================================================== #
    # Funciones puras — grafo
    # ================================================================== #

    def test_TST_LIN_001_complete_path_for_every_published_node(self) -> None:
        self.assertEqual([], validate_graph(synthetic_graph(), self.model))

    def test_TST_LIN_002_published_field_without_edge_is_blocked(self) -> None:
        graph = synthetic_graph()
        graph["nodes"].append(
            {"id": "node_source_record_orphan", "type": "source_record_field", "company_id": C1})
        self.assertIn("GRAPH-PATH-INCOMPLETE", self._graph_codes(graph))

    def test_TST_LIN_003_cross_company_edge_is_rejected(self) -> None:
        graph = synthetic_graph()
        graph["nodes"].append({"id": "node_fact_other_company", "type": "financial_fact_field",
                               "company_id": C2})
        graph["edges"].append({"edge_id": "edge_synthetic_cross", "company_id": C1,
                               "from_node_id": "node_fact_other_company",
                               "to_node_id": "node_decision_v1", "operation": "decided_using"})
        self.assertIn("GRAPH-CROSS-COMPANY", self._graph_codes(graph))

    def test_TST_LIN_004_cycle_is_rejected(self) -> None:
        graph = synthetic_graph()
        graph["edges"].append({"edge_id": "edge_synthetic_cycle", "company_id": C1,
                               "from_node_id": "node_fact_v1",
                               "to_node_id": "node_transformed_v1", "operation": "derived_from"})
        self.assertIn("GRAPH-ACYCLIC", self._graph_codes(graph))

    def test_dangling_edge_target_is_rejected(self) -> None:
        graph = synthetic_graph()
        graph["edges"].append({"edge_id": "edge_synthetic_dangling", "company_id": C1,
                               "from_node_id": "node_fact_v1",
                               "to_node_id": "node_does_not_exist", "operation": "derived_from"})
        self.assertIn("GRAPH-TARGET-EXISTS", self._graph_codes(graph))

    def test_superseded_source_requires_explicit_declaration(self) -> None:
        graph = synthetic_graph()
        next(n for n in graph["nodes"] if n["id"] == "node_transformed_v1")["superseded"] = True
        self.assertIn("GRAPH-SUPERSEDED-DECLARED", self._graph_codes(graph))

    def test_raw_value_never_travels_in_node_or_edge(self) -> None:
        by_node = synthetic_graph()
        by_node["nodes"][0]["raw_value"] = "synthetic-raw-payload"
        self.assertIn("GRAPH-RAW-VALUE", self._graph_codes(by_node))
        by_edge = synthetic_graph()
        by_edge["edges"][0]["raw_value"] = "synthetic-raw-payload"
        self.assertIn("GRAPH-RAW-VALUE", self._graph_codes(by_edge))

    def test_company_scoped_node_without_company_is_rejected(self) -> None:
        graph = synthetic_graph()
        next(n for n in graph["nodes"] if n["id"] == "node_fact_v1")["company_id"] = ""
        self.assertIn("GRAPH-NODE-COMPANY", self._graph_codes(graph))

    # ================================================================== #
    # Funciones puras — overlays
    # ================================================================== #

    def _overlay(self, overlay_id: str, sequence: int, expected: str, value: object,
                 state: str = "approved") -> dict:
        return {"overlay_id": overlay_id, "sequence": sequence, "approval_state": state,
                "expected_base_digest": expected, "action": "set_typed_value",
                "new_typed_value": value}

    def test_TST_OVR_001_overlay_does_not_mutate_source(self) -> None:
        base_value = {"amount": "100.00"}
        base_digest = digest_of(base_value)
        overlays = [self._overlay("overlay_synthetic_01", 1, base_digest, {"amount": "120.00"})]
        snapshot = copy.deepcopy(overlays)
        result = apply_overlay_chain(base_value, base_digest, overlays)
        self.assertEqual({"amount": "120.00"}, result["effective_value"])
        self.assertEqual({"amount": "100.00"}, base_value, "el valor base no se muta")
        self.assertEqual(snapshot, overlays, "la cadena de overlays no se muta")

    def test_TST_OVR_002_stale_base_produces_conflict(self) -> None:
        base_digest = digest_of({"amount": "100.00"})
        overlays = [self._overlay("overlay_synthetic_stale", 1,
                                  digest_of({"amount": "999.99"}), {"amount": "120.00"})]
        result = apply_overlay_chain({"amount": "100.00"}, base_digest, overlays)
        self.assertEqual([], result["applied"])
        self.assertEqual(1, len(result["conflicts"]))
        self.assertEqual("stale_base", result["conflicts"][0]["reason"])

    def test_TST_OVR_003_undo_is_another_append_only_overlay(self) -> None:
        base_value = {"amount": "100.00"}
        base_digest = digest_of(base_value)
        first = self._overlay("overlay_synthetic_01", 1, base_digest, {"amount": "120.00"})
        after_first = digest_of({"amount": "120.00"})
        undo = self._overlay("overlay_synthetic_02", 2, after_first, {"amount": "100.00"})
        undo["reverts_overlay_id"] = "overlay_synthetic_01"
        result = apply_overlay_chain(base_value, base_digest, [first, undo])
        self.assertEqual(["overlay_synthetic_01", "overlay_synthetic_02"], result["applied"])
        self.assertEqual({"amount": "100.00"}, result["effective_value"])
        self.assertNotIn("deleted", first)

    def test_TST_OVR_004_effective_order_is_deterministic(self) -> None:
        base_value = {"amount": "100.00"}
        base_digest = digest_of(base_value)
        first = self._overlay("overlay_synthetic_01", 1, base_digest, {"amount": "120.00"})
        second = self._overlay("overlay_synthetic_02", 2,
                               digest_of({"amount": "120.00"}), {"amount": "130.00"})
        forward = apply_overlay_chain(base_value, base_digest, [first, second])
        reversed_input = apply_overlay_chain(base_value, base_digest, [second, first])
        self.assertEqual(forward, reversed_input, "el orden de llegada no altera el resultado")
        self.assertEqual({"amount": "130.00"}, forward["effective_value"])

    def test_TST_OVR_006_pending_overlay_does_not_feed_publication(self) -> None:
        base_value = {"amount": "100.00"}
        base_digest = digest_of(base_value)
        for state in ("draft", "pending_review", "rejected", "conflicted"):
            overlays = [self._overlay("overlay_synthetic_pending", 1, base_digest,
                                      {"amount": "999.99"}, state=state)]
            result = apply_overlay_chain(base_value, base_digest, overlays)
            self.assertEqual([], result["applied"], state)
            self.assertEqual(base_value, result["effective_value"], state)

    def test_unknown_overlay_action_is_a_conflict_not_a_silent_pass(self) -> None:
        base_digest = digest_of({"amount": "100.00"})
        overlay = self._overlay("overlay_synthetic_bad", 1, base_digest, None)
        overlay["action"] = "execute_arbitrary_code"
        result = apply_overlay_chain({"amount": "100.00"}, base_digest, [overlay])
        self.assertEqual([], result["applied"])
        self.assertEqual("unknown_action", result["conflicts"][0]["reason"])

    def test_redaction_and_unknown_actions_are_supported(self) -> None:
        base_value = {"amount": "100.00"}
        base_digest = digest_of(base_value)
        redact = self._overlay("overlay_synthetic_redact", 1, base_digest, None)
        redact["action"] = "redact_value"
        self.assertIsNone(apply_overlay_chain(base_value, base_digest, [redact])["effective_value"])
        mark = self._overlay("overlay_synthetic_unknown", 1, base_digest, None)
        mark["action"] = "mark_unknown"
        self.assertEqual("unknown",
                         apply_overlay_chain(base_value, base_digest, [mark])["effective_value"])

    # ================================================================== #
    # Funciones puras — reproduction key
    # ================================================================== #

    def test_TST_PAR_001_same_manifest_yields_same_key(self) -> None:
        manifest = {"engine_release_id": "release_synthetic_0001",
                    "input_artifact_sha256": "0" * 64, "locale": "es-CO",
                    "timezone": "America/Bogota", "random_seed": 0,
                    "output_digests": {"dataset": "a" * 64}}
        reordered = {k: manifest[k] for k in reversed(list(manifest))}
        self.assertEqual(reproduction_key(manifest), reproduction_key(reordered))

    def test_reproduction_key_ignores_outputs_but_not_inputs(self) -> None:
        manifest = {"engine_release_id": "release_synthetic_0001", "locale": "es-CO",
                    "output_digests": {"dataset": "a" * 64}}
        other_output = dict(manifest, output_digests={"dataset": "b" * 64})
        other_input = dict(manifest, locale="es-MX")
        self.assertEqual(reproduction_key(manifest), reproduction_key(other_output))
        self.assertNotEqual(reproduction_key(manifest), reproduction_key(other_input))

    def test_canonical_json_is_stable_and_compact(self) -> None:
        self.assertEqual('{"a":1,"b":2}', canonical_json({"b": 2, "a": 1}))

    # ================================================================== #
    # Mutaciones del contrato
    # ================================================================== #

    def test_TST_LIN_005_locator_without_bounds_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._locator(mutated, "tabular_delimited")["bounds_validations"] = []
        self.assertIn("LIN-LOCATOR-BOUNDS", self._codes(mutated))

        relaxed = copy.deepcopy(self.model)
        relaxed["locator_rules"]["out_of_bounds_outcome"] = "best_effort_guess"
        self.assertIn("LIN-LOCATOR-BOUNDS", self._codes(relaxed))

    def test_TST_LIN_006_unknown_format_cannot_fabricate_a_locator(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._locator(mutated, "unknown_format")["fabricated_locator_allowed"] = True
        self.assertIn("LIN-LOCATOR-FABRICATED", self._codes(mutated))

        ambiguous = copy.deepcopy(self.model)
        self._locator(ambiguous, "document_visual")["ambiguity_outcome"] = "assume_first_match"
        self.assertIn("LIN-LOCATOR-AMBIGUITY", self._codes(ambiguous))

    def test_locator_without_artifact_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        locator = self._locator(mutated, "record_stream")
        locator["required_fields"] = [f for f in locator["required_fields"]
                                      if f != "artifact_sha256"]
        self.assertIn("LIN-LOCATOR-ARTIFACT", self._codes(mutated))

    def test_universal_opaque_locator_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["locator_rules"]["universal_opaque_locator_allowed"] = True
        self.assertIn("LIN-LOCATOR-UNIVERSAL", self._codes(mutated))

    def test_spreadsheet_macro_execution_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._locator(mutated, "spreadsheet")["macro_execution"] = "allowed"
        self.assertIn("LIN-LOCATOR-MACRO", self._codes(mutated))

    def test_user_supplied_xpath_execution_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._locator(mutated, "structured_markup")["user_supplied_xpath_executed"] = True
        self.assertIn("LIN-LOCATOR-XPATH", self._codes(mutated))

    def test_average_coverage_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._path(mutated, "PATH-FINANCIAL-FACT")["average_coverage_allowed"] = True
        self.assertIn("LIN-PATH-AVERAGE", self._codes(mutated))

    def test_incomplete_path_must_block_not_warn(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._path(mutated, "PATH-CLOSE")["on_incomplete"] = "warn_and_continue"
        self.assertIn("LIN-PATH-BLOCK", self._codes(mutated))

    def test_missing_required_path_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["required_paths"] = [p for p in mutated["required_paths"]
                                     if p["id"] != "PATH-DECISION"]
        self.assertIn("LIN-PATH-COVERAGE", self._codes(mutated))

    def test_edge_operations_must_stay_distinct(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["edge_operations"] = [o for o in mutated["edge_operations"]
                                      if o["id"] != "decided_using"]
        self.assertIn("LIN-EDGE-OPERATIONS", self._codes(mutated))

    def test_edges_cannot_become_mutable(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["edge_contract"]["mutable_after_write"] = True
        self.assertIn("LIN-EDGE-APPEND-ONLY", self._codes(mutated))

    def test_edge_cannot_carry_raw_values(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["edge_contract"]["raw_value_fields_forbidden"] = False
        self.assertIn("LIN-RAW-IN-LOGS", self._codes(mutated))

    def test_immutable_node_cannot_become_mutable(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._node(mutated, "artifact_version")["mutability"] = "mutable_master_versioned"
        self.assertIn("LIN-NODE-MUTABILITY", self._codes(mutated))

    def test_node_cannot_drop_one_of_the_two_classification_axes(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._node(mutated, "financial_fact_field")["personal_data_tags_required"] = False
        self.assertIn("LIN-TWO-AXES", self._codes(mutated))

    def test_TST_OVR_005_critical_field_requires_segregation_of_duties(self) -> None:
        removed = copy.deepcopy(self.model)
        removed["critical_overlay_fields"] = [c for c in removed["critical_overlay_fields"]
                                              if c["id"] != "amount"]
        self.assertIn("OVR-SOD-COVERAGE", self._codes(removed))

        relaxed = copy.deepcopy(self.model)
        next(c for c in relaxed["critical_overlay_fields"]
             if c["id"] == "currency")["requires_independent_review"] = False
        self.assertIn("OVR-SOD", self._codes(relaxed))

    def test_overlay_cannot_use_clock_ordering(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["concurrency"]["last_write_wins_by_clock"] = True
        self.assertIn("OVR-CLOCK", self._codes(mutated))

    def test_overlay_stale_base_must_conflict(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["concurrency"]["stale_base_outcome"] = "overwrite"
        self.assertIn("OVR-STALE", self._codes(mutated))

    def test_overlay_undo_cannot_mutate_prior_overlay(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["undo"]["mutates_prior_overlay"] = True
        self.assertIn("OVR-UNDO", self._codes(mutated))

    def test_overlay_cannot_mutate_raw_evidence(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["immutability"]["raw_unchanged"] = False
        self.assertIn("OVR-IMMUTABLE-SOURCE", self._codes(mutated))

    def test_overlay_cannot_carry_arbitrary_code(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["arbitrary_code_allowed"] = True
        self.assertIn("OVR-NO-CODE", self._codes(mutated))

    def test_schema_drift_cannot_apply_silently(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_contract"]["schema_drift"]["silent_application"] = True
        self.assertIn("OVR-DRIFT", self._codes(mutated))

    def test_pending_overlay_cannot_be_declared_authoritative(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["overlay_state_machine"]["states_feeding_authoritative_use"] = \
            ["applied", "pending_review"]
        self.assertIn("OVR-PENDING-BLOCKED", self._codes(mutated))

    def test_TST_PAR_002_affects_results_without_evaluation_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        rules = mutated["engine_release_contract"]["classification_rules"]
        rules["affects_results_requires"] = [r for r in rules["affects_results_requires"]
                                             if r != "adjudicated_corpus_manifest"]
        self.assertIn("PAR-AFFECTS-EVALUATION", self._codes(mutated))

    def test_TST_PAR_003_neutral_without_byte_equivalence_is_rejected(self) -> None:
        removed = copy.deepcopy(self.model)
        rules = removed["engine_release_contract"]["classification_rules"]
        rules["neutral_requires"] = [r for r in rules["neutral_requires"]
                                     if r != "byte_for_byte_equivalence_proof"]
        self.assertIn("PAR-NEUTRAL-EQUIVALENCE", self._codes(removed))

        relaxed = copy.deepcopy(self.model)
        relaxed["engine_release_contract"]["classification_rules"][
            "neutral_without_equivalence_proof"] = "still_neutral"
        self.assertIn("PAR-NEUTRAL-EQUIVALENCE", self._codes(relaxed))

    def test_TST_PAR_004_dirty_build_or_missing_sbom_is_rejected(self) -> None:
        for field in ("source_tree_clean", "artifact_digests", "sbom_digest",
                      "source_commit_sha"):
            mutated = copy.deepcopy(self.model)
            contract = mutated["engine_release_contract"]
            contract["required_fields"] = [f for f in contract["required_fields"] if f != field]
            self.assertIn("PAR-RELEASE-FIELDS", self._codes(mutated), field)

    def test_TST_PAR_005_reprocess_cannot_overwrite(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reprocessing_contract"]["overwrites_previous_version"] = True
        self.assertIn("PAR-REPROCESS-VERSION", self._codes(mutated))

    def test_TST_PAR_006_snapshot_keeps_original_release_and_version_set(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["reprocessing_contract"]["close_snapshot"]["keeps_original_engine_release"] = False
        self.assertIn("PAR-SNAPSHOT-IMMUTABLE", self._codes(mutated))

        revision = copy.deepcopy(self.model)
        revision["reprocessing_contract"]["close_snapshot"]["revision_mutates_previous"] = True
        self.assertIn("PAR-SNAPSHOT-REVISION", self._codes(revision))

    def test_TST_PAR_007_revoked_release_cannot_start_new_runs(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["engine_release_contract"]["revocation"]["can_start_new_runs"] = True
        self.assertIn("PAR-REVOKED-RUNS", self._codes(mutated))

    def test_revoked_release_stays_referenceable(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["engine_release_contract"]["revocation"]["release_record_deleted"] = True
        self.assertIn("PAR-REVOKED-HISTORY", self._codes(mutated))

    def test_agent_cannot_self_approve_a_release(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["engine_release_contract"]["approval"]["agent_can_self_approve"] = True
        self.assertIn("PAR-RELEASE-APPROVAL", self._codes(mutated))

    def test_latest_token_cannot_be_allowed(self) -> None:
        mutated = copy.deepcopy(self.model)
        manifest = mutated["reproducibility_manifest"]
        manifest["floating_version_tokens_forbidden"] = [
            t for t in manifest["floating_version_tokens_forbidden"] if t != "latest"]
        self.assertIn("PAR-NO-LATEST", self._codes(mutated))

        silent = copy.deepcopy(self.model)
        silent["reprocessing_contract"]["substitute_with_latest_allowed"] = True
        self.assertIn("PAR-NO-LATEST", self._codes(silent))

    def test_manifest_missing_a_pinned_input_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        manifest = mutated["reproducibility_manifest"]
        manifest["required_fields"] = [f for f in manifest["required_fields"]
                                       if f != "ordered_overlay_ids"]
        self.assertIn("PAR-MANIFEST-FIELDS", self._codes(mutated))

    def test_TST_PRV_001_tags_cannot_be_downgraded_silently(self) -> None:
        allowed = copy.deepcopy(self.model)
        allowed["privacy_propagation"]["downgrade_rule"]["downgrade_or_removal_allowed"] = True
        self.assertIn("PRV-TAG-DOWNGRADE", self._codes(allowed))

        without_rule = copy.deepcopy(self.model)
        downgrade = without_rule["privacy_propagation"]["downgrade_rule"]
        downgrade["exception_requires"] = [r for r in downgrade["exception_requires"]
                                           if r != "versioned_minimization_rule_id"]
        self.assertIn("PRV-TAG-DOWNGRADE", self._codes(without_rule))

    def test_agent_cannot_invent_the_legal_taxonomy(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["privacy_propagation"]["personal_data_tags"]["content_invented_by_agent"] = True
        self.assertIn("PRV-TAG-TAXONOMY", self._codes(mutated))

    def test_decision_request_cannot_be_resolved_here(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["privacy_propagation"]["resolved_here"] = True
        self.assertIn("PRV-DR-OPEN", self._codes(mutated))

    def test_unknown_personal_assessment_blocks_external_egress(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["privacy_propagation"]["unknown_state_effect"][
            "external_egress_when_purpose_requires_personal_assessment"] = "allowed"
        self.assertIn("PRV-UNKNOWN-EGRESS", self._codes(mutated))

    def test_both_axes_must_travel_through_every_carrier(self) -> None:
        mutated = copy.deepcopy(self.model)
        propagation = mutated["privacy_propagation"]
        propagation["carriers"] = [c for c in propagation["carriers"] if c != "export_manifest"]
        self.assertIn("PRV-TAG-CARRIER", self._codes(mutated))

    def test_TST_DED_002_lineage_never_merges_two_legitimate_identical_facts(self) -> None:
        merged = copy.deepcopy(self.model)
        merged["reprocessing_contract"]["lineage_is_not_dedupe"][
            "two_identical_legitimate_movements_merged"] = True
        self.assertIn("LIN-NOT-DEDUPE", self._codes(merged))

        shared = copy.deepcopy(self.model)
        shared["reprocessing_contract"]["lineage_is_not_dedupe"][
            "shared_locator_implies_same_fact"] = True
        self.assertIn("LIN-NOT-DEDUPE", self._codes(shared))

        dangling = copy.deepcopy(self.model)
        dangling["reprocessing_contract"]["lineage_is_not_dedupe"][
            "legitimate_identical_case_ref"] = "TST-DED-999"
        self.assertIn("LIN-NOT-DEDUPE", self._codes(dangling))

    def test_lineage_is_not_an_excuse_to_keep_deleted_payload(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_binding"]["tombstone_behaviour"][
            "personal_payload_retained_as_lineage_excuse"] = True
        self.assertIn("PRV-TOMBSTONE", self._codes(mutated))

    def test_restore_must_reapply_tombstones_before_reopen(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_binding"]["tombstone_behaviour"][
            "restore_reapplies_tombstones_before_service_reopen"] = False
        self.assertIn("PRV-TOMBSTONE", self._codes(mutated))

    def test_numeric_retention_duration_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retention_binding"]["note"] = "purge lineage 90 days after publication"
        self.assertIn("PRV-RETENTION-DURATION", self._codes(mutated))

    def test_canonical_coverage_drift_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["canonical_binding"]["entities_requiring_lineage"] = ["money_movement"]
        self.assertIn("LIN-CANONICAL-COVERAGE", self._codes(mutated))

        parallel = copy.deepcopy(self.model)
        parallel["canonical_binding"]["parallel_list_maintained"] = True
        self.assertIn("LIN-CANONICAL-BINDING", self._codes(parallel))

    def test_canonical_schema_version_must_match(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["canonical_schema_version"] = "9.9.9"
        self.assertIn("LIN-SCHEMA-MATCH", self._codes(mutated))

    def test_missing_privacy_binding_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["privacy_activity_bindings"] = [
            b for b in mutated["privacy_activity_bindings"] if b["activity_id"] != "PA-15"]
        self.assertIn("PRV-ACTIVITY-BINDING", self._codes(mutated))

    def test_unknown_privacy_reference_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["privacy_activity_bindings"].append(
            {"activity_id": "PA-99", "relationship": "synthetic"})
        self.assertIn("PRV-ACTIVITY-REFERENCE", self._codes(mutated))

    def test_missing_retention_binding_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.model)
        binding = mutated["retention_binding"]
        binding["policies"] = [p for p in binding["policies"]
                               if p["retention_policy_id"] != "L-01-DELETE-LEDGER"]
        self.assertIn("PRV-RETENTION-BINDING", self._codes(mutated))

    def test_required_test_cannot_be_dropped(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["required_tests"] = [t for t in mutated["required_tests"]
                                     if t["id"] != "TST-OVR-005"]
        self.assertIn("LIN-TEST-COVERAGE", self._codes(mutated))

    def test_gate_cannot_be_marked_as_met(self) -> None:
        mutated = copy.deepcopy(self.model)
        next(g for g in mutated["gates"] if g["id"] == "S1-READY")["status"] = "met"
        self.assertIn("LIN-GATE-STATUS", self._codes(mutated))

    def test_human_acceptance_cannot_be_recorded_by_an_agent(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["human_acceptance"] = "accepted"
        self.assertIn("LIN-HUMAN-ACCEPTANCE", self._codes(mutated))

    def test_unresolved_decision_cannot_be_closed(self) -> None:
        mutated = copy.deepcopy(self.model)
        next(d for d in mutated["unresolved_decisions"]
             if d["id"] == "UD-DR-PRV-001")["state"] = "resolved"
        self.assertIn("LIN-DECISION-STATE", self._codes(mutated))

    def test_engine_release_owner_module_is_platform(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["engine_release_contract"]["owner_module"] = "finance"
        self.assertIn("PAR-RELEASE-OWNER", self._codes(mutated))


if __name__ == "__main__":
    unittest.main()
