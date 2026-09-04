"""Provision Google in Cognito without placing its secret in argv or files."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from .aws_cli import AwsCliCognito
from .probe import inspect_identity
from .tofu import discover_identity


GOOGLE_CLIENT_ID = re.compile(
    r"^[0-9]+-[a-z0-9_-]{8,160}\.apps\.googleusercontent\.com$"
)
SAFE_SELECTOR = re.compile(r"^[A-Za-z0-9_+./=@:-]{1,256}$")
GOOGLE_SECRET_NAME = "fincilia/private-pilot/google-oidc-v1"
EXPECTED_PRECONFIGURATION_FAILURES = {
    "IAM-LIVE-09", "IAM-LIVE-13", "IAM-LIVE-14", "IAM-LIVE-15"
}
MAX_AWS_RESPONSE_BYTES = 256 * 1024
CLIENT_UPDATE_FIELDS = (
    "ClientName",
    "RefreshTokenValidity",
    "AccessTokenValidity",
    "IdTokenValidity",
    "TokenValidityUnits",
    "ReadAttributes",
    "WriteAttributes",
    "ExplicitAuthFlows",
    "CallbackURLs",
    "LogoutURLs",
    "DefaultRedirectURI",
    "AllowedOAuthFlows",
    "AllowedOAuthScopes",
    "AllowedOAuthFlowsUserPoolClient",
    "AnalyticsConfiguration",
    "PreventUserExistenceErrors",
    "EnableTokenRevocation",
    "EnablePropagateAdditionalUserContextData",
    "AuthSessionValidity",
    "RefreshTokenRotation",
)


class ConfigurationError(RuntimeError):
    """The requested mutation cannot be proven safe."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _validate_public_inputs(profile: str, region: str,
                            client_id: str, secret: str) -> None:
    if not SAFE_SELECTOR.fullmatch(profile) or not SAFE_SELECTOR.fullmatch(region):
        raise ValueError("invalid AWS selector")
    if region != "sa-east-1":
        raise ValueError("Google provisioning is restricted to sa-east-1")
    if not GOOGLE_CLIENT_ID.fullmatch(client_id):
        raise ValueError("invalid Google web client id")
    if not 16 <= len(secret) <= 2048 or any(ord(char) < 32 for char in secret):
        raise ValueError("invalid Google client secret")


