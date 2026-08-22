"""Descubrimiento, clasificación y reconciliación del catálogo de pruebas (FNC-QA-004).

Distingue tres conjuntos que la auditoría encontró mezclados:

1. IDs **requeridos por contratos ejecutables**;
2. IDs **documentados** en el catálogo Markdown;
3. IDs **materializados** por tests o manifiestos.

Un ID contractual ausente del catálogo es *drift de trazabilidad*. Un ID del
catálogo sin contrato puede ser una especificación runtime planeada legítima.
No son lo mismo y no se cuentan juntos.

Solo biblioteca estándar. Determinista y offline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.test_catalog.extractors import (
    EXTRACTOR_APPLICABILITY,
    EXTRACTORS,
    RANGE_PATTERN,
    SOURCE_CLASS_PRECEDENCE,
    TEST_ID_EXACT,
    Provenance,
    discover_files,
    sha256_file,
)

REQUIRED_TASK_ID = "FNC-QA-004"
ACCEPTED_TOKENS = {"accepted", "approved", "met", "final", "signed", "done", "closed", "resolved"}

STATES = (
    "contract_required", "catalog_planned", "implemented", "evidenced",
    "waived_pending_human", "orphan", "conflict",
)


@dataclass(frozen=True, order=True)
class CatalogError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def resolve_inside(root: Path, relative: str) -> Path | None:
    """Resuelve manteniendo la ruta dentro de la raíz declarada."""
    if not relative or relative.startswith(("/", "\\")):
        return None
    if len(relative) > 1 and relative[1] == ":":
        return None
    if ".." in Path(relative).parts:
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


# --------------------------------------------------------------------------- #
# Descubrimiento
# --------------------------------------------------------------------------- #

def discover(model: dict[str, Any], root: Path) -> dict[str, Any]:
    """Inventario estable y ordenado de identificadores con toda su procedencia."""
    allowlist = model.get("file_allowlist", {})
    include = allowlist.get("include_globs", [])
    files = discover_files(root, include, allowlist.get("excluded_path_globs", []))

    observations: dict[str, list[Provenance]] = {}
    scanned: list[dict[str, str]] = []
    range_mentions: list[dict[str, str]] = []

    for relative in files:
        absolute = root / relative
        digest = sha256_file(absolute)
        scanned.append({"path": relative.as_posix(), "digest": digest})
        for extractor_id in EXTRACTOR_APPLICABILITY.get(relative.suffix.lower(), ()):  # noqa: E501
            for identifier, provenance in EXTRACTORS[extractor_id](root, relative, digest):
                observations.setdefault(identifier, []).append(provenance)
                if provenance.detail == "narrative_range_not_expanded":
                    range_mentions.append({"path": provenance.path,
                                           "locator": provenance.locator,
                                           "anchor_id": identifier})

    inventory = []
    for identifier in sorted(observations):
        provenances = sorted(set(observations[identifier]))
        classes = {p.source_class for p in provenances}
        inventory.append({
            "test_id": identifier,
            "well_formed": bool(TEST_ID_EXACT.match(identifier)),
            "namespace": identifier.split("-")[1] if identifier.count("-") >= 2 else "",
            "source_classes": sorted(classes),
            "primary_source_class": next(
                (c for c in SOURCE_CLASS_PRECEDENCE if c in classes), "unknown"),
            "provenance": [p.as_dict() for p in provenances],
        })

    return {
        "root": root.resolve().name,
        "scanned_files": sorted(scanned, key=lambda item: item["path"]),
        "scanned_file_count": len(scanned),
        "identifier_count": len(inventory),
        "narrative_ranges_not_expanded": sorted(
            range_mentions, key=lambda item: (item["path"], item["locator"])),
        "identifiers": inventory,
    }


# --------------------------------------------------------------------------- #
# Clasificación y reconciliación
# --------------------------------------------------------------------------- #

def classify(model: dict[str, Any], inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Asigna estado a cada ID a partir de sus clases de fuente."""
    waived = {w["test_id"]: w for w in model.get("waivers", [])}
    evidence_paths = set(model.get("evidence_sources", {}).get("paths", []))

    classified = []
    for entry in inventory["identifiers"]:
        classes = set(entry["source_classes"])
        provenance_paths = {p["path"] for p in entry["provenance"]}
        states: list[str] = []

        if "contract_definition" in classes:
            states.append("contract_required")
        if "catalog_row" in classes and "contract_definition" not in classes:
            states.append("catalog_planned")
        if "implementation" in classes:
            states.append("implemented")
            if provenance_paths & evidence_paths or any(
                    p["source_class"] == "reference"
                    and p["path"] in evidence_paths for p in entry["provenance"]):
                states.append("evidenced")
        if entry["test_id"] in waived:
            states.append("waived_pending_human")
        # Es huérfano cualquier identificador sin clase de definición: da igual que
        # exista una implementación. Un test que nadie exige es tan huérfano
        # como una mención suelta, y esconde la pregunta de por qué se escribió.
        if not (classes & {"contract_definition", "catalog_row"}):
            states.append("orphan")

        # Definiciones incompatibles: dos contratos que definen la misma ID con
        # detalle sustantivo distinto.
        definitions = {p["detail"].strip() for p in entry["provenance"]
                       if p["source_class"] == "contract_definition" and p["detail"].strip()}
        if len(definitions) > 1:
            states.append("conflict")

        classified.append({**entry, "states": sorted(set(states)),
                           "conflicting_definitions": sorted(definitions)
                           if len(definitions) > 1 else []})
    return classified


