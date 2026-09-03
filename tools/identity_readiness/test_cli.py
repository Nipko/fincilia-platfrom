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

    @patch("tools.identity_readiness.cli.discover_identity")
    @patch("tools.identity_readiness.cli.inspect_identity")
    @patch("tools.identity_readiness.cli.AwsCliCognito")
    def test_tofu_discovery_never_serializes_selectors(
            self, _aws, inspect, discover) -> None:
        discover.return_value = {
            "user_pool_id": "secret-pool-selector",
            "client_id": "secret-client-selector",
            "domain_prefix": "secret-domain-selector",
        }
        inspect.return_value = {
            "ok": True, "activation_authorized": False,
            "real_data_authorized": False, "checks": [],
        }
        output = io.StringIO()
        args = [
            "--profile", "fincilia-sandbox", "--region", "sa-east-1",
            "--tofu-dir", "infra/aws/t0", "--app-origin", "https://fincilia.com",
        ]
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(args))
        serialized = output.getvalue()
        self.assertNotIn("secret-pool-selector", serialized)
        self.assertNotIn("secret-client-selector", serialized)
        self.assertNotIn("secret-domain-selector", serialized)

    def test_partial_direct_selectors_fail_closed(self) -> None:
        output = io.StringIO()
        args = [
            "--profile", "fincilia-sandbox", "--region", "sa-east-1",
            "--user-pool-id", "pool-only", "--app-origin", "https://fincilia.com",
        ]
        with contextlib.redirect_stdout(output):
            self.assertEqual(2, main(args))
        self.assertEqual({"error": "ValueError", "ok": False},
                         json.loads(output.getvalue()))



if __name__ == "__main__":
    unittest.main()
