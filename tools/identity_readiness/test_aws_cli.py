from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from .aws_cli import AwsCliCognito


class AwsCliAdapterTests(unittest.TestCase):
    @patch("tools.identity_readiness.aws_cli.subprocess.run")
    def test_uses_argument_vector_and_never_shell(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"UserPool": {"Status": "ACTIVE"}}),
            stderr="")
        client = AwsCliCognito(profile="fincilia-sandbox", region="sa-east-1")
        result = client.describe_user_pool(UserPoolId="sa-east-1_Example123")
        self.assertEqual("ACTIVE", result["UserPool"]["Status"])
        command = run.call_args.args[0]
        self.assertEqual("aws", command[0])
        self.assertIn("--no-cli-pager", command)
        self.assertFalse(run.call_args.kwargs["shell"])

    @patch("tools.identity_readiness.aws_cli.subprocess.run")
    def test_provider_error_does_not_escape_in_exception(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 255, stdout="", stderr="secret-provider-detail")
        client = AwsCliCognito(profile="fincilia-sandbox", region="sa-east-1")
        with self.assertRaisesRegex(RuntimeError, "control plane request failed") as raised:
            client.describe_user_pool(UserPoolId="sa-east-1_Example123")
        self.assertNotIn("secret-provider-detail", str(raised.exception))

    @patch("tools.identity_readiness.aws_cli.subprocess.run")
    def test_missing_google_provider_becomes_a_redacted_failed_check(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 254, stdout="", stderr="ResourceNotFoundException: hidden")
        client = AwsCliCognito(profile="fincilia-sandbox", region="sa-east-1")
        self.assertEqual(
            {"IdentityProvider": {}},
            client.describe_identity_provider(
                UserPoolId="sa-east-1_Example123", ProviderName="Google"),
        )

    @patch("tools.identity_readiness.aws_cli.subprocess.run")
    def test_access_denied_is_not_misreported_as_missing_provider(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 254, stdout="", stderr="AccessDeniedException: hidden")
        client = AwsCliCognito(profile="fincilia-sandbox", region="sa-east-1")
        with self.assertRaisesRegex(RuntimeError, "control plane request failed"):
            client.describe_identity_provider(
                UserPoolId="sa-east-1_Example123", ProviderName="Google")

    def test_rejects_shell_metacharacters_before_execution(self) -> None:
        with self.assertRaises(ValueError):
            AwsCliCognito(profile="fincilia;evil", region="sa-east-1")


if __name__ == "__main__":
    unittest.main()
