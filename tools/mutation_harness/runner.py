"""Ejecución aislada de mutaciones (FNC-QA-005).

Cada caso vive en un directorio temporal propio que contiene únicamente los
inputs allowlisted. El árbol compartido nunca se toca, y al terminar se
comprueban sus digests para demostrarlo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - argv list, shell=False, allowlisted local modules only
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.mutation_harness.operators import MutationError, apply_operator
from tools.mutation_harness.registry import (
    canonical_json,
    mutation_digest,
    registry_digest,
    resolve_inside,
    sha256_file,
    sha256_text,
)

ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "LANG", "LC_ALL")


def build_environment(repository_root: Path,
                      parent_env: dict[str, str] | None = None) -> dict[str, str]:
    """Entorno mínimo: sin proxies, sin credenciales, sin configuración de red."""
    source = os.environ if parent_env is None else parent_env
    env = {name: source[name] for name in ENV_ALLOWLIST if name in source}
    env["PYTHONPATH"] = str(repository_root)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def source_tree_digests(root: Path, paths: list[str]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for relative in sorted(set(paths)):
        resolved = resolve_inside(root, relative)
        if resolved is not None and resolved.is_file():
            digests[relative] = sha256_file(resolved)
    return digests


def _run(argv: list[str], cwd: Path, env: dict[str, str], timeout: int,
         limit: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(  # nosec B603 - argv list, shell=False, no user input
            [sys.executable, *argv], cwd=str(cwd), env=env, capture_output=True,
            shell=False, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "exit_code": None, "codes": [], "truncated": False}
    except (OSError, ValueError) as error:
        return {"status": "error", "exit_code": None, "codes": [],
                "truncated": False, "detail": type(error).__name__}
    raw = completed.stdout
    truncated = len(raw) > limit
    text = raw[:limit].decode("utf-8", errors="replace")
    codes: list[str] = []
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    if isinstance(parsed, dict):
        for error in parsed.get("errors", []) or []:
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                codes.append(error["code"])
        for error in parsed.get("model_errors", []) or []:
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                codes.append(error["code"])
    return {
        "status": "completed" if parsed is not None else "unparseable",
        "exit_code": completed.returncode,
        "codes": sorted(set(codes)),
        "truncated": truncated,
    }


def run_mutation(mutation: dict[str, Any], registry: dict[str, Any],
                 root: Path, parent_env: dict[str, str] | None = None) -> dict[str, Any]:
    """Ejecuta una mutación y devuelve su manifiesto.

    Clasifica en `killed`, `survived`, `invalid`, `equivalent_pending_review` o
    `error`. Un timeout, una excepción o una salida truncada **nunca** cuentan
    como `killed`: no se sabe qué ocurrió.
    """
    root = root.resolve()
    validator = next((v for v in registry.get("validators", [])
                      if v.get("id") == mutation.get("validator")), None)
    expectation = mutation.get("expectation", {})

    def manifest(outcome: str, detail: str, baseline: dict | None = None,
                 mutated: dict | None = None) -> dict[str, Any]:
        deterministic = {
            "registry_digest": registry_digest(registry),
            "mutation_digest": mutation_digest(mutation),
            "target": mutation.get("target"),
            "target_sha256": mutation.get("target_sha256"),
            "expectation": expectation,
            "baseline_exit_code": (baseline or {}).get("exit_code"),
            "mutated_exit_code": (mutated or {}).get("exit_code"),
            "observed_finding_codes": (mutated or {}).get("codes", []),
            "outcome": outcome,
        }
        return {
            "mutation_id": mutation.get("mutation_id"),
            "validator": mutation.get("validator"),
            "risk_refs": mutation.get("risk_refs", []),
            "control_refs": mutation.get("control_refs", []),
            "owner_role": mutation.get("owner_role"),
            "gate": mutation.get("gate"),
            "detail": detail,
            "baseline_truncated": (baseline or {}).get("truncated", False),
            "mutated_truncated": (mutated or {}).get("truncated", False),
            **deterministic,
            # La duración queda fuera del digest determinista a propósito.
            "deterministic_result_digest": sha256_text(canonical_json(deterministic)),
        }

    if validator is None:
        return manifest("error", "unknown validator")

    env = build_environment(root, parent_env)
    timeout = mutation.get("timeout_seconds", 60)
    limit = mutation.get("max_output_bytes", 262144)

    with tempfile.TemporaryDirectory(prefix="fnc-mutation-") as temporary:
        workspace = Path(temporary)
        for relative in sorted(set(validator.get("copy_paths", []))):
            source = resolve_inside(root, relative)
            if source is None or not source.is_file():
                return manifest("invalid", f"copy path missing or unsafe: {relative}")
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        # 1. Línea base sobre la copia sin mutar.
        baseline = _run(validator["argv"], workspace, env, timeout, limit)
        if baseline["status"] != "completed" or baseline["exit_code"] != 0:
            return manifest("invalid",
                            f"baseline is not clean ({baseline['status']}, "
                            f"exit {baseline['exit_code']}); a kill would be ambiguous",
                            baseline)

        # 2. Aplicar exactamente una mutación sobre la copia.
        target_path = workspace / mutation["target"]
        try:
            document = json.loads(target_path.read_text(encoding="utf-8"))
            mutated_document = apply_operator(document, mutation["operator"],
                                              mutation.get("operator_params", {}))
        except (MutationError, json.JSONDecodeError, OSError) as error:
            return manifest("invalid", f"mutation could not be applied: {error}", baseline)
        if mutated_document == document:
            return manifest("invalid", "the operator produced no change", baseline)
        target_path.write_text(
            json.dumps(mutated_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")

        # 3. Ejecutar el validador sobre la copia mutada.
        mutated = _run(validator["argv"], workspace, env, timeout, limit)

    if mutated["status"] == "timeout":
        return manifest("error", "timeout expired; the outcome is unknown", baseline, mutated)
    if mutated["status"] == "error":
        return manifest("error", "execution failed", baseline, mutated)
    if mutated["truncated"]:
        return manifest("error", "output truncated; the outcome cannot be evaluated",
                        baseline, mutated)
    if mutated["status"] != "completed":
        return manifest("error", "validator output could not be parsed", baseline, mutated)

    kind = expectation.get("kind")
    if kind == "expect_no_findings":
        if mutated["exit_code"] == 0 and not mutated["codes"]:
            return manifest("killed", "metamorphic control held: reordering changed nothing",
                            baseline, mutated)
        return manifest("survived",
                        f"metamorphic control broke: the validator is order sensitive "
                        f"({mutated['codes']})", baseline, mutated)

    expected_codes = set(expectation.get("finding_codes", []))
    observed = set(mutated["codes"])
    expected_exit = expectation.get("exit_code", 1)

    if mutated["exit_code"] == 0:
        return manifest("survived", "the validator accepted the weakened contract",
                        baseline, mutated)
    if mutated["exit_code"] != expected_exit:
        return manifest("error",
                        f"unexpected exit {mutated['exit_code']} (expected {expected_exit})",
                        baseline, mutated)
    if not expected_codes <= observed:
        # Salir distinto de cero por otro motivo no acredita el control.
        return manifest("survived",
                        f"non-zero exit for the wrong reason: expected {sorted(expected_codes)}, "
                        f"observed {sorted(observed)}", baseline, mutated)
    return manifest("killed", f"expected findings observed: {sorted(expected_codes)}",
                    baseline, mutated)
