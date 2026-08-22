"""Validación ejecutable de la estrategia de pruebas de Fincilia (FNC-QA-002).

Solo biblioteca estándar. Determinista: no consulta red, reloj, entorno ni
aleatoriedad. Los contratos externos llegan por rutas explícitas y se leen en
modo read-only.

Expone la función pura `discover_test_ids`, que extrae los IDs de prueba de los
contratos ejecutables y del catálogo. El modelo no mantiene una lista paralela:
una lista paralela es drift disfrazado de cobertura.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK_ID = "FNC-QA-002"
REQUIRED_DATA_CEILING = "synthetic_only"

REQUIRED_LAYERS = {
    "unit", "property", "contract", "integration", "golden", "security", "e2e",
    "usability_accessibility",
}
REQUIRED_ORACLES = {"exact", "invariant", "metamorphic", "property", "adjudicated_snapshot"}
REQUIRED_PROTECTED_DOMAINS = {
    "rls_and_company_isolation", "money_and_decimal", "completeness_and_balances",
    "restore_and_tombstones", "security_and_egress",
}
REQUIRED_SECURITY_SCENARIOS = {
    "cross_company", "pool_context", "replay_idempotency", "worker_escape",
    "unauthorized_egress", "restore_resurrection",
}
REQUIRED_AI_ORACLES = {
    "semantic_field_accuracy", "abstention_rate", "adversarial_prompt_injection",
    "redaction_recall",
}
REQUIRED_TEST_CASE_FIELDS = {
    "test_id", "layer", "oracle_type", "owner_role", "reviewer_roles", "risk_refs",
    "command", "data_classification", "deterministic", "network_access", "state",
}
REQUIRED_EVIDENCE_FIELDS = {
    "evidence_id", "command", "runtime_version", "input_digests",
    "data_classification", "result", "produced_by_role", "reviewed_by_role",
}
REQUIRED_WAIVER_FIELDS = {"waiver_id", "owner_role", "reviewer_role", "reason", "expiry_gate"}
REQUIRED_QUARANTINE_FIELDS = {"owner_role", "reviewer_role", "reason", "expiry_gate"}
REQUIRED_GATES = {"S1-READY", "DRG-00", "DRG-01", "GA-01"}
COVERAGE_STATES = {"covered_executable", "covered_contract_only", "gap_declared"}
ACCEPTED_TOKENS = {"accepted", "approved", "met", "final", "signed", "done", "closed", "resolved"}
TEST_ID_PATTERN = re.compile(r"\bTST-[A-Z0-9]+-\d{3}\b")


@dataclass(frozen=True, order=True)
class QualityStrategyError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def discover_test_ids(repository_root: Path, sources: list[str]) -> set[str]:
    """Extrae dinámicamente los IDs de prueba de contratos y catálogo.

    Una fuente ausente no se ignora en silencio: el llamador compara el conjunto
    devuelto contra las fuentes declaradas y falla si alguna no existe.
    """
    found: set[str] = set()
    for relative in sorted(sources):
        candidate = repository_root / relative
        if not candidate.is_file():
            continue
        found.update(TEST_ID_PATTERN.findall(candidate.read_text(encoding="utf-8")))
    return found


def missing_sources(repository_root: Path, sources: list[str]) -> list[str]:
    return sorted(rel for rel in sources if not (repository_root / rel).is_file())


def _ids(items: Any, key: str = "id") -> list[str]:
    if not isinstance(items, list):
        return []
    return [item[key] for item in items if isinstance(item, dict) and key in item]


def validate_model(
    model: dict[str, Any],
    threat_model: dict[str, Any],
    architecture: dict[str, Any],
    discovered_ids: set[str],
    missing_discovery_sources: list[str] | None = None,
) -> list[QualityStrategyError]:
    errors: list[QualityStrategyError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(QualityStrategyError(code, location, message))

    # -- cabecera y techos ------------------------------------------------
    if model.get("schema_version") != 1:
        fail("QS-SCHEMA-VERSION", "schema_version", "schema_version must equal 1")
    if model.get("task_id") != REQUIRED_TASK_ID:
        fail("QS-TASK", "task_id", f"task_id must be {REQUIRED_TASK_ID}")
    if model.get("status") != "review_pending":
        fail("QS-STATUS", "status", "the strategy stays review_pending")
    if model.get("human_acceptance") != "pending":
        fail("QS-HUMAN-ACCEPTANCE", "human_acceptance", "an agent cannot record human acceptance")
    if model.get("data_ceiling") != REQUIRED_DATA_CEILING:
        fail("QS-DATA-CEILING", "data_ceiling", f"expected {REQUIRED_DATA_CEILING}")

    # -- capas -------------------------------------------------------------
    layers = model.get("layers", [])
    layer_by_id = {layer["id"]: layer for layer in layers if isinstance(layer, dict) and "id" in layer}
    missing_layers = sorted(REQUIRED_LAYERS - set(layer_by_id))
    if missing_layers:
        fail("QS-LAYER-COVERAGE", "layers", f"missing layers: {missing_layers}")
    for layer_id, layer in sorted(layer_by_id.items()):
        location = f"layers[{layer_id}]"
        if not layer.get("proves"):
            fail("QS-LAYER-SCOPE", location, "a layer must declare what it proves")
        if not layer.get("cannot_prove"):
            fail("QS-LAYER-SCOPE", location, "a layer must declare what it cannot prove")
        if not isinstance(layer.get("test_doubles_allowed"), bool):
            fail("QS-LAYER-SCOPE", location, "test_doubles_allowed must be declared")

    # -- oráculos ----------------------------------------------------------
    oracles = model.get("oracle_types", [])
    oracle_by_id = {o["id"]: o for o in oracles if isinstance(o, dict) and "id" in o}
    missing_oracles = sorted(REQUIRED_ORACLES - set(oracle_by_id))
    if missing_oracles:
        fail("QS-ORACLE-COVERAGE", "oracle_types", f"missing oracle types: {missing_oracles}")
    for oracle_id, oracle in sorted(oracle_by_id.items()):
        if oracle.get("money_safe") is not True:
            fail("QS-MONEY-FLOAT", f"oracle_types[{oracle_id}]",
                 "an oracle used for money must be exact, never approximate")
    snapshot = oracle_by_id.get("adjudicated_snapshot", {})
    if snapshot.get("auto_update_allowed") is not False:
        fail("QS-SNAPSHOT-AUTOUPDATE", "oracle_types[adjudicated_snapshot]",
             "a snapshot is never updated automatically; adjudication is human")
    if snapshot.get("requires_adjudication") is not True:
        fail("QS-SNAPSHOT-AUTOUPDATE", "oracle_types[adjudicated_snapshot]",
             "a snapshot requires explicit adjudication")

    # -- política de IDs y descubrimiento dinámico -------------------------
    id_policy = model.get("id_policy", {})
    if id_policy.get("parallel_fixed_list_maintained") is not False:
        fail("QS-FIXED-LIST-DRIFT", "id_policy",
             "a parallel fixed list of test IDs simulates coverage; discover dynamically")
    if id_policy.get("unknown_id_effect") != "reject" or \
            id_policy.get("duplicate_id_effect") != "reject":
        fail("QS-ID-POLICY", "id_policy", "unknown and duplicate IDs must be rejected")
    for source in missing_discovery_sources or []:
        fail("QS-DISCOVERY-SOURCE", "id_policy",
             f"declared discovery source does not exist: {source}")

    # -- matriz riesgo -> control -> prueba -> evidencia -------------------
    risks = {risk["id"]: risk for risk in threat_model.get("risks", [])}
    matrix = model.get("risk_control_matrix", [])
    seen_rows: set[str] = set()
    covered_risks: set[str] = set()

    for row in matrix:
        risk_id = row.get("risk_id", "<missing>")
        location = f"risk_control_matrix[{risk_id}]"
        if risk_id in seen_rows:
            fail("QS-ID-DUPLICATE", location, "duplicate risk row")
        seen_rows.add(risk_id)
        if risk_id not in risks:
            fail("QS-RISK-REFERENCE", location, f"unknown risk {risk_id!r}")
            continue
        covered_risks.add(risk_id)

        severity = risks[risk_id]["inherent"]["severity"]
        if row.get("risk_severity") != severity:
            fail("QS-RISK-SEVERITY", location,
                 f"severity drift: model says {row.get('risk_severity')!r}, "
                 f"threat model says {severity!r}")

        state = row.get("coverage_state")
        if state not in COVERAGE_STATES:
            fail("QS-COVERAGE-STATE", location, f"unknown coverage state {state!r}")
            continue

        test_ids = row.get("test_ids", [])
        duplicates = sorted({t for t in test_ids if test_ids.count(t) > 1})
        if duplicates:
            fail("QS-ID-DUPLICATE", location, f"duplicate test ids: {duplicates}")
        for test_id in sorted(set(test_ids) - discovered_ids):
            fail("QS-ID-UNKNOWN", location,
                 f"test id {test_id!r} is not discoverable from any contract or the catalogue")

        if severity in {"critical", "high"}:
            if state in {"covered_executable", "covered_contract_only"} and not test_ids:
                fail("QS-RISK-UNCOVERED", location,
                     "a critical or high risk claiming coverage needs at least one test id")
            if not row.get("evidence_ref"):
                fail("QS-RISK-UNCOVERED", location,
                     "a critical or high risk needs an evidence reference")
        if state == "gap_declared":
            for field in ("gap_owner_role", "gap_gate", "gap_reason"):
                if not row.get(field):
                    fail("QS-RISK-GAP-UNOWNED", location,
                         f"a declared gap needs {field}")
            if row.get("blocks_gate") is not True:
                fail("QS-RISK-GAP-UNOWNED", location, "a declared gap must block its gate")

        for layer_id in row.get("test_layers", []):
            if layer_id not in layer_by_id:
                fail("QS-LAYER-REFERENCE", location, f"unknown layer {layer_id!r}")
        if str(row.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("QS-RISK-ACCEPTANCE", location, "an agent cannot accept a residual risk")
        owner = row.get("owner_role")
        if owner and owner in set(row.get("reviewer_roles", [])):
            fail("QS-OWNER-INDEPENDENCE", location, "owner cannot be its own reviewer")

    missing_risks = sorted(set(risks) - covered_risks)
    if missing_risks:
        fail("QS-RISK-UNCOVERED", "risk_control_matrix",
             f"risks absent from the matrix: {missing_risks}")

    # -- contratos de caso y evidencia -------------------------------------
    case_contract = model.get("test_case_contract", {})
    missing_case = sorted(REQUIRED_TEST_CASE_FIELDS - set(case_contract.get("required_fields", [])))
    if missing_case:
        fail("QS-CASE-FIELDS", "test_case_contract", f"missing case fields: {missing_case}")
    if case_contract.get("silent_skip_allowed") is not False:
        fail("QS-PROTECTED-SKIP", "test_case_contract", "a silent skip is never allowed")
    if case_contract.get("network_access_allowed") is not False:
        fail("QS-NETWORK-OR-CLOCK", "test_case_contract", "a test with network access is not evidence")

    evidence = model.get("evidence_contract", {})
    missing_evidence = sorted(REQUIRED_EVIDENCE_FIELDS - set(evidence.get("required_fields", [])))
    if missing_evidence:
        fail("QS-EVIDENCE-FIELDS", "evidence_contract",
             f"evidence without {missing_evidence} cannot be audited")
    if evidence.get("payload_included") is not False or evidence.get("secrets_included") is not False:
        fail("QS-EVIDENCE-FIELDS", "evidence_contract",
             "evidence records digests and results, never payloads or secrets")
    if set(evidence.get("data_classification_values", [])) != {"synthetic_only"}:
        fail("QS-FIXTURE-PROVENANCE", "evidence_contract",
             "evidence classification stays synthetic_only during E0")

    # -- fixtures ----------------------------------------------------------
    fixtures = model.get("data_and_fixture_policy", {})
    if fixtures.get("real_or_derived_allowed") is not False:
        fail("QS-FIXTURE-PROVENANCE", "data_and_fixture_policy",
             "real or real-derived fixtures are not allowed during E0")
    if fixtures.get("provenance_required") is not True or \
            fixtures.get("manifest_required") is not True:
        fail("QS-FIXTURE-PROVENANCE", "data_and_fixture_policy",
             "every fixture needs demonstrable provenance and a manifest")
    if fixtures.get("allowed_classification") != "synthetic_only":
        fail("QS-FIXTURE-PROVENANCE", "data_and_fixture_policy", "only synthetic fixtures")

    # -- dobles de prueba ---------------------------------------------------
    doubles = model.get("double_policy", {})
    allowed = set(doubles.get("allowed_layers", []))
    forbidden = set(doubles.get("forbidden_layers", []))
    overlap = sorted(allowed & forbidden)
    if overlap:
        fail("QS-DOUBLE-AS-INTEGRATION", "double_policy",
             f"layers cannot both allow and forbid doubles: {overlap}")
    for layer_id in sorted(allowed):
        if layer_id in layer_by_id and layer_by_id[layer_id].get("test_doubles_allowed") is not True:
            fail("QS-DOUBLE-AS-INTEGRATION", "double_policy",
                 f"layer {layer_id!r} does not admit doubles")
    for layer_id in ("integration", "security", "e2e"):
        if layer_id in allowed:
            fail("QS-DOUBLE-AS-INTEGRATION", "double_policy",
                 f"a double can never stand in for the {layer_id} layer")
    if doubles.get("double_counted_as_integration") is not False:
        fail("QS-DOUBLE-AS-INTEGRATION", "double_policy",
             "a mock is not an integration test")
    if not doubles.get("cannot_demonstrate"):
        fail("QS-DOUBLE-AS-INTEGRATION", "double_policy",
             "the policy must state what a double cannot demonstrate")

    # -- lanes de CI --------------------------------------------------------
    lanes = model.get("ci_lanes", [])
    lane_by_id = {lane["id"]: lane for lane in lanes if isinstance(lane, dict) and "id" in lane}
    for lane_id, lane in sorted(lane_by_id.items()):
        location = f"ci_lanes[{lane_id}]"
        for dependency in lane.get("depends_on", []):
            if dependency not in lane_by_id:
                fail("QS-LANE-REFERENCE", location, f"unknown lane dependency {dependency!r}")
            elif lane_by_id[dependency].get("order", 0) >= lane.get("order", 0):
                fail("QS-LANE-ORDER", location,
                     f"lane {lane_id!r} cannot depend on a lane that runs later or at the same time")

    # -- flaky, skip, quarantine, retry y waiver ---------------------------
    flake = model.get("flake_policy", {})
    if flake.get("retry_allowed") is not False or flake.get("retry_masks_flake") is not False:
        fail("QS-RETRY-MASKS-FLAKE", "flake_policy",
             "a retry that turns red into green hides a non-deterministic defect")
    if flake.get("skip_allowed") is not False or flake.get("silent_skip_allowed") is not False:
        fail("QS-PROTECTED-SKIP", "flake_policy", "a skip is never silent")
    if flake.get("known_failure_counts_as_pass") is not False:
        fail("QS-PROTECTED-SKIP", "flake_policy", "a known failure is not a pass")
    protected = set(flake.get("protected_control_domains", []))
    missing_protected = sorted(REQUIRED_PROTECTED_DOMAINS - protected)
    if missing_protected:
        fail("QS-PROTECTED-SKIP", "flake_policy",
             f"protected control domains missing: {missing_protected}")
    if flake.get("protected_domain_skip_allowed") is not False or \
            flake.get("protected_domain_quarantine_allowed") is not False:
        fail("QS-PROTECTED-SKIP", "flake_policy",
             "RLS, money, completeness, restore and security never skip or quarantine")
    missing_waiver = sorted(REQUIRED_WAIVER_FIELDS - set(flake.get("waiver_required_fields", [])))
    if missing_waiver:
        fail("QS-WAIVER-FIELDS", "flake_policy", f"a waiver needs {missing_waiver}")
    if flake.get("waiver_self_approval_allowed") is not False:
        fail("QS-WAIVER-FIELDS", "flake_policy", "a waiver cannot be self-approved")
    missing_quarantine = sorted(REQUIRED_QUARANTINE_FIELDS - set(flake.get("quarantine_requires", [])))
    if missing_quarantine:
        fail("QS-WAIVER-FIELDS", "flake_policy", f"quarantine needs {missing_quarantine}")

    # -- cobertura sin promedios -------------------------------------------
    coverage = model.get("coverage_policy", {})
    if coverage.get("average_hides_failure") is not False or \
            coverage.get("aggregate_percentage_as_gate") is not False:
        fail("QS-AVERAGE-COVERAGE", "coverage_policy",
             "an aggregate percentage hides the field, company or format that failed")
    for field in ("per_field_enumeration_required", "per_company_enumeration_required",
                  "per_format_enumeration_required"):
        if coverage.get(field) is not True:
            fail("QS-AVERAGE-COVERAGE", "coverage_policy", f"{field} must be true")
    if coverage.get("structural_coverage_is_not_correctness") is not True:
        fail("QS-AVERAGE-COVERAGE", "coverage_policy",
             "structural coverage is not accounting correctness")

    # -- mutación -----------------------------------------------------------
    mutation = model.get("mutation_policy", {})
    if mutation.get("required") is not True:
        fail("QS-MUTATION", "mutation_policy", "mutation testing is required")
    if mutation.get("surviving_mutant_effect") != "treated_as_missing_test":
        fail("QS-MUTATION", "mutation_policy", "a surviving mutant is a missing test")
    if not isinstance(mutation.get("minimum_mutants_per_validator"), int) or \
            mutation["minimum_mutants_per_validator"] < 1:
        fail("QS-MUTATION", "mutation_policy", "declare a minimum number of mutants")

    # -- seguridad ----------------------------------------------------------
    security = model.get("security_testing", {})
    missing_scenarios = sorted(REQUIRED_SECURITY_SCENARIOS - set(security.get("required_scenarios", [])))
    if missing_scenarios:
        fail("QS-SECURITY-SCENARIOS", "security_testing",
             f"missing security scenarios: {missing_scenarios}")
    if security.get("doubles_allowed") is not False:
        fail("QS-DOUBLE-AS-INTEGRATION", "security_testing",
             "security scenarios cannot be proven with doubles")
    security_layer = security.get("layer")
    if security_layer in layer_by_id and \
            layer_by_id[security_layer].get("test_doubles_allowed") is not False:
        fail("QS-LAYER-MISMATCH", "security_testing",
             f"layer {security_layer!r} admits doubles and cannot host security scenarios")
    if security.get("negative_tests_required") is not True:
        fail("QS-SECURITY-SCENARIOS", "security_testing", "negative tests are required")

    # -- contabilidad -------------------------------------------------------
    accounting = model.get("accounting_testing", {})
    if accounting.get("money_representation") != "exact_decimal":
        fail("QS-MONEY-FLOAT", "accounting_testing", "money uses exact decimal")
    if accounting.get("float_allowed") is not False or \
            accounting.get("approximate_comparison_allowed") is not False:
        fail("QS-MONEY-FLOAT", "accounting_testing",
             "float or approximate comparison is never valid for money")
    if accounting.get("unknown_or_partial_blocks_close") is not True:
        fail("QS-ACCOUNTING", "accounting_testing", "unknown or partial data blocks close")
    if accounting.get("segregation_of_duties_required") is not True:
        fail("QS-ACCOUNTING", "accounting_testing", "segregation of duties is required")
    if len(set(accounting.get("semantic_dates_distinct", []))) < 5:
        fail("QS-ACCOUNTING", "accounting_testing", "semantic dates must stay distinct")

    # -- IA ------------------------------------------------------------------
    ai = model.get("ai_testing", {})
    if ai.get("json_validity_is_sufficient_oracle") is not False:
        fail("QS-AI-SEMANTIC-ORACLE", "ai_testing",
             "valid JSON proves shape, not semantics; it is not an oracle")
    missing_ai = sorted(REQUIRED_AI_ORACLES - set(ai.get("required_oracles", [])))
    if missing_ai:
        fail("QS-AI-SEMANTIC-ORACLE", "ai_testing", f"missing AI oracles: {missing_ai}")
    for field in ("abstention_required", "redaction_fail_closed_required", "fallback_required",
                  "adjudicated_dataset_required", "drift_monitoring_required"):
        if ai.get(field) is not True:
            fail("QS-AI-SAFETY", "ai_testing", f"{field} must be true")
    if ai.get("model_has_financial_authority") is not False:
        fail("QS-AI-SAFETY", "ai_testing", "a model never holds financial authority")
    if ai.get("external_ai_enabled") is not False:
        fail("QS-AI-SAFETY", "ai_testing", "external AI stays disabled during E0")

    # -- performance ---------------------------------------------------------
    performance = model.get("performance_slo", {})
    if performance.get("thresholds_declared") is not False or \
            performance.get("invented_threshold_allowed") is not False:
        fail("QS-PERF-THRESHOLD", "performance_slo",
             "a threshold without an approved budget is invented")
    if performance.get("budget_state") != "pending_human" or \
            str(performance.get("budget_state", "")).lower() in ACCEPTED_TOKENS:
        fail("QS-PERF-THRESHOLD", "performance_slo", "the performance budget stays pending_human")
    if performance.get("measurement_required_before_threshold") is not True:
        fail("QS-PERF-THRESHOLD", "performance_slo", "measure before fixing a threshold")

    # -- accesibilidad --------------------------------------------------------
    a11y = model.get("accessibility_testing", {})
    if a11y.get("component_existence_counts_as_evidence") is not False:
        fail("QS-A11Y-EVIDENCE", "accessibility_testing",
             "the existence of a component is not an accessibility test")
    if a11y.get("human_testing_claimed") is not False:
        fail("QS-A11Y-EVIDENCE", "accessibility_testing",
             "human testing that has not happened cannot be claimed")
    if a11y.get("human_testing_state") != "pending_human":
        fail("QS-A11Y-EVIDENCE", "accessibility_testing", "human testing stays pending_human")
    if len(set(a11y.get("automated_scope", []))) < 4:
        fail("QS-A11Y-EVIDENCE", "accessibility_testing",
             "declare the automatable criteria being verified")

    # -- ownership y adjudicación ----------------------------------------------
    ownership = model.get("ownership", {})
    if ownership.get("author_is_sole_reviewer_allowed") is not False:
        fail("QS-OWNER-INDEPENDENCE", "ownership", "an author cannot be their sole reviewer")
    if ownership.get("expected_output_adjudicator_equals_code_author_allowed") is not False:
        fail("QS-ADJUDICATION-SOD", "ownership",
             "whoever changes the code cannot approve the expected output that change modifies")
    missing_domains = sorted(REQUIRED_PROTECTED_DOMAINS -
                             set(ownership.get("independent_review_required_domains", [])))
    if missing_domains:
        fail("QS-OWNER-INDEPENDENCE", "ownership",
             f"independent review required for: {missing_domains}")

    # -- pirámide por módulo ----------------------------------------------------
    modules = {module["id"] for module in architecture.get("modules", [])}
    for entry in model.get("pyramid_by_module", []):
        module_id = entry.get("module")
        if module_id not in modules:
            fail("QS-MODULE-REFERENCE", f"pyramid_by_module[{module_id}]",
                 f"unknown module {module_id!r}")
        if not entry.get("boundary"):
            fail("QS-MODULE-REFERENCE", f"pyramid_by_module[{module_id}]",
                 "each module declares its responsibility boundary")

    # -- gates y decisiones ------------------------------------------------------
    gate_ids = set(_ids(model.get("gates", [])))
    missing_gates = sorted(REQUIRED_GATES - gate_ids)
    if missing_gates:
        fail("QS-GATE-COVERAGE", "gates", f"missing gates: {missing_gates}")
    for gate in model.get("gates", []):
        if gate.get("status") != "not_met" or \
                str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("QS-GATE-STATUS", f"gates[{gate.get('id')}]",
                 "an agent cannot mark a gate as met")
    for decision in model.get("unresolved_decisions", []):
        if decision.get("state") != "pending_human":
            fail("QS-DECISION-STATE", f"unresolved_decisions[{decision.get('id')}]",
                 "an agent cannot close a human decision")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia executable test strategy")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/testing/test-strategy.json"))
    parser.add_argument("--threat-model", type=Path, default=Path("docs/security/threat-model.json"))
    parser.add_argument("--architecture", type=Path,
                        default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    model = json.loads(args.model.read_text(encoding="utf-8"))
    threat_model = json.loads(args.threat_model.read_text(encoding="utf-8"))
    architecture = json.loads(args.architecture.read_text(encoding="utf-8"))
    sources = model.get("id_policy", {}).get("discovery_sources", [])
    discovered = discover_test_ids(args.root, sources)
    absent = missing_sources(args.root, sources)

    errors = validate_model(model, threat_model, architecture, discovered, absent)
    print(json.dumps(
        {"errors": [error.as_dict() for error in errors],
         "discovered_test_ids": len(discovered),
         "ok": not errors},
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
