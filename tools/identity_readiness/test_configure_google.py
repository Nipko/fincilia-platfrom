from __future__ import annotations

import json
import subprocess
import unittest

from .configure_google import (
    AwsCliMutation,
    ConfigurationError,
    _client_update_payload,
    configure_google,
)
from .test_probe import FakeCognito


CLIENT_ID = (
    "255965823492-" + "u" * 32 + ".apps.googleusercontent.com"
)
SECRET = "synthetic-google-secret-value"
SELECTORS = {
    "user_pool_id": "sa-east-1_Example123",
    "client_id": "client123",
    "domain_prefix": "fincilia-private-pilot",
}


class StatefulMutation:
    def __init__(self, cognito: FakeCognito) -> None:
        self.profile = "fincilia-sandbox"
        self.region = "sa-east-1"
        self.cognito = cognito
        self.calls: list[tuple[str, str, dict]] = []

    def invoke(self, service: str, operation: str, payload: dict):
        self.calls.append((service, operation, payload))
        if operation in {"create-identity-provider", "update-identity-provider"}:
            self.cognito.provider = {
                "ProviderType": "Google",
                "ProviderDetails": payload["ProviderDetails"],
                "AttributeMapping": payload["AttributeMapping"],
            }
        if operation == "update-user-pool-client":
            self.cognito.client = {
                **self.cognito.client,
                **payload,
            }
        return {}


def unconfigured_cognito() -> FakeCognito:
    value = FakeCognito()
    value.client["CallbackURLs"] = [
        "https://fincilia.com/api/auth/callback/cognito"
    ]
    value.client["LogoutURLs"] = ["https://fincilia.com/entrar"]
    value.client["SupportedIdentityProviders"] = ["COGNITO"]
    value.provider = {}
    return value


class GoogleConfigurationTests(unittest.TestCase):
    def test_secret_bearing_payload_uses_stdin_and_never_argv(self) -> None:
        observed = {}

        def runner(arguments, **kwargs):
            observed["arguments"] = arguments
            observed["kwargs"] = kwargs
            return subprocess.CompletedProcess(arguments, 0, "{}", "")

        mutation = AwsCliMutation(
            profile="fincilia-sandbox", region="sa-east-1", runner=runner
        )
        mutation.invoke("secretsmanager", "put-secret-value", {
            "SecretId": "known-name", "SecretString": SECRET,
        })
        self.assertNotIn(SECRET, " ".join(observed["arguments"]))
        self.assertIn(SECRET, observed["kwargs"]["input"])
        self.assertEqual("file:///dev/stdin",
                         observed["arguments"][8])
        self.assertFalse(observed["kwargs"]["shell"])

    def test_configuration_is_ordered_and_finishes_16_of_16(self) -> None:
        cognito = unconfigured_cognito()
        mutation = StatefulMutation(cognito)
        report = configure_google(
            selectors=SELECTORS,
            app_origin="https://fincilia.com",
            google_client_id=CLIENT_ID,
            google_client_secret=SECRET,
            cognito=cognito,
            mutation=mutation,
        )
        self.assertTrue(report["ok"])
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["real_data_authorized"])
        self.assertEqual("created", report["provider_operation"])
        self.assertEqual(
            [
                ("secretsmanager", "put-secret-value"),
                ("cognito-idp", "create-identity-provider"),
                ("cognito-idp", "update-user-pool-client"),
            ],
            [(service, operation) for service, operation, _ in mutation.calls],
        )
        serialized = json.dumps(report)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn(CLIENT_ID, serialized)
        self.assertEqual(["Google"], cognito.client["SupportedIdentityProviders"])

    def test_existing_provider_is_updated_without_provider_type(self) -> None:
        cognito = unconfigured_cognito()
        cognito.provider = {
            "ProviderType": "Google",
            "ProviderDetails": {
                "client_id": "old", "client_secret": "old",
                "authorize_scopes": "openid email profile",
            },
            "AttributeMapping": {
                "email": "email", "email_verified": "email_verified",
                "name": "name",
            },
        }
        mutation = StatefulMutation(cognito)
        report = configure_google(
            selectors=SELECTORS, app_origin="https://fincilia.com",
            google_client_id=CLIENT_ID, google_client_secret=SECRET,
            cognito=cognito, mutation=mutation,
        )
        provider_call = mutation.calls[1]
        self.assertEqual("update-identity-provider", provider_call[1])
        self.assertNotIn("ProviderType", provider_call[2])
        self.assertEqual("updated", report["provider_operation"])

    def test_unrelated_failed_control_prevents_every_mutation(self) -> None:
        cognito = unconfigured_cognito()
        cognito.pool["DeletionProtection"] = "INACTIVE"
        mutation = StatefulMutation(cognito)
        with self.assertRaises(ConfigurationError):
            configure_google(
                selectors=SELECTORS, app_origin="https://fincilia.com",
                google_client_id=CLIENT_ID, google_client_secret=SECRET,
                cognito=cognito, mutation=mutation,
            )
        self.assertEqual([], mutation.calls)

    def test_client_update_preserves_every_supported_observed_value(self) -> None:
        current = {
            "ClientName": "fincilia-web",
            "ClientSecret": "must-not-copy",
            "LastModifiedDate": "timestamp",
            "ExplicitAuthFlows": ["ALLOW_REFRESH_TOKEN_AUTH"],
            "AllowedOAuthFlows": ["code"],
            "AllowedOAuthScopes": ["openid", "email", "profile"],
            "AllowedOAuthFlowsUserPoolClient": True,
        }
        payload = _client_update_payload(
            current=current,
            user_pool_id=SELECTORS["user_pool_id"],
            app_client_id=SELECTORS["client_id"],
        )
        self.assertEqual(["ALLOW_REFRESH_TOKEN_AUTH"],
                         payload["ExplicitAuthFlows"])
        self.assertNotIn("ClientSecret", payload)
        self.assertNotIn("LastModifiedDate", payload)
        self.assertEqual(["Google"], payload["SupportedIdentityProviders"])


if __name__ == "__main__":
    unittest.main()
