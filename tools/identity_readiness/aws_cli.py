"""Adaptador AWS CLI sin shell; nunca reenvia stdout/stderr del proveedor."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any


SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9_.@/+,:=-]{1,160}$")
MAX_RESPONSE_BYTES = 131_072


class AwsCliCognito:
    def __init__(self, *, profile: str, region: str) -> None:
        if not SAFE_ARGUMENT.fullmatch(profile) or not SAFE_ARGUMENT.fullmatch(region):
            raise ValueError("invalid AWS CLI selector")
        self.profile = profile
        self.region = region

    def _call(self, operation: str, arguments: list[str]) -> dict[str, Any]:
        values = [operation, *arguments]
        if any(not SAFE_ARGUMENT.fullmatch(value) for value in values):
            raise ValueError("invalid AWS Cognito selector")
        command = [
            "aws", "--profile", self.profile, "--region", self.region,
            "cognito-idp", operation, *arguments, "--output", "json",
            "--no-cli-pager",
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                timeout=20, check=False, shell=False)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError("AWS control plane request failed") from error
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) \
                > MAX_RESPONSE_BYTES:
            raise RuntimeError("AWS control plane request failed")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("AWS control plane response was invalid") from error
        if not isinstance(value, dict):
            raise RuntimeError("AWS control plane response was invalid")
        return value

    def describe_user_pool(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("describe-user-pool", ["--user-pool-id", kwargs["UserPoolId"]])

    def describe_user_pool_client(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("describe-user-pool-client", [
            "--user-pool-id", kwargs["UserPoolId"],
            "--client-id", kwargs["ClientId"],
        ])

    def describe_identity_provider(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("describe-identity-provider", [
            "--user-pool-id", kwargs["UserPoolId"],
            "--provider-name", kwargs["ProviderName"],
        ])

    def describe_user_pool_domain(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("describe-user-pool-domain", ["--domain", kwargs["Domain"]])
