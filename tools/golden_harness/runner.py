"""Ejecución aislada y determinista de casos golden (FNC-QA-003).

`subprocess` con lista argv, `shell=False`, cwd validado, timeout, salida acotada
y entorno mínimo. Sin red por contrato, sin secretos y sin proxies heredados.

El runner **nunca** modifica el registro, los fixtures ni los expected outputs.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - argv list, shell=False, allowlisted local modules only
import sys
from pathlib import Path
from typing import Any

from tools.golden_harness.registry import (
    canonical_json,
    case_digest,
    registry_digest,
    resolve_inside,
    sha256_adjudicated_input,
    sha256_text,
)

# Variables que el subproceso puede heredar. El resto se descarta:
# ninguna credencial, ningún proxy, ninguna configuración de red.
ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "LANG", "LC_ALL")
PROXY_VARIABLES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy",
)


def build_environment(repository_root: Path, parent_env: dict[str, str] | None = None) -> dict[str, str]:
    """Entorno mínimo y allowlisted. Determinista y sin proxies."""
    source = os.environ if parent_env is None else parent_env
    env = {name: source[name] for name in ENV_ALLOWLIST if name in source}
    env["PYTHONPATH"] = str(repository_root)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _truncate(raw: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(raw) > limit
    return raw[:limit].decode("utf-8", errors="replace"), truncated


def _is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and _is_subset(value, actual[key])
                   for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        return all(_is_subset(a, b) for a, b in zip(expected, actual))
    return expected == actual


def _normalise(document: Any, fields: list[str]) -> Any:
    """Elimina únicamente los campos declarados explícitamente por el caso."""
    if not isinstance(document, dict) or not fields:
        return document
    return {key: value for key, value in document.items() if key not in set(fields)}


def evaluate_oracle(case: dict[str, Any], exit_code: int, stdout: str) -> dict[str, Any]:
    """Compara resultado observado contra la expectativa adjudicada."""
    reasons: list[str] = []
    expected_exit = case.get("expected_exit_code")
    if exit_code != expected_exit:
        reasons.append(f"exit_code {exit_code} != expected {expected_exit}")

    oracle = case.get("oracle", {})
    kind = oracle.get("kind")
    normalised: Any = None

    if kind == "exit_code_only":
        normalised = {"exit_code": exit_code}
    elif kind in {"json_subset", "json_equals"}:
        try:
            document = json.loads(stdout)
        except json.JSONDecodeError as error:
            reasons.append(f"stdout is not valid JSON: {error.msg}")
            document = None
        if document is not None:
            normalised = _normalise(document, oracle.get("normalize_fields", []))
            expected = oracle.get("expect", {})
            if kind == "json_subset":
                if not _is_subset(expected, normalised):
                    reasons.append("stdout does not contain the adjudicated subset")
            elif normalised != expected:
                reasons.append("stdout does not equal the adjudicated document")
    else:
        reasons.append(f"unsupported oracle kind {kind!r}")

    return {
        "passed": not reasons,
        "reasons": reasons,
        "normalised_output_digest": sha256_text(canonical_json(normalised)),
    }


def run_case(
    case: dict[str, Any],
    registry: dict[str, Any],
    repository_root: Path,
    parent_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Ejecuta un caso y devuelve su manifiesto.

    El manifiesto no transporta payloads, entorno completo ni secretos: solo
    digests, códigos y motivos acotados.
    """
    root = repository_root.resolve()
    raw_cwd = case.get("cwd", ".")
    working_directory = root if raw_cwd in {".", ""} else resolve_inside(root, raw_cwd)
    if working_directory is None:
        return _manifest(case, registry, root, exit_code=None, passed=False,
                         reasons=["cwd escapes the repository"], output_digest=None,
                         truncated=False, timed_out=False)

    argv = case.get("argv", [])
    command = [sys.executable, *argv]
    env = build_environment(root, parent_env)

    try:
        completed = subprocess.run(  # nosec B603 - argv list, shell=False, no user input
            command,
            cwd=str(working_directory),
            env=env,
            capture_output=True,
            shell=False,
            timeout=case.get("timeout_seconds", 60),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _manifest(case, registry, root, exit_code=None, passed=False,
                         reasons=["timeout expired"], output_digest=None,
                         truncated=False, timed_out=True)
    except (OSError, ValueError) as error:
        return _manifest(case, registry, root, exit_code=None, passed=False,
                         reasons=[f"execution failed: {type(error).__name__}"],
                         output_digest=None, truncated=False, timed_out=False)

    limit = case.get("max_output_bytes", 65536)
    stdout, stdout_truncated = _truncate(completed.stdout, limit)
    _, stderr_truncated = _truncate(completed.stderr, limit)
    outcome = evaluate_oracle(case, completed.returncode, stdout)
    reasons = list(outcome["reasons"])
    if stdout_truncated:
        reasons.append("stdout exceeded the declared output limit")

    return _manifest(case, registry, root, exit_code=completed.returncode,
                     passed=outcome["passed"] and not stdout_truncated,
                     reasons=reasons, output_digest=outcome["normalised_output_digest"],
                     truncated=stdout_truncated or stderr_truncated, timed_out=False)


def _manifest(
    case: dict[str, Any],
    registry: dict[str, Any],
    repository_root: Path,
    *,
    exit_code: int | None,
    passed: bool,
    reasons: list[str],
    output_digest: str | None,
    truncated: bool,
    timed_out: bool,
) -> dict[str, Any]:
    input_digests: dict[str, str] = {}
    for item in case.get("inputs", []):
        raw_path = item.get("path")
        resolved = resolve_inside(repository_root, raw_path) if raw_path else None
        if resolved is not None and resolved.is_file():
            input_digests[raw_path] = sha256_adjudicated_input(resolved)

    deterministic_material = {
        "registry_digest": registry_digest(registry),
        "case_digest": case_digest(case),
        "input_digests": input_digests,
        "expected_exit_code": case.get("expected_exit_code"),
        "actual_exit_code": exit_code,
        "normalised_output_digest": output_digest,
    }
    return {
        "case_id": case.get("case_id"),
        "suite": case.get("suite"),
        "passed": passed,
        "reasons": reasons,
        "timed_out": timed_out,
        "output_truncated": truncated,
        "runtime": {"kind": case.get("runtime"),
                    "interpreter_minor": f"{sys.version_info[0]}.{sys.version_info[1]}"},
        **deterministic_material,
        # La duración se registra fuera del digest determinista, igual que el
        # intérprete concreto: ninguna de las dos afecta al resultado adjudicado.
        "deterministic_result_digest": sha256_text(canonical_json(deterministic_material)),
    }
