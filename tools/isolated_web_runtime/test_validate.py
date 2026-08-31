from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from .model import validate_contract, validate_repository, validate_scripts


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "docs/platform/isolated-web-runtime.json").read_text(
    encoding="utf-8"
))
SHELL_PATH = ROOT / "infra/local/test-web-isolated.sh"
POWERSHELL_PATH = ROOT / "infra/local/test-web-isolated.ps1"
COMPOSE = (ROOT / "infra/local/compose.yaml").read_text(encoding="utf-8")


def codes(findings) -> set[str]:
    return {item.code for item in findings}


class ContractTests(unittest.TestCase):
    def mutate(self, *path_and_value):
        model = copy.deepcopy(CONTRACT)
        *path, value = path_and_value
        target = model
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return model

    def test_contract_is_valid(self) -> None:
        self.assertEqual([], validate_contract(CONTRACT))

    def test_real_repository_is_valid(self) -> None:
        if not SHELL_PATH.is_file() or not POWERSHELL_PATH.is_file():
            self.skipTest("entrypoints arrive in the implementation commit")
        self.assertEqual([], validate_repository(ROOT))

    def test_data_ceiling_bites(self) -> None:
        self.assertIn("IWR-DATA", codes(validate_contract(
            self.mutate("data_ceiling", "customer_data")
        )))

    def test_project_drift_bites(self) -> None:
        for runtime, value in (("persistent_runtime", "demo"),
                               ("disposable_runtime", "random")):
            with self.subTest(runtime=runtime):
                expected = "IWR-PERSISTENT-PROJECT" if runtime.startswith("persistent") \
                    else "IWR-DISPOSABLE-PROJECT"
                self.assertIn(expected, codes(validate_contract(
                    self.mutate(runtime, "project", value)
                )))

    def test_same_project_bites_independently(self) -> None:
        model = self.mutate("disposable_runtime", "project", "fincilia-local")
        self.assertIn("IWR-PROJECT-COLLISION", codes(validate_contract(model)))

    def test_shared_volume_or_network_bites(self) -> None:
        for resource in ("volumes", "networks"):
            with self.subTest(resource=resource):
                model = copy.deepcopy(CONTRACT)
                model["disposable_runtime"][resource][0] = \
                    model["persistent_runtime"][resource][0]
                self.assertIn("IWR-RESOURCE-COLLISION", codes(validate_contract(model)))

    def test_bad_disposable_prefix_bites(self) -> None:
        model = self.mutate("disposable_runtime", "volumes", ["tmp_pg", "tmp_object"])
        self.assertIn("IWR-RESOURCE-NAME", codes(validate_contract(model)))

    def test_resource_input_bites(self) -> None:
        model = self.mutate("disposable_runtime", "accepts_resource_name_input", True)
        self.assertIn("IWR-RESOURCE-INPUT", codes(validate_contract(model)))

    def test_reusing_demo_port_bites(self) -> None:
        model = self.mutate("disposable_runtime", "published_ports", {
            "web": 53000, "api": 58180, "object": 59100, "object_console": 59101,
        })
        self.assertIn("IWR-PORT-COLLISION", codes(validate_contract(model)))

    def test_duplicate_disposable_port_bites(self) -> None:
        model = self.mutate("disposable_runtime", "published_ports", {
            "web": 53100, "api": 53100, "object": 59100, "object_console": 59101,
        })
        self.assertIn("IWR-PORT-COLLISION", codes(validate_contract(model)))

    def test_public_bind_bites(self) -> None:
        model = self.mutate("disposable_runtime", "bind_address", "0.0.0.0")
        self.assertIn("IWR-LOOPBACK", codes(validate_contract(model)))

    def test_api_helpers_cannot_fall_back_to_the_demo(self) -> None:
        model = self.mutate("execution", "api_base_url", "http://127.0.0.1:58080")
        self.assertIn("IWR-API-URL", codes(validate_contract(model)))

    def test_each_cleanup_guarantee_bites(self) -> None:
        targets = (
            ("disposable_runtime", "precleans_exact_project"),
            ("disposable_runtime", "removes_volumes_on_cleanup"),
            ("disposable_runtime", "removes_orphans_on_cleanup"),
            ("execution", "cleanup_in_finally"),
            ("execution", "cleanup_after_success"),
            ("execution", "cleanup_after_failure"),
        )
        for section, field in targets:
            with self.subTest(field=field):
                self.assertIn("IWR-CLEANUP", codes(validate_contract(
                    self.mutate(section, field, False)
                )))

    def test_phase_order_bites(self) -> None:
        phases = list(CONTRACT["execution"]["phases"])
        phases[1], phases[-1] = phases[-1], phases[1]
        self.assertIn("IWR-PHASES", codes(validate_contract(
            self.mutate("execution", "phases", phases)
        )))

    def test_omitting_each_browser_suite_bites(self) -> None:
        for scripts in (
            ["test:e2e", "test:a11y"],
            ["test:bootstrap", "test:a11y"],
            ["test:bootstrap", "test:e2e"],
        ):
            with self.subTest(scripts=scripts):
                self.assertIn("IWR-SUITES", codes(validate_contract(
                    self.mutate("execution", "npm_scripts", scripts)
                )))

    def test_parallel_workers_bite(self) -> None:
        self.assertIn("IWR-WORKERS", codes(validate_contract(
            self.mutate("execution", "playwright_workers", 4)
        )))

    def test_one_run_is_not_repeatability(self) -> None:
        self.assertIn("IWR-REPEAT", codes(validate_contract(
            self.mutate("execution", "repeatable_runs_required", 1)
        )))


