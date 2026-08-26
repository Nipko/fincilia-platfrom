"""Validación ejecutable del contrato de linaje de Fincilia (FNC-DOM-005).

Solo biblioteca estándar. Determinista: no consulta red, reloj, entorno ni
aleatoriedad. Las lecturas externas son ficheros del repositorio, en modo
read-only, recibidos por parámetro.

Expone además tres funciones puras reutilizables por las pruebas:

- `validate_graph`      valida un grafo de linaje sintético;
- `apply_overlay_chain` aplica una cadena de overlays de forma determinista;
- `reproduction_key`    calcula SHA-256 sobre JSON canónico.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK_ID = "FNC-DOM-005"
REQUIRED_DATA_CEILING = "synthetic_only"

REQUIRED_NODE_TYPES = {
    "artifact_version", "raw_locator", "extracted_field", "transformed_value",
    "source_record_field", "financial_fact_field", "decision", "report_field",
    "close_snapshot_field",
}
IMMUTABLE_NODE_TYPES = {
    "artifact_version", "raw_locator", "extracted_field", "close_snapshot_field",
}
REQUIRED_EDGE_OPERATIONS = {"derived_from", "decided_using", "included_in_snapshot"}
REQUIRED_EDGE_FIELDS = {
    "edge_id", "company_id", "from_node_type", "from_node_id", "to_node_type",
    "to_node_id", "operation", "processing_run_id", "engine_release_id",
    "canonical_schema_version", "actor_kind", "actor_id", "occurred_at", "audit_event_ref",
}
REQUIRED_PATH_IDS = {
    "PATH-SOURCE-RECORD", "PATH-FINANCIAL-FACT", "PATH-DECISION",
    "PATH-REPORT", "PATH-CLOSE",
}
REQUIRED_LOCATOR_TYPES = {
    "tabular_delimited", "spreadsheet", "document_visual", "structured_markup",
    "record_stream", "unknown_format",
}
REQUIRED_RELEASE_FIELDS = {
    "engine_release_id", "semver", "source_commit_sha", "source_tree_clean",
    "artifact_digests", "sbom_digest", "dependency_lock_digest", "build_provenance_ref",
    "canonical_schema_compatibility", "classification", "attestation_ref",
    "builder_identity", "build_timestamp", "state",
}
REQUIRED_MANIFEST_FIELDS = {
    "input_artifact_version_id", "input_artifact_sha256", "dataset_version_id",
    "mapping_template_version_id", "recipe_version_id", "ordered_overlay_ids",
    "reference_dataset_version_ids", "parser_versions", "model_versions",
    "rule_versions", "engine_release_id", "canonical_schema_version", "locale",
    "timezone", "deterministic_config", "random_seed", "output_digests",
}
REQUIRED_OVERLAY_FIELDS = {
    "overlay_id", "company_id", "target_node_id", "target_field_path", "base_version_ref",
    "expected_base_digest", "action", "reason_code", "actor_id", "authorization_version",
    "occurred_at", "engine_release_id", "field_risk_class", "approval_state",
    "audit_event_ref", "sequence",
}
REQUIRED_CRITICAL_OVERLAY_FIELDS = {
    "amount", "currency", "direction", "financial_account_identifier",
    "tax_identity", "accounting_date",
}
REQUIRED_PRIVACY_ACTIVITIES = {"PA-03", "PA-06", "PA-07", "PA-08", "PA-09", "PA-15", "PA-17"}
REQUIRED_RETENTION_POLICIES = {
    "L-01-DERIVED", "L-01-FINANCIAL", "L-01-AUDITABLE-DECISION", "L-01-AUDIT",
    "L-01-DELETE-LEDGER", "L-01-BACKUP",
}
REQUIRED_TEST_IDS = {
    "TST-LIN-001", "TST-LIN-002", "TST-LIN-003", "TST-LIN-004", "TST-LIN-005",
    "TST-LIN-006", "TST-OVR-001", "TST-OVR-002", "TST-OVR-003", "TST-OVR-004",
    "TST-OVR-005", "TST-OVR-006", "TST-PAR-001", "TST-PAR-002", "TST-PAR-003",
    "TST-PAR-004", "TST-PAR-005", "TST-PAR-006", "TST-PAR-007", "TST-PRV-001",
    "TST-DED-002",
}
REQUIRED_DFD_LINEAGE_FLOWS = {"F05", "F06"}
REQUIRED_LINEAGE_RISKS = {"TM-007", "TM-008", "TM-015"}
REQUIRED_DECISION_ENTITIES = {
    "completeness_assessment", "completeness_control_result",
    "reconciliation_statement", "reconciling_item",
}
REQUIRED_PLAN_INVARIANTS = {
    "PLAN-STAGE-COVERAGE", "PLAN-TYPE-CHAIN", "PLAN-TRANSFORM-NAMED",
    "PLAN-NO-VALUES", "PLAN-VERSIONED", "PLAN-APPEND-ONLY",
    "PLAN-HISTORY-PRESERVED",
}
REQUIRED_PLAN_STEP_FIELDS = {
    "canonical_field", "company_id", "configuration_digest",
    "input_semantic_type", "operation", "output_semantic_type",
    "parser_version", "plan_id", "rule_version", "stage", "step_id",
    "step_ordinal",
}
REQUIRED_OVERRIDE_INVARIANTS = {
    "OVR-NO-VALUES", "OVR-SEGREGATION", "OVR-UNAPPROVED-BLOCKS",
    "OVR-NO-CROSS-COMPANY", "OVR-DIGEST-CHAIN", "OVR-POSITIONED",
    "OVR-OPTIONAL", "OVR-IMMUTABLE",
}
REQUIRED_OVERRIDE_FIELDS = {
    "approved_by", "base_plan_step_id", "canonical_schema_version",
    "company_id", "created_at", "created_by", "dataset_version_id",
    "engine_release_id", "field_name", "original_value_digest",
    "override_id", "override_kind", "raw_record_id", "reason_code",
    "resulting_value_digest", "rule_version", "source_record_id",
}
REQUIRED_APPROVAL_INVARIANTS = {
    "REL-ONE-SIGNATURE", "REL-SIGNED-DIGEST", "REL-RUNTIME-CANNOT-SIGN",
    "REL-SUPERSEDED-KEEPS-SIGNATURE", "REL-DRAFT-CANNOT-PUBLISH",
}
REQUIRED_APPROVAL_FIELDS = {
    "action", "actor_identity", "approval_ref", "approval_id",
    "components_digest", "occurred_at", "rationale", "release_id",
}
# Lo que **no** puede llevar un override ni un paso del plan. El grafo guarda
# huellas; una clave con esta pinta seria el valor entrando por la puerta de
# atras.
VALUE_BEARING_FIELDS = {
    "value", "typed_value", "original_value", "resulting_value", "new_value",
    "raw_value", "amount", "cell_text",
}

FLOATING_TOKENS = {"latest", "main", "head", "stable", "current"}
ACCEPTED_TOKENS = {"accepted", "approved", "met", "final", "signed", "done", "closed"}
DURATION_PATTERN = re.compile(
    r"\d+\s*[-_ ]?\s*(days?|months?|years?|hours?|weeks?|dias?|d[ií]as?|meses|a[nñ]os?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class LineageModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Funciones puras
# --------------------------------------------------------------------------- #

def canonical_json(value: Any) -> str:
    """JSON canónico: claves ordenadas, separadores compactos, UTF-8 preservado."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def reproduction_key(manifest: dict[str, Any]) -> str:
    """SHA-256 sobre el JSON canónico del manifest, excluyendo los digests de salida.

    Excluir `output_digests` es deliberado: la clave identifica **la entrada**, de
    modo que dos ejecuciones con la misma clave deben producir la misma salida o
    declararse `not_reproducible`.
    """
    material = {k: v for k, v in manifest.items() if k != "output_digests"}
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def apply_overlay_chain(
    base_value: Any, base_digest: str, overlays: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aplica una cadena de overlays de forma determinista.

    El orden efectivo es `(sequence, overlay_id)`: nunca el reloj, nunca el orden
    de llegada. Un overlay cuyo `expected_base_digest` no coincida con el digest
    vigente produce conflicto y **no** se aplica; la cadena continúa para poder
    reportar todos los conflictos de una vez.

    Solo se consideran overlays en estado `approved` o `applied`: un overlay
    `draft`, `pending_review`, `rejected` o `conflicted` nunca alimenta un valor
    efectivo.
    """
    current_value = base_value
    current_digest = base_digest
    applied: list[str] = []
    conflicts: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    ordered = sorted(overlays, key=lambda o: (o.get("sequence", 0), str(o.get("overlay_id", ""))))
    for overlay in ordered:
        overlay_id = str(overlay.get("overlay_id", ""))
        state = overlay.get("approval_state")
        if state not in {"approved", "applied"}:
            skipped.append({"overlay_id": overlay_id, "reason": f"state_{state}"})
            continue
        if overlay.get("expected_base_digest") != current_digest:
            conflicts.append({
                "overlay_id": overlay_id,
                "reason": "stale_base",
                "expected": str(overlay.get("expected_base_digest")),
                "actual": current_digest,
            })
            continue
        action = overlay.get("action")
        if action == "set_typed_value":
            current_value = overlay.get("new_typed_value")
        elif action == "redact_value":
            current_value = None
        elif action == "mark_unknown":
            current_value = "unknown"
        else:
            conflicts.append({"overlay_id": overlay_id, "reason": "unknown_action",
                              "expected": "set_typed_value|redact_value|mark_unknown",
                              "actual": str(action)})
            continue
        current_digest = hashlib.sha256(canonical_json(current_value).encode("utf-8")).hexdigest()
        applied.append(overlay_id)

    return {
        "effective_value": current_value,
        "effective_digest": current_digest,
        "applied": applied,
        "conflicts": conflicts,
        "skipped": skipped,
    }


def validate_graph(graph: dict[str, Any], model: dict[str, Any]) -> list[LineageModelError]:
    """Valida un grafo de linaje sintético contra el contrato del modelo."""
    errors: list[LineageModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(LineageModelError(code, location, message))

    nodes = {n["id"]: n for n in graph.get("nodes", []) if isinstance(n, dict) and "id" in n}
    known_types = {n["id"] for n in model.get("node_types", [])}
    known_ops = {o["id"] for o in model.get("edge_operations", [])}
    edges = graph.get("edges", [])

    for node_id, node in sorted(nodes.items()):
        if node.get("type") not in known_types:
            fail("GRAPH-NODE-TYPE", f"nodes[{node_id}]", f"unknown node type {node.get('type')!r}")
        if node.get("type") in REQUIRED_NODE_TYPES and not node.get("company_id"):
            fail("GRAPH-NODE-COMPANY", f"nodes[{node_id}]", "company-scoped node without company_id")
        if "raw_value" in node:
            fail("GRAPH-RAW-VALUE", f"nodes[{node_id}]", "raw values never live in lineage nodes")

    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for index, edge in enumerate(edges):
        location = f"edges[{edge.get('edge_id', index)}]"
        source = edge.get("from_node_id")
        target = edge.get("to_node_id")
        if source not in nodes:
            fail("GRAPH-TARGET-EXISTS", location, f"dangling source {source!r}")
        if target not in nodes:
            fail("GRAPH-TARGET-EXISTS", location, f"dangling target {target!r}")
        if edge.get("operation") not in known_ops:
            fail("GRAPH-OPERATION", location, f"unknown operation {edge.get('operation')!r}")
        if "raw_value" in edge:
            fail("GRAPH-RAW-VALUE", location, "raw values never travel in lineage edges")
        if source in nodes and target in nodes:
            source_company = nodes[source].get("company_id")
            target_company = nodes[target].get("company_id")
            if source_company and target_company and source_company != target_company:
                fail("GRAPH-CROSS-COMPANY", location,
                     f"edge crosses companies {source_company!r} -> {target_company!r}")
            if edge.get("company_id") and edge["company_id"] != target_company:
                fail("GRAPH-CROSS-COMPANY", location, "edge company_id does not match its target")
            if nodes[source].get("superseded") and not edge.get("supersession_declared"):
                fail("GRAPH-SUPERSEDED-DECLARED", location,
                     "using a superseded source requires an explicit supersession declaration")
            adjacency[source].append(target)

    # Aciclicidad por búsqueda en profundidad con marcado tricolor.
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {node_id: WHITE for node_id in nodes}

    def visit(start: str) -> bool:
        stack = [(start, iter(adjacency.get(start, [])))]
        colour[start] = GREY
        while stack:
            current, children = stack[-1]
            advanced = False
            for child in children:
                if colour.get(child) == GREY:
                    return True
                if colour.get(child) == WHITE:
                    colour[child] = GREY
                    stack.append((child, iter(adjacency.get(child, []))))
                    advanced = True
                    break
            if not advanced:
                colour[current] = BLACK
                stack.pop()
        return False

    for node_id in sorted(nodes):
        if colour[node_id] == WHITE and visit(node_id):
            fail("GRAPH-ACYCLIC", "edges", "the lineage graph contains a cycle")
            break

    # Cobertura de caminos obligatorios: 100%, sin promedio.
    incoming: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        target = edge.get("to_node_id")
        source = edge.get("from_node_id")
        if target in incoming and source in nodes:
            incoming[target].append((source, str(edge.get("operation"))))

    paths = {p["applies_to_node_type"]: p for p in model.get("required_paths", [])}

    def reaches_evidence(node_id: str, seen: set[str]) -> bool:
        if nodes[node_id].get("type") == "artifact_version":
            return True
        if node_id in seen:
            return False
        seen.add(node_id)
        return any(reaches_evidence(src, seen) for src, _ in incoming.get(node_id, [])
                   if src in nodes)

    for node_id, node in sorted(nodes.items()):
        node_type = node.get("type")
        if node_type not in paths or not node.get("published", True):
            continue
        if not reaches_evidence(node_id, set()):
            fail("GRAPH-PATH-INCOMPLETE", f"nodes[{node_id}]",
                 f"{node_type} has no complete path to artifact_version evidence")

    return sorted(set(errors))


# --------------------------------------------------------------------------- #
# Validación del contrato
# --------------------------------------------------------------------------- #

def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item["id"] for item in items if isinstance(item, dict) and "id" in item}


def _strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            found.extend(_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_strings(child))
    elif isinstance(value, str):
        found.append(value)
    return found


def validate_model(
    model: dict[str, Any],
    canonical: dict[str, Any],
    architecture: dict[str, Any],
    idempotency: dict[str, Any],
    privacy: dict[str, Any],
    dfd: dict[str, Any],
    threats: dict[str, Any],
) -> list[LineageModelError]:
    errors: list[LineageModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(LineageModelError(code, location, message))

    # -- cabecera --------------------------------------------------------
    if model.get("schema_version") != 1:
        fail("LIN-SCHEMA-VERSION", "schema_version", "schema_version must equal 1")
    if model.get("task_id") != REQUIRED_TASK_ID:
        fail("LIN-TASK", "task_id", f"task_id must be {REQUIRED_TASK_ID}")
    if model.get("status") != "review_pending":
        fail("LIN-STATUS", "status", "the model stays review_pending")
    if model.get("human_acceptance") != "pending":
        fail("LIN-HUMAN-ACCEPTANCE", "human_acceptance", "an agent cannot record human acceptance")
    if model.get("data_ceiling") != REQUIRED_DATA_CEILING:
        fail("LIN-DATA-CEILING", "data_ceiling", f"expected {REQUIRED_DATA_CEILING}")
    if model.get("canonical_schema_version") != canonical.get("canonical_schema_version"):
        fail("LIN-SCHEMA-MATCH", "canonical_schema_version",
             "canonical_schema_version must match docs/domain/canonical-model.json")

    module_ids = {m["id"] for m in architecture.get("modules", [])}

    # -- nodos -----------------------------------------------------------
    node_types = model.get("node_types", [])
    node_ids = _ids(node_types)
    missing_nodes = sorted(REQUIRED_NODE_TYPES - node_ids)
    if missing_nodes:
        fail("LIN-NODE-COVERAGE", "node_types", f"missing node types: {missing_nodes}")
    for node in node_types:
        location = f"node_types[{node.get('id')}]"
        if node.get("owner_module") not in module_ids:
            fail("LIN-NODE-OWNER", location, f"unknown owner module {node.get('owner_module')!r}")
        if not node.get("identity_immutable"):
            fail("LIN-NODE-IDENTITY", location, "node identity must be immutable")
        if not node.get("version_reference_required"):
            fail("LIN-NODE-VERSION", location, "node must reference a version")
        digest = node.get("value_digest", {})
        if digest.get("algorithm") != "sha256":
            fail("LIN-NODE-DIGEST", location, "value digest must be sha256")
        if digest.get("raw_value_in_logs_or_edges") is not False:
            fail("LIN-RAW-IN-LOGS", location, "raw values never reach logs or edges")
        payload = node.get("payload_contract", {})
        if not (payload.get("schema_ref_required") and payload.get("schema_version_required")
                and payload.get("max_bytes_required")):
            fail("LIN-NODE-PAYLOAD", location,
                 "payload needs schema reference, schema version and max byte size")
        if payload.get("free_form_json_allowed") is not False:
            fail("LIN-NODE-PAYLOAD", location, "free-form JSON without schema is not allowed")
        if not node.get("operational_classification_required") or \
                not node.get("personal_data_tags_required"):
            fail("LIN-TWO-AXES", location,
                 "both operational classification and personal data tags are required")
        if node.get("id") in IMMUTABLE_NODE_TYPES and \
                node.get("mutability") not in {"immutable", "immutable_version"}:
            fail("LIN-NODE-MUTABILITY", location,
                 f"{node.get('id')} must be immutable")
        if node.get("id") in REQUIRED_NODE_TYPES and node.get("company_scoped") is not True:
            fail("LIN-NODE-COMPANY", location, "financial lineage nodes are company-scoped")

    decision = next((node for node in node_types if node.get("id") == "decision"), {})
    decision_entities = set(decision.get("produces_lineage_for", []))
    missing_decisions = sorted(REQUIRED_DECISION_ENTITIES - decision_entities)
    if missing_decisions:
        fail("LIN-DECISION-COVERAGE", "node_types[decision].produces_lineage_for",
             f"missing materialized financial decisions: {missing_decisions}")

    # -- aristas ---------------------------------------------------------
    operation_ids = _ids(model.get("edge_operations", []))
    missing_ops = sorted(REQUIRED_EDGE_OPERATIONS - operation_ids)
    if missing_ops:
        fail("LIN-EDGE-OPERATIONS", "edge_operations",
             f"derived_from, decided_using and included_in_snapshot must be distinct: {missing_ops}")
    contract = model.get("edge_contract", {})
    if contract.get("append_only") is not True or contract.get("mutable_after_write") is not False:
        fail("LIN-EDGE-APPEND-ONLY", "edge_contract", "lineage edges are append-only")
    missing_fields = sorted(REQUIRED_EDGE_FIELDS - set(contract.get("required_fields", [])))
    if missing_fields:
        fail("LIN-EDGE-FIELDS", "edge_contract", f"missing required edge fields: {missing_fields}")
    if contract.get("cross_company_forbidden") is not True:
        fail("LIN-EDGE-CROSS-COMPANY", "edge_contract", "cross-company edges must be forbidden")
    if contract.get("raw_value_fields_forbidden") is not True:
        fail("LIN-RAW-IN-LOGS", "edge_contract", "edges never carry raw values")

    # -- caminos ---------------------------------------------------------
    paths = model.get("required_paths", [])
    missing_paths = sorted(REQUIRED_PATH_IDS - _ids(paths))
    if missing_paths:
        fail("LIN-PATH-COVERAGE", "required_paths", f"missing required paths: {missing_paths}")
    for path in paths:
        location = f"required_paths[{path.get('id')}]"
        sequence = path.get("sequence", [])
        for step in sequence:
            if step not in node_ids:
                fail("LIN-PATH-NODE", location, f"unknown node type in sequence: {step!r}")
        if not sequence or sequence[0] != "artifact_version":
            fail("LIN-PATH-EVIDENCE", location, "every path starts at artifact_version")
        if path.get("terminal_evidence") != "artifact_version":
            fail("LIN-PATH-EVIDENCE", location, "terminal evidence must be artifact_version")
        if path.get("average_coverage_allowed") is not False:
            fail("LIN-PATH-AVERAGE", location,
                 "an average must never hide fields without lineage")
        if not str(path.get("coverage_requirement", "")).startswith("100_percent"):
            fail("LIN-PATH-COVERAGE", location, "coverage must be 100 percent")
        if not str(path.get("on_incomplete", "")).startswith("block"):
            fail("LIN-PATH-BLOCK", location, "an incomplete path must block, not warn")

    # -- localizadores ----------------------------------------------------
    locators = model.get("locator_types", [])
    missing_locators = sorted(REQUIRED_LOCATOR_TYPES - _ids(locators))
    if missing_locators:
        fail("LIN-LOCATOR-COVERAGE", "locator_types", f"missing locator types: {missing_locators}")
    for locator in locators:
        location = f"locator_types[{locator.get('id')}]"
        required = set(locator.get("required_fields", []))
        if "artifact_version_id" not in required or "artifact_sha256" not in required:
            fail("LIN-LOCATOR-ARTIFACT", location,
                 "every locator references artifact_version_id and artifact_sha256")
        if locator.get("ordinal_base") not in {0, 1}:
            fail("LIN-LOCATOR-ORDINAL", location, "ordinal base must be declared as 0 or 1")
        if locator.get("ambiguity_outcome") not in {"invalid", "review_required"}:
            fail("LIN-LOCATOR-AMBIGUITY", location,
                 "ambiguity yields invalid or review_required, never a fabricated locator")
        if locator.get("id") != "unknown_format" and not locator.get("bounds_validations"):
            fail("LIN-LOCATOR-BOUNDS", location, "bounds validations are required")
        if locator.get("id") == "spreadsheet" and locator.get("macro_execution") != "forbidden":
            fail("LIN-LOCATOR-MACRO", location, "spreadsheet macros are never executed")
        if locator.get("id") == "structured_markup" and \
                locator.get("user_supplied_xpath_executed") is not False:
            fail("LIN-LOCATOR-XPATH", location, "user supplied XPath is never executed")
        if locator.get("id") == "unknown_format" and \
                locator.get("fabricated_locator_allowed") is not False:
            fail("LIN-LOCATOR-FABRICATED", location, "an unknown format never yields a locator")
    rules = model.get("locator_rules", {})
    if rules.get("universal_opaque_locator_allowed") is not False:
        fail("LIN-LOCATOR-UNIVERSAL", "locator_rules", "a universal opaque locator is not allowed")
    if rules.get("locator_mutable") is not False:
        fail("LIN-LOCATOR-IMMUTABLE", "locator_rules", "origin locators are immutable")
    if rules.get("out_of_bounds_outcome") != "invalid":
        fail("LIN-LOCATOR-BOUNDS", "locator_rules", "out of bounds yields invalid")

    # -- overlays ---------------------------------------------------------
    overlay = model.get("overlay_contract", {})
    if overlay.get("append_only") is not True or overlay.get("mutable_after_write") is not False:
        fail("OVR-APPEND-ONLY", "overlay_contract", "overlays are append-only")
    if overlay.get("arbitrary_code_allowed") is not False:
        fail("OVR-NO-CODE", "overlay_contract", "an overlay carries a typed value, never code")
    missing_overlay = sorted(REQUIRED_OVERLAY_FIELDS - set(overlay.get("required_fields", [])))
    if missing_overlay:
        fail("OVR-FIELDS", "overlay_contract", f"missing overlay fields: {missing_overlay}")
    concurrency = overlay.get("concurrency", {})
    if concurrency.get("mechanism") != "optimistic_expected_base_digest":
        fail("OVR-CONCURRENCY", "overlay_contract", "overlays use optimistic concurrency")
    if concurrency.get("stale_base_outcome") != "conflict":
        fail("OVR-STALE", "overlay_contract", "a stale base must produce a conflict")
    if concurrency.get("last_write_wins_by_clock") is not False or \
            concurrency.get("clock_ordering_authoritative") is not False:
        fail("OVR-CLOCK", "overlay_contract", "clock ordering is never authoritative")
    determinism = overlay.get("determinism", {})
    if determinism.get("ordering_key", [])[:1] != ["base_version_ref"] or \
            "sequence" not in determinism.get("ordering_key", []):
        fail("OVR-DETERMINISM", "overlay_contract",
             "effective order is keyed by base version and sequence")
    undo = overlay.get("undo", {})
    if undo.get("mechanism") != "new_reversing_overlay" or \
            undo.get("mutates_prior_overlay") is not False or \
            undo.get("deletes_prior_overlay") is not False:
        fail("OVR-UNDO", "overlay_contract", "undo is another append-only overlay")
    immutability = overlay.get("immutability", {})
    if not (immutability.get("raw_unchanged") and immutability.get("extracted_unchanged")
            and immutability.get("artifact_version_unchanged")):
        fail("OVR-IMMUTABLE-SOURCE", "overlay_contract",
             "an overlay never mutates raw, extraction or artifact version")
    if overlay.get("schema_drift", {}).get("silent_application") is not False:
        fail("OVR-DRIFT", "overlay_contract", "schema drift blocks silent application")
    export_manifest = overlay.get("export_manifest", {})
    if not (export_manifest.get("overlay_set_declared") and export_manifest.get("ordered")
            and export_manifest.get("digest_of_overlay_set_required")):
        fail("OVR-EXPORT-MANIFEST", "overlay_contract",
             "export and reprocess declare the exact ordered overlay set")
    if not overlay.get("ui_contract", {}).get("must_display"):
        fail("OVR-UI-CONTRACT", "overlay_contract",
             "the contract must state what the interface has to explain")

    machine = model.get("overlay_state_machine", {})
    states = set(machine.get("states", []))
    if machine.get("states_feeding_authoritative_use") != ["applied"]:
        fail("OVR-PENDING-BLOCKED", "overlay_state_machine",
             "only an applied overlay feeds authoritative use")
    for blocked in ("draft", "pending_review", "rejected", "conflicted"):
        if blocked not in machine.get("states_blocked_from_publication", []):
            fail("OVR-PENDING-BLOCKED", "overlay_state_machine",
                 f"state {blocked} must be blocked from publication")
    for transition in machine.get("transitions", []):
        if transition.get("from") not in states or transition.get("to") not in states:
            fail("OVR-STATE-TRANSITION", "overlay_state_machine",
                 f"transition references unknown state: {transition}")

    critical = {c["id"] for c in model.get("critical_overlay_fields", [])}
    missing_critical = sorted(REQUIRED_CRITICAL_OVERLAY_FIELDS - critical)
    if missing_critical:
        fail("OVR-SOD-COVERAGE", "critical_overlay_fields",
             f"critical financial fields missing SoD: {missing_critical}")
    for field in model.get("critical_overlay_fields", []):
        if field.get("requires_independent_review") is not True or \
                field.get("sod_rule") != "author_cannot_approve":
            fail("OVR-SOD", f"critical_overlay_fields[{field.get('id')}]",
                 "a critical field requires independent review before authoritative use")

    # -- engine release ---------------------------------------------------
    release = model.get("engine_release_contract", {})
    if release.get("owner_module") != "platform":
        fail("PAR-RELEASE-OWNER", "engine_release_contract",
             "engine_release belongs to platform per module boundaries")
    missing_release = sorted(REQUIRED_RELEASE_FIELDS - set(release.get("required_fields", [])))
    if missing_release:
        fail("PAR-RELEASE-FIELDS", "engine_release_contract",
             f"missing release manifest fields: {missing_release}")
    if set(release.get("classification_values", [])) != {"neutral", "affects_results"}:
        fail("PAR-RELEASE-CLASSIFICATION", "engine_release_contract",
             "classification is neutral or affects_results")
    classification_rules = release.get("classification_rules", {})
    for requirement in ("adjudicated_corpus_manifest", "result_diff_report", "independent_review"):
        if requirement not in classification_rules.get("affects_results_requires", []):
            fail("PAR-AFFECTS-EVALUATION", "engine_release_contract",
                 f"affects_results requires {requirement}")
    if "byte_for_byte_equivalence_proof" not in classification_rules.get("neutral_requires", []):
        fail("PAR-NEUTRAL-EQUIVALENCE", "engine_release_contract",
             "a neutral release must prove byte-for-byte equivalence")
    if classification_rules.get("neutral_without_equivalence_proof") != "reclassified_as_affects_results":
        fail("PAR-NEUTRAL-EQUIVALENCE", "engine_release_contract",
             "without equivalence proof a release is affects_results")
    approval = release.get("approval", {})
    if approval.get("agent_can_self_approve") is not False:
        fail("PAR-RELEASE-APPROVAL", "engine_release_contract",
             "an agent can never grant itself an approved release")
    if approval.get("authority") not in {"human_platform_owner"}:
        fail("PAR-RELEASE-APPROVAL", "engine_release_contract",
             "approval authority must be a named human owner")
    revocation = release.get("revocation", {})
    if revocation.get("release_record_deleted") is not False or \
            revocation.get("still_referenceable_for_history") is not True:
        fail("PAR-REVOKED-HISTORY", "engine_release_contract",
             "a revoked release stays referenceable to explain history")
    if revocation.get("can_start_new_runs") is not False:
        fail("PAR-REVOKED-RUNS", "engine_release_contract",
             "a revoked release cannot start new runs")

    # -- reproducibilidad --------------------------------------------------
    manifest = model.get("reproducibility_manifest", {})
    missing_manifest = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest.get("required_fields", [])))
    if missing_manifest:
        fail("PAR-MANIFEST-FIELDS", "reproducibility_manifest",
             f"missing manifest fields: {missing_manifest}")
    forbidden = set(manifest.get("floating_version_tokens_forbidden", []))
    if not FLOATING_TOKENS <= forbidden:
        fail("PAR-NO-LATEST", "reproducibility_manifest",
             f"floating tokens must be forbidden: {sorted(FLOATING_TOKENS - forbidden)}")
    if manifest.get("silent_substitution_with_latest") is not False:
        fail("PAR-NO-LATEST", "reproducibility_manifest", "latest is never substituted silently")
    if manifest.get("failure_state") != "not_reproducible":
        fail("PAR-NOT-REPRODUCIBLE", "reproducibility_manifest",
             "an unreproducible manifest yields not_reproducible")
    key_spec = manifest.get("reproduction_key", {})
    if key_spec.get("algorithm") != "sha256" or "canonical_json" not in str(key_spec.get("encoding")):
        fail("PAR-REPRODUCTION-KEY", "reproducibility_manifest",
             "reproduction key is sha256 over canonical json")

    # -- reprocesamiento ---------------------------------------------------
    reprocess = model.get("reprocessing_contract", {})
    if reprocess.get("creates_dataset_version") is not True or \
            reprocess.get("overwrites_previous_version") is not False:
        fail("PAR-REPROCESS-VERSION", "reprocessing_contract",
             "a reprocess creates a version and never overwrites")
    if reprocess.get("previous_version_deleted") is not False or \
            reprocess.get("prior_edges_preserved") is not True:
        fail("PAR-HISTORY-PRESERVED", "reprocessing_contract",
             "previous versions and their edges are preserved")
    snapshot = reprocess.get("close_snapshot", {})
    if snapshot.get("keeps_original_engine_release") is not True or \
            snapshot.get("keeps_original_version_set") is not True or \
            snapshot.get("mutated_by_reprocess") is not False:
        fail("PAR-SNAPSHOT-IMMUTABLE", "reprocessing_contract",
             "a closed snapshot keeps its original release and version set")
    if snapshot.get("reopen_or_republish_creates_revision") != "n_plus_1" or \
            snapshot.get("revision_mutates_previous") is not False:
        fail("PAR-SNAPSHOT-REVISION", "reprocessing_contract",
             "reopening creates revision N+1 and never changes N")
    if reprocess.get("substitute_with_latest_allowed") is not False:
        fail("PAR-NO-LATEST", "reprocessing_contract", "a missing input is never replaced by latest")
    dedupe = reprocess.get("lineage_is_not_dedupe", {})
    if dedupe.get("two_identical_legitimate_movements_merged") is not False or \
            dedupe.get("shared_locator_implies_same_fact") is not False:
        fail("LIN-NOT-DEDUPE", "reprocessing_contract",
             "lineage never collapses two legitimate identical facts")
    dedupe_tests = {t["id"] for t in idempotency.get("required_tests", [])}
    if dedupe.get("legitimate_identical_case_ref") not in dedupe_tests:
        fail("LIN-NOT-DEDUPE", "reprocessing_contract",
             "the legitimate identical case must reference an existing DOM-004 test")

    # -- privacidad --------------------------------------------------------
    propagation = model.get("privacy_propagation", {})
    if propagation.get("axes_are_distinct_fields") is not True:
        fail("PRV-TWO-AXES", "privacy_propagation",
             "operational classification and personal data tags are distinct fields")
    tags = propagation.get("personal_data_tags", {})
    if tags.get("catalog_version_required") is not True:
        fail("PRV-TAG-CATALOG", "privacy_propagation", "personal data tags carry a catalog version")
    if set(tags.get("state_values", [])) != {"pending", "approved"}:
        fail("PRV-TAG-STATE", "privacy_propagation", "tag state is pending or approved")
    if tags.get("content_invented_by_agent") is not False or \
            tags.get("legal_taxonomy_declared_here") is not False:
        fail("PRV-TAG-TAXONOMY", "privacy_propagation",
             "an agent never invents the legal taxonomy; DR-PRV-001 owns it")
    downgrade = propagation.get("downgrade_rule", {})
    if downgrade.get("downgrade_or_removal_allowed") is not False or \
            downgrade.get("silent_downgrade") is not False:
        fail("PRV-TAG-DOWNGRADE", "privacy_propagation",
             "tags never drop without a versioned minimization rule and evidence")
    for requirement in ("versioned_minimization_rule_id", "redaction_evidence_ref"):
        if requirement not in downgrade.get("exception_requires", []):
            fail("PRV-TAG-DOWNGRADE", "privacy_propagation", f"downgrade requires {requirement}")
    for carrier in ("lineage_edge", "field_overlay", "export_manifest", "ai_request_record",
                    "delete_ledger_entry"):
        if carrier not in propagation.get("carriers", []):
            fail("PRV-TAG-CARRIER", "privacy_propagation", f"both axes must travel through {carrier}")
    if propagation.get("unknown_state_effect", {}).get(
            "external_egress_when_purpose_requires_personal_assessment") != "blocked":
        fail("PRV-UNKNOWN-EGRESS", "privacy_propagation",
             "an unknown personal assessment blocks external egress")
    if propagation.get("resolved_here") is not False:
        fail("PRV-DR-OPEN", "privacy_propagation", "DR-PRV-001 is not resolved by this contract")

    # -- referencias de privacidad y retención -----------------------------
    privacy_activities = {a["id"] for a in privacy.get("processing_activities", [])}
    privacy_policies = {p["id"] for p in privacy.get("retention_policies", [])}
    bound_activities = {b.get("activity_id") for b in model.get("privacy_activity_bindings", [])}
    missing_activities = sorted(REQUIRED_PRIVACY_ACTIVITIES - bound_activities)
    if missing_activities:
        fail("PRV-ACTIVITY-BINDING", "privacy_activity_bindings",
             f"missing privacy activity bindings: {missing_activities}")
    for activity_id in sorted(bound_activities - privacy_activities):
        fail("PRV-ACTIVITY-REFERENCE", "privacy_activity_bindings",
             f"unknown privacy activity {activity_id!r}")

    retention = model.get("retention_binding", {})
    bound_policies = {p.get("retention_policy_id") for p in retention.get("policies", [])}
    missing_policies = sorted(REQUIRED_RETENTION_POLICIES - bound_policies)
    if missing_policies:
        fail("PRV-RETENTION-BINDING", "retention_binding",
             f"missing retention bindings: {missing_policies}")
    for policy_id in sorted(bound_policies - privacy_policies):
        fail("PRV-RETENTION-REFERENCE", "retention_binding",
             f"unknown retention policy {policy_id!r}")
    if retention.get("numeric_duration_declared_here") is not False:
        fail("PRV-RETENTION-DURATION", "retention_binding", "L-01 owns durations, not this contract")
    for text in _strings(retention):
        if DURATION_PATTERN.search(text):
            fail("PRV-RETENTION-DURATION", "retention_binding",
                 f"numeric retention duration is not decided yet: {text!r}")
    tombstone = retention.get("tombstone_behaviour", {})
    if tombstone.get("personal_payload_retained_as_lineage_excuse") is not False:
        fail("PRV-TOMBSTONE", "retention_binding",
             "lineage is never an excuse to keep deleted personal payload")
    if tombstone.get("restore_reapplies_tombstones_before_service_reopen") is not True:
        fail("PRV-TOMBSTONE", "retention_binding",
             "restore reapplies tombstones before the service reopens")

    # -- vínculo canónico dinámico -----------------------------------------
    binding = model.get("canonical_binding", {})
    if binding.get("parallel_list_maintained") is not False:
        fail("LIN-CANONICAL-BINDING", "canonical_binding",
             "a parallel list would give false coverage; derive dynamically")
    declared = set(binding.get("entities_requiring_lineage", []))
    expected = {e["id"] for e in canonical.get("entities", []) if e.get("lineage_required")}
    if declared != expected:
        fail("LIN-CANONICAL-COVERAGE", "canonical_binding",
             f"lineage_required entities out of sync: missing={sorted(expected - declared)} "
             f"unexpected={sorted(declared - expected)}")

    # -- vínculos DFD y threat model ---------------------------------------
    dfd_controls = _ids(dfd.get("control_catalog", []))
    if "C-LINEAGE" not in dfd_controls:
        fail("LIN-DFD-CONTROL", "dfd.controls", "DFD must retain C-LINEAGE")
    dfd_flows = {flow.get("id"): flow for flow in dfd.get("flows", [])}
    for flow_id in sorted(REQUIRED_DFD_LINEAGE_FLOWS):
        flow = dfd_flows.get(flow_id)
        if flow is None or "C-LINEAGE" not in flow.get("controls", []):
            fail("LIN-DFD-FLOW", f"dfd.flows[{flow_id}]",
                 f"{flow_id} must enforce C-LINEAGE")

    risk_by_id = {risk.get("id"): risk for risk in threats.get("risks", [])}
    for risk_id in sorted(REQUIRED_LINEAGE_RISKS):
        risk = risk_by_id.get(risk_id)
        if risk is None or "C-LINEAGE" not in risk.get("controls", []) or \
                "A05" not in risk.get("assets", []):
            fail("LIN-THREAT-BINDING", f"threats.risks[{risk_id}]",
                 f"{risk_id} must bind lineage asset A05 and control C-LINEAGE")

    # -- pruebas, gates y decisiones ----------------------------------------
    missing_tests = sorted(REQUIRED_TEST_IDS - _ids(model.get("required_tests", [])))
    if missing_tests:
        fail("LIN-TEST-COVERAGE", "required_tests", f"missing required tests: {missing_tests}")
    for gate in model.get("gates", []):
        if gate.get("status") != "not_met" or \
                str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("LIN-GATE-STATUS", f"gates[{gate.get('id')}]",
                 "an agent cannot mark a gate as met")
    for decision in model.get("unresolved_decisions", []):
        if decision.get("state") != "pending_human":
            fail("LIN-DECISION-STATE", f"unresolved_decisions[{decision.get('id')}]",
                 "unresolved decisions stay pending_human")

    # -- plan de transformacion ------------------------------------------
    # Las seis etapas viven en un plan por columna, y el contrato tiene que
    # decirlo de forma comprobable: sin esto, la representacion hibrida seria
    # una decision de implementacion que nadie puede auditar.
    plan = model.get("transform_plan_contract")
    if not isinstance(plan, dict):
        fail("LIN-PLAN-CONTRACT", "transform_plan_contract",
             "the transform plan needs a declared contract")
    else:
        if plan.get("on_incomplete") != "block_publication":
            fail("LIN-PLAN-INCOMPLETE", "transform_plan_contract.on_incomplete",
                 "a field without its stages blocks publication")
        if plan.get("average_coverage_allowed") is not False:
            fail("LIN-PLAN-COVERAGE", "transform_plan_contract",
                 "coverage is per field, never an average")
        binding = plan.get("binding") or {}
        if sorted(binding.get("keys") or []) != ["engine_release_id",
                                                 "mapping_version_id"]:
            fail("LIN-PLAN-BINDING", "transform_plan_contract.binding",
                 "a plan is bound to one mapping version and one engine release")
        if binding.get("unique") is not True:
            fail("LIN-PLAN-BINDING", "transform_plan_contract.binding",
                 "the binding must be unique or two plans could explain one dataset")
        declared = {item.get("id") for item in plan.get("invariants", [])
                    if isinstance(item, dict)}
        for missing in sorted(REQUIRED_PLAN_INVARIANTS - declared):
            fail("LIN-PLAN-INVARIANT", f"transform_plan_contract.{missing}",
                 "required plan invariant is missing")
        step_fields = set(plan.get("step_required_fields") or [])
        for missing in sorted(REQUIRED_PLAN_STEP_FIELDS - step_fields):
            fail("LIN-PLAN-STEP-FIELD", f"transform_plan_contract.{missing}",
                 "a step without this field cannot be reproduced")
        leaking = sorted(step_fields & VALUE_BEARING_FIELDS)
        if leaking:
            fail("LIN-PLAN-VALUE", "transform_plan_contract.step_required_fields",
                 f"a plan step must not carry values: {leaking}")

    # -- excepcion por fila ----------------------------------------------
    override = model.get("row_override_contract")
    if not isinstance(override, dict):
        fail("LIN-OVERRIDE-CONTRACT", "row_override_contract",
             "the per-row exception path needs a declared contract")
    else:
        if override.get("immutable") is not True:
            fail("LIN-OVERRIDE-MUTABLE", "row_override_contract",
                 "an override is not edited; changing your mind is another override")
        if override.get("company_scoped") is not True:
            fail("LIN-OVERRIDE-SCOPE", "row_override_contract",
                 "an override belongs to one company")
        if override.get("on_missing_required_override") != "block_publication":
            fail("LIN-OVERRIDE-INCOMPLETE",
                 "row_override_contract.on_missing_required_override",
                 "a required override that is absent blocks publication")
        declared = {item.get("id") for item in override.get("invariants", [])
                    if isinstance(item, dict)}
        for missing in sorted(REQUIRED_OVERRIDE_INVARIANTS - declared):
            fail("LIN-OVERRIDE-INVARIANT", f"row_override_contract.{missing}",
                 "required override invariant is missing")
        fields = set(override.get("required_fields") or [])
        for missing in sorted(REQUIRED_OVERRIDE_FIELDS - fields):
            fail("LIN-OVERRIDE-FIELD", f"row_override_contract.{missing}",
                 "an override without this field cannot be audited")
        leaking = sorted(fields & VALUE_BEARING_FIELDS)
        if leaking:
            fail("LIN-OVERRIDE-VALUE", "row_override_contract.required_fields",
                 f"an override stores digests, never values: {leaking}")
        if override.get("critical_field_source") != "critical_overlay_fields":
            fail("LIN-OVERRIDE-CRITICAL", "row_override_contract",
                 "which fields need an independent approver comes from "
                 "critical_overlay_fields, not from a second list")

    # -- firma de una version del motor ----------------------------------
    approval = (model.get("engine_release_contract") or {}).get("approval_record")
    if not isinstance(approval, dict):
        fail("LIN-APPROVAL-RECORD", "engine_release_contract.approval_record",
             "the release signature needs a declared record")
    else:
        if approval.get("company_scoped") is not False:
            fail("LIN-APPROVAL-SCOPE", "engine_release_contract.approval_record",
                 "approving a build is a platform act, not company data")
        if approval.get("agent_can_self_approve") is not False:
            fail("LIN-APPROVAL-SELF", "engine_release_contract.approval_record",
                 "an agent cannot approve its own release")
        if approval.get("separation_from_build") is not True:
            fail("LIN-APPROVAL-BUILD", "engine_release_contract.approval_record",
                 "approval is separate from build")
        declared = {item.get("id") for item in approval.get("invariants", [])
                    if isinstance(item, dict)}
        for missing in sorted(REQUIRED_APPROVAL_INVARIANTS - declared):
            fail("LIN-APPROVAL-INVARIANT",
                 f"engine_release_contract.approval_record.{missing}",
                 "required approval invariant is missing")
        fields = set(approval.get("required_fields") or [])
        for missing in sorted(REQUIRED_APPROVAL_FIELDS - fields):
            fail("LIN-APPROVAL-FIELD",
                 f"engine_release_contract.approval_record.{missing}",
                 "a signature without this field does not answer for anything")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia executable lineage contract")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/domain/lineage-model.json"))
    parser.add_argument("--canonical", type=Path, default=Path("docs/domain/canonical-model.json"))
    parser.add_argument("--architecture", type=Path,
                        default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--idempotency", type=Path, default=Path("docs/domain/idempotency-dedupe.json"))
    parser.add_argument("--privacy", type=Path, default=Path("docs/privacy/privacy-map.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    parser.add_argument("--threats", type=Path,
                        default=Path("docs/security/threat-model.json"))
    args = parser.parse_args()
    errors = validate_model(
        json.loads(args.model.read_text(encoding="utf-8")),
        json.loads(args.canonical.read_text(encoding="utf-8")),
        json.loads(args.architecture.read_text(encoding="utf-8")),
        json.loads(args.idempotency.read_text(encoding="utf-8")),
        json.loads(args.privacy.read_text(encoding="utf-8")),
        json.loads(args.dfd.read_text(encoding="utf-8")),
        json.loads(args.threats.read_text(encoding="utf-8")),
    )
    print(json.dumps(
        {"errors": [error.as_dict() for error in errors], "ok": not errors},
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
