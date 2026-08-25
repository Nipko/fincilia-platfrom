from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from .validate import (CONTRACT, ROOT, SCRIPT, validate_contract,
                       validate_repository, validate_script)

DOCUMENT = json.loads(CONTRACT.read_text(encoding="utf-8"))
SOURCE = SCRIPT.read_text(encoding="utf-8")


def codes(findings) -> set[str]:
    return {item.code for item in findings}


class WslRuntimeContractTests(unittest.TestCase):
    def test_real_repository_is_valid(self) -> None:
        self.assertEqual([], validate_repository(ROOT))

    def test_foreign_project_or_compose_file_bites(self) -> None:
        for field, value in (("compose_project", "another-project"),
                             ("compose_file", "compose.yaml")):
            with self.subTest(field=field):
                document = copy.deepcopy(DOCUMENT)
                document[field] = value
                self.assertIn("WSL-CONTRACT", codes(validate_contract(document)))

    def test_destructive_lifecycle_claims_bite(self) -> None:
        for field in ("removes_orphans", "terminates_distribution",
                      "modifies_wsl_configuration", "installs_or_updates_dependencies"):
            with self.subTest(field=field):
                document = copy.deepcopy(DOCUMENT)
                document["lifecycle"][field] = True
                self.assertIn("WSL-DESTRUCTIVE", codes(validate_contract(document)))

    def test_volume_preservation_and_lock_bite_independently(self) -> None:
        for field in ("preserves_volumes", "lock_required"):
            with self.subTest(field=field):
                document = copy.deepcopy(DOCUMENT)
                document["lifecycle"][field] = False
                self.assertIn("WSL-LIFECYCLE", codes(validate_contract(document)))

    def test_state_cannot_grow_credentials_or_free_text(self) -> None:
        document = copy.deepcopy(DOCUMENT)
        document["keepalive"]["state_fields"].append("environment")
        self.assertIn("WSL-STATE-MINIMIZATION", codes(validate_contract(document)))

    def test_status_cannot_expose_labels_or_environment(self) -> None:
        document = copy.deepcopy(DOCUMENT)
        document["status_output"]["fields"].append("labels")
        document["status_output"]["includes_environment"] = True
        self.assertIn("WSL-STATUS-MINIMIZATION",
                      codes(validate_contract(document)))

    def test_visible_or_unvalidated_keeper_bites(self) -> None:
        document = copy.deepcopy(DOCUMENT)
        document["keepalive"]["window_style"] = "normal"
        document["keepalive"]["validates_pid_command_line"] = False
        found = codes(validate_contract(document))
        self.assertIn("WSL-NO-WINDOW", found)
        self.assertIn("WSL-PID-SCOPE", found)

    def test_unbounded_wait_and_gate_promotion_bite(self) -> None:
        document = copy.deepcopy(DOCUMENT)
        document["lifecycle"]["waits_for_docker_seconds"] = 0
        document["gate"]["status"] = "met"
        found = codes(validate_contract(document))
        self.assertIn("WSL-BOUNDED-WAIT", found)
        self.assertIn("WSL-GATE", found)

    def test_each_script_guard_bites_when_removed(self) -> None:
        guards = (
            "Set-StrictMode -Version Latest",
            "-WindowStyle Hidden",
            "'sleep', 'infinity'",
            "Get-CimInstance Win32_Process",
            "$Project = 'fincilia-local'",
            "$ComposeFile = 'infra/local/compose.yaml'",
            "'--cd', $RepositoryRoot",
            "[IO.FileMode]::CreateNew",
            "@('sh', 'infra/local/up.sh')",
            "$Project, 'down'",
            "services = @($services | Sort-Object service)",
        )
        for guard in guards:
            with self.subTest(guard=guard):
                mutated = SOURCE.replace(guard, "guard_removed", 1)
                self.assertTrue(validate_script(mutated))

    def test_destructive_or_dynamic_commands_bite(self) -> None:
        for command in ("docker compose down --volumes", "docker system prune",
                        "wsl --shutdown", "wsl --terminate Ubuntu",
                        "Remove-Item -Recurse C:\\temp", "Invoke-Expression x"):
            with self.subTest(command=command):
                self.assertIn("WSL-SCRIPT-DESTRUCTIVE",
                              codes(validate_script(SOURCE + "\n" + command)))

    def test_missing_files_fail_closed(self) -> None:
        with self.subTest("missing root"):
            findings = validate_repository(Path("Z:/fincilia-absent"))
            self.assertIn("WSL-CONTRACT-MISSING", codes(findings))


if __name__ == "__main__":
    unittest.main()