class EntrypointTests(unittest.TestCase):
    def validate(self, shell: str, powershell: str, compose: str = COMPOSE) -> set[str]:
        return codes(validate_scripts(shell, powershell, compose))

    def test_shell_project_cannot_come_from_input(self) -> None:
        findings = self.validate(
            'PROJECT=${PROJECT:-fincilia-e2e}\nEXPECTED_PROJECT=fincilia-e2e\n',
            "finally up-empty verify-backend test:bootstrap test:e2e test:a11y http://127.0.0.1:53100 "
            "test-web-isolated.sh 'down' 'assert-clean'",
        )
        self.assertIn("IWR-PROJECT-INPUT", findings)

    def test_shell_cannot_name_persistent_resources(self) -> None:
        base = ("PROJECT=fincilia-e2e\nEXPECTED_PROJECT=fincilia-e2e\n"
                "PGDATA_VOLUME=fincilia_e2e_pgdata\n"
                "OBJECTDATA_VOLUME=fincilia_e2e_objectdata\n"
                "PRIVATE_NETWORK=fincilia_e2e_private\nEDGE_NETWORK=fincilia_e2e_edge\n"
                "compose down --volumes --remove-orphans\npython -m db.seed.local\n"
                "/health/ready\nassert_isolated\nassert_absent\n")
        powershell = ("finally up-empty verify-backend test:bootstrap test:e2e test:a11y http://127.0.0.1:53100 "
                      "http://127.0.0.1:58180 FINCILIA_E2E_API_URL "
                      "test-web-isolated.sh 'down' 'assert-clean'")
        for resource in ("fincilia_local_pgdata", "fincilia_local_private"):
            with self.subTest(resource=resource):
                self.assertIn("IWR-PERSISTENT-TARGET", self.validate(
                    base + resource, powershell
                ))

    def test_removing_finally_bites(self) -> None:
        if not SHELL_PATH.is_file() or not POWERSHELL_PATH.is_file():
            self.skipTest("entrypoints arrive in the implementation commit")
        shell = SHELL_PATH.read_text(encoding="utf-8")
        powershell = POWERSHELL_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("IWR-POWERSHELL", self.validate(
            shell, powershell.replace("finally", "removed", 1)
        ))

    def test_removing_network_override_bites(self) -> None:
        mutated = COMPOSE.replace(
            "${FINCILIA_LOCAL_PRIVATE_NETWORK:-fincilia_local_private}",
            "fincilia_local_private",
        )
        self.assertIn("IWR-COMPOSE-OVERRIDE", self.validate("", "", mutated))


if __name__ == "__main__":
    unittest.main()
