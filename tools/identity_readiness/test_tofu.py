from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from .tofu import ROOT, discover_identity


class TofuIdentityDiscoveryTests(unittest.TestCase):
    def outputs(self) -> str:
        return json.dumps({
            "cognito_user_pool_id": {"value": "pool-sensitive"},
            "cognito_google_web_client_id": {"value": "client-sensitive"},
            "cognito_domain": {"value": "domain-sensitive"},
        })

    @patch("tools.identity_readiness.tofu.subprocess.run")
    def test_discovers_in_memory_with_shell_disabled(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=self.outputs(), stderr="")
        result = discover_identity(
            directory=ROOT / "infra" / "aws" / "t0",
            profile="fincilia-sandbox", region="sa-east-1")
        self.assertEqual("pool-sensitive", result["user_pool_id"])
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual("tofu", run.call_args.args[0][0])
        self.assertEqual("fincilia-sandbox",
                         run.call_args.kwargs["env"]["AWS_PROFILE"])

    @patch("tools.identity_readiness.tofu.subprocess.run")
    def test_provider_failure_is_neutral(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="state-secret")
        with self.assertRaisesRegex(RuntimeError, "discovery failed") as raised:
            discover_identity(
                directory=ROOT / "infra" / "aws" / "t0",
                profile="fincilia-sandbox", region="sa-east-1")
        self.assertNotIn("state-secret", str(raised.exception))

    @patch("tools.identity_readiness.tofu.subprocess.run")
    def test_missing_output_fails_closed(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({}), stderr="")
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            discover_identity(
                directory=ROOT / "infra" / "aws" / "t0",
                profile="fincilia-sandbox", region="sa-east-1")

    def test_directory_outside_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            discover_identity(
                directory=Path(ROOT.anchor), profile="safe", region="sa-east-1")

    def test_traversal_is_rejected_even_if_it_resolves_inside(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical path"):
            discover_identity(
                directory=ROOT / "infra" / ".." / "infra" / "aws" / "t0",
                profile="safe", region="sa-east-1")


if __name__ == "__main__":
    unittest.main()
