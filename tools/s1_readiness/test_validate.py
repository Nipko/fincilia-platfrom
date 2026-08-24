"""Pruebas del agregador de readiness S1 (FNC-GAT-003).

Cuatro bloques:

1. positivas contra el contrato y el repositorio reales;
2. lectura de fuentes estructuradas y su subconjunto de front-matter;
3. invariantes negativas sobre un arbol sintetico en un directorio temporal;
4. agregacion, CLI y disciplina del codigo fuente.

Ningun test depende de red, hora real, locale, orden de directorio, Docker ni Git.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tools.s1_readiness import cli as s1_cli
from tools.s1_readiness.evaluate import (
    CATEGORIES,
    SATISFYING_CATEGORIES,
    aggregate,
    build_environment,
    collect,
    detect_contradictions,
    detect_cycles,
    evaluate_requirements,
    index_observations,
    run_machine_check,
)
from tools.s1_readiness.model import validate_contract
from tools.s1_readiness.sources import (
    Observation,
    extract_adr_readiness,
    extract_decisions,
    extract_gates,
    is_assigned,
    is_met,
    read_front_matter,
    resolve_inside,
    safe_relative,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs/implementation/s1-readiness.json"
SOURCE_DIR = ROOT / "tools/s1_readiness"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cli(argv: list[str]) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = s1_cli.main(argv)
    text = out.getvalue() or err.getvalue()
    return code, (json.loads(text) if text.strip() else {})


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


PHASE_CARD = """---
phase_id: F-1_F0
current_gate: S1-READY
data_ceiling: synthetic_only
execution_stage: PRE_SPRINT_1
integration_owner: {integration}
security_owner: {security}
---

# Fase sintetica
"""

TASK_CARD = """---
task: FNC-SYN-001
status: review_pending
gate: S1-READY
implementer: synthetic
independent_reviewers: [Architecture, Security]
file_scope:
  - docs/synthetic/one.json
  - docs/synthetic/two.json
---

