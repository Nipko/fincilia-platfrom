from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from .cli import main


ARGS = [
    "--profile", "fincilia-sandbox", "--region", "sa-east-1",
    "--user-pool-id", "sa-east-1_Example123", "--client-id", "client123",
    "--domain-prefix", "fincilia-private-pilot",
    "--app-origin", "https://beta.fincilia.test",
]


class IdentityReadinessCliTests(unittest.TestCase):
    @patch("tools.identity_readiness.cli.inspect_identity")
    @patch("tools.identity_readiness.cli.AwsCliCognito")
    def test_exit_zero_only_for_a_passing_probe(self, aws, inspect) -> None:
        inspect.return_value = {"ok": True, "activation_authorized": False,
                                "real_data_authorized": False, "checks": []}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(ARGS))
        self.assertTrue(json.loads(output.getvalue())["ok"])
        aws.assert_called_once_with(profile="fincilia-sandbox", region="sa-east-1")

    @patch("tools.identity_readiness.cli.inspect_identity")
    @patch("tools.identity_readiness.cli.AwsCliCognito")
    def test_valid_but_not_ready_uses_distinct_exit(self, _aws, inspect) -> None:
        inspect.return_value = {"ok": False, "activation_authorized": False,
                                "real_data_authorized": False, "checks": []}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(10, main(ARGS))

    @patch("tools.identity_readiness.cli.AwsCliCognito")
    def test_provider_failure_is_redacted(self, aws) -> None:
        aws.side_effect = RuntimeError("provider secret detail")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(2, main(ARGS))
        self.assertEqual({"error": "RuntimeError", "ok": False},
                         json.loads(output.getvalue()))
        self.assertNotIn("provider secret detail", output.getvalue())


if __name__ == "__main__":
    unittest.main()
