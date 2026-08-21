from __future__ import annotations

import unittest

from tools.quality_gate.repo_policy import scan_entries


class RepositoryPolicyTest(unittest.TestCase):
    def _codes(self, entries: dict[str, bytes]) -> set[str]:
        return {finding.code for finding in scan_entries(entries)}

    def test_clean_pinned_configuration_passes(self) -> None:
        entries = {
            ".github/workflows/ci.yml": (
                "permissions:\n  contents: read\nsteps:\n"
                "  - uses: actions/checkout@" + "a" * 40 + "\n"
            ).encode(),
            "spikes/example/compose.yaml": (
                "services:\n  db:\n    image: postgres:17@sha256:" + "b" * 64 + "\n"
            ).encode(),
            "src/example.py": b"# TODO FNC-PLT-003: synthetic follow-up\n",
        }
        self.assertEqual(set(), self._codes(entries))

    def test_forbidden_data_and_environment_paths_fail(self) -> None:
        codes = self._codes({"raw/customer.csv": b"x", ".env.local": b"X=y"})
        self.assertIn("POL-DATA-PATH-PROHIBITED", codes)
        self.assertIn("POL-ENV-TRACKED", codes)

    def test_private_key_and_high_signal_token_fail(self) -> None:
        github_token = ("gh" + "p_" + "A" * 36).encode()
        private_key = ("-----BEGIN " + "PRIVATE KEY-----\nSYN\n").encode()
        codes = self._codes(
            {
                "fixture.txt": github_token,
                "server.pem": private_key,
            }
        )
        self.assertIn("POL-GITHUB-TOKEN", codes)
        self.assertIn("POL-PRIVATE-KEY", codes)
        self.assertIn("POL-SENSITIVE-FILE", codes)

    def test_unpinned_action_and_image_fail(self) -> None:
        codes = self._codes(
            {
                ".github/workflows/ci.yml": (
                    b"permissions:\n  contents: read\nsteps:\n  - uses: actions/checkout@v7\n"
                ),
                "compose.yaml": b"services:\n  db:\n    image: postgres:17\n",
            }
        )
        self.assertIn("POL-ACTION-UNPINNED", codes)
        self.assertIn("POL-IMAGE-UNPINNED", codes)

    def test_dangerous_workflow_permissions_and_trigger_fail(self) -> None:
        codes = self._codes(
            {
                ".github/workflows/unsafe.yml": (
                    "pull_request_target:\npermissions:\n  contents: write\nsteps:\n"
                    "  - uses: actions/checkout@" + "c" * 40 + "\n"
                ).encode()
            }
        )
        self.assertIn("POL-WORKFLOW-DANGEROUS-TRIGGER", codes)
        self.assertIn("POL-WORKFLOW-WRITE-PERMISSION", codes)
        self.assertIn("POL-WORKFLOW-PERMISSIONS", codes)

    def test_anonymous_todo_fails_but_task_linked_todo_passes(self) -> None:
        marker = "TO" + "DO"
        self.assertIn(
            "POL-ANONYMOUS-TODO",
            self._codes({"src/a.py": f"# {marker}: later\n".encode()}),
        )
        self.assertNotIn(
            "POL-ANONYMOUS-TODO",
            self._codes({"src/a.py": f"# {marker} FNC-PLT-003: later\n".encode()}),
        )

    def test_example_env_is_allowed(self) -> None:
        self.assertNotIn("POL-ENV-TRACKED", self._codes({".env.example": b"TOKEN=placeholder\n"}))


if __name__ == "__main__":
    unittest.main()
