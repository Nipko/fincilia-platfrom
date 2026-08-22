"""Pruebas del golden harness (FNC-QA-003).

Positivas contra el registro real del repositorio; negativas por mutación de una
copia profunda. Todo offline y con datos sintéticos.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.golden_harness.cli import command_list, command_run, command_verify
from tools.golden_harness.registry import (
    canonical_json,
    case_digest,
    registry_digest,
    resolve_inside,
    sha256_file,
    validate_registry,
)
from tools.golden_harness.runner import build_environment, evaluate_oracle, run_case

ROOT = Path(__file__).parents[2]
REGISTRY_PATH = ROOT / "docs/testing/golden-harness.json"
FIXTURE_PATH = ROOT / "tests/golden/harness/sample_case_input.json"
FIXTURE_MANIFEST = ROOT / "tests/golden/harness/MANIFEST.json"
RUNNER_PATH = ROOT / "tools/golden_harness/runner.py"

FAST_CASE = "GH-SELFCHECK"


class GoldenHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def _codes(self, registry: dict) -> set[str]:
        return {error.code for error in validate_registry(registry, ROOT)}

    def _case(self, registry: dict, case_id: str) -> dict:
        return next(c for c in registry["cases"] if c["case_id"] == case_id)

    # ================================================================== #
    # Positivas
    # ================================================================== #

    def test_repository_registry_is_valid(self) -> None:
        self.assertEqual([], validate_registry(self.registry, ROOT))

    def test_list_reports_every_case(self) -> None:
        payload, code = command_list(self.registry, ROOT)
        self.assertEqual(0, code)
        self.assertEqual(len(self.registry["cases"]), payload["count"])
        self.assertTrue(all(item["state"] == "active" for item in payload["cases"]))

    def test_verify_succeeds_without_executing_anything(self) -> None:
        payload, code = command_verify(self.registry, ROOT)
        self.assertEqual(0, code)
        self.assertTrue(payload["ok"])
        self.assertNotIn("results", payload)

    def test_fixture_manifest_matches_disk(self) -> None:
        manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("synthetic_only", manifest["data_classification"])
        for relative, declared in manifest["files"].items():
            path = FIXTURE_MANIFEST.parent / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(declared, sha256_file(path), relative)

    def test_every_case_input_digest_matches_disk(self) -> None:
        for case in self.registry["cases"]:
            for item in case["inputs"]:
                path = resolve_inside(ROOT, item["path"])
                self.assertIsNotNone(path, item["path"])
                self.assertEqual(item["sha256"], sha256_file(path), item["path"])

    def test_replay_of_the_same_case_yields_the_same_digest(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        first = run_case(case, self.registry, ROOT)
        second = run_case(case, self.registry, ROOT)
        self.assertTrue(first["passed"])
        self.assertEqual(first["deterministic_result_digest"],
                         second["deterministic_result_digest"])

    def test_running_a_single_case_selects_only_that_case(self) -> None:
        payload, code = command_run(self.registry, ROOT, FAST_CASE)
        self.assertEqual(0, code)
        self.assertEqual(1, payload["executed"])
        self.assertEqual([FAST_CASE], [r["case_id"] for r in payload["results"]])

    def test_harness_is_offline_and_deterministic_by_construction(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import socket", "import requests",
                          "import random", "shell=True"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertIn("shell=False", source)

    # ================================================================== #
    # Negativas 1-18 del encargo
    # ================================================================== #

    def test_neg_01_registry_or_input_hash_tampering(self) -> None:
        mutated = copy.deepcopy(self.registry)
        self._case(mutated, "GH-VALIDATE-CANONICAL")["inputs"][0]["sha256"] = "0" * 64
        self.assertIn("GH-INPUT-HASH", self._codes(mutated))

        malformed = copy.deepcopy(self.registry)
        self._case(malformed, "GH-VALIDATE-DFD")["inputs"][0]["sha256"] = "not-a-digest"
        self.assertIn("GH-INPUT-HASH", self._codes(malformed))

        # Cualquier cambio del registro cambia su digest y, con él, el del resultado.
        drifted = copy.deepcopy(self.registry)
        self._case(drifted, "GH-VALIDATE-DFD")["timeout_seconds"] = 119
        self.assertNotEqual(registry_digest(self.registry), registry_digest(drifted))

    def test_neg_02_duplicate_case_or_missing_independent_reviewer(self) -> None:
        duplicated = copy.deepcopy(self.registry)
        duplicated["cases"].append(copy.deepcopy(self._case(duplicated, "GH-VALIDATE-DFD")))
        self.assertIn("GH-CASE-DUPLICATE", self._codes(duplicated))

        for mutation in ({"owner_role": ""}, {"reviewer_roles": []}):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD").update(mutation)
            self.assertIn("GH-CASE-OWNER", self._codes(mutated), mutation)

        self_review = copy.deepcopy(self.registry)
        case = self._case(self_review, "GH-VALIDATE-DFD")
        case["reviewer_roles"] = [case["owner_role"]]
        self.assertIn("GH-CASE-OWNER", self._codes(self_review))

    def test_neg_03_shell_string_command_is_rejected(self) -> None:
        as_string = copy.deepcopy(self.registry)
        self._case(as_string, "GH-VALIDATE-DFD")["argv"] = \
            "python -m tools.dfd_model.validate"
        self.assertIn("GH-ARGV-LIST", self._codes(as_string))

        with_shell = copy.deepcopy(self.registry)
        self._case(with_shell, "GH-VALIDATE-DFD")["argv"] = \
            ["-m", "tools.dfd_model.validate", "&& echo pwned"]
        self.assertIn("GH-ARGV-SHELL", self._codes(with_shell))

    def test_neg_04_non_allowlisted_runtime_or_module(self) -> None:
        runtime = copy.deepcopy(self.registry)
        self._case(runtime, "GH-VALIDATE-DFD")["runtime"] = "bash"
        self.assertIn("GH-RUNTIME", self._codes(runtime))

        outside = copy.deepcopy(self.registry)
        case = self._case(outside, "GH-VALIDATE-DFD")
        case["argv"] = ["-m", "os"]
        case["module_allowlist"] = ["os"]
        self.assertIn("GH-MODULE-ALLOWLIST", self._codes(outside))

        unlisted = copy.deepcopy(self.registry)
        self._case(unlisted, "GH-VALIDATE-DFD")["argv"] = ["-m", "tools.privacy_model.validate"]
        self.assertIn("GH-MODULE-ALLOWLIST", self._codes(unlisted))

        not_a_module = copy.deepcopy(self.registry)
        self._case(not_a_module, "GH-VALIDATE-DFD")["argv"] = ["-c", "print(1)"]
        self.assertIn("GH-ARGV-MODULE", self._codes(not_a_module))

    def test_neg_05_absolute_path_traversal_or_external_symlink(self) -> None:
        for bad in ("/etc/passwd", "C:/Windows/win.ini", "../../secrets.json",
                    "docs/../../outside.json"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["inputs"] = [
                {"path": bad, "sha256": "0" * 64}]
            self.assertIn("GH-INPUT-PATH", self._codes(mutated), bad)

        cwd = copy.deepcopy(self.registry)
        self._case(cwd, "GH-VALIDATE-DFD")["cwd"] = "../"
        self.assertIn("GH-CWD", self._codes(cwd))

        self.assertIsNone(resolve_inside(ROOT, "../outside"))
        self.assertIsNone(resolve_inside(ROOT, "/absolute"))

        # Un `..` que resuelve dentro del repositorio tambien se rechaza: dos
        # grafias del mismo fichero harian ambigua la contabilidad de digests.
        self.assertIsNone(resolve_inside(ROOT, "docs/../docs/testing/test-strategy.json"))
        non_canonical = copy.deepcopy(self.registry)
        self._case(non_canonical, "GH-VALIDATE-DFD")["inputs"] = [
            {"path": "docs/../docs/architecture/dfd-flows.json", "sha256": "0" * 64}]
        self.assertIn("GH-INPUT-PATH", self._codes(non_canonical))

    def test_neg_08b_output_beyond_the_declared_limit_fails_the_case(self) -> None:
        case = copy.deepcopy(self._case(self.registry, FAST_CASE))
        case["max_output_bytes"] = 10
        manifest = run_case(case, self.registry, ROOT)
        self.assertFalse(manifest["passed"])
        self.assertTrue(manifest["output_truncated"])
        self.assertTrue(any("output limit" in reason for reason in manifest["reasons"]))

        # Caso decisivo: con un oraculo que no lee stdout, el truncamiento seria
        # invisible salvo que el runner lo trate como fallo por si mismo. Una
        # ejecucion cuya salida se corto no es una ejecucion de la que fiarse.
        blind = copy.deepcopy(self._case(self.registry, FAST_CASE))
        blind["max_output_bytes"] = 10
        blind["oracle"] = {"kind": "exit_code_only", "normalize_fields": []}
        blind_manifest = run_case(blind, self.registry, ROOT)
        self.assertEqual(0, blind_manifest["actual_exit_code"])
        self.assertTrue(blind_manifest["output_truncated"])
        self.assertFalse(blind_manifest["passed"],
                         "una salida truncada no puede declararse PASS")

    def test_neg_06_non_synthetic_or_uninventoried_fixture(self) -> None:
        classification = copy.deepcopy(self.registry)
        self._case(classification, "GH-SELFCHECK")["data_classification"] = "real_derived"
        self.assertIn("GH-DATA-CLASSIFICATION", self._codes(classification))

        missing = copy.deepcopy(self.registry)
        self._case(missing, "GH-SELFCHECK")["inputs"] = [
            {"path": "tests/golden/harness/not_inventoried.json", "sha256": "0" * 64}]
        self.assertIn("GH-INPUT-MISSING", self._codes(missing))

        ceiling = copy.deepcopy(self.registry)
        ceiling["data_ceiling"] = "real_allowed"
        self.assertIn("GH-DATA-CEILING", self._codes(ceiling))

    def test_neg_07_missing_or_excessive_timeout(self) -> None:
        for value in (None, 0, -1, "60", 3600):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["timeout_seconds"] = value
            self.assertIn("GH-TIMEOUT", self._codes(mutated), repr(value))

    def test_neg_08_unbounded_output(self) -> None:
        for value in (None, 0, 10_000_000):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["max_output_bytes"] = value
            self.assertIn("GH-OUTPUT-LIMIT", self._codes(mutated), repr(value))

    def test_neg_09_missing_expected_exit_code(self) -> None:
        mutated = copy.deepcopy(self.registry)
        del self._case(mutated, "GH-VALIDATE-DFD")["expected_exit_code"]
        codes = self._codes(mutated)
        self.assertIn("GH-EXPECTED-EXIT", codes)
        self.assertIn("GH-CASE-FIELDS", codes)

    def test_neg_10_always_pass_oracle_or_financial_normalisation(self) -> None:
        for kind in ("always_pass", "always_true", "regex_loose", "ignore_output"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["oracle"] = {"kind": kind}
            codes = self._codes(mutated)
            # El denylist nombrado y el allowlist son dos defensas distintas:
            # la primera explica por que, la segunda cierra la puerta.
            self.assertIn("GH-ORACLE-FORBIDDEN", codes, kind)
            self.assertIn("GH-ORACLE-KIND", codes, kind)

        unknown = copy.deepcopy(self.registry)
        self._case(unknown, "GH-VALIDATE-DFD")["oracle"] = {"kind": "vibes"}
        self.assertIn("GH-ORACLE-KIND", self._codes(unknown))

        for field in ("ok", "errors", "amount", "currency", "balance", "digest"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["oracle"]["normalize_fields"] = [field]
            self.assertIn("GH-ORACLE-NORMALIZE", self._codes(mutated), field)

        no_expect = copy.deepcopy(self.registry)
        self._case(no_expect, "GH-VALIDATE-DFD")["oracle"] = {"kind": "json_subset"}
        self.assertIn("GH-ORACLE-EXPECT", self._codes(no_expect))

    def test_neg_11_floating_version_token(self) -> None:
        for token in ("latest", "main", "head", "stable", "current"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["result_affecting_versions"] = \
                {"engine": token}
            self.assertIn("GH-FLOATING-VERSION", self._codes(mutated), token)

        empty = copy.deepcopy(self.registry)
        self._case(empty, "GH-VALIDATE-DFD")["result_affecting_versions"] = {}
        self.assertIn("GH-VERSIONS", self._codes(empty))

    def test_neg_12_skipped_case_never_counts_as_pass(self) -> None:
        for state in ("skipped", "quarantined", "waived", "disabled"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")["state"] = state
            self.assertIn("GH-CASE-STATE", self._codes(mutated), state)

    def test_neg_13_different_output_cannot_share_a_deterministic_key(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        one = evaluate_oracle(case, 0, json.dumps({"ok": True, "record_count": 3,
                                                   "data_classification": "synthetic_only"}))
        other = evaluate_oracle(case, 0, json.dumps({"ok": True, "record_count": 4,
                                                     "data_classification": "synthetic_only"}))
        self.assertNotEqual(one["normalised_output_digest"], other["normalised_output_digest"])
        self.assertTrue(one["passed"])
        self.assertFalse(other["passed"])

        # Un cambio de caso cambia el digest determinista aunque la salida coincida.
        variant = copy.deepcopy(case)
        variant["timeout_seconds"] = case["timeout_seconds"] - 1
        self.assertNotEqual(case_digest(case), case_digest(variant))

    def test_neg_14_manifest_carries_no_secrets_env_or_raw_payload(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        manifest = run_case(case, self.registry, ROOT)
        serialised = canonical_json(manifest)
        for forbidden in ("PATH", "SYSTEMROOT", "PYTHONPATH", "stdout", "stderr",
                          "environment", "secret", "token"):
            self.assertNotIn(forbidden, serialised, forbidden)
        self.assertLessEqual(
            set(manifest) - {
                "case_id", "suite", "passed", "reasons", "timed_out", "output_truncated",
                "runtime", "registry_digest", "case_digest", "input_digests",
                "expected_exit_code", "actual_exit_code", "normalised_output_digest",
                "deterministic_result_digest",
            }, set())

    def test_neg_15_runner_never_modifies_registry_or_fixtures(self) -> None:
        before = {
            "registry": sha256_file(REGISTRY_PATH),
            "fixture": sha256_file(FIXTURE_PATH),
            "manifest": sha256_file(FIXTURE_MANIFEST),
        }
        command_run(self.registry, ROOT, FAST_CASE)
        after = {
            "registry": sha256_file(REGISTRY_PATH),
            "fixture": sha256_file(FIXTURE_PATH),
            "manifest": sha256_file(FIXTURE_MANIFEST),
        }
        self.assertEqual(before, after)
        self.assertFalse(self.registry["auto_update_expected_allowed"])

    def test_neg_16_failing_case_never_exits_zero(self) -> None:
        mutated = copy.deepcopy(self.registry)
        case = self._case(mutated, FAST_CASE)
        case["oracle"]["expect"] = {"ok": True, "record_count": 99}
        payload, code = command_run(mutated, ROOT, FAST_CASE)
        self.assertEqual(1, code)
        self.assertFalse(payload["ok"])
        self.assertEqual([FAST_CASE], payload["failed"])

        invalid_registry = copy.deepcopy(self.registry)
        self._case(invalid_registry, "GH-VALIDATE-DFD")["state"] = "skipped"
        payload, code = command_run(invalid_registry, ROOT, None)
        self.assertEqual(1, code)
        self.assertNotIn("results", payload)

    def test_neg_17_unknown_case_selection_is_not_a_silent_success(self) -> None:
        payload, code = command_run(self.registry, ROOT, "GH-DOES-NOT-EXIST")
        self.assertEqual(1, code)
        self.assertFalse(payload["ok"])
        self.assertEqual([], payload["results"])

    def test_neg_18_subprocess_inherits_no_proxy_or_secret(self) -> None:
        hostile_parent = {
            "PATH": "/usr/bin",
            "HTTPS_PROXY": "http://proxy.example.invalid:8080",
            "http_proxy": "http://proxy.example.invalid:8080",
            "NO_PROXY": "localhost",
            "AWS_SECRET_ACCESS_KEY": "synthetic-not-a-real-key",
            "GITHUB_TOKEN": "synthetic-not-a-real-token",
        }
        env = build_environment(ROOT, hostile_parent)
        for forbidden in ("HTTPS_PROXY", "http_proxy", "NO_PROXY",
                          "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"):
            self.assertNotIn(forbidden, env, forbidden)
        self.assertEqual("/usr/bin", env["PATH"])
        self.assertEqual("0", env["PYTHONHASHSEED"])
        self.assertEqual(str(ROOT), env["PYTHONPATH"])

    # ================================================================== #
    # Refuerzos
    # ================================================================== #

    def test_registry_cannot_enable_network_or_auto_update(self) -> None:
        network = copy.deepcopy(self.registry)
        network["network_access"] = True
        self.assertIn("GH-NETWORK", self._codes(network))

        auto = copy.deepcopy(self.registry)
        auto["auto_update_expected_allowed"] = True
        self.assertIn("GH-AUTO-UPDATE", self._codes(auto))

    def test_agent_cannot_accept_the_registry(self) -> None:
        mutated = copy.deepcopy(self.registry)
        mutated["human_acceptance"] = "accepted"
        self.assertIn("GH-HUMAN-ACCEPTANCE", self._codes(mutated))

        status = copy.deepcopy(self.registry)
        status["status"] = "accepted"
        self.assertIn("GH-STATUS", self._codes(status))

    def test_case_must_declare_evidence_and_consumer_gate(self) -> None:
        for field in ("evidence_ref", "consumer_gates"):
            mutated = copy.deepcopy(self.registry)
            self._case(mutated, "GH-VALIDATE-DFD")[field] = "" if field == "evidence_ref" else []
            codes = self._codes(mutated)
            self.assertTrue({"GH-EVIDENCE-REF", "GH-CONSUMER-GATE"} & codes, field)

    def test_empty_registry_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.registry)
        mutated["cases"] = []
        self.assertIn("GH-CASES-MISSING", self._codes(mutated))

    def test_oracle_detects_a_wrong_exit_code(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        outcome = evaluate_oracle(case, 1, json.dumps({"ok": True, "record_count": 3,
                                                       "data_classification": "synthetic_only"}))
        self.assertFalse(outcome["passed"])
        self.assertTrue(any("exit_code" in reason for reason in outcome["reasons"]))

    def test_oracle_rejects_non_json_output_when_structure_is_expected(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        outcome = evaluate_oracle(case, 0, "not json at all")
        self.assertFalse(outcome["passed"])

    def test_input_digests_travel_in_the_deterministic_material(self) -> None:
        case = self._case(self.registry, FAST_CASE)
        manifest = run_case(case, self.registry, ROOT)
        self.assertIn("tests/golden/harness/sample_case_input.json", manifest["input_digests"])
        expected = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
        self.assertEqual(expected,
                         manifest["input_digests"]["tests/golden/harness/sample_case_input.json"])


if __name__ == "__main__":
    unittest.main()
