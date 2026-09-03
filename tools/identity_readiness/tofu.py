"""Descubre selectores Cognito sin imprimir valores del estado OpenTofu."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAX_OUTPUT_BYTES = 262_144
REQUIRED_OUTPUTS = {
    "cognito_user_pool_id",
    "cognito_google_web_client_id",
    "cognito_domain",
}


def _value(outputs: dict[str, Any], name: str) -> str:
    item = outputs.get(name)
    if not isinstance(item, dict) or not isinstance(item.get("value"), str):
        raise RuntimeError("OpenTofu identity outputs are incomplete")
    value = item["value"]
    if not value or len(value) > 180:
        raise RuntimeError("OpenTofu identity outputs are invalid")
    return value


def discover_identity(*, directory: Path, profile: str,
                      region: str) -> dict[str, str]:
    """Return selectors in memory; callers must never serialize this mapping."""
    raw = directory
    if ".." in raw.parts:
        raise ValueError("OpenTofu directory must use a canonical path")
    resolved = raw.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("OpenTofu directory must be inside the repository") from error
    if not (resolved / "outputs.tf").is_file():
        raise ValueError("OpenTofu directory is not an identity module")

    environment = {
        **os.environ,
        "AWS_PROFILE": profile,
        "AWS_REGION": region,
        "AWS_DEFAULT_REGION": region,
    }
    try:
        completed = subprocess.run(
            ["tofu", f"-chdir={resolved}", "output", "-json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
            shell=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("OpenTofu identity discovery failed") from error
    if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise RuntimeError("OpenTofu identity discovery failed")
    try:
        outputs = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenTofu identity discovery failed") from error
    if not isinstance(outputs, dict) or not REQUIRED_OUTPUTS.issubset(outputs):
        raise RuntimeError("OpenTofu identity outputs are incomplete")
    return {
        "user_pool_id": _value(outputs, "cognito_user_pool_id"),
        "client_id": _value(outputs, "cognito_google_web_client_id"),
        "domain_prefix": _value(outputs, "cognito_domain"),
    }