class AwsCliMutation:
    """Bounded AWS mutation adapter; secret-bearing JSON travels on stdin only."""

    def __init__(self, *, profile: str, region: str,
                 runner: Runner = subprocess.run) -> None:
        self.profile = profile
        self.region = region
        self._runner = runner

    def invoke(self, service: str, operation: str,
               payload: dict[str, Any]) -> dict[str, Any]:
        for selector in (service, operation, self.profile, self.region):
            if not SAFE_SELECTOR.fullmatch(selector):
                raise ValueError("invalid AWS selector")
        arguments = [
            "aws", service, operation,
            "--profile", self.profile,
            "--region", self.region,
            "--cli-input-json", "file:///dev/stdin",
            "--output", "json", "--no-cli-pager",
        ]
        environment = {**os.environ, "AWS_PAGER": ""}
        try:
            completed = self._runner(
                arguments,
                input=json.dumps(payload, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
                shell=False,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ConfigurationError("AWS mutation failed") from error
        if completed.returncode != 0 or len(
            completed.stdout.encode("utf-8")
        ) > MAX_AWS_RESPONSE_BYTES:
            raise ConfigurationError("AWS mutation failed")
        if not completed.stdout.strip():
            return {}
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ConfigurationError("AWS mutation failed") from error
        if not isinstance(value, dict):
            raise ConfigurationError("AWS mutation failed")
        return value


def _assert_safe_preconfiguration(report: dict[str, Any]) -> None:
    failures = {
        str(item.get("id"))
        for item in report.get("checks", [])
        if item.get("status") != "pass"
    }
    if failures - EXPECTED_PRECONFIGURATION_FAILURES:
        raise ConfigurationError("Cognito baseline is not safe to modify")


def _provider_payload(*, user_pool_id: str, google_client_id: str,
                      google_client_secret: str) -> dict[str, Any]:
    return {
        "UserPoolId": user_pool_id,
        "ProviderName": "Google",
        "ProviderType": "Google",
        "ProviderDetails": {
            "client_id": google_client_id,
            "client_secret": google_client_secret,
            "authorize_scopes": "openid email profile",
        },
        "AttributeMapping": {
            "email": "email",
            "email_verified": "email_verified",
            "name": "name",
        },
    }


def _client_update_payload(*, current: dict[str, Any],
                           user_pool_id: str,
                           app_client_id: str) -> dict[str, Any]:
    payload = {
        key: current[key]
        for key in CLIENT_UPDATE_FIELDS
        if key in current
    }
    payload.update({
        "UserPoolId": user_pool_id,
        "ClientId": app_client_id,
        "SupportedIdentityProviders": ["Google"],
    })
    return payload


def configure_google(*, selectors: dict[str, str], app_origin: str,
                     google_client_id: str, google_client_secret: str,
                     cognito: AwsCliCognito,
                     mutation: AwsCliMutation) -> dict[str, Any]:
    _validate_public_inputs(
        mutation.profile, mutation.region,
        google_client_id, google_client_secret,
    )
    pool_id = selectors["user_pool_id"]
    app_client_id = selectors["client_id"]
    domain_prefix = selectors["domain_prefix"]
    before = inspect_identity(
        cognito=cognito,
        user_pool_id=pool_id,
        client_id=app_client_id,
        domain_prefix=domain_prefix,
        app_origin=app_origin,
    )
    _assert_safe_preconfiguration(before)
    current = cognito.describe_user_pool_client(
        UserPoolId=pool_id, ClientId=app_client_id
    )["UserPoolClient"]
    existing_provider = cognito.describe_identity_provider(
        UserPoolId=pool_id, ProviderName="Google"
    ).get("IdentityProvider") or {}

    stored_value = json.dumps({
        "client_id": google_client_id,
        "client_secret": google_client_secret,
    }, separators=(",", ":"))
    mutation.invoke("secretsmanager", "put-secret-value", {
        "SecretId": GOOGLE_SECRET_NAME,
        "SecretString": stored_value,
        "VersionStages": ["AWSCURRENT"],
    })
    provider_payload = _provider_payload(
        user_pool_id=pool_id,
        google_client_id=google_client_id,
        google_client_secret=google_client_secret,
    )
    provider_operation = (
        "update-identity-provider" if existing_provider
        else "create-identity-provider"
    )
    if provider_operation == "update-identity-provider":
        provider_payload.pop("ProviderType")
    mutation.invoke("cognito-idp", provider_operation, provider_payload)
    mutation.invoke("cognito-idp", "update-user-pool-client",
                    _client_update_payload(
                        current=current,
                        user_pool_id=pool_id,
                        app_client_id=app_client_id,
                    ))
    after = inspect_identity(
        cognito=cognito,
        user_pool_id=pool_id,
        client_id=app_client_id,
        domain_prefix=domain_prefix,
        app_origin=app_origin,
    )
    return {
        **after,
        "configuration_applied": True,
        "provider_operation": (
            "updated" if existing_provider else "created"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Configure Google in private-pilot Cognito safely"
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="sa-east-1")
    parser.add_argument("--tofu-dir", required=True, type=Path)
    parser.add_argument("--app-origin", required=True)
    parser.add_argument("--google-client-id", required=True)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args(argv)
    if args.confirmation != "CONFIGURE_GOOGLE":
        print(json.dumps({"ok": False, "error": "confirmation_required"}))
        return 2
    secret = getpass.getpass("Google client secret (hidden): ")
    try:
        selectors = discover_identity(
            directory=args.tofu_dir,
            profile=args.profile,
            region=args.region,
        )
        cognito = AwsCliCognito(profile=args.profile, region=args.region)
        result = configure_google(
            selectors=selectors,
            app_origin=args.app_origin,
            google_client_id=args.google_client_id,
            google_client_secret=secret,
            cognito=cognito,
            mutation=AwsCliMutation(profile=args.profile, region=args.region),
        )
    except (ConfigurationError, KeyError, RuntimeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__},
                         sort_keys=True))
        return 2
    finally:
        secret = ""
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
