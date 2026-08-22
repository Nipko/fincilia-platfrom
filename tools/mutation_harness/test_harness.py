"""Pruebas del arnes de mutaciones (FNC-QA-005).

Cada invariante negativa parte de una entrada valida y la degrada exactamente una
vez. Los casos que ejercitan el clasificador del runner usan el laboratorio
sintetico de `tests/golden/mutations`, no los contratos reales: si el runner solo
se probara contra validadores que funcionan, no se sabria si distingue un control
que muerde de un proceso que se cayo.

Sin red, sin reloj de pared, sin locale del host, sin Git, sin orden de directorio.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.mutation_harness import cli, operators, registry, runner

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs/testing/mutation-harness.json"
FIXTURES = "tests/golden/mutations"
SYNTHETIC_VALIDATOR = f"{FIXTURES}/synthetic_validator.py"
SYNTHETIC_CONTRACT = f"{FIXTURES}/synthetic_contract.json"
SYNTHETIC_EVIDENCE = f"{FIXTURES}/synthetic_evidence.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cli(argv: list[str]) -> tuple[int, dict]:
    """Ejecuta el CLI capturando su salida para que la suite no sea ruidosa."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    text = out.getvalue()
    return code, (json.loads(text) if text.strip() else {})


# --------------------------------------------------------------------------- #
# Laboratorio sintetico
# --------------------------------------------------------------------------- #

def lab_registry(mode: str = "strict") -> dict:
    return {
        "schema_version": 1,
        "task_id": "FNC-QA-005",
        "status": "review_pending",
        "human_acceptance": "pending",
        "data_ceiling": "synthetic_only",
        "network_access": False,
        "mutates_source_tree": False,
        "global_score_as_gate": False,
        "risk_severity": {"TM-013": "high"},
        "validators": [{
            "id": "synthetic",
            "module": "tests.golden.mutations.synthetic_validator",
            "argv": [SYNTHETIC_VALIDATOR, "--mode", mode],
            "copy_paths": [SYNTHETIC_VALIDATOR, SYNTHETIC_CONTRACT, SYNTHETIC_EVIDENCE],
            "runtime": "python",
        }],
        "mutations": [],
        "gates": [],
        "declared_gaps": [],
    }


def lab_mutation(operator: str, params: dict, codes: list[str] | None = None,
                 **overrides) -> dict:
    metamorphic = codes is None
    mutation = {
        "mutation_id": "MUT-LAB-001",
        "title": "mutacion de laboratorio",
        "risk_refs": ["TM-013"],
        "control_refs": ["SYN-FLAG"],
        "test_refs": ["TST-MUT-001"],
        "owner_role": "QA",
        "reviewer_roles": ["Security"],
        "validator": "synthetic",
        "target": SYNTHETIC_CONTRACT,
        "target_sha256": sha256_file(ROOT / SYNTHETIC_CONTRACT),
        "precondition": {"baseline_must_be_clean": True, "single_change": True,
                         "target_digest_must_match": True},
        "operator": operator,
        "operator_params": params,
        "expectation": ({"kind": "expect_no_findings", "exit_code": 0} if metamorphic
                        else {"kind": "expect_findings", "exit_code": 1,
                              "finding_codes": sorted(codes)}),
        "timeout_seconds": 120,
        "max_output_bytes": 262144,
        "independence": {"mode": "independent"},
        "data_classification": "synthetic_only",
        "evidence_ref": "EV-QA-MUTATION",
        "state": "active",
        "gate": "S1-READY",
    }
    mutation.update(overrides)
    return mutation


def policy_registry() -> dict:
    """Registro con la forma que la politica exige: modulo local y argv `-m`.

    El laboratorio sintetico usa un script de fixture a proposito, y por eso
    `validate_registry` lo rechaza; eso se comprueba aparte.
    """
    document = lab_registry()
    document["validators"] = [{
        "id": "canonical_model",
        "module": "tools.canonical_model.validate",
        "argv": ["-m", "tools.canonical_model.validate"],
        "copy_paths": ["docs/domain/canonical-model.json",
                       "docs/architecture/module-boundaries.json"],
        "runtime": "python",
    }]
    return document


