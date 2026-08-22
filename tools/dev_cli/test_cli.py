"""Pruebas de la CLI de desarrollo (FNC-PLT-007).

La capa de proceso se prueba con dobles y con comandos locales inocuos. **Ninguno
de estos tests es evidencia de integracion con Docker**: lo unico que demuestran
es que la CLI construye lo que dice construir y que se niega a lo que dice negar.

Sin red, sin reloj de pared, sin locale del host, sin Git y sin orden de directorio.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tools.dev_cli import cli as dev_cli
from tools.dev_cli.process import (
    DEFAULT_ENV_ALLOWLIST,
    DevCliError,
    Outcome,
    StackLock,
    build_environment,
    external_argv,
    probe_dependency,
    python_argv,
    run,
)
from tools.dev_cli.registry import (
    ALLOWED_COMPOSE_FILE,
    ALLOWED_COMPOSE_PROJECT,
    ALLOWED_MODULES,
    EXIT_CHECK_FAILED,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INVALID_USAGE,
    EXIT_OK,
    EXIT_TIMEOUT,
    checks_for,
    known_groups,
    resolve_inside,
    safe_relative,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs/platform/developer-cli.json"
SOURCE_DIR = ROOT / "tools/dev_cli"


def run_cli(argv: list[str]) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dev_cli.main(argv)
    text = out.getvalue() or err.getvalue()
    if not text.strip():
        return code, {}
    try:
        return code, json.loads(text)
    except json.JSONDecodeError:
        return code, {"_text": text}


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Contrato
# --------------------------------------------------------------------------- #

class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def codes(self, contract: dict) -> set[str]:
        return {item.code for item in validate_contract(contract, ROOT)}

    def broken(self, **changes) -> dict:
        contract = copy.deepcopy(self.contract)
        for path, value in changes.items():
            keys = path.split("__")
            target = contract
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = value
        return contract

    def test_con_01_the_real_contract_is_valid(self) -> None:
        self.assertEqual(validate_contract(self.contract, ROOT), [])

    # 1. Modulo, cwd o Compose no allowlisted.
    def test_con_02_a_module_outside_the_allowlist_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["module"] = "os"
        contract["checks"][0]["argv"] = ["-m", "os"]
        self.assertIn("DVC-MODULE-ALLOWLIST", self.codes(contract))

    def test_con_03_a_foreign_compose_project_is_refused(self) -> None:
        self.assertIn("DVC-COMPOSE-PROJECT",
                      self.codes(self.broken(stack__compose_project="fincilia-db-spike")))

    def test_con_04_a_foreign_compose_file_is_refused(self) -> None:
        self.assertIn("DVC-COMPOSE-FILE",
                      self.codes(self.broken(
                          stack__compose_file="spikes/FNC-PLT-001/compose.yaml")))

    def test_con_05_a_cwd_outside_the_repository_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["cwd"] = "../elsewhere"
        self.assertIn("DVC-CWD", self.codes(contract))

    def test_con_06_an_absolute_cwd_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["cwd"] = "C:/Windows"
        self.assertIn("DVC-CWD", self.codes(contract))

    # 2 y 3. argv como string, metacaracteres, expansion.
    def test_con_07_an_argv_that_is_not_a_list_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["argv"] = "-m tools.architecture_model.validate"
        self.assertIn("DVC-ARGV-LIST", self.codes(contract))

    def test_con_08_shell_metacharacters_in_argv_are_refused(self) -> None:
        for poisoned in ("&& rm -rf /", "; whoami", "| cat", "`id`", "$(id)",
                         "tools/*", "~/secrets"):
            with self.subTest(poisoned=poisoned):
                contract = copy.deepcopy(self.contract)
                contract["checks"][0]["argv"] = [
                    "-m", "tools.architecture_model.validate", poisoned]
                self.assertIn("DVC-ARGV-SHELL", self.codes(contract))

    def test_con_09_argv_must_run_exactly_the_declared_module(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["argv"] = ["-m", "tools.privacy_model.validate"]
        self.assertIn("DVC-ARGV-FORM", self.codes(contract))

    def test_con_10_argv_must_start_with_dash_m(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["argv"] = ["tools.architecture_model.validate"]
        self.assertIn("DVC-ARGV-FORM", self.codes(contract))

    # 5. El entorno no hereda token, proxy ni secreto.
    def test_con_11_an_env_allowlist_that_leaks_is_refused(self) -> None:
        for leaky in ("HTTP_PROXY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY",
                      "DATABASE_PASSWORD", "API_KEY"):
            with self.subTest(leaky=leaky):
                contract = copy.deepcopy(self.contract)
                contract["environment_policy"]["env_allowlist"].append(leaky)
                self.assertIn("DVC-ENV-LEAK", self.codes(contract))

    def test_con_12_declaring_inherited_proxies_or_tokens_is_refused(self) -> None:
        for field in ("inherits_proxies", "inherits_tokens", "inherits_credentials",
                      "shell"):
            with self.subTest(field=field):
                contract = copy.deepcopy(self.contract)
                contract["environment_policy"][field] = True
                self.assertIn("DVC-ENV", self.codes(contract))

    # 9. `stack down` destructivo.
    def test_con_13_declaring_a_destructive_stack_is_refused(self) -> None:
        for field in ("removes_volumes", "removes_orphans", "purges_data",
                      "seeds_real_data", "runs_product_migrations"):
            with self.subTest(field=field):
                contract = copy.deepcopy(self.contract)
                contract["stack"][field] = True
                self.assertIn("DVC-STACK-DESTRUCTIVE", self.codes(contract))

    # 10. Lock obligatorio.
    def test_con_14_dropping_the_stack_lock_is_refused(self) -> None:
        self.assertIn("DVC-STACK-LOCK", self.codes(self.broken(stack__lock_required=False)))

    # 11. Doctor no puede exigir Docker.
    def test_con_15_requiring_docker_for_doctor_is_refused(self) -> None:
        self.assertIn("DVC-DEGRADATION",
                      self.codes(self.broken(degradation__doctor_requires_docker=True)))

    # 13. La CLI no marca gates.
    def test_con_16_claiming_authority_over_gates_is_refused(self) -> None:
        self.assertIn("DVC-AUTHORITY", self.codes(self.broken(writes_gate_or_status=True)))

    def test_con_17_claiming_it_installs_dependencies_is_refused(self) -> None:
        self.assertIn("DVC-AUTHORITY",
                      self.codes(self.broken(installs_or_updates_dependencies=True)))

    def test_con_18_marking_a_gate_as_met_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["gates"][0]["status"] = "met"
        self.assertIn("DVC-GATE", self.codes(contract))

    def test_con_19_recording_human_acceptance_is_refused(self) -> None:
        self.assertIn("DVC-ACCEPTANCE", self.codes(self.broken(human_acceptance="accepted")))

    def test_con_20_an_aggregate_score_as_gate_is_refused(self) -> None:
        self.assertIn("DVC-SCORE", self.codes(self.broken(aggregate_score_as_gate=True)))

    def test_con_21_altered_exit_codes_are_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["exit_codes"]["check_failed"] = 0
        self.assertIn("DVC-EXIT-CODES", self.codes(contract))

    def test_con_22_a_duplicate_check_id_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"].append(copy.deepcopy(contract["checks"][0]))
        self.assertIn("DVC-CHECK-DUPLICATE", self.codes(contract))

    def test_con_23_an_unknown_group_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["group"] = "everything"
        self.assertIn("DVC-GROUP", self.codes(contract))

    def test_con_24_an_unbounded_timeout_or_output_cap_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["timeout_seconds"] = 0
        self.assertIn("DVC-TIMEOUT", self.codes(contract))
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["max_output_bytes"] = 99_999_999
        self.assertIn("DVC-OUTPUT-CAP", self.codes(contract))

    def test_con_25_a_mutating_validate_check_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["classification"] = "local_reversible"
        self.assertIn("DVC-CLASSIFICATION", self.codes(contract))

    def test_con_26_an_undeclared_dependency_reference_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["checks"][0]["requires"] = ["kubernetes"]
        self.assertIn("DVC-DEPENDENCY", self.codes(contract))

    def test_con_27_a_probe_binary_outside_the_allowlist_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["dependencies"][0]["probe_argv"] = ["curl", "https://example.invalid"]
        self.assertIn("DVC-DEPENDENCY-ALLOWLIST", self.codes(contract))

    def test_con_28_an_empty_registry_is_refused(self) -> None:
        self.assertIn("DVC-CHECKS", self.codes(self.broken(checks=[])))

    def test_con_29_every_declared_module_is_in_the_code_allowlist(self) -> None:
        for check in self.contract["checks"]:
            self.assertIn(check["module"], ALLOWED_MODULES, check["id"])

    def test_con_30_no_expected_today_note_is_left_without_a_reason(self) -> None:
        for check in self.contract["checks"]:
            if "expected_today" in check:
                self.assertGreater(len(check["expected_today"]), 40, check["id"])


# --------------------------------------------------------------------------- #
# Seleccion determinista
# --------------------------------------------------------------------------- #

class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_sel_01_selection_is_sorted_and_independent_of_registry_order(self) -> None:
        shuffled = copy.deepcopy(self.contract)
        shuffled["checks"] = list(reversed(shuffled["checks"]))
        self.assertEqual(checks_for(self.contract, "validate", "all"),
                         checks_for(shuffled, "validate", "all"))

    def test_sel_02_group_all_is_the_union_of_the_groups(self) -> None:
        every = {check["id"] for check in checks_for(self.contract, "validate", "all")}
        union: set[str] = set()
        for group in known_groups(self.contract, "validate"):
            union |= {check["id"] for check in checks_for(self.contract, "validate", group)}
        self.assertEqual(every, union)

    def test_sel_03_validate_and_test_do_not_overlap(self) -> None:
        validate_ids = {check["id"] for check in checks_for(self.contract, "validate", "all")}
        test_ids = {check["id"] for check in checks_for(self.contract, "test", "all")}
        self.assertEqual(validate_ids & test_ids, set())

    def test_sel_04_every_group_declared_by_the_contract_has_checks(self) -> None:
        for kind in ("validate", "test"):
            for group in known_groups(self.contract, kind):
                self.assertTrue(checks_for(self.contract, kind, group), f"{kind}/{group}")


# --------------------------------------------------------------------------- #
# Capa de proceso
# --------------------------------------------------------------------------- #

class ProcessTests(unittest.TestCase):
    def test_proc_01_only_dash_m_invocations_are_allowed(self) -> None:
        with self.assertRaises(DevCliError):
            python_argv(["tools.architecture_model.validate"])
        with self.assertRaises(DevCliError):
            python_argv(["-c", "print(1)"])

    def test_proc_02_a_module_outside_the_allowlist_is_refused(self) -> None:
        with self.assertRaises(DevCliError):
            python_argv(["-m", "os"])

    def test_proc_03_shell_metacharacters_are_refused(self) -> None:
        for poisoned in ("a && b", "a; b", "a | b", "a > b", "`id`", "$(id)", "x*", "~/x"):
            with self.assertRaises(DevCliError):
                python_argv(["-m", "unittest", poisoned])

    def test_proc_04_an_external_binary_outside_the_allowlist_is_refused(self) -> None:
        with self.assertRaises(DevCliError):
            external_argv(["curl", "https://example.invalid"])
        self.assertEqual(external_argv(["docker", "--version"]), ["docker", "--version"])

    def test_proc_05_the_environment_drops_proxies_tokens_and_credentials(self) -> None:
        env = build_environment(
            list(DEFAULT_ENV_ALLOWLIST) + ["HTTP_PROXY", "GITHUB_TOKEN", "API_KEY"],
            {"PATH": "p", "HTTP_PROXY": "http://proxy", "GITHUB_TOKEN": "gh",
             "API_KEY": "k", "HOME": "/home/x"})
        self.assertEqual(env["PATH"], "p")
        self.assertEqual(env["HOME"], "/home/x")
        for forbidden in ("HTTP_PROXY", "GITHUB_TOKEN", "API_KEY"):
            self.assertNotIn(forbidden, env)

    def test_proc_06_the_environment_is_deterministic(self) -> None:
        env = build_environment(DEFAULT_ENV_ALLOWLIST, {"PATH": "p"})
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_proc_07_a_cwd_outside_the_tree_is_refused(self) -> None:
        for cwd in ("../elsewhere", "C:/Windows", "/etc"):
            with self.assertRaises(DevCliError):
                run([sys.executable, "-V"], root=ROOT, cwd=cwd)

    def test_proc_08_a_timeout_is_reported_as_timeout_not_as_pass(self) -> None:
        outcome = run([sys.executable, "-c", "__import__('time').sleep(5)"],
                      root=ROOT, timeout=1, check_id="slow")
        self.assertEqual(outcome.status, "timeout")
        self.assertIsNone(outcome.exit_code)

    def test_proc_09_truncated_output_is_a_failure_not_a_pass(self) -> None:
        outcome = run([sys.executable, "-c", "print('x' * 20000)"],
                      root=ROOT, cap=100, check_id="noisy")
        self.assertEqual(outcome.status, "failed")
        self.assertTrue(outcome.truncated)
        self.assertIn("truncated", outcome.detail)

    def test_proc_10_a_missing_binary_is_a_diagnosis_not_a_traceback(self) -> None:
        outcome = run(["fincilia-binary-that-does-not-exist"], root=ROOT, check_id="absent")
        self.assertEqual(outcome.status, "dependency_missing")
        self.assertIsNone(outcome.exit_code)

    def test_proc_11_a_non_zero_exit_is_a_failure(self) -> None:
        outcome = run([sys.executable, "-c", "raise SystemExit(7)"], root=ROOT,
                      check_id="failing")
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.exit_code, 7)

    def test_proc_12_the_outcome_hides_output_by_default(self) -> None:
        outcome = run([sys.executable, "-c", "print(input())"], root=ROOT, check_id="quiet")
        payload = outcome.as_dict()
        self.assertNotIn("stdout_tail", payload)
        self.assertIn("stdout_tail", outcome.as_dict(include_output=True))

    def test_proc_13_a_missing_dependency_reports_its_declared_diagnosis(self) -> None:
        dependency = {"id": "absent_tool", "kind": "external_binary", "required": False,
                      "probe_argv": ["docker", "--version"],
                      "diagnosis": "diagnostico estable declarado en el contrato"}
        result = probe_dependency(dependency, ROOT)
        self.assertIn(result["status"], ("available", "missing", "unusable"))
        if result["status"] != "available":
            self.assertEqual(result["detail"],
                             "diagnostico estable declarado en el contrato")

    def test_proc_14_an_invalid_probe_never_raises(self) -> None:
        dependency = {"id": "bad", "required": True, "probe_argv": ["rm", "-rf", "/"],
                      "diagnosis": "d"}
        result = probe_dependency(dependency, ROOT)
        self.assertEqual(result["status"], "invalid_probe")

    def test_proc_15_paths_are_contained(self) -> None:
        self.assertTrue(safe_relative("."))
        for candidate in ("../x", "/etc/passwd", "C:/Windows", "a/../../b", ""):
            self.assertFalse(safe_relative(candidate), candidate)
        self.assertIsNone(resolve_inside(ROOT, "docs/../../outside"))
        self.assertIsNotNone(resolve_inside(ROOT, "tools"))


# --------------------------------------------------------------------------- #
# Lock de stack
# --------------------------------------------------------------------------- #

class StackLockTests(unittest.TestCase):
    def test_lock_01_a_second_holder_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = StackLock(Path(directory))
            first.acquire()
            try:
                second = StackLock(Path(directory))
                with self.assertRaises(DevCliError):
                    second.acquire()
            finally:
                first.release()

    def test_lock_02_the_lock_is_released_and_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with StackLock(Path(directory)) as lock:
                self.assertTrue(lock.path.exists())
            self.assertFalse(lock.path.exists())
            with StackLock(Path(directory)):
                pass

    def test_lock_03_the_lock_records_the_holding_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with StackLock(Path(directory)) as lock:
                self.assertEqual(lock.path.read_text(encoding="ascii"), str(os.getpid()))

    def test_lock_04_the_error_names_the_file_to_remove(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with StackLock(Path(directory)) as held:
                with self.assertRaises(DevCliError) as raised:
                    StackLock(Path(directory)).acquire()
                self.assertIn(str(held.path), str(raised.exception))


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #

class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_cmd_01_doctor_works_without_docker(self) -> None:
        code, payload = run_cli(["doctor"])
        self.assertIn(code, (EXIT_OK, EXIT_CHECK_FAILED))
        self.assertTrue(payload["contract_valid"])
        self.assertTrue(payload["python"]["satisfied"])
        docker = [item for item in payload["dependencies"]
                  if item["id"].startswith("docker")]
        self.assertTrue(docker)
        self.assertTrue(all(not item["required"] for item in docker))

    def test_cmd_02_doctor_never_prints_the_environment(self) -> None:
        _, payload = run_cli(["doctor"])
        serialised = json.dumps(payload, ensure_ascii=False)
        for forbidden in ("PATH=", "PYTHONPATH", "USERPROFILE", "TEMP=", ".env"):
            self.assertNotIn(forbidden, serialised, forbidden)

    def test_cmd_03_an_unknown_group_is_invalid_usage(self) -> None:
        code, payload = run_cli(["validate", "--group", "everything"])
        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertEqual(payload["checks"], [])

    def test_cmd_04_an_invalid_contract_stops_before_executing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken_path = Path(directory) / "broken.json"
            contract = copy.deepcopy(self.contract)
            contract["task_id"] = "FNC-WRONG-000"
            broken_path.write_text(json.dumps(contract), encoding="utf-8")
            code, payload = run_cli(["--contract", str(broken_path), "validate"])
            self.assertEqual(code, EXIT_INVALID_USAGE)
            self.assertEqual(payload["checks"], [])

    def test_cmd_05_an_unreadable_contract_is_invalid_usage(self) -> None:
        code, _ = run_cli(["--contract", str(ROOT / "docs/platform/absent.json"), "doctor"])
        self.assertEqual(code, EXIT_INVALID_USAGE)

    def test_cmd_06_a_traversing_root_is_refused(self) -> None:
        code, _ = run_cli(["--root", "../outside", "doctor"])
        self.assertEqual(code, EXIT_INVALID_USAGE)

    def test_cmd_07_validate_keeps_every_individual_result(self) -> None:
        code, payload = run_cli(["validate", "--group", "core"])
        expected = {check["id"] for check in checks_for(self.contract, "validate", "core")}
        self.assertEqual({item["check_id"] for item in payload["checks"]}, expected)
        self.assertEqual(payload["executed"], len(expected))
        self.assertIsNone(payload["aggregate_score"])

    def test_cmd_08_a_failing_check_survives_in_the_summary(self) -> None:
        code, payload = run_cli(["validate", "--group", "security"])
        if payload["failed_checks"]:
            self.assertEqual(code, EXIT_CHECK_FAILED)
            for identifier in payload["failed_checks"]:
                row = next(item for item in payload["checks"]
                           if item["check_id"] == identifier)
                self.assertEqual(row["status"], "failed")
        self.assertIn("failed_checks", payload)

    def test_cmd_09_an_expected_failure_does_not_become_a_pass(self) -> None:
        _, payload = run_cli(["validate", "--group", "security"])
        for identifier in payload.get("expected_failures", {}):
            self.assertIn(identifier, payload["failed_checks"])
        self.assertFalse(set(payload.get("expected_failures", {})) &
                         {item["check_id"] for item in payload["checks"]
                          if item["status"] == "passed"})

    def test_cmd_10_stack_status_is_read_only_and_never_destructive(self) -> None:
        _, payload = run_cli(["stack", "status"])
        if "classification" in payload:
            self.assertEqual(payload["classification"], "read_only")
            self.assertFalse(payload["removes_volumes"])
            self.assertFalse(payload["removes_orphans"])

    def test_cmd_11_stack_without_docker_is_a_stable_diagnosis(self) -> None:
        code, payload = run_cli(["stack", "up"])
        if code == EXIT_DEPENDENCY_MISSING:
            self.assertIn("Docker", payload["reason"])
            self.assertNotIn("Traceback", json.dumps(payload))

    def test_cmd_12_the_compose_argv_never_removes_volumes_or_orphans(self) -> None:
        argv = dev_cli._compose_argv(self.contract, ROOT, "down")
        self.assertNotIn("--volumes", argv)
        self.assertNotIn("--remove-orphans", argv)
        self.assertEqual(argv[argv.index("-p") + 1], ALLOWED_COMPOSE_PROJECT)
        self.assertTrue(argv[argv.index("-f") + 1].endswith(ALLOWED_COMPOSE_FILE))

    def test_cmd_13_the_compose_argv_refuses_a_missing_compose_file(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["stack"]["compose_file"] = "infra/local/absent.yaml"
        with self.assertRaises(DevCliError):
            dev_cli._compose_argv(contract, ROOT, "down")

    def test_cmd_14_evidence_summary_reads_without_executing(self) -> None:
        code, payload = run_cli(["evidence", "summary"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(payload["sources"])
        self.assertEqual(payload["unreadable_sources"], [])
        self.assertIsNone(payload["aggregate_score"])

    def test_cmd_15_evidence_reports_no_source_as_humanly_accepted(self) -> None:
        _, payload = run_cli(["evidence", "summary"])
        self.assertEqual(payload["sources_with_human_acceptance"], [])
        self.assertGreater(payload["total_unresolved_decisions"], 0)

    def test_cmd_16_evidence_carries_no_payload_or_secret(self) -> None:
        _, payload = run_cli(["evidence", "summary"])
        serialised = json.dumps(payload, ensure_ascii=False)
        for forbidden in ("PASSWORD", "password", "SECRET", "token", "@gmail", "NIT"):
            self.assertNotIn(forbidden, serialised, forbidden)

    def test_cmd_17_text_output_adds_nothing_the_json_does_not_have(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            dev_cli.main(["--format", "text", "evidence", "summary"])
        text = out.getvalue()
        self.assertIn("evidence summary", text)
        self.assertNotIn("{", text.splitlines()[0])

    def test_cmd_18_the_cli_never_reports_a_gate_as_met(self) -> None:
        for arguments in (["doctor"], ["evidence", "summary"],
                          ["validate", "--group", "core"]):
            with self.subTest(arguments=arguments):
                _, payload = run_cli(arguments)
                serialised = json.dumps(payload, ensure_ascii=False)
                self.assertNotIn('"S1-READY": "met"', serialised)
                self.assertNotIn('"status": "met"', serialised)

    def test_cmd_19_running_twice_gives_the_same_verdict(self) -> None:
        first_code, first = run_cli(["validate", "--group", "core"])
        second_code, second = run_cli(["validate", "--group", "core"])
        self.assertEqual(first_code, second_code)
        self.assertEqual([item["check_id"] for item in first["checks"]],
                         [item["check_id"] for item in second["checks"]])
        self.assertEqual(first["counts"], second["counts"])

    def test_cmd_20_the_contract_on_disk_is_never_modified_by_a_run(self) -> None:
        before = CONTRACT_PATH.read_bytes()
        run_cli(["doctor"])
        run_cli(["validate", "--group", "core"])
        run_cli(["evidence", "summary"])
        self.assertEqual(CONTRACT_PATH.read_bytes(), before)


# --------------------------------------------------------------------------- #
# Disciplina del codigo fuente
# --------------------------------------------------------------------------- #

class SourceDisciplineTests(unittest.TestCase):
    def sources(self) -> list[Path]:
        return [path for path in sorted(SOURCE_DIR.glob("*.py"))
                if path.name != "test_cli.py"]

    def test_src_01_no_shell_eval_exec_or_system(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            for token in ("shell=True", "eval(", "exec(", "os.system", "popen"):
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_02_no_network_clock_or_randomness(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            for token in ("import socket", "import urllib", "import requests",
                          "import random", "datetime.now(", "time.time("):
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_03_no_anonymous_todo(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in self.sources():
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)

    def test_src_04_the_environment_is_never_read_wholesale(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("dict(os.environ)", text, source.name)
            self.assertNotIn("os.environ.copy()", text, source.name)

    def test_src_05_the_outcome_dataclass_never_stores_the_environment(self) -> None:
        outcome = Outcome("x", "passed", 0)
        self.assertNotIn("env", outcome.as_dict())
        self.assertNotIn("env", outcome.as_dict(include_output=True))


if __name__ == "__main__":
    unittest.main()