def reconcile(model: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Reconciliación contract ↔ catalog ↔ implementation ↔ evidence."""
    classified = classify(model, inventory)
    rules = {rule["id"]: rule for rule in model.get("finding_rules", [])}

    findings: list[dict[str, Any]] = []

    def add(rule_id: str, test_id: str, detail: str) -> None:
        rule = rules.get(rule_id, {})
        findings.append({
            "finding_id": rule_id,
            "test_id": test_id,
            "severity": rule.get("severity", "unknown"),
            "owner_role": rule.get("owner_role", "UNASSIGNED"),
            "gate": rule.get("gate", "UNASSIGNED"),
            "classification": rule.get("classification", "unknown"),
            "detail": detail,
        })

    for entry in classified:
        identifier = entry["test_id"]
        states = set(entry["states"])
        classes = set(entry["source_classes"])

        if not entry["well_formed"]:
            add("TCM-ID-MALFORMED", identifier, "identifier does not match the canonical syntax")
        elif entry["namespace"] not in set(model.get("id_syntax", {}).get("namespaces", [])):
            add("TCM-NAMESPACE-UNKNOWN", identifier, f"namespace {entry['namespace']!r} is not declared")

        if "conflict" in states:
            add("TCM-DEFINITION-CONFLICT", identifier,
                f"incompatible definitions: {entry['conflicting_definitions']}")

        if "contract_required" in states and "catalog_row" not in classes:
            add("TCM-CONTRACT-NOT-IN-CATALOG", identifier,
                "a contract requires this test and the catalogue does not document it")

        if "catalog_planned" in states and "implementation" not in classes:
            add("TCM-CATALOG-PLANNED", identifier,
                "documented runtime specification with neither contract nor implementation")

        if "contract_required" in states and "implementation" not in classes:
            add("TCM-CONTRACT-NOT-IMPLEMENTED", identifier,
                "a contract requires this test and no implementation materialises it")

        if "orphan" in states:
            add("TCM-ORPHAN", identifier,
                "referenced or mentioned but defined by no contract and no catalogue row")

    counts_by_state: dict[str, int] = {state: 0 for state in STATES}
    for entry in classified:
        for state in entry["states"]:
            counts_by_state[state] = counts_by_state.get(state, 0) + 1

    counts_by_finding: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for finding in findings:
        counts_by_finding[finding["finding_id"]] = counts_by_finding.get(finding["finding_id"], 0) + 1
        counts_by_severity[finding["severity"]] = counts_by_severity.get(finding["severity"], 0) + 1

    blocking = sorted({f["finding_id"] for f in findings
                       if f["severity"] in set(model.get("blocking_severities", []))})

    return {
        "identifiers": classified,
        "findings": sorted(findings, key=lambda f: (f["finding_id"], f["test_id"])),
        "counts_by_state": dict(sorted(counts_by_state.items())),
        "counts_by_finding": dict(sorted(counts_by_finding.items())),
        "counts_by_severity": dict(sorted(counts_by_severity.items())),
        "blocking_finding_ids": blocking,
        "scanned_file_count": inventory["scanned_file_count"],
        "narrative_ranges_not_expanded": inventory["narrative_ranges_not_expanded"],
    }


# --------------------------------------------------------------------------- #
# Validación estructural del modelo
# --------------------------------------------------------------------------- #

def validate_model(model: dict[str, Any]) -> list[CatalogError]:
    """Valida el modelo en sí, con independencia del estado del repositorio.

    Separar esto de la reconciliación es deliberado: `model valid` y
    `repository has reconciliation findings` son dos hechos distintos y
    confundirlos llevaría a rebajar la política para forzar verde.
    """
    errors: list[CatalogError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(CatalogError(code, location, message))

    if model.get("schema_version") != 1:
        fail("TCM-SCHEMA-VERSION", "schema_version", "schema_version must equal 1")
    if model.get("task_id") != REQUIRED_TASK_ID:
        fail("TCM-TASK", "task_id", f"task_id must be {REQUIRED_TASK_ID}")
    if model.get("status") != "review_pending":
        fail("TCM-STATUS", "status", "the model stays review_pending")
    if model.get("human_acceptance") != "pending":
        fail("TCM-HUMAN-ACCEPTANCE", "human_acceptance", "an agent cannot record human acceptance")
    if model.get("data_ceiling") != "synthetic_only":
        fail("TCM-DATA-CEILING", "data_ceiling", "expected synthetic_only")

    syntax = model.get("id_syntax", {})
    if not syntax.get("pattern"):
        fail("TCM-SYNTAX", "id_syntax", "declare the canonical identifier syntax")
    if not syntax.get("namespaces"):
        fail("TCM-SYNTAX", "id_syntax", "declare the allowed namespaces")

    declared_classes = {c["id"] for c in model.get("source_classes", [])}
    if set(SOURCE_CLASS_PRECEDENCE) - declared_classes:
        fail("TCM-SOURCE-CLASSES", "source_classes",
             f"missing source classes: {sorted(set(SOURCE_CLASS_PRECEDENCE) - declared_classes)}")
    precedence = [c["id"] for c in sorted(model.get("source_classes", []),
                                          key=lambda c: c.get("precedence", 99))]
    if precedence != list(SOURCE_CLASS_PRECEDENCE):
        fail("TCM-SOURCE-CLASSES", "source_classes",
             "declared precedence does not match the implemented precedence")

    declared_states = set(model.get("states", []))
    if set(STATES) - declared_states:
        fail("TCM-STATES", "states", f"missing states: {sorted(set(STATES) - declared_states)}")

    declared_extractors = {e["id"] for e in model.get("extractors", [])}
    if declared_extractors != set(EXTRACTORS):
        fail("TCM-EXTRACTOR-DRIFT", "extractors",
             f"model and code disagree: only_model={sorted(declared_extractors - set(EXTRACTORS))} "
             f"only_code={sorted(set(EXTRACTORS) - declared_extractors)}")
    for extractor in model.get("extractors", []):
        location = f"extractors[{extractor.get('id')}]"
        if extractor.get("source_class") not in declared_classes:
            fail("TCM-EXTRACTOR-CLASS", location, "unknown source class")
        if not extractor.get("version"):
            fail("TCM-EXTRACTOR-VERSION", location, "an extractor declares its version")

    allowlist = model.get("file_allowlist", {})
    if not allowlist.get("include_globs"):
        fail("TCM-ALLOWLIST", "file_allowlist", "declare which files are scanned")
    if not allowlist.get("excluded_directory_names"):
        fail("TCM-ALLOWLIST", "file_allowlist", "declare deterministic exclusions")
    if not allowlist.get("excluded_path_globs"):
        fail("TCM-ALLOWLIST", "file_allowlist", "declare non-authoritative artifact exclusions")
    if allowlist.get("follow_symlinks") is not False:
        fail("TCM-SYMLINK", "file_allowlist", "symlinks are never followed")

    if model.get("aggregate_id_policy", {}).get("expand_ranges") is not False:
        fail("TCM-RANGE-EXPANSION", "aggregate_id_policy",
             "expanding a narrative range would invent coverage nobody wrote")

    projection = model.get("projection_contract", {})
    if projection.get("writes_test_catalog") is not False:
        fail("TCM-PROJECTION-WRITE", "projection_contract",
             "the projection is data for a human; it never edits TEST_CATALOG.md")
    if projection.get("output") != "machine_readable_diff":
        fail("TCM-PROJECTION-WRITE", "projection_contract", "the projection is a diff, not a file write")

    rule_ids = {r["id"] for r in model.get("finding_rules", [])}
    for required in ("TCM-CONTRACT-NOT-IN-CATALOG", "TCM-CATALOG-PLANNED",
                     "TCM-DEFINITION-CONFLICT", "TCM-ID-MALFORMED",
                     "TCM-NAMESPACE-UNKNOWN", "TCM-ORPHAN",
                     "TCM-CONTRACT-NOT-IMPLEMENTED"):
        if required not in rule_ids:
            fail("TCM-RULE-COVERAGE", "finding_rules", f"missing finding rule {required}")
    for rule in model.get("finding_rules", []):
        location = f"finding_rules[{rule.get('id')}]"
        for field in ("severity", "owner_role", "gate", "classification"):
            if not rule.get(field):
                fail("TCM-RULE-FIELDS", location, f"a finding rule declares {field}")
        if rule.get("classification") not in {"traceability_drift", "planned_backlog",
                                              "integrity_error", "hygiene"}:
            fail("TCM-RULE-FIELDS", location, "unknown finding classification")

    if not model.get("blocking_severities"):
        fail("TCM-BLOCKING", "blocking_severities", "declare which severities block")

    if model.get("reporting", {}).get("single_aggregate_score_as_gate") is not False:
        fail("TCM-AGGREGATE-SCORE", "reporting",
             "a single aggregate percentage would hide the critical gap")
    if model.get("reporting", {}).get("per_finding_breakdown_required") is not True:
        fail("TCM-AGGREGATE-SCORE", "reporting", "report per finding, state, owner and gate")

    for waiver in model.get("waivers", []):
        location = f"waivers[{waiver.get('waiver_id', '<missing>')}]"
        for field in ("waiver_id", "test_id", "owner_role", "reviewer_role", "reason",
                      "expiry_gate", "gate"):
            if not waiver.get(field):
                fail("TCM-WAIVER-FIELDS", location, f"a waiver declares {field}")
        if waiver.get("owner_role") and waiver.get("owner_role") == waiver.get("reviewer_role"):
            fail("TCM-WAIVER-FIELDS", location, "a waiver cannot be self-approved")
        if waiver.get("state") != "pending_human":
            fail("TCM-WAIVER-FIELDS", location, "a waiver stays pending_human")

    retirement = model.get("retirement_policy", {})
    if retirement.get("tombstone_required") is not True:
        fail("TCM-RETIREMENT", "retirement_policy",
             "a retired identifier keeps a tombstone or superseded_by")
    for tombstone in model.get("tombstones", []):
        location = f"tombstones[{tombstone.get('test_id')}]"
        if not tombstone.get("superseded_by") and not tombstone.get("reason"):
            fail("TCM-RETIREMENT", location, "a tombstone declares superseded_by or a reason")

    for gate in model.get("gates", []):
        if gate.get("status") != "not_met" or \
                str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("TCM-GATE-STATUS", f"gates[{gate.get('id')}]", "an agent cannot mark a gate as met")
    for decision in model.get("unresolved_decisions", []):
        if decision.get("state") != "pending_human":
            fail("TCM-DECISION-STATE", f"unresolved_decisions[{decision.get('id')}]",
                 "an agent cannot close a human decision")

    if not model.get("anti_promises"):
        fail("TCM-ANTI-PROMISES", "anti_promises",
             "state explicitly what a green run does not prove")

    return sorted(set(errors))


def project(model: dict[str, Any], reconciliation: dict[str, Any]) -> dict[str, Any]:
    """Propuesta machine-readable para el Integration Steward. **No escribe nada.**"""
    additions = []
    reviews = []
    for finding in reconciliation["findings"]:
        if finding["finding_id"] == "TCM-CONTRACT-NOT-IN-CATALOG":
            entry = next(e for e in reconciliation["identifiers"]
                         if e["test_id"] == finding["test_id"])
            definition = next((p["detail"] for p in entry["provenance"]
                               if p["source_class"] == "contract_definition" and p["detail"]), "")
            source = next((p["path"] for p in entry["provenance"]
                           if p["source_class"] == "contract_definition"), "")
            additions.append({
                "test_id": finding["test_id"],
                "proposed_row": {"id": finding["test_id"],
                                 "description": definition[:120],
                                 "declared_by_contract": source},
                "owner_role": finding["owner_role"],
                "gate": finding["gate"],
            })
        elif finding["finding_id"] in {"TCM-DEFINITION-CONFLICT", "TCM-ID-MALFORMED",
                                       "TCM-NAMESPACE-UNKNOWN", "TCM-ORPHAN"}:
            reviews.append({"test_id": finding["test_id"], "finding_id": finding["finding_id"],
                            "detail": finding["detail"], "owner_role": finding["owner_role"]})
    return {
        "target_document": model.get("projection_contract", {}).get("target_document"),
        "writes_target_document": False,
        "proposed_catalog_additions": sorted(additions, key=lambda a: a["test_id"]),
        "requires_human_review": sorted(reviews, key=lambda r: (r["finding_id"], r["test_id"])),
        "planned_backlog_not_drift": sorted(
            f["test_id"] for f in reconciliation["findings"]
            if f["finding_id"] == "TCM-CATALOG-PLANNED"),
        "note": "Datos para una decisión humana. Este comando nunca edita el catálogo.",
    }


def load_model(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
