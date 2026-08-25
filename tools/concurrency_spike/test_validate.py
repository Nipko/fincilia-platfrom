from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .runner import Lab, RunnerError, environment, execute, probe_adapter, wsl_path
from .validate import EXPECTED_TESTS, load_model, validate_model


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_model()

    def codes(self, model: dict) -> set[str]:
        return {item["code"] for item in validate_model(model)}

    def mutate(self) -> dict:
        return copy.deepcopy(self.model)

    def test_contract_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model))

    def test_human_acceptance_cannot_be_fabricated(self) -> None:
        model = self.mutate(); model["human_acceptance"] = "accepted"
        self.assertIn("CSP-HUMAN", self.codes(model))

    def test_data_ceiling_is_synthetic(self) -> None:
        model = self.mutate(); model["data_ceiling"] = "real"
        self.assertIn("CSP-DATA", self.codes(model))

    def test_project_is_fixed(self) -> None:
        model = self.mutate(); model["runtime"]["project"] = "fincilia-local"
        self.assertIn("CSP-PROJECT", self.codes(model))

    def test_image_is_pinned(self) -> None:
        model = self.mutate(); model["runtime"]["image"] = "postgres:latest"
        self.assertIn("CSP-RUNTIME", self.codes(model))

    def test_ports_remain_unpublished(self) -> None:
        model = self.mutate(); model["runtime"]["published_ports"] = True
        self.assertIn("CSP-NETWORK", self.codes(model))

    def test_cleanup_is_required(self) -> None:
        model = self.mutate(); model["runtime"]["cleanup_with_volumes"] = False
        self.assertIn("CSP-CLEANUP", self.codes(model))

    def test_runtime_has_no_direct_writes(self) -> None:
        model = self.mutate(); model["roles"]["runtime_direct_table_writes"] = True
        self.assertIn("CSP-PRIVILEGES", self.codes(model))

    def test_function_allowlist_is_exact(self) -> None:
        model = self.mutate(); model["roles"]["runtime_function_allowlist"].pop()
        self.assertIn("CSP-FUNCTIONS", self.codes(model))

    def test_required_test_set_is_dynamic_and_exact(self) -> None:
        self.assertEqual(EXPECTED_TESTS, {case["id"] for case in self.model["cases"]})
        model = self.mutate(); model["cases"].pop()
        self.assertIn("CSP-CASES", self.codes(model))

    def test_TST_IDEM_001_concurrent_claim_case_is_materialized(self) -> None:
        case = next(item for item in self.model["cases"] if item["id"] == "TST-IDEM-001")
        self.assertEqual("FNC_IDEM_001_OK", case["marker"])

    def test_TST_IDEM_004_outbox_crash_case_is_materialized(self) -> None:
        case = next(item for item in self.model["cases"] if item["id"] == "TST-IDEM-004")
        self.assertEqual("FNC_IDEM_004_OK", case["marker"])

    def test_TST_IDEM_005_stale_lease_case_is_materialized(self) -> None:
        case = next(item for item in self.model["cases"] if item["id"] == "TST-IDEM-005")
        self.assertEqual("FNC_IDEM_005_OK", case["marker"])

    def test_shell_cannot_be_enabled(self) -> None:
        model = self.mutate(); model["safety"]["shell"] = True
        self.assertIn("CSP-SAFETY", self.codes(model))

    def test_agent_cannot_accept_architecture(self) -> None:
        model = self.mutate(); model["safety"]["agent_may_accept_architecture"] = True
        self.assertIn("CSP-AUTHORITY", self.codes(model))


class RunnerTests(unittest.TestCase):
    def adapter(self) -> dict:
        return {"id": "fake", "prefix": ("docker",), "translate": False}

    def test_environment_is_allowlisted(self) -> None:
        self.assertEqual({"PATH": "safe"}, environment({"PATH": "safe", "TOKEN": "secret"}))

    def test_shell_syntax_is_rejected(self) -> None:
        with self.assertRaises(RunnerError): execute(["docker", "ps", "&&", "whoami"])

    def test_empty_argv_is_rejected(self) -> None:
        with self.assertRaises(RunnerError): execute([])

    def test_project_escape_is_rejected(self) -> None:
        with self.assertRaises(RunnerError): Lab(self.adapter(), project="fincilia-local")

    def test_role_is_allowlisted(self) -> None:
        lab = Lab(self.adapter())
        with self.assertRaises(RunnerError): lab.psql_argv("postgres", "reset.sql")

    def test_sql_traversal_is_rejected(self) -> None:
        lab = Lab(self.adapter())
        with self.assertRaises(RunnerError): lab.psql_argv(
            "fnc_concurrency_runtime", "../db/init/001_bootstrap.sql")

    def test_unknown_sql_is_rejected(self) -> None:
        lab = Lab(self.adapter())
        with self.assertRaises(RunnerError): lab.psql_argv(
            "fnc_concurrency_runtime", "missing.sql")

    def test_compose_argv_always_fixes_project_and_file(self) -> None:
        argv = Lab(self.adapter()).compose_argv("config", "--quiet")
        self.assertIn(PROJECT := "fincilia-concurrency-spike", argv)
        self.assertEqual(PROJECT, argv[argv.index("-p") + 1])
        self.assertTrue(argv[argv.index("-f") + 1].endswith("spikes/FNC-DB-004/compose.yaml"))

    def test_wsl_path_is_deterministic(self) -> None:
        rendered = wsl_path(Path("C:/synthetic/path"))
        self.assertEqual("/mnt/c/synthetic/path", rendered)

    def test_probe_returns_none_when_runtime_is_unavailable(self) -> None:
        with patch("tools.concurrency_spike.runner.execute") as mocked:
            mocked.return_value.status = "unavailable"
            mocked.return_value.exit_code = None
            self.assertIsNone(probe_adapter((self.adapter() | {"probe": ("x",)},)))


if __name__ == "__main__":
    unittest.main()