def run_lab(mutation: dict, mode: str = "strict") -> dict:
    reg = lab_registry(mode)
    reg["mutations"] = [mutation]
    return runner.run_mutation(mutation, reg, ROOT)


# --------------------------------------------------------------------------- #
# Operadores
# --------------------------------------------------------------------------- #

class OperatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = {
            "flag": True,
            "version": "1.4.2",
            "path": "docs/testing/test-strategy.json",
            "items": ["a", "b", "c"],
            "nested": {"keep": 1, "drop": 2},
        }

    def test_op_01_delete_key_removes_exactly_one_key(self) -> None:
        result = operators.apply_operator(self.document, "delete_key",
                                          {"pointer": "/nested/drop"})
        self.assertEqual(result["nested"], {"keep": 1})

    def test_op_02_delete_key_removes_exactly_one_list_element(self) -> None:
        result = operators.apply_operator(self.document, "delete_key", {"pointer": "/items/1"})
        self.assertEqual(result["items"], ["a", "c"])

    def test_op_03_operators_never_mutate_the_input_document(self) -> None:
        pristine = copy.deepcopy(self.document)
        operators.apply_operator(self.document, "delete_key", {"pointer": "/nested/drop"})
        operators.apply_operator(self.document, "flip_boolean",
                                 {"pointer": "/flag", "expected_current": True})
        self.assertEqual(self.document, pristine)

    def test_op_04_replace_scalar_requires_the_declared_current_value(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "replace_scalar",
                                     {"pointer": "/version", "expected_current": "9.9.9",
                                      "new_value": "2.0.0"})

    def test_op_05_flip_boolean_refuses_a_non_boolean_pointer(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "flip_boolean",
                                     {"pointer": "/version", "expected_current": True})

    def test_op_06_insert_element_refuses_an_out_of_range_index(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "insert_element",
                                     {"pointer": "/items", "value": "z", "index": 99})

    def test_op_07_reorder_list_refuses_a_list_that_proves_nothing(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator({"only": [1]}, "reorder_list", {"pointer": "/only"})

    def test_op_08_reorder_list_preserves_content(self) -> None:
        result = operators.apply_operator(self.document, "reorder_list", {"pointer": "/items"})
        self.assertEqual(sorted(result["items"]), sorted(self.document["items"]))
        self.assertNotEqual(result["items"], self.document["items"])

    def test_op_09_path_traversal_stays_inside_but_stops_being_canonical(self) -> None:
        result = operators.apply_operator(
            self.document, "path_traversal_internal",
            {"pointer": "/path", "expected_current": "docs/testing/test-strategy.json"})
        mutated = result["path"]
        self.assertIn("..", Path(mutated).parts)
        self.assertTrue((ROOT / mutated).resolve().is_file())

    def test_op_10_float_version_token_refuses_an_unknown_token(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "float_version_token",
                                     {"pointer": "/version", "expected_current": "1.4.2",
                                      "token": "whatever"})

    def test_op_11_operator_outside_the_allowlist_is_refused(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "exec_python", {"pointer": "/flag"})

    def test_op_12_missing_parameters_are_refused_before_touching_the_document(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "replace_scalar", {"pointer": "/version"})

    def test_op_13_the_document_root_cannot_be_mutated(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "delete_key", {"pointer": ""})

    def test_op_14_a_pointer_must_be_rfc6901(self) -> None:
        with self.assertRaises(operators.MutationError):
            operators.apply_operator(self.document, "delete_key", {"pointer": "nested/drop"})

    def test_op_15_every_operator_declares_its_required_parameters(self) -> None:
        self.assertEqual(set(operators.OPERATORS), set(operators.OPERATOR_REQUIRED_PARAMS))


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #

class RegistryTests(unittest.TestCase):
    TARGET = "docs/domain/canonical-model.json"

    def setUp(self) -> None:
        self.registry = policy_registry()
        self.registry["mutations"] = [lab_mutation(
            "flip_boolean", {"pointer": "/entities/13/company_scoped", "expected_current": True},
            ["DOM-FINANCE-SCOPE"], validator="canonical_model", target=self.TARGET,
            target_sha256=sha256_file(ROOT / self.TARGET))]

    def codes(self, registry_document: dict) -> set[str]:
        return {error.code for error in registry.validate_registry(registry_document, ROOT)}

    def test_reg_01_the_laboratory_registry_is_valid(self) -> None:
        self.assertEqual(registry.validate_registry(self.registry, ROOT), [])

    def test_reg_02_absolute_target_is_refused(self) -> None:
        self.registry["mutations"][0]["target"] = "C:/Windows/win.ini"
        self.assertIn("MH-TARGET-UNSAFE", self.codes(self.registry))

    def test_reg_03_traversing_target_is_refused_even_if_it_resolves_inside(self) -> None:
        self.registry["mutations"][0]["target"] = f"{FIXTURES}/../mutations/x.json"
        self.assertIn("MH-TARGET-UNSAFE", self.codes(self.registry))

    def test_reg_04_a_drifted_target_digest_is_refused(self) -> None:
        self.registry["mutations"][0]["target_sha256"] = "a" * 64
        self.assertIn("MH-TARGET-HASH", self.codes(self.registry))

    def test_reg_05_a_target_outside_the_copied_inputs_is_refused(self) -> None:
        other = "docs/security/threat-model.json"
        self.registry["mutations"][0]["target"] = other
        self.registry["mutations"][0]["target_sha256"] = sha256_file(ROOT / other)
        self.assertIn("MH-TARGET-NOT-COPIED", self.codes(self.registry))

    def test_reg_06_an_operator_outside_the_allowlist_is_refused(self) -> None:
        self.registry["mutations"][0]["operator"] = "run_shell"
        self.assertIn("MH-OPERATOR-ALLOWLIST", self.codes(self.registry))

    def test_reg_07_argv_that_looks_like_shell_is_refused(self) -> None:
        self.registry["validators"][0]["argv"] = ["-m", "tools.x", "&& rm -rf /"]
        self.assertIn("MH-ARGV-SHELL", self.codes(self.registry))

    def test_reg_08_argv_must_run_exactly_the_declared_module(self) -> None:
        self.registry["validators"][0]["module"] = "tools.canonical_model.validate"
        self.registry["validators"][0]["argv"] = ["-m", "tools.privacy_model.validate"]
        self.assertIn("MH-ARGV-MODULE", self.codes(self.registry))

    def test_reg_09_a_module_outside_the_local_namespace_is_refused(self) -> None:
        self.registry["validators"][0]["module"] = "os"
        self.assertIn("MH-MODULE-ALLOWLIST", self.codes(self.registry))

    def test_reg_10_parameters_that_look_like_code_are_refused(self) -> None:
        self.registry["mutations"][0]["operator_params"] = {
            "pointer": "/entities/13/company_scoped", "expected_current": True,
            "payload": "eval(open('x').read())"}
        self.assertIn("MH-OPERATOR-PARAMS", self.codes(self.registry))

    def test_reg_11_a_mutation_without_a_clean_baseline_precondition_is_refused(self) -> None:
        self.registry["mutations"][0]["precondition"] = {"baseline_must_be_clean": False}
        self.assertIn("MH-PRECONDITION", self.codes(self.registry))

    def test_reg_12_expected_findings_without_codes_are_refused(self) -> None:
        self.registry["mutations"][0]["expectation"] = {"kind": "expect_findings", "exit_code": 1,
                                                        "finding_codes": []}
        self.assertIn("MH-EXPECTATION-CODES", self.codes(self.registry))

    def test_reg_13_a_metamorphic_control_that_expects_failure_is_refused(self) -> None:
        self.registry["mutations"][0]["expectation"] = {"kind": "expect_no_findings",
                                                        "exit_code": 1}
        self.assertIn("MH-EXPECTATION-EXIT", self.codes(self.registry))

    def test_reg_14_two_independent_mutations_cannot_claim_the_same_control(self) -> None:
        twin = copy.deepcopy(self.registry["mutations"][0])
        twin["mutation_id"] = "MUT-LAB-002"
        twin["operator_params"] = {"pointer": "/entities/13/company_scoped",
                                   "expected_current": True}
        self.registry["mutations"].append(twin)
        self.assertIn("MH-REDUNDANT-CONTROL", self.codes(self.registry))

    def test_reg_15_an_equivalence_group_is_not_redundancy(self) -> None:
        twin = copy.deepcopy(self.registry["mutations"][0])
        twin["mutation_id"] = "MUT-LAB-002"
        for mutation in (self.registry["mutations"][0], twin):
            mutation["independence"] = {"mode": "equivalence_group", "group_id": "EQG-LAB"}
        self.registry["mutations"].append(twin)
        self.assertNotIn("MH-REDUNDANT-CONTROL", self.codes(self.registry))

    def test_reg_16_an_equivalence_group_without_an_id_is_refused(self) -> None:
        self.registry["mutations"][0]["independence"] = {"mode": "equivalence_group"}
        self.assertIn("MH-INDEPENDENCE", self.codes(self.registry))

    def test_reg_17_a_skipped_mutation_is_refused_rather_than_counted(self) -> None:
        self.registry["mutations"][0]["state"] = "skipped"
        self.assertIn("MH-MUTATION-STATE", self.codes(self.registry))

    def test_reg_18_a_duplicate_mutation_id_is_refused(self) -> None:
        self.registry["mutations"].append(copy.deepcopy(self.registry["mutations"][0]))
        self.assertIn("MH-MUTATION-DUPLICATE", self.codes(self.registry))

    def test_reg_19_a_mutation_without_traceability_is_refused(self) -> None:
        self.registry["mutations"][0]["risk_refs"] = []
        self.assertIn("MH-MUTATION-TRACE", self.codes(self.registry))

    def test_reg_20_an_owner_cannot_review_itself(self) -> None:
        self.registry["mutations"][0]["reviewer_roles"] = ["QA"]
        self.assertIn("MH-MUTATION-OWNER", self.codes(self.registry))

    def test_reg_21_an_agent_cannot_mark_a_gate_as_met(self) -> None:
        self.registry["gates"] = [{"id": "S1-READY", "status": "met", "acceptance": "accepted"}]
        self.assertIn("MH-GATE-STATUS", self.codes(self.registry))

    def test_reg_22_an_agent_cannot_record_human_acceptance(self) -> None:
        self.registry["human_acceptance"] = "accepted"
        self.assertIn("MH-HUMAN-ACCEPTANCE", self.codes(self.registry))

    def test_reg_23_a_declared_gap_keeps_its_gate_blocked(self) -> None:
        self.registry["declared_gaps"] = [{"risk_id": "TM-002", "reason": "sin base de datos",
                                           "owner_role": "Backend", "gate": "DRG-01",
                                           "blocks_gate": False}]
        self.assertIn("MH-GAP-FIELDS", self.codes(self.registry))

    def test_reg_24_a_floating_result_affecting_version_is_refused(self) -> None:
        self.registry["mutations"][0]["result_affecting_versions"] = {"engine": "latest"}
        self.assertIn("MH-FLOATING-VERSION", self.codes(self.registry))

    def test_reg_25_an_unsafe_copy_path_is_refused(self) -> None:
        self.registry["validators"][0]["copy_paths"] = ["../outside.json"]
        self.assertIn("MH-COPY-PATH-UNSAFE", self.codes(self.registry))

    def test_reg_26_a_missing_copy_path_is_refused(self) -> None:
        self.registry["validators"][0]["copy_paths"] = [f"{FIXTURES}/nope.json", self.TARGET]
        self.assertIn("MH-COPY-PATH-MISSING", self.codes(self.registry))

    def test_reg_27_an_unbounded_timeout_is_refused(self) -> None:
        self.registry["mutations"][0]["timeout_seconds"] = 0
        self.assertIn("MH-TIMEOUT", self.codes(self.registry))

    def test_reg_28_an_unbounded_output_limit_is_refused(self) -> None:
        self.registry["mutations"][0]["max_output_bytes"] = 99_999_999
        self.assertIn("MH-OUTPUT-LIMIT", self.codes(self.registry))

    def test_reg_29_a_non_synthetic_classification_is_refused(self) -> None:
        self.registry["mutations"][0]["data_classification"] = "production"
        self.assertIn("MH-DATA-CLASSIFICATION", self.codes(self.registry))

    def test_reg_30_declaring_network_access_is_refused(self) -> None:
        self.registry["network_access"] = True
        self.assertIn("MH-NETWORK", self.codes(self.registry))

    def test_reg_31_declaring_a_global_score_as_a_gate_is_refused(self) -> None:
        self.registry["global_score_as_gate"] = True
        self.assertIn("MH-GLOBAL-SCORE", self.codes(self.registry))

    def test_reg_32_declaring_that_the_source_tree_is_mutated_is_refused(self) -> None:
        self.registry["mutates_source_tree"] = True
        self.assertIn("MH-SOURCE-TREE", self.codes(self.registry))

    def test_reg_33_an_empty_registry_is_refused_rather_than_passing_vacuously(self) -> None:
        self.registry["mutations"] = []
        self.assertIn("MH-MUTATIONS-MISSING", self.codes(self.registry))

    def test_reg_34_resolve_inside_rejects_absolute_traversal_and_escape(self) -> None:
        for candidate in ("C:/Windows/win.ini", "/etc/passwd", "../outside.json",
                          "docs/../../outside.json", ""):
            self.assertIsNone(registry.resolve_inside(ROOT, candidate), candidate)

    def test_reg_35_resolve_inside_rejects_traversal_that_resolves_inside(self) -> None:
        # Resuelve dentro del repositorio y aun asi se rechaza: dos grafias del
        # mismo fichero hacen ambigua la contabilidad de digests.
        candidate = "docs/../docs/testing/test-strategy.json"
        self.assertTrue((ROOT / candidate).resolve().is_file())
        self.assertIsNone(registry.resolve_inside(ROOT, candidate))

    def test_reg_36_watched_paths_cover_every_copy_path_and_target(self) -> None:
        watched = set(registry.source_tree_digests_paths(self.registry))
        self.assertTrue(set(self.registry["validators"][0]["copy_paths"]) <= watched)
        self.assertIn(self.registry["mutations"][0]["target"], watched)

    def test_reg_37_the_registry_digest_ignores_key_order(self) -> None:
        shuffled = dict(reversed(list(self.registry.items())))
        self.assertEqual(registry.registry_digest(self.registry),
                         registry.registry_digest(shuffled))


    def test_reg_38_a_fixture_script_is_never_an_allowlisted_validator(self) -> None:
        # El laboratorio sintetico se ejecuta a proposito por ruta de script; la
        # politica lo rechaza, y por eso el laboratorio no pasa por aqui.
        self.assertEqual(
            {"MH-ARGV-MODULE", "MH-MODULE-ALLOWLIST"} & self.codes(lab_registry() | {
                "mutations": [lab_mutation(
                    "flip_boolean",
                    {"pointer": "/authority_flag", "expected_current": True}, ["SYN-FLAG"])]}),
            {"MH-ARGV-MODULE", "MH-MODULE-ALLOWLIST"})

    def test_reg_39_the_real_registry_on_disk_verifies_clean(self) -> None:
        document = registry.load_registry(REGISTRY_PATH)
        self.assertEqual(registry.validate_registry(document, ROOT), [])


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

class RunnerTests(unittest.TestCase):
    def test_run_01_TST_MUT_001_a_real_finding_kills_the_mutation(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]))
        self.assertEqual(result["outcome"], "killed")
        self.assertEqual(result["baseline_exit_code"], 0)

    def test_run_02_a_blind_validator_produces_a_survivor_not_a_kill(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]), mode="blind")
        self.assertEqual(result["outcome"], "survived")

    def test_run_03_a_non_zero_exit_for_the_wrong_reason_is_not_a_kill(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]), mode="wrongcode")
        self.assertEqual(result["outcome"], "survived")
        self.assertEqual(result["observed_finding_codes"], ["SYN-OTHER"])

    def test_run_04_a_dirty_baseline_makes_the_case_invalid_not_killed(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]), mode="dirty")
        self.assertEqual(result["outcome"], "invalid")
        self.assertIn("baseline", result["detail"])

    def test_run_05_unparseable_output_is_an_error_not_a_kill(self) -> None:
        result = run_lab(lab_mutation(
            "insert_element", {"pointer": "/controls", "value": "marker_garbage", "index": 0}))
        self.assertEqual(result["outcome"], "error")

    def test_run_06_truncated_output_is_an_error_not_a_kill(self) -> None:
        result = run_lab(lab_mutation(
            "insert_element", {"pointer": "/controls", "value": "marker_noise", "index": 0},
            ["SYN-FLAG"], max_output_bytes=512))
        self.assertEqual(result["outcome"], "error")
        self.assertTrue(result["mutated_truncated"])

    def test_run_07_a_timeout_is_an_error_not_a_kill(self) -> None:
        result = run_lab(lab_mutation(
            "insert_element", {"pointer": "/controls", "value": "marker_sleep", "index": 0},
            ["SYN-FLAG"], timeout_seconds=1))
        self.assertEqual(result["outcome"], "error")
        self.assertIn("timeout", result["detail"])

    def test_run_08_an_inapplicable_operator_is_invalid_not_killed(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": False},
            ["SYN-FLAG"]))
        self.assertEqual(result["outcome"], "invalid")

    def test_run_09_an_unknown_validator_is_an_error(self) -> None:
        mutation = lab_mutation("flip_boolean",
                                {"pointer": "/authority_flag", "expected_current": True},
                                ["SYN-FLAG"], validator="does-not-exist")
        self.assertEqual(run_lab(mutation)["outcome"], "error")

    def test_run_10_TST_META_001_a_held_metamorphic_control_counts_as_killed(self) -> None:
        result = run_lab(lab_mutation("reorder_list", {"pointer": "/controls"}))
        self.assertEqual(result["outcome"], "killed")
        self.assertEqual(result["mutated_exit_code"], 0)

    def test_run_11_a_broken_metamorphic_control_is_reported_as_a_survivor(self) -> None:
        mutation = lab_mutation("insert_element",
                                {"pointer": "/controls", "value": "alpha", "index": 0})
        self.assertEqual(run_lab(mutation)["outcome"], "survived")

    def test_run_12_internal_traversal_in_an_evidence_path_is_killed(self) -> None:
        result = run_lab(lab_mutation(
            "path_traversal_internal",
            {"pointer": "/evidence_path", "expected_current": SYNTHETIC_EVIDENCE},
            ["SYN-PATH"]))
        self.assertEqual(result["outcome"], "killed")

    def test_run_13_a_floating_version_is_killed(self) -> None:
        result = run_lab(lab_mutation(
            "float_version_token", {"pointer": "/engine_version", "expected_current": "1.4.2"},
            ["SYN-VERSION"]))
        self.assertEqual(result["outcome"], "killed")

    def test_run_14_the_source_tree_is_never_touched(self) -> None:
        watched = [SYNTHETIC_CONTRACT, SYNTHETIC_EVIDENCE, SYNTHETIC_VALIDATOR]
        before = runner.source_tree_digests(ROOT, watched)
        run_lab(lab_mutation("flip_boolean",
                             {"pointer": "/authority_flag", "expected_current": True},
                             ["SYN-FLAG"]))
        self.assertEqual(before, runner.source_tree_digests(ROOT, watched))

    def test_run_15_an_identical_replay_produces_an_identical_digest(self) -> None:
        mutation = lab_mutation("flip_boolean",
                                {"pointer": "/authority_flag", "expected_current": True},
                                ["SYN-FLAG"])
        first, second = run_lab(mutation), run_lab(mutation)
        self.assertEqual(first["deterministic_result_digest"],
                         second["deterministic_result_digest"])

    def test_run_16_the_manifest_carries_no_payload_no_environment_no_duration(self) -> None:
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]))
        serialised = json.dumps(result, ensure_ascii=False)
        for forbidden in ("PATH", "TEMP", "duration", "stdout", "stderr", "PYTHONPATH"):
            self.assertNotIn(forbidden, serialised, forbidden)
        self.assertNotIn("marker_", serialised)

    def test_run_17_the_environment_drops_proxies_and_secrets(self) -> None:
        env = runner.build_environment(ROOT, {
            "PATH": "p", "SYSTEMROOT": "s", "HTTP_PROXY": "http://proxy",
            "HTTPS_PROXY": "http://proxy", "AWS_SECRET_ACCESS_KEY": "sk", "GITHUB_TOKEN": "gh",
        })
        self.assertEqual(env["PATH"], "p")
        for forbidden in ("HTTP_PROXY", "HTTPS_PROXY", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"):
            self.assertNotIn(forbidden, env)

    def test_run_18_the_environment_is_deterministic(self) -> None:
        env = runner.build_environment(ROOT, {"PATH": "p"})
        self.assertEqual(env["PYTHONHASHSEED"], "0")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")

    def test_run_19_a_missing_copy_path_makes_the_case_invalid(self) -> None:
        reg = lab_registry()
        reg["validators"][0]["copy_paths"] = [SYNTHETIC_VALIDATOR, SYNTHETIC_CONTRACT,
                                              f"{FIXTURES}/absent.json"]
        mutation = lab_mutation("flip_boolean",
                                {"pointer": "/authority_flag", "expected_current": True},
                                ["SYN-FLAG"])
        reg["mutations"] = [mutation]
        result = runner.run_mutation(mutation, reg, ROOT)
        self.assertEqual(result["outcome"], "invalid")

    def test_run_20_only_the_declared_inputs_reach_the_workspace(self) -> None:
        # El validador sintetico no puede leer nada que no se haya copiado: si el
        # aislamiento fallara, encontraria el contrato real de la estrategia.
        reg = lab_registry()
        self.assertNotIn("docs/testing/test-strategy.json", reg["validators"][0]["copy_paths"])
        result = run_lab(lab_mutation(
            "flip_boolean", {"pointer": "/authority_flag", "expected_current": True},
            ["SYN-FLAG"]))
        self.assertEqual(result["baseline_exit_code"], 0)


# --------------------------------------------------------------------------- #
# CLI y registro real
# --------------------------------------------------------------------------- #

class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = registry.load_registry(REGISTRY_PATH)

    def test_cli_01_verify_accepts_the_real_registry(self) -> None:
        code, payload = run_cli(["verify"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(code, 0)

    def test_cli_02_list_shows_every_mutation_and_every_declared_gap(self) -> None:
        _, payload = run_cli(["list"])
        self.assertEqual(payload["count"], len(self.document["mutations"]))
        self.assertEqual({gap["risk_id"] for gap in payload["declared_gaps"]},
                         {"TM-002", "TM-005", "TM-006", "TM-010"})

    def test_cli_03_the_registry_covers_at_least_six_validators(self) -> None:
        validators = {m["validator"] for m in self.document["mutations"]}
        self.assertGreaterEqual(len(validators), 6)
        self.assertGreaterEqual(len(self.document["mutations"]), 18)

    def test_cli_04_every_validator_carries_at_least_five_mutations(self) -> None:
        # `test-strategy.json` exige minimum_mutants_per_validator = 5.
        counts: dict[str, int] = {}
        for mutation in self.document["mutations"]:
            counts[mutation["validator"]] = counts.get(mutation["validator"], 0) + 1
        thin = sorted(name for name, total in counts.items() if total < 5)
        self.assertEqual(thin, [])

    def test_cli_05_an_unknown_mutation_id_runs_nothing_and_fails(self) -> None:
        code, payload = run_cli(["run", "--mutation", "MUT-DOES-NOT-EXIST"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["results"], [])

    def test_cli_06_selecting_one_mutation_executes_exactly_one(self) -> None:
        _, payload = run_cli(["run", "--mutation", "MUT-CAN-002"])
        self.assertEqual(payload["executed"], 1)
        self.assertEqual(payload["results"][0]["outcome"], "killed")

    def test_cli_07_severity_ranks_critical_above_high(self) -> None:
        self.assertEqual(cli.severity_of(self.document, ["TM-005", "TM-001"]), "critical")
        self.assertEqual(cli.severity_of(self.document, ["TM-013"]), "high")
        self.assertEqual(cli.severity_of(self.document, ["TM-999"]), "unknown")

    def test_cli_08_report_refuses_to_produce_a_single_passing_score(self) -> None:
        _, payload = run_cli(["report"])
        self.assertIsNone(payload["single_pass_score"])
        self.assertIn("by_risk", payload)
        self.assertIn("by_control", payload)

    def test_cli_09_report_keeps_declared_gaps_visible(self) -> None:
        _, payload = run_cli(["report"])
        self.assertEqual(len(payload["declared_gaps"]), 4)

    def test_cli_10_the_declared_survivors_match_what_the_run_observes(self) -> None:
        _, payload = run_cli(["run"])
        declared = {row["mutation_id"] for row in self.document["known_survivors"]}
        self.assertEqual(set(payload["survivors"]), declared)
        self.assertTrue(payload["source_tree_unchanged"])

    def test_cli_11_a_clean_full_run_has_no_blocking_survivor(self) -> None:
        code, payload = run_cli(["run"])
        self.assertEqual([], payload["blocking_survivors"])
        self.assertTrue(payload["ok"])
        self.assertEqual(code, 0)

    def test_cli_12_run_refuses_to_execute_when_the_registry_does_not_verify(self) -> None:
        document = copy.deepcopy(self.document)
        document["mutations"][0]["operator"] = "run_shell"
        with tempfile.TemporaryDirectory(prefix="fnc-broken-") as temporary:
            broken = Path(temporary) / "broken-registry.json"
            broken.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            code, payload = run_cli(["--registry", str(broken), "run"])
        self.assertEqual(code, 1)
        self.assertNotIn("results", payload)
        self.assertIn("nothing was executed", payload["reason"])

    def test_cli_13_no_mutation_is_skipped_or_quarantined(self) -> None:
        self.assertEqual({m["state"] for m in self.document["mutations"]}, {"active"})

    def test_cli_14_every_gate_in_the_registry_stays_unmet(self) -> None:
        for gate in self.document["gates"]:
            self.assertEqual(gate["status"], "not_met")
            self.assertEqual(gate["acceptance"], "pending_human")

    def test_cli_15_no_coverage_is_invented_for_the_infrastructure_risks(self) -> None:
        gaps = {gap["risk_id"] for gap in self.document["declared_gaps"]}
        self.assertTrue({"TM-002", "TM-005", "TM-006", "TM-010"} <= gaps)
        for gap in self.document["declared_gaps"]:
            self.assertTrue(gap["blocks_gate"])
            self.assertTrue(gap["owner_role"] and gap["gate"])


# --------------------------------------------------------------------------- #
# Fixtures sinteticos
# --------------------------------------------------------------------------- #

class FixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ROOT / FIXTURES
        self.manifest = json.loads((self.root / "MANIFEST.json").read_text(encoding="utf-8"))

    def files_on_disk(self) -> list[Path]:
        return sorted(p for p in self.root.rglob("*")
                      if p.is_file() and p.name != "MANIFEST.json"
                      and "__pycache__" not in p.parts)

    def test_fix_01_every_fixture_is_inventoried(self) -> None:
        inventoried = {row["path"] for row in self.manifest["files"]}
        on_disk = {str(p.relative_to(ROOT)).replace("\\", "/") for p in self.files_on_disk()}
        self.assertEqual(on_disk, inventoried)

    def test_fix_02_every_inventoried_digest_matches_the_file(self) -> None:
        for row in self.manifest["files"]:
            self.assertEqual(sha256_file(ROOT / row["path"]), row["sha256"], row["path"])

    def test_fix_03_the_fixtures_are_declared_synthetic_and_offline(self) -> None:
        self.assertEqual(self.manifest["data_classification"], "synthetic_only")
        self.assertFalse(self.manifest["network_access"])
        self.assertEqual(self.manifest["human_acceptance"], "pending")

    def test_fix_04_no_fixture_contains_anything_that_looks_real(self) -> None:
        patterns = {
            "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            "nit": re.compile(r"\b\d{9}-\d\b"),
            "public ip": re.compile(r"\b(?!10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)"
                                    r"(\d{1,3}\.){3}\d{1,3}\b"),
            "anonymous todo": re.compile(r"\b(TODO|FIXME)\b(?!\s*\()"),
        }
        for path in self.files_on_disk():
            text = path.read_text(encoding="utf-8")
            for name, pattern in patterns.items():
                self.assertIsNone(pattern.search(text), f"{path.name}: {name}")

    def test_fix_05_the_synthetic_contract_is_a_clean_baseline(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "synthetic_validator", ROOT / SYNTHETIC_VALIDATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document = json.loads((ROOT / SYNTHETIC_CONTRACT).read_text(encoding="utf-8"))
        import os
        cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            self.assertEqual(module.check(document), [])
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
