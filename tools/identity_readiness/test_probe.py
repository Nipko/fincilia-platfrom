from __future__ import annotations

import json
import unittest

from .probe import inspect_identity


class FakeCognito:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.pool = {
            "DeletionProtection": "ACTIVE", "MfaConfiguration": "ON",
            "AdminCreateUserConfig": {"AllowAdminCreateUserOnly": True},
        }
        self.client = {
            "AllowedOAuthFlowsUserPoolClient": True,
            "AllowedOAuthFlows": ["code"],
            "AllowedOAuthScopes": ["openid", "email", "profile"],
            "CallbackURLs": [
                "https://beta.fincilia.test/api/auth/callback/cognito"],
            "LogoutURLs": ["https://beta.fincilia.test/entrar"],
            "SupportedIdentityProviders": ["Google"],
            "PreventUserExistenceErrors": "ENABLED",
            "EnableTokenRevocation": True,
            "AccessTokenValidity": 15, "IdTokenValidity": 15,
            "RefreshTokenValidity": 1,
            "TokenValidityUnits": {
                "AccessToken": "minutes", "IdToken": "minutes",
                "RefreshToken": "days",
            },
        }
        self.provider = {
            "ProviderType": "Google",
            "ProviderDetails": {
                "client_id": "opaque-client-id",
                "client_secret": "MUST-NOT-APPEAR-IN-REPORT",
                "authorize_scopes": "openid email profile",
            },
            "AttributeMapping": {
                "email": "email", "email_verified": "email_verified",
                "name": "name",
            },
        }
        self.domain = {"Status": "ACTIVE"}

    def describe_user_pool(self, **kwargs):
        self.calls.append(("pool", kwargs)); return {"UserPool": self.pool}

    def describe_user_pool_client(self, **kwargs):
        self.calls.append(("client", kwargs)); return {"UserPoolClient": self.client}

    def describe_identity_provider(self, **kwargs):
        self.calls.append(("provider", kwargs)); return {"IdentityProvider": self.provider}

    def describe_user_pool_domain(self, **kwargs):
        self.calls.append(("domain", kwargs)); return {"DomainDescription": self.domain}


class IdentityReadinessTests(unittest.TestCase):
    def report(self, client: FakeCognito | None = None):
        return inspect_identity(
            cognito=client or FakeCognito(), user_pool_id="pool-id",
            client_id="client-id", domain_prefix="fincilia-private-pilot",
            app_origin="https://beta.fincilia.test")

    def test_safe_live_shape_passes_without_disclosing_control_plane_values(self):
        fake = FakeCognito()
        report = self.report(fake)
        self.assertTrue(report["ok"])
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["real_data_authorized"])
        serialized = json.dumps(report)
        self.assertNotIn("MUST-NOT-APPEAR", serialized)
        self.assertNotIn("pool-id", serialized)
        self.assertNotIn("client-id", serialized)
        self.assertEqual(["pool", "client", "provider", "domain"],
                         [name for name, _ in fake.calls])

    def test_each_security_boundary_fails_independently(self):
        mutations = [
            lambda f: f.pool.update({"DeletionProtection": "INACTIVE"}),
            lambda f: f.pool["AdminCreateUserConfig"].update(
                {"AllowAdminCreateUserOnly": False}),
            lambda f: f.client.update({"SupportedIdentityProviders": ["COGNITO", "Google"]}),
            lambda f: f.client.update({"AllowedOAuthScopes": ["openid", "email", "profile", "drive"]}),
            lambda f: f.client.update({"CallbackURLs": ["https://evil.test/callback"]}),
            lambda f: f.client.update({"EnableTokenRevocation": False}),
            lambda f: f.provider["ProviderDetails"].update(
                {"authorize_scopes": "openid email profile drive"}),
            lambda f: f.domain.update({"Status": "CREATING"}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                fake = FakeCognito(); mutate(fake)
                self.assertFalse(self.report(fake)["ok"])

    def test_http_or_non_origin_application_url_is_rejected_before_aws(self):
        fake = FakeCognito()
        for origin in ("http://beta.fincilia.test", "https://beta.fincilia.test/path"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                inspect_identity(
                    cognito=fake, user_pool_id="pool", client_id="client",
                    domain_prefix="domain", app_origin=origin)
        self.assertEqual([], fake.calls)


if __name__ == "__main__":
    unittest.main()
