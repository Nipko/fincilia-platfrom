"""Carga y validación estricta del registro de casos golden (FNC-QA-003).

Solo biblioteca estándar. Determinista: sin red, reloj, entorno ni aleatoriedad.
El registro es adjudicado: el runner nunca lo modifica.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK_ID = "FNC-QA-003"
REQUIRED_DATA_CLASSIFICATION = "synthetic_only"

RUNTIME_ALLOWLIST = {"python"}
MODULE_PREFIX_ALLOWLIST = ("tools.",)
MAX_TIMEOUT_SECONDS = 300
MAX_OUTPUT_BYTES = 1_048_576
FLOATING_TOKENS = {"latest", "main", "head", "stable", "current"}
FORBIDDEN_ORACLE_KINDS = {"always_pass", "always_true", "regex_loose", "ignore_output"}
ALLOWED_ORACLE_KINDS = {"json_subset", "json_equals", "exit_code_only"}
FORBIDDEN_NORMALIZE_KEYS = {
    "ok", "errors", "error", "amount", "amounts", "currency", "balance", "total",
    "totals", "digest", "sha256", "hash", "money", "debit", "credit", "count",
}
REQUIRED_CASE_FIELDS = {
    "case_id", "suite", "owner_role", "reviewer_roles", "risk_refs", "test_refs",
    "runtime", "argv", "module_allowlist", "cwd", "timeout_seconds",
    "max_output_bytes", "inputs", "data_classification", "expected_exit_code",
    "oracle", "result_affecting_versions", "state", "evidence_ref", "consumer_gates",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, order=True)
class HarnessError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_digest(case: dict[str, Any]) -> str:
    return sha256_text(canonical_json(case))


def registry_digest(registry: dict[str, Any]) -> str:
    return sha256_text(canonical_json(registry))


def _is_safe_relative(raw: str) -> bool:
    if not raw or raw.startswith("/") or raw.startswith("\\"):
        return False
    if re.match(r"^[A-Za-z]:", raw):
        return False
    parts = Path(raw).parts
    return ".." not in parts


def resolve_inside(repository_root: Path, relative: str) -> Path | None:
    """Resuelve una ruta relativa garantizando que queda dentro del repositorio.

    Devuelve `None` ante ruta absoluta, traversal o symlink que escape del árbol.
    """
    if not _is_safe_relative(relative):
        return None
    root = repository_root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def validate_registry(
    registry: dict[str, Any], repository_root: Path
) -> list[HarnessError]:
    errors: list[HarnessError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(HarnessError(code, location, message))

    if registry.get("schema_version") != 1:
        fail("GH-SCHEMA-VERSION", "schema_version", "schema_version must equal 1")
    if registry.get("task_id") != REQUIRED_TASK_ID:
        fail("GH-TASK", "task_id", f"task_id must be {REQUIRED_TASK_ID}")
    if registry.get("status") != "review_pending":
        fail("GH-STATUS", "status", "the registry stays review_pending")
    if registry.get("human_acceptance") != "pending":
        fail("GH-HUMAN-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if registry.get("data_ceiling") != REQUIRED_DATA_CLASSIFICATION:
        fail("GH-DATA-CEILING", "data_ceiling", f"expected {REQUIRED_DATA_CLASSIFICATION}")
    if registry.get("auto_update_expected_allowed") is not False:
        fail("GH-AUTO-UPDATE", "auto_update_expected_allowed",
             "the runner never adjudicates its own expected outputs")
    adjudication = registry.get("adjudication")
    if (
        not isinstance(adjudication, dict)
        or adjudication.get("runner_can_update_expected") is not False
        or adjudication.get("runner_can_update_input_digests") is not False
        or not adjudication.get("authority")
        or not adjudication.get("procedure")
    ):
        fail("GH-ADJUDICATION-AUTHORITY", "adjudication",
             "expected outputs and input digests require explicit human adjudication")
    if registry.get("network_access") is not False:
        fail("GH-NETWORK", "network_access", "the harness has zero network by contract")

    cases = registry.get("cases", [])
    if not isinstance(cases, list) or not cases:
        fail("GH-CASES-MISSING", "cases", "the registry declares no cases")
        return sorted(set(errors))

    seen: set[str] = set()
    for case in cases:
        case_id = case.get("case_id", "<missing>")
        location = f"cases[{case_id}]"

        missing = sorted(REQUIRED_CASE_FIELDS - set(case))
        if missing:
            fail("GH-CASE-FIELDS", location, f"missing required fields: {missing}")
        if case_id in seen:
            fail("GH-CASE-DUPLICATE", location, "duplicate case id")
        seen.add(case_id)

        # -- ownership independiente -------------------------------------
        owner = case.get("owner_role")
        reviewers = case.get("reviewer_roles", [])
        if not owner:
            fail("GH-CASE-OWNER", location, "a case needs an owner role")
        if not reviewers:
            fail("GH-CASE-OWNER", location, "a case needs at least one reviewer role")
        if owner and owner in set(reviewers):
            fail("GH-CASE-OWNER", location, "owner cannot be its own reviewer")

        # -- runtime y argv ----------------------------------------------
        if case.get("runtime") not in RUNTIME_ALLOWLIST:
            fail("GH-RUNTIME", location, f"runtime {case.get('runtime')!r} is not allowlisted")
        argv = case.get("argv")
        if not isinstance(argv, list) or not argv:
            fail("GH-ARGV-LIST", location, "argv must be a non-empty list, never a shell string")
        elif not all(isinstance(item, str) for item in argv):
            fail("GH-ARGV-LIST", location, "every argv element must be a string")
        else:
            if argv[0] != "-m":
                fail("GH-ARGV-MODULE", location, "only module execution is allowed: argv[0] == '-m'")
            elif len(argv) < 2:
                fail("GH-ARGV-MODULE", location, "argv must name a module")
            else:
                module = argv[1]
                allowlist = set(case.get("module_allowlist", []))
                if module not in allowlist:
                    fail("GH-MODULE-ALLOWLIST", location,
                         f"module {module!r} is not in the case allowlist")
                if not module.startswith(MODULE_PREFIX_ALLOWLIST):
                    fail("GH-MODULE-ALLOWLIST", location,
                         f"module {module!r} is outside the local tools namespace")
                for entry in sorted(allowlist):
                    if not entry.startswith(MODULE_PREFIX_ALLOWLIST):
                        fail("GH-MODULE-ALLOWLIST", location,
                             f"allowlisted module {entry!r} is outside the local tools namespace")
            for item in argv:
                if any(token in item for token in ("&&", "||", ";", "|", ">", "<", "`", "$(")):
                    fail("GH-ARGV-SHELL", location,
                         f"argv element {item!r} looks like shell syntax")

        # -- cwd -----------------------------------------------------------
        cwd = case.get("cwd", "")
        if cwd not in {".", ""} and resolve_inside(repository_root, cwd) is None:
            fail("GH-CWD", location, f"cwd {cwd!r} escapes the repository")

        # -- límites --------------------------------------------------------
        timeout = case.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            fail("GH-TIMEOUT", location, "a case needs a positive integer timeout")
        elif timeout > MAX_TIMEOUT_SECONDS:
            fail("GH-TIMEOUT", location,
                 f"timeout {timeout} exceeds the maximum of {MAX_TIMEOUT_SECONDS}")
        output_limit = case.get("max_output_bytes")
        if not isinstance(output_limit, int) or output_limit <= 0:
            fail("GH-OUTPUT-LIMIT", location, "a case needs a positive output limit")
        elif output_limit > MAX_OUTPUT_BYTES:
            fail("GH-OUTPUT-LIMIT", location,
                 f"output limit {output_limit} exceeds {MAX_OUTPUT_BYTES}")

        # -- inputs adjudicados ---------------------------------------------
        inputs = case.get("inputs", [])
        if not isinstance(inputs, list):
            fail("GH-INPUT-LIST", location, "inputs must be a list")
            inputs = []
        for index, item in enumerate(inputs):
            input_location = f"{location}.inputs[{index}]"
            raw_path = item.get("path") if isinstance(item, dict) else None
            declared = item.get("sha256") if isinstance(item, dict) else None
            if not raw_path:
                fail("GH-INPUT-PATH", input_location, "input without path")
                continue
            if not declared or not SHA256_PATTERN.match(str(declared)):
                fail("GH-INPUT-HASH", input_location, "input without an adjudicated sha256")
                continue
            resolved = resolve_inside(repository_root, raw_path)
            if resolved is None:
                fail("GH-INPUT-PATH", input_location,
                     f"path {raw_path!r} is absolute, traverses or escapes the repository")
                continue
            if not resolved.is_file():
                fail("GH-INPUT-MISSING", input_location, f"input does not exist: {raw_path}")
                continue
            actual = sha256_file(resolved)
            if actual != declared:
                fail("GH-INPUT-HASH", input_location,
                     f"adjudicated digest drifted: recorded {declared}, actual {actual}")

        # -- clasificación de datos ------------------------------------------
        if case.get("data_classification") != REQUIRED_DATA_CLASSIFICATION:
            fail("GH-DATA-CLASSIFICATION", location,
                 "every case input stays synthetic_only")

        # -- expectativas ------------------------------------------------------
        if not isinstance(case.get("expected_exit_code"), int):
            fail("GH-EXPECTED-EXIT", location, "expected_exit_code is required")

        oracle = case.get("oracle", {})
        kind = oracle.get("kind") if isinstance(oracle, dict) else None
        if kind in FORBIDDEN_ORACLE_KINDS:
            fail("GH-ORACLE-FORBIDDEN", location,
                 f"oracle {kind!r} is explicitly denylisted because it proves nothing")
        if kind not in ALLOWED_ORACLE_KINDS:
            fail("GH-ORACLE-KIND", location, f"unknown oracle kind {kind!r}")
        if kind in {"json_subset", "json_equals"} and not isinstance(oracle.get("expect"), dict):
            fail("GH-ORACLE-EXPECT", location, "a structured oracle needs an expected object")
        for field in oracle.get("normalize_fields", []) if isinstance(oracle, dict) else []:
            if str(field).lower() in FORBIDDEN_NORMALIZE_KEYS:
                fail("GH-ORACLE-NORMALIZE", location,
                     f"normalising {field!r} would erase a financial or semantic difference")

        # -- versiones que afectan resultados -----------------------------------
        versions = case.get("result_affecting_versions", {})
        if not isinstance(versions, dict) or not versions:
            fail("GH-VERSIONS", location, "declare the versions that affect the result")
        else:
            for key, value in sorted(versions.items()):
                if str(value).strip().lower() in FLOATING_TOKENS:
                    fail("GH-FLOATING-VERSION", location,
                         f"version {key}={value!r} is a floating token")

        # -- estado -------------------------------------------------------------
        if case.get("state") != "active":
            fail("GH-CASE-STATE", location,
                 f"state {case.get('state')!r} is not active; a skipped case is never a pass")

        if not case.get("evidence_ref"):
            fail("GH-EVIDENCE-REF", location, "a case declares which evidence it produces")
        if not case.get("consumer_gates"):
            fail("GH-CONSUMER-GATE", location, "a case declares which gate consumes it")

    return sorted(set(errors))


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
