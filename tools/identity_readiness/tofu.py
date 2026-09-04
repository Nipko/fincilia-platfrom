"""Descubre selectores Cognito sin imprimir valores del estado OpenTofu."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
MAX_OUTPUT_BYTES = 262_144
REQUIRED_OUTPUTS = {
    "cognito_user_pool_id",
    "cognito_google_web_client_id",
    "cognito_domain",
}
PRIVATE_PILOT_OUTPUT = "cognito"
DOMAIN_PREFIX = re.compile(r"^[a-z0-9-]{8,63}$")


def _value(outputs: dict[str, Any], name: str) -> str:
    item = outputs.get(name)
    if not isinstance(item, dict) or not isinstance(item.get("value"), str):
        raise RuntimeError("OpenTofu identity outputs are incomplete")
    value = item["value"]
    if not value or len(value) > 180:
        raise RuntimeError("OpenTofu identity outputs are invalid")
    return value


def _bounded_text(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 180:
        raise RuntimeError("OpenTofu identity outputs are invalid")
    return value


def _private_pilot_values(outputs: dict[str, Any], region: str) -> dict[str, str]:
    item = outputs.get(PRIVATE_PILOT_OUTPUT)
    value = item.get("value") if isinstance(item, dict) else None
    if not isinstance(value, dict):
        raise RuntimeError("OpenTofu identity outputs are incomplete")
    pool = _bounded_text(value.get("user_pool_id"))
    client = _bounded_text(value.get("web_client_id"))
    hosted = _bounded_text(value.get("hosted_ui_domain"))
    parsed = urlparse(hosted)
    suffix = f".auth.{region}.amazoncognito.com"
    hostname = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.netloc != hostname \
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment \
            or not hostname.endswith(suffix):
        raise RuntimeError("OpenTofu identity outputs are invalid")
    prefix = hostname[:-len(suffix)]
    if not DOMAIN_PREFIX.fullmatch(prefix):
        raise RuntimeError("OpenTofu identity outputs are invalid")
    return {
        "user_pool_id": pool,
        "client_id": client,
        "domain_prefix": prefix,
    }


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
    outputs_path = resolved / "outputs.tf"
    if not outputs_path.is_file():
        raise ValueError("OpenTofu directory is not an identity module")
    compound_output = 'output "cognito"' in outputs_path.read_text(encoding="utf-8")

    environment = {
        **os.environ,
        "AWS_PROFILE": profile,
        "AWS_REGION": region,
        "AWS_DEFAULT_REGION": region,
    }
    try:
        completed = subprocess.run(
            [
                "tofu", f"-chdir={resolved}", "output", "-json",
                *([PRIVATE_PILOT_OUTPUT] if compound_output else []),
            ],
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
    if not isinstance(outputs, dict):
        raise RuntimeError("OpenTofu identity outputs are incomplete")
    if compound_output:
        outputs = {PRIVATE_PILOT_OUTPUT: {"value": outputs}}
    if REQUIRED_OUTPUTS.issubset(outputs):
        return {
            "user_pool_id": _value(outputs, "cognito_user_pool_id"),
            "client_id": _value(outputs, "cognito_google_web_client_id"),
            "domain_prefix": _value(outputs, "cognito_domain"),
        }
    return _private_pilot_values(outputs, region)