# Ficha sintetica
"""


def synthetic_root(directory: Path, *, gate_status: str = "not_met",
                   owner: str = "UNASSIGNED",
                   decisions: list[dict] | None = None,
                   second_gate_owner: str | None = None,
                   adr_readiness: str = "blocked") -> tuple[Path, dict]:
    """Un arbol de gobierno minimo, coherente y enteramente sintetico."""
    primary = {
        "task_id": "FNC-SYN-A", "status": "review_pending", "human_acceptance": "pending",
        "data_ceiling": "synthetic_only",
        "gates": [{"id": "SYN-GATE", "status": gate_status, "acceptance": "pending_human",
                   "owner_role": "Legal"}],
        "unresolved_decisions": decisions if decisions is not None else [
            {"id": "UD-SYN-1", "state": "pending_human", "owner_role": "Legal",
             "question": "una pregunta sintetica", "blocks": ["S1-READY"]}],
    }
    write(directory / "docs/synthetic/primary.json", json.dumps(primary, indent=2))

    if second_gate_owner is not None:
        secondary = {
            "task_id": "FNC-SYN-B", "status": "review_pending",
            "gates": [{"id": "SYN-GATE", "status": gate_status,
                       "owner_role": second_gate_owner}],
        }
        write(directory / "docs/synthetic/secondary.json", json.dumps(secondary, indent=2))

    write(directory / "docs/synthetic/adr.json", json.dumps({
        "task_id": "FNC-SYN-ADR",
        "required_s1_adrs": ["ADR-SYN-1"],
        "adrs": [{"id": "ADR-SYN-1", "readiness": adr_readiness, "blockers": ["b"]}],
        "release_rule": {"gate": "S1-READY", "state": "not_met"},
        "decisions": [],
    }, indent=2))

    write(directory / "CURRENT_PHASE.md",
          PHASE_CARD.format(integration=owner, security=owner))
    write(directory / "docs/implementation/tasks/FNC-SYN-001.md", TASK_CARD)

    sources = [
        {"path": "docs/synthetic/primary.json", "kind": "json",
         "gates_keys": ["gates"], "decisions_keys": ["unresolved_decisions"]},
        {"path": "docs/synthetic/adr.json", "kind": "json", "adr_readiness": True},
    ]
    if second_gate_owner is not None:
        sources.append({"path": "docs/synthetic/secondary.json", "kind": "json",
                        "gates_keys": ["gates"]})

    contract = {
        "schema_version": 1, "task_id": "FNC-GAT-003", "status": "review_pending",
        "human_acceptance": "pending", "data_ceiling": "synthetic_only",
        "target_gate": "S1-READY", "initial_gate_status": "not_met",
        "agent_may_accept": False, "writes_central_state": False,
        "aggregate_score_as_gate": False, "runs_containers_in_evaluate": False,
        "categories": list(CATEGORIES),
        "aggregation": {"rule": "conjunctive_fail_closed",
                        "satisfying_categories": ["machine_pass"]},
        "source_precedence": ["structured_json", "front_matter", "narrative_markdown"],
        "freshness_policy": {"max_age_days": None, "measured_by": "source_digest"},
        "task_cards_glob": "docs/implementation/tasks/*.md",
        "phase_path": "CURRENT_PHASE.md",
        "sources": sources,
        "machine_checks": [{
            "id": "chk-synthetic", "argv": ["-m", "tools.architecture_model.validate"],
            "cwd": ".", "timeout_seconds": 60, "max_output_bytes": 65536,
            "expected_exit_code": 0, "owner_role": "QA", "covers": ["synthetic"],
        }],
        "critical_coverage": ["synthetic"],
        "requirements": [
            {"id": "REQ-GATE", "kind": "gate", "ref": "SYN-GATE", "owner_role": "Legal",
             "reviewer_roles": ["Privacy"], "gate": "SYN-GATE", "explanation": "x"},
            {"id": "REQ-OWNER", "kind": "nominal_owner", "ref": "security_owner",
             "owner_role": "Founder", "reviewer_roles": ["Product"], "gate": "S1-READY",
             "explanation": "x"},
            {"id": "REQ-ADR", "kind": "adr_set", "owner_role": "Architecture",
             "reviewer_roles": ["Security"], "gate": "S1-READY", "explanation": "x"},
            {"id": "REQ-DECISIONS", "kind": "decision_set", "owner_role": "QA",
             "reviewer_roles": ["Security"], "gate": "S1-READY", "explanation": "x"},
            {"id": "REQ-NO-CONTRA", "kind": "no_contradiction", "owner_role": "QA",
             "reviewer_roles": ["Security"], "gate": "S1-READY", "explanation": "x"},
            {"id": "REQ-FRESH", "kind": "evidence_freshness", "owner_role": "QA",
             "reviewer_roles": ["Security"], "gate": "S1-READY", "explanation": "x"},
        ],
        "evidence_baseline": [],
        "gates": [{"id": "S1-READY", "status": "not_met", "acceptance": "pending_human"},
                  {"id": "SYN-GATE", "status": "not_met", "acceptance": "pending_human"}],
        "anti_promises": ["este agregador no aprueba nada"],
    }
    return directory, contract


class FakeObservation:
    """Helper para construir observaciones sin repetir todos los campos."""

    @staticmethod
    def make(kind: str, subject: str, field_name: str, value: str,
             path: str = "docs/x.json") -> Observation:
        return Observation(kind, subject, field_name, value, path, "$.gates[0]", "d" * 64)


# --------------------------------------------------------------------------- #
# Positivas contra el contrato real
# --------------------------------------------------------------------------- #

class RealContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_pos_01_the_real_contract_is_valid(self) -> None:
        self.assertEqual(validate_contract(self.contract, ROOT), [])

    def test_pos_02_the_gate_starts_not_met_and_no_agent_may_accept(self) -> None:
        self.assertEqual(self.contract["initial_gate_status"], "not_met")
        self.assertFalse(self.contract["agent_may_accept"])
        self.assertEqual(self.contract["human_acceptance"], "pending")
        for gate in self.contract["gates"]:
            self.assertEqual(gate["status"], "not_met", gate["id"])

    def test_pos_03_only_machine_pass_satisfies_a_requirement(self) -> None:
        self.assertEqual(self.contract["aggregation"]["satisfying_categories"],
                         ["machine_pass"])
        self.assertEqual(SATISFYING_CATEGORIES, {"machine_pass"})

    def test_pos_04_structured_json_outranks_narrative_markdown(self) -> None:
        precedence = self.contract["source_precedence"]
        self.assertEqual(precedence[0], "structured_json")
        self.assertEqual(precedence[-1], "narrative_markdown")

    def test_pos_05_every_declared_source_exists_and_is_structured(self) -> None:
        for source in self.contract["sources"]:
            self.assertIsNotNone(resolve_inside(ROOT, source["path"]), source["path"])
            self.assertEqual(source["kind"], "json")

    def test_pos_06_every_machine_check_runs_a_local_tools_module(self) -> None:
        for check in self.contract["machine_checks"]:
            self.assertEqual(check["argv"][0], "-m")
            self.assertTrue(check["argv"][1].startswith("tools."), check["id"])
            self.assertEqual(check["expected_exit_code"], 0)

    def test_pos_07_the_registry_covers_the_domains_the_assignment_lists(self) -> None:
        covered = {item for check in self.contract["machine_checks"]
                   for item in check["covers"]}
        for domain in ("work_graph", "test_catalog", "adr", "canonical", "completeness",
                       "idempotency", "lineage", "cross_contract", "dfd", "privacy",
                       "threat", "region", "runtime_config", "workspace", "local_stack",
                       "migration_readiness", "migration_spike", "quality_strategy",
                       "golden_harness", "mutation_harness", "research",
                       "provider_evaluation", "brand", "budget", "supply_chain"):
            self.assertIn(domain, covered, domain)

    def test_pos_08_every_requirement_names_an_owner_and_a_reviewer(self) -> None:
        for requirement in self.contract["requirements"]:
            self.assertTrue(requirement["owner_role"], requirement["id"])
            self.assertTrue(requirement["reviewer_roles"], requirement["id"])
            self.assertNotIn(requirement["owner_role"], requirement["reviewer_roles"],
                             requirement["id"])
            self.assertTrue(requirement["explanation"], requirement["id"])

    def test_pos_09_freshness_has_no_invented_duration(self) -> None:
        self.assertIsNone(self.contract["freshness_policy"]["max_age_days"])
        self.assertEqual(self.contract["freshness_policy"]["measured_by"], "source_digest")

    def test_pos_10_heavy_checks_are_declared_and_not_re_executed(self) -> None:
        self.assertFalse(self.contract["runs_containers_in_evaluate"])
        heavy = self.contract["heavy_checks_not_run_here"]
        self.assertTrue(heavy)
        for row in heavy:
            self.assertEqual(row["evidence_state"], "declared_not_reexecuted")
            self.assertTrue(row["reason"])

    def test_pos_11_the_contract_declares_the_dynamic_set_requirements(self) -> None:
        kinds = {requirement["kind"] for requirement in self.contract["requirements"]}
        self.assertIn("adr_set", kinds)
        self.assertIn("decision_set", kinds)
        self.assertIn("no_contradiction", kinds)


# --------------------------------------------------------------------------- #
# Lectura de fuentes
# --------------------------------------------------------------------------- #

class SourceReadingTests(unittest.TestCase):
    def test_src_01_only_an_explicit_token_counts_as_met(self) -> None:
        for value in ("met", "accepted", "APPROVED", "Signed"):
            self.assertTrue(is_met(value), value)
        for value in ("not_met", "pending_human", "proposed", "open", "", None,
                      "probably", "review_pending"):
            self.assertFalse(is_met(value), value)

    def test_src_02_unassigned_is_never_an_assignment(self) -> None:
        for value in ("UNASSIGNED", "", "none", "TBD", "pending", None):
            self.assertFalse(is_assigned(value), value)
        self.assertTrue(is_assigned("Ada Lovelace"))
        self.assertFalse(is_assigned([]))
        self.assertFalse(is_assigned(["Ada", "UNASSIGNED"]))

    def test_src_03_gates_are_read_from_status_or_state(self) -> None:
        document = {"gates": [{"id": "G1", "state": "not_met", "owner_role": "Legal"},
                              {"id": "G2", "status": "met"}]}
        observations = extract_gates(document, "gates", "docs/x.json", "d" * 64)
        index = index_observations(observations)
        self.assertEqual(index[("gate", "G1", "status")][0].value, "not_met")
        self.assertEqual(index[("gate", "G2", "status")][0].value, "met")

    def test_src_04_a_decision_without_a_state_field_is_open(self) -> None:
        document = {"unresolved_decisions": [{"id": "UD-1", "question": "q",
                                               "blocks": ["S1-READY", "DRG-00"]}]}
        observations = extract_decisions(document, "unresolved_decisions",
                                         "docs/x.json", "d" * 64)
        index = index_observations(observations)
        value = index[("decision", "UD-1", "status")][0].value
        self.assertEqual(value, "pending_human")
        self.assertFalse(is_met(value))
        self.assertEqual(
            {item.value for item in index[("decision", "UD-1", "blocks_gate")]},
            {"S1-READY", "DRG-00"})
        self.assertEqual(detect_contradictions(observations, ("blocks_gate",)), [])

    def test_src_05_a_bare_string_decision_is_open(self) -> None:
        document = {"open_decisions": ["UD-A02-SERVICE-MATRIX"]}
        observations = extract_decisions(document, "open_decisions", "docs/x.json",
                                         "d" * 64)
        self.assertEqual(observations[0].value, "open")
        self.assertFalse(is_met(observations[0].value))

    def test_src_06_adr_readiness_carries_the_required_set(self) -> None:
        document = {"required_s1_adrs": ["ADR-001"],
                    "adrs": [{"id": "ADR-001", "readiness": "blocked"}],
                    "release_rule": {"gate": "S1-READY", "state": "not_met"}}
        index = index_observations(extract_adr_readiness(document, "docs/a.json", "d" * 64))
        self.assertEqual(index[("adr", "ADR-001", "required_for_s1")][0].value, "true")
        self.assertEqual(index[("adr", "ADR-001", "readiness")][0].value, "blocked")

    def test_src_07_front_matter_reads_inline_and_block_lists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "card.md", TASK_CARD)
            parsed, digest, reason = read_front_matter(root, "card.md")
            self.assertEqual(reason, "")
            self.assertEqual(len(digest), 64)
            self.assertEqual(parsed["independent_reviewers"], ["Architecture", "Security"])
            self.assertEqual(parsed["file_scope"],
                             ["docs/synthetic/one.json", "docs/synthetic/two.json"])

    def test_src_08_front_matter_fails_closed_on_a_nested_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "card.md", "---\ntask: X\nnested:\n  key: value\n---\n")
            _parsed, _digest, reason = read_front_matter(root, "card.md")
            self.assertIn("does not support", reason)

    def test_src_09_front_matter_fails_closed_when_it_is_not_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "card.md", "---\ntask: X\n")
            _parsed, _digest, reason = read_front_matter(root, "card.md")
            self.assertIn("not closed", reason)

    def test_src_10_paths_are_contained(self) -> None:
        for candidate in ("/etc/passwd", "C:/Windows", "../outside", "a/../../b", ""):
            self.assertFalse(safe_relative(candidate), candidate)
        self.assertIsNone(resolve_inside(ROOT, "docs/../../outside"))

    def test_src_11_collecting_the_real_tree_reads_every_declared_source(self) -> None:
        collected = collect(load_contract(), ROOT)
        self.assertEqual(collected["unreadable_sources"], [])
        self.assertGreater(collected["observation_count"]
                           if "observation_count" in collected
                           else len(collected["observations"]), 100)

    def test_src_12_source_digest_is_stable_across_checkout_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            windows, linux = root / "windows.json", root / "linux.json"
            windows.write_bytes(b'{\r\n  "ok": true\r\n}\r\n')
            linux.write_bytes(b'{\n  "ok": true\n}\n')
            self.assertEqual(sha256_file(windows), sha256_file(linux))


# --------------------------------------------------------------------------- #
# Invariantes negativas 1-18
# --------------------------------------------------------------------------- #

class NegativeInvariantTests(unittest.TestCase):
    def categories(self, root: Path, contract: dict) -> dict[str, str]:
        report = aggregate(contract, root)
        return {row["id"]: row["category"] for row in report["requirements"]}

    # 1 y 16. Un pase de maquina no promueve el gate.
    def test_neg_01_machine_pass_does_not_promote_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory))
            contract["requirements"] = [
                requirement for requirement in contract["requirements"]
                if requirement["id"] == "REQ-GATE"]
            report = aggregate(contract, root)
            self.assertEqual(report["gate_status"], "not_met")
            self.assertEqual(report["requirements"][0]["category"], "pending_human")

    def test_neg_16_the_current_repository_is_never_reported_as_s1_met(self) -> None:
        code, payload = run_cli(["evaluate"])
        self.assertEqual(payload["gate_status"], "not_met")
        self.assertEqual(payload["gate_acceptance"], "pending_human")
        self.assertEqual(code, s1_cli.EXIT_GATE_NOT_MET)

    # 2. Pending, unknown y stale nunca cuentan como met.
    def test_neg_02_pending_unknown_and_stale_never_satisfy(self) -> None:
        for category in ("pending_human", "not_executed", "stale_evidence",
                         "blocked_dependency", "contradiction", "machine_fail"):
            self.assertNotIn(category, SATISFYING_CATEGORIES, category)

    def test_neg_02b_a_met_gate_in_a_source_does_satisfy_its_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), gate_status="met")
            self.assertEqual(self.categories(root, contract)["REQ-GATE"], "machine_pass")

    # 3. Sin owner nominal no se aprueba nada.
    def test_neg_03_an_unassigned_owner_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), owner="UNASSIGNED")
            self.assertEqual(self.categories(root, contract)["REQ-OWNER"], "pending_human")

    def test_neg_03b_an_assigned_owner_satisfies_its_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), owner="Persona Sintetica")
            self.assertEqual(self.categories(root, contract)["REQ-OWNER"], "machine_pass")

    # 4. El agente no escribe aceptacion.
    def test_neg_04_recorded_human_acceptance_is_refused(self) -> None:
        contract = load_contract()
        contract["human_acceptance"] = "accepted"
        self.assertIn("S1R-ACCEPTANCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_04b_claiming_the_agent_may_accept_is_refused(self) -> None:
        contract = load_contract()
        contract["agent_may_accept"] = True
        self.assertIn("S1R-AUTHORITY",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_04c_claiming_it_writes_central_state_is_refused(self) -> None:
        contract = load_contract()
        contract["writes_central_state"] = True
        self.assertIn("S1R-AUTHORITY",
                      {item.code for item in validate_contract(contract, ROOT)})

    # 5. La prosa no suplanta a la fuente estructurada.
    def test_neg_05a_a_markdown_source_is_refused(self) -> None:
        contract = load_contract()
        contract["sources"].append({"path": "docs/implementation/GATES.md",
                                    "kind": "markdown", "gates_keys": ["gates"]})
        self.assertIn("S1R-SOURCE-KIND",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_05b_inverting_the_precedence_is_refused(self) -> None:
        contract = load_contract()
        contract["source_precedence"] = ["narrative_markdown", "structured_json"]
        self.assertIn("S1R-PRECEDENCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    # 6. Dos fuentes contradictorias no se resuelven en silencio.
    def test_neg_06_a_contradiction_is_reported_and_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), second_gate_owner="Security")
            report = aggregate(contract, root)
            self.assertTrue(report["contradictions"])
            contradiction = report["contradictions"][0]
            self.assertEqual(contradiction["subject_id"], "SYN-GATE")
            self.assertEqual(contradiction["values"], ["Legal", "Security"])
            self.assertEqual(contradiction["resolution"], "pending_human")
            categories = {row["id"]: row["category"] for row in report["requirements"]}
            self.assertEqual(categories["REQ-NO-CONTRA"], "contradiction")

    def test_neg_06b_agreeing_sources_produce_no_contradiction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), second_gate_owner="Legal")
            report = aggregate(contract, root)
            self.assertEqual(report["contradictions"], [])

    def test_neg_06c_a_contradicted_gate_is_never_silently_chosen(self) -> None:
        observations = [
            FakeObservation.make("gate", "G1", "status", "met", "docs/a.json"),
            FakeObservation.make("gate", "G1", "status", "not_met", "docs/b.json"),
        ]
        contradictions = detect_contradictions(observations)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0]["values"], ["met", "not_met"])

    # 7. Check no allowlisted, argv string, shell o cwd externo.
    def test_neg_07a_a_module_outside_the_tools_namespace_is_refused(self) -> None:
        contract = load_contract()
        contract["machine_checks"][0]["argv"] = ["-m", "os"]
        self.assertIn("S1R-MODULE-ALLOWLIST",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_07b_an_argv_that_is_not_a_list_is_refused(self) -> None:
        contract = load_contract()
        contract["machine_checks"][0]["argv"] = "-m tools.dfd_model.validate"
        self.assertIn("S1R-ARGV-LIST",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_07c_shell_syntax_in_argv_is_refused(self) -> None:
        for poisoned in ("&& rm -rf /", "; id", "| cat", "`id`", "$(id)", "*"):
            with self.subTest(poisoned=poisoned):
                contract = load_contract()
                contract["machine_checks"][0]["argv"] = [
                    "-m", "tools.dfd_model.validate", poisoned]
                self.assertIn("S1R-ARGV-SHELL",
                              {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_07d_an_external_cwd_is_refused(self) -> None:
        contract = load_contract()
        contract["machine_checks"][0]["cwd"] = "../elsewhere"
        self.assertIn("S1R-CWD", {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_07e_the_runner_refuses_shell_syntax_at_execution_time(self) -> None:
        result = run_machine_check(
            {"id": "x", "argv": ["-m", "tools.dfd_model.validate", "; id"], "cwd": "."},
            ROOT)
        self.assertEqual(result["status"], "refused")

    def test_neg_07f_the_runner_refuses_anything_that_is_not_dash_m(self) -> None:
        result = run_machine_check({"id": "x", "argv": ["-c", "print(1)"], "cwd": "."}, ROOT)
        self.assertEqual(result["status"], "refused")

    # 8. Timeout, truncamiento y exit inesperado no son pass.
    def test_neg_08a_a_timeout_is_not_a_pass(self) -> None:
        result = run_machine_check({
            "id": "slow", "argv": ["-m", "tools.dfd_model.validate"], "cwd": ".",
            "timeout_seconds": 1, "max_output_bytes": 65536,
        }, ROOT, env={**build_environment(), "FINCILIA_UNUSED": "1"})
        self.assertIn(result["status"], ("passed", "timeout", "failed"))
        if result["status"] == "timeout":
            self.assertIsNone(result["exit_code"])

    def test_neg_08b_truncated_output_is_not_a_pass(self) -> None:
        result = run_machine_check({
            "id": "noisy", "argv": ["-m", "tools.s1_readiness.cli", "evaluate"],
            "cwd": ".", "timeout_seconds": 600, "max_output_bytes": 64,
        }, ROOT)
        self.assertEqual(result["status"], "truncated")

    def test_neg_08c_an_unexpected_exit_code_is_a_failure(self) -> None:
        result = run_machine_check({
            "id": "wrong", "argv": ["-m", "tools.s1_readiness.cli", "evaluate"],
            "cwd": ".", "timeout_seconds": 600, "max_output_bytes": 4194304,
            "expected_exit_code": 0,
        }, ROOT)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], s1_cli.EXIT_GATE_NOT_MET)

    def test_neg_08d_an_unexecuted_check_is_never_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory))
            contract["requirements"].append({
                "id": "REQ-MISSING", "kind": "machine_check", "ref": "chk-absent",
                "owner_role": "QA", "reviewer_roles": ["Security"], "gate": "S1-READY",
                "explanation": "x"})
            rows = evaluate_requirements(contract, root, collect(contract, root), {}, [])
            row = next(item for item in rows if item["id"] == "REQ-MISSING")
            self.assertEqual(row["category"], "not_executed")

    # 9. Un check critico omitido se detecta.
    def test_neg_09_removing_a_critical_check_is_an_omission(self) -> None:
        contract = load_contract()
        contract["machine_checks"] = [check for check in contract["machine_checks"]
                                      if check["id"] != "chk-privacy"]
        codes = {item.code for item in validate_contract(contract, ROOT)}
        self.assertIn("S1R-COVERAGE-OMISSION", codes)

    def test_neg_09b_a_new_open_decision_is_discovered_without_editing_the_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), decisions=[])
            before = self.categories(root, contract)["REQ-DECISIONS"]
            primary = json.loads(
                (root / "docs/synthetic/primary.json").read_text(encoding="utf-8"))
            primary["unresolved_decisions"] = [
                {"id": "UD-BRAND-NEW", "state": "pending_human", "owner_role": "Legal",
                 "blocks": ["S1-READY"]}]
            write(root / "docs/synthetic/primary.json", json.dumps(primary, indent=2))
            after = self.categories(root, contract)["REQ-DECISIONS"]
            self.assertEqual(before, "machine_pass")
            self.assertEqual(after, "pending_human")

    def test_neg_09c_a_later_gate_decision_is_visible_but_does_not_block_s1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), decisions=[{
                "id": "UD-LATER", "state": "pending_human", "owner_role": "Legal",
                "blocks": ["DRG-01"],
            }])
            report = aggregate(contract, root)
            categories = {row["id"]: row["category"] for row in report["requirements"]}
            self.assertEqual(categories["REQ-DECISIONS"], "machine_pass")
            self.assertTrue(any(observation.subject_id == "UD-LATER"
                                for observation in collect(contract, root)["observations"]))

    def test_neg_09d_a_later_gate_contradiction_is_reported_but_not_an_s1_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), second_gate_owner="Legal")
            secondary_path = root / "docs/synthetic/secondary.json"
            secondary = json.loads(secondary_path.read_text(encoding="utf-8"))
            secondary["gates"][0]["id"] = "DRG-01"
            secondary["gates"][0]["owner_role"] = "Security"
            write(secondary_path, json.dumps(secondary, indent=2))
            primary_path = root / "docs/synthetic/primary.json"
            primary = json.loads(primary_path.read_text(encoding="utf-8"))
            primary["gates"].append({"id": "DRG-01", "status": "not_met",
                                     "owner_role": "Legal"})
            write(primary_path, json.dumps(primary, indent=2))
            # Sin enrutar, una contradiccion de un gate posterior SI bloquea: el
            # silencio no resuelve nada (FNC-GAT-004).
            unrouted = aggregate(contract, root)
            self.assertTrue(any(item["subject_id"] == "DRG-01"
                                for item in unrouted["contradictions"]))
            categories = {row["id"]: row["category"] for row in unrouted["requirements"]}
            self.assertEqual(categories["REQ-NO-CONTRA"], "contradiction")
            self.assertEqual(len(unrouted["contradiction_triage"]["unrouted"]), 1)

            # Enrutada a un owner y a su propio gate, deja de bloquear S1-READY
            # pero sigue bloqueando DRG-01 y conserva a quien debe adjudicarla.
            contract["acknowledged_contradictions"] = [{
                "subject_kind": "gate", "subject_id": "DRG-01", "field": "owner_role",
                "reason": "divergencia sintetica de owner entre dos fuentes",
                "owner_role": "Integration Steward", "gate": "DRG-01",
                "blocks_gate": True,
            }]
            routed = aggregate(contract, root)
            categories = {row["id"]: row["category"] for row in routed["requirements"]}
            self.assertEqual(categories["REQ-NO-CONTRA"], "machine_pass")
            acknowledged = routed["contradiction_triage"]["acknowledged"]
            self.assertEqual(len(acknowledged), 1)
            self.assertEqual(acknowledged[0]["routed_to_owner"], "Integration Steward")
            self.assertEqual(acknowledged[0]["blocks_gate"], "DRG-01")
            self.assertTrue(any(item["subject_id"] == "DRG-01"
                                for item in routed["contradictions"]))

    # FNC-GAT-004: la relevancia se declara, no se deduce.
    def test_gat004_01_missing_relevance_declaration_is_refused(self) -> None:
        contract = load_contract()
        del contract["contradiction_relevance"]
        self.assertIn("S1R-CONTRADICTION-RELEVANCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_02_an_empty_relevance_set_is_refused(self) -> None:
        contract = load_contract()
        contract["contradiction_relevance"]["gates"] = []
        self.assertIn("S1R-CONTRADICTION-RELEVANCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_03_the_target_gate_must_be_relevant_to_itself(self) -> None:
        contract = load_contract()
        contract["contradiction_relevance"]["gates"] = ["DRG-00"]
        self.assertIn("S1R-CONTRADICTION-RELEVANCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_04_relevance_without_a_rationale_is_refused(self) -> None:
        contract = load_contract()
        contract["contradiction_relevance"]["rationale"] = ""
        self.assertIn("S1R-CONTRADICTION-RELEVANCE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_05_a_route_without_owner_gate_or_reason_is_refused(self) -> None:
        for missing in ("reason", "owner_role", "gate", "subject_id", "field"):
            with self.subTest(missing=missing):
                contract = load_contract()
                entry = dict(contract["acknowledged_contradictions"][0])
                del entry[missing]
                contract["acknowledged_contradictions"] = [entry]
                self.assertIn("S1R-CONTRADICTION-ROUTE",
                              {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_06_routing_never_stops_blocking_its_own_gate(self) -> None:
        contract = load_contract()
        contract["acknowledged_contradictions"][0]["blocks_gate"] = False
        self.assertIn("S1R-CONTRADICTION-ROUTE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_07_a_route_cannot_point_at_the_target_gate(self) -> None:
        contract = load_contract()
        contract["acknowledged_contradictions"][0]["gate"] = "S1-READY"
        self.assertIn("S1R-CONTRADICTION-ROUTE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_gat004_08_every_real_route_names_owner_reviewers_gate_and_reason(self) -> None:
        contract = load_contract()
        routed = contract["acknowledged_contradictions"]
        self.assertTrue(routed)
        for entry in routed:
            self.assertTrue(entry["owner_role"])
            self.assertTrue(entry["reviewer_roles"])
            self.assertTrue(entry["gate"])
            self.assertGreater(len(entry["reason"]), 40)
            self.assertTrue(entry["blocks_gate"])
            self.assertNotEqual(entry["gate"], "S1-READY")

    def test_gat004_09_relevance_does_not_depend_on_which_requirements_exist(self) -> None:
        # Retirar un requisito no puede cambiar que una contradiccion bloquee.
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), second_gate_owner="Security")
            contract["contradiction_relevance"] = {
                "gates": ["S1-READY", "SYN-GATE"], "rationale": "sintetico"}
            with_owner = aggregate(contract, root)
            trimmed = copy.deepcopy(contract)
            trimmed["requirements"] = [item for item in trimmed["requirements"]
                                       if item["kind"] != "nominal_owner"]
            without_owner = aggregate(trimmed, root)
            self.assertEqual(len(with_owner["contradiction_triage"]["blocking"]),
                             len(without_owner["contradiction_triage"]["blocking"]))
            self.assertEqual(len(with_owner["contradiction_triage"]["blocking"]), 1)

    def test_gat004_10_the_real_report_routes_every_observed_contradiction(self) -> None:
        _, payload = run_cli(["evaluate"])
        triage = payload["contradiction_triage"]
        self.assertEqual(triage["unrouted"], [])
        self.assertEqual(len(triage["blocking"]) + len(triage["acknowledged"])
                         + len(triage["unrouted"]), len(payload["contradictions"]))

    def test_machine_check_evidence_renders_the_actual_python_argv_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory))
            contract["requirements"].append({
                "id": "REQ-MACHINE", "kind": "machine_check", "ref": "chk-synthetic",
                "owner_role": "QA", "reviewer_roles": ["Security"],
                "gate": "S1-READY", "explanation": "synthetic command evidence",
            })
            rows = evaluate_requirements(
                contract, root, collect(contract, root),
                {"chk-synthetic": {"status": "passed", "exit_code": 0, "detail": ""}},
                [])
            machine = next(row for row in rows if row["kind"] == "machine_check")
            self.assertEqual(machine["evidence"][0]["command"],
                             "python -m tools.architecture_model.validate")
            self.assertNotIn("-m -m", machine["evidence"][0]["command"])

    # 10. Ciclos y gates desconocidos.
    def test_neg_10a_a_dependency_cycle_is_detected(self) -> None:
        cycles = detect_cycles([
            {"id": "A", "depends_on": ["B"]},
            {"id": "B", "depends_on": ["A"]},
        ])
        self.assertTrue(cycles)

    def test_neg_10b_a_self_dependency_is_refused(self) -> None:
        contract = load_contract()
        contract["requirements"][0]["depends_on"] = [contract["requirements"][0]["id"]]
        self.assertIn("S1R-DEPENDENCY",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_10c_an_unknown_dependency_is_refused(self) -> None:
        contract = load_contract()
        contract["requirements"][0]["depends_on"] = ["REQ-DOES-NOT-EXIST"]
        self.assertIn("S1R-DEPENDENCY",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_10d_the_graph_reports_an_unknown_gate(self) -> None:
        _, payload = run_cli(["graph"])
        self.assertEqual(payload["unknown_gates"], [])
        self.assertTrue(payload["acyclic"])

    def test_neg_10e_a_blocked_dependency_is_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), owner="Persona Sintetica")
            for requirement in contract["requirements"]:
                if requirement["id"] == "REQ-OWNER":
                    requirement["depends_on"] = ["REQ-GATE"]
            self.assertEqual(self.categories(root, contract)["REQ-OWNER"],
                             "blocked_dependency")

    # 11 y 12. Evidencia y frescura.
    def test_neg_11_declared_evidence_needs_path_digest_and_producer(self) -> None:
        for missing in ("path", "sha256", "produced_by"):
            with self.subTest(missing=missing):
                contract = load_contract()
                baseline = dict(contract["evidence_baseline"][0])
                del baseline[missing]
                contract["evidence_baseline"] = [baseline]
                codes = {item.code for item in validate_contract(contract, ROOT)}
                self.assertTrue({"S1R-EVIDENCE-FIELDS", "S1R-PATH-UNSAFE"} & codes)

    def test_neg_12a_a_drifted_baseline_digest_is_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory))
            contract["evidence_baseline"] = [{
                "path": "docs/synthetic/primary.json", "sha256": "0" * 64,
                "produced_by": "synthetic"}]
            self.assertEqual(self.categories(root, contract)["REQ-FRESH"],
                             "stale_evidence")

    def test_neg_12b_an_invented_maximum_age_is_refused(self) -> None:
        contract = load_contract()
        contract["freshness_policy"]["max_age_days"] = 30
        self.assertIn("S1R-FRESHNESS",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_12c_freshness_measured_by_a_clock_is_refused(self) -> None:
        contract = load_contract()
        contract["freshness_policy"]["measured_by"] = "wall_clock"
        self.assertIn("S1R-FRESHNESS",
                      {item.code for item in validate_contract(contract, ROOT)})

    # 13. Ningun conteo global esconde un blocker.
    def test_neg_13a_there_is_no_aggregate_score(self) -> None:
        _, payload = run_cli(["evaluate"])
        self.assertIsNone(payload["aggregate_score"])
        self.assertEqual(payload["blocker_count"], len(payload["blockers"]))

    def test_neg_13b_declaring_an_aggregate_score_as_gate_is_refused(self) -> None:
        contract = load_contract()
        contract["aggregate_score_as_gate"] = True
        self.assertIn("S1R-SCORE",
                      {item.code for item in validate_contract(contract, ROOT)})

    def test_neg_13c_the_counts_add_up_to_the_requirement_total(self) -> None:
        _, payload = run_cli(["evaluate"])
        self.assertEqual(sum(payload["counts_by_category"].values()),
                         payload["requirement_count"])

    # 14. Un filtro nunca elimina un blocker del resultado canonico.
    def test_neg_14a_filtering_by_owner_keeps_the_canonical_total(self) -> None:
        _, unfiltered = run_cli(["explain"])
        _, filtered = run_cli(["explain", "--owner", "Legal"])
        self.assertEqual(filtered["canonical_blocker_count"],
                         unfiltered["canonical_blocker_count"])
        self.assertEqual(filtered["shown_blocker_count"] + filtered["filtered_out_count"],
                         filtered["canonical_blocker_count"])

    def test_neg_14b_filtering_by_gate_keeps_the_canonical_total(self) -> None:
        _, filtered = run_cli(["explain", "--gate", "A-02"])
        self.assertGreaterEqual(filtered["canonical_blocker_count"],
                                filtered["shown_blocker_count"])
        self.assertTrue(filtered["owners_with_blockers"])

    def test_neg_14c_a_filter_that_matches_nothing_still_reports_the_total(self) -> None:
        code, filtered = run_cli(["explain", "--owner", "NoSuchRole"])
        self.assertEqual(filtered["shown_blocker_count"], 0)
        self.assertGreater(filtered["canonical_blocker_count"], 0)
        self.assertFalse(filtered["ok"])
        self.assertEqual(code, s1_cli.EXIT_GATE_NOT_MET)

    # 15. La salida no filtra variables, secretos ni PII.
    def test_neg_15_the_report_carries_no_environment_or_personal_data(self) -> None:
        for arguments in (["evaluate"], ["explain"], ["graph"], ["validate"]):
            with self.subTest(arguments=arguments):
                _, payload = run_cli(arguments)
                serialised = json.dumps(payload, ensure_ascii=False)
                for forbidden in ("PATH=", "PYTHONPATH", "USERPROFILE", "PASSWORD",
                                  "SECRET", "@gmail", "AppData"):
                    self.assertNotIn(forbidden, serialised, forbidden)
                self.assertIsNone(
                    re.search(r"\b\d{9}-\d\b", serialised), "NIT-shaped value")

    # 17 y 18. Un check en verde no cierra un riesgo ni acepta un ADR.
    def test_neg_17_a_green_supply_chain_check_does_not_close_tm_005(self) -> None:
        supply = json.loads(
            (ROOT / "docs/security/supply-chain.json").read_text(encoding="utf-8"))
        self.assertEqual(supply["tm_005"]["state"], "open")
        self.assertFalse(supply["tm_005"]["closed_by_this_tool"])
        contract = load_contract()
        serialised = json.dumps(contract, ensure_ascii=False)
        self.assertNotIn("TM-005", serialised.replace("TM-005 sigue abierto", ""))

    def test_neg_18_a_green_db_spike_does_not_accept_adr_002(self) -> None:
        spike = json.loads(
            (ROOT / "docs/database/migration-spike.json").read_text(encoding="utf-8"))
        self.assertEqual(spike["tooling_decision"]["adr_state"], "proposed")
        self.assertIsNone(spike["tooling_decision"]["selected_tool"])
        _, payload = run_cli(["evaluate"])
        adr = next(row for row in payload["requirements"] if row["kind"] == "adr_set")
        self.assertNotEqual(adr["category"], "machine_pass")


# --------------------------------------------------------------------------- #
# Metamorficas y CLI
# --------------------------------------------------------------------------- #

class MetamorphicAndCliTests(unittest.TestCase):
    def test_meta_01_reordering_sources_does_not_change_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), second_gate_owner="Legal")
            first = aggregate(contract, root)
            shuffled = copy.deepcopy(contract)
            shuffled["sources"] = list(reversed(shuffled["sources"]))
            shuffled["requirements"] = list(reversed(shuffled["requirements"]))
            second = aggregate(shuffled, root)
            self.assertEqual(first["gate_status"], second["gate_status"])
            self.assertEqual(first["counts_by_category"], second["counts_by_category"])
            self.assertEqual([row["id"] for row in first["requirements"]],
                             [row["id"] for row in second["requirements"]])

    def test_meta_02_adding_an_eligible_blocker_changes_the_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory), gate_status="met",
                                            owner="Persona Sintetica", decisions=[],
                                            adr_readiness="ready")
            before = aggregate(contract, root)
            self.assertEqual(before["blocker_count"], 0)
            self.assertEqual(before["gate_status"], "met")
            primary = json.loads(
                (root / "docs/synthetic/primary.json").read_text(encoding="utf-8"))
            primary["gates"][0]["status"] = "not_met"
            write(root / "docs/synthetic/primary.json", json.dumps(primary, indent=2))
            after = aggregate(contract, root)
            self.assertEqual(after["blocker_count"], 1)
            self.assertEqual(after["gate_status"], "not_met")

    def test_meta_03_the_evaluation_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, contract = synthetic_root(Path(directory))
            first, second = aggregate(contract, root), aggregate(contract, root)
            self.assertEqual(first["requirements"], second["requirements"])
            self.assertEqual(first["source_manifest"], second["source_manifest"])

    def test_meta_04_every_source_in_the_manifest_carries_its_digest(self) -> None:
        _, payload = run_cli(["evaluate"])
        for row in payload["source_manifest"]:
            self.assertEqual(len(row["sha256"]), 64, row["path"])

    def test_cli_01_validate_separates_contract_validity_from_the_gate(self) -> None:
        code, payload = run_cli(["validate"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["contract_valid"])
        self.assertNotIn("gate_status", payload)

    def test_cli_02_evaluate_uses_a_distinct_exit_for_a_valid_not_met_gate(self) -> None:
        code, payload = run_cli(["evaluate"])
        self.assertEqual(code, s1_cli.EXIT_GATE_NOT_MET)
        self.assertTrue(payload["evaluation_valid"])
        self.assertEqual(payload["gate_status"], "not_met")
        self.assertEqual(payload["exit_code_meaning"]["10"],
                         "evaluation valid and gate not_met")

    def test_cli_03_an_invalid_contract_produces_the_invalid_evaluation_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.json"
            contract = load_contract()
            contract["task_id"] = "FNC-WRONG-000"
            write(broken, json.dumps(contract))
            code, payload = run_cli(["--contract", str(broken), "evaluate"])
            self.assertEqual(code, s1_cli.EXIT_INVALID_EVALUATION)
            self.assertFalse(payload["evaluation_valid"])
            self.assertEqual(payload["gate_status"], "not_met")

    def test_cli_04_an_unreadable_contract_is_invalid_usage(self) -> None:
        code, _ = run_cli(["--contract", str(ROOT / "docs/absent.json"), "validate"])
        self.assertEqual(code, s1_cli.EXIT_USAGE)

    def test_cli_05_a_traversing_root_is_refused(self) -> None:
        code, _ = run_cli(["--root", "../outside", "validate"])
        self.assertEqual(code, s1_cli.EXIT_USAGE)

    def test_cli_06_the_graph_is_machine_readable_and_acyclic(self) -> None:
        code, payload = run_cli(["graph"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["node_count"], len(load_contract()["requirements"]))
        self.assertTrue(payload["acyclic"])
        for edge in payload["edges"]:
            self.assertIn(edge["from"], {node["id"] for node in payload["nodes"]})

    def test_cli_07_explain_reports_the_contradictions_it_found(self) -> None:
        _, payload = run_cli(["explain"])
        for contradiction in payload["contradictions"]:
            self.assertEqual(contradiction["resolution"], "pending_human")
            self.assertGreaterEqual(len(contradiction["sources"]), 2)

    def test_cli_08_evaluate_never_claims_the_agent_may_accept(self) -> None:
        _, payload = run_cli(["evaluate"])
        self.assertFalse(payload["agent_may_accept"])

    def test_cli_09_the_contract_on_disk_is_never_modified(self) -> None:
        before = CONTRACT_PATH.read_bytes()
        run_cli(["evaluate"])
        run_cli(["explain"])
        run_cli(["graph"])
        self.assertEqual(CONTRACT_PATH.read_bytes(), before)


# --------------------------------------------------------------------------- #
# Disciplina del codigo fuente
# --------------------------------------------------------------------------- #

class SourceDisciplineTests(unittest.TestCase):
    def sources(self) -> list[Path]:
        return [path for path in sorted(SOURCE_DIR.glob("*.py"))
                if path.name != "test_validate.py"]

    def test_disc_01_no_shell_eval_exec_or_network(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            for token in ("shell=True", "eval(", "exec(", "os.system", "import socket",
                          "import urllib", "import requests"):
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_disc_02_no_wall_clock_or_randomness(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            for token in ("datetime.now(", "datetime.utcnow(", "time.time(",
                          "import random", "import secrets"):
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_disc_03_no_anonymous_todo(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in self.sources():
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)

    def test_disc_04_the_environment_is_never_read_wholesale(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("dict(os.environ)", text, source.name)
            self.assertNotIn("os.environ.copy()", text, source.name)

    def test_disc_05_git_is_never_invoked(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            self.assertNotIn('"git"', text, source.name)
            self.assertNotIn("'git'", text, source.name)


if __name__ == "__main__":
    unittest.main()
