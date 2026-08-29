"""Evalua Cognito sin devolver identificadores, usuarios o secretos."""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import urlparse


class CognitoControlPlane(Protocol):
    def describe_user_pool(self, **kwargs: Any) -> dict[str, Any]: ...
    def describe_user_pool_client(self, **kwargs: Any) -> dict[str, Any]: ...
    def describe_identity_provider(self, **kwargs: Any) -> dict[str, Any]: ...
    def describe_user_pool_domain(self, **kwargs: Any) -> dict[str, Any]: ...


def _check(identifier: str, condition: bool, detail: str) -> dict[str, Any]:
    return {"id": identifier, "status": "pass" if condition else "fail",
            "detail": detail}


def _exact_https_origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username \
            or parsed.password or parsed.path not in ("", "/") \
            or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("app_origin must be an exact HTTPS origin")
    return f"https://{parsed.netloc}"


def inspect_identity(*, cognito: CognitoControlPlane, user_pool_id: str,
                     client_id: str, domain_prefix: str,
                     app_origin: str) -> dict[str, Any]:
    """Return a secret-free readiness report from four bounded AWS calls."""
    origin = _exact_https_origin(app_origin)
    pool = cognito.describe_user_pool(UserPoolId=user_pool_id)["UserPool"]
    client = cognito.describe_user_pool_client(
        UserPoolId=user_pool_id, ClientId=client_id)["UserPoolClient"]
    provider = cognito.describe_identity_provider(
        UserPoolId=user_pool_id, ProviderName="Google")["IdentityProvider"]
    domain = cognito.describe_user_pool_domain(
        Domain=domain_prefix)["DomainDescription"]

    admin = pool.get("AdminCreateUserConfig") or {}
    scopes = client.get("AllowedOAuthScopes") or []
    provider_details = provider.get("ProviderDetails") or {}
    provider_scopes = str(provider_details.get("authorize_scopes", "")).split()
    mapping = provider.get("AttributeMapping") or {}
    token_units = client.get("TokenValidityUnits") or {}
    callbacks = client.get("CallbackURLs") or []
    logouts = client.get("LogoutURLs") or []
    providers = client.get("SupportedIdentityProviders") or []

    checks = [
        _check("IAM-LIVE-01", pool.get("DeletionProtection") == "ACTIVE",
               "user pool deletion protection is active"),
        _check("IAM-LIVE-02", pool.get("MfaConfiguration") == "ON",
               "native Cognito identities require MFA; this does not assert Google MFA"),
        _check("IAM-LIVE-03", admin.get("AllowAdminCreateUserOnly") is True,
               "native public SignUp is disabled"),
        _check("IAM-LIVE-04", not client.get("ClientSecret"),
               "the browser PKCE client has no client secret"),
        _check("IAM-LIVE-05", client.get("AllowedOAuthFlowsUserPoolClient") is True
               and client.get("AllowedOAuthFlows") == ["code"],
               "only Authorization Code is enabled"),
        _check("IAM-LIVE-06", len(scopes) == 3
               and set(scopes) == {"openid", "email", "profile"},
               "OAuth scopes are exactly openid email profile"),
        _check("IAM-LIVE-07", callbacks == [
            f"{origin}/api/auth/callback/cognito"],
            "the callback is the exact Fincilia HTTPS endpoint"),
        _check("IAM-LIVE-08", logouts == [f"{origin}/entrar"],
               "the logout URI returns exactly to Fincilia"),
        _check("IAM-LIVE-09", providers == ["Google"],
               "the public web app client exposes Google only"),
        _check("IAM-LIVE-10", client.get("PreventUserExistenceErrors") == "ENABLED",
               "user-existence errors are suppressed"),
        _check("IAM-LIVE-11", client.get("EnableTokenRevocation") is True,
               "Cognito token revocation is enabled"),
        _check("IAM-LIVE-12", client.get("AccessTokenValidity") == 15
               and client.get("IdTokenValidity") == 15
               and client.get("RefreshTokenValidity") == 1
               and token_units.get("AccessToken") == "minutes"
               and token_units.get("IdToken") == "minutes"
               and token_units.get("RefreshToken") == "days",
               "access/ID tokens are 15 minutes and refresh validity is one day"),
        _check("IAM-LIVE-13", provider.get("ProviderType") == "Google"
               and bool(provider_details.get("client_id"))
               and bool(provider_details.get("client_secret")),
               "Google provider credentials are configured; values are never reported"),
        _check("IAM-LIVE-14", len(provider_scopes) == 3
               and set(provider_scopes) == {"openid", "email", "profile"},
               "Google provider scopes are minimal"),
        _check("IAM-LIVE-15", all(mapping.get(name) == name
                                  for name in ("email", "email_verified", "name")),
               "verified email and display name mappings are exact"),
        _check("IAM-LIVE-16", domain.get("Status") == "ACTIVE",
               "the Cognito managed-login domain is active"),
    ]
    ok = all(item["status"] == "pass" for item in checks)
    return {
        "schema_version": "1.0",
        "ok": ok,
        "activation_authorized": False,
        "real_data_authorized": False,
        "assurance": "federated_google_not_asserted_as_mfa",
        "checks": checks,
    }
