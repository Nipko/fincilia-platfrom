"""Validación estricta del registro de mutaciones (FNC-QA-005).

Solo biblioteca estándar. Determinista, sin red ni reloj.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.mutation_harness.operators import FLOATING_TOKENS, OPERATORS

REQUIRED_TASK_ID = "FNC-QA-005"
MAX_TIMEOUT_SECONDS = 300
MAX_OUTPUT_BYTES = 1_048_576
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ACCEPTED_TOKENS = {"accepted", "approved", "met", "final", "signed", "done", "closed", "resolved"}

MODULE_PREFIX = "tools."
OUTCOMES = {"killed", "survived", "invalid", "equivalent_pending_review", "error"}

REQUIRED_MUTATION_FIELDS = {
    "mutation_id", "title", "risk_refs", "control_refs", "test_refs", "owner_role",
    "reviewer_roles", "validator", "target", "target_sha256", "precondition",
    "operator", "operator_params", "expectation", "timeout_seconds",
    "max_output_bytes", "independence", "data_classification", "evidence_ref",
    "state", "gate",
}
REQUIRED_VALIDATOR_FIELDS = {"id", "module", "argv", "copy_paths", "runtime"}


@dataclass(frozen=True, order=True)
class MutationRegistryError:
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


def registry_digest(registry: dict[str, Any]) -> str:
    return sha256_text(canonical_json(registry))


def mutation_digest(mutation: dict[str, Any]) -> str:
    return sha256_text(canonical_json(mutation))


def safe_relative(raw: str) -> bool:
    if not raw or raw.startswith(("/", "\\")):
        return False
    if len(raw) > 1 and raw[1] == ":":
        return False
    return ".." not in Path(raw).parts


def resolve_inside(root: Path, relative: str) -> Path | None:
    if not safe_relative(relative):
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def validate_registry(registry: dict[str, Any], root: Path) -> list[MutationRegistryError]:
    errors: list[MutationRegistryError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(MutationRegistryError(code, location, message))

    if registry.get("schema_version") != 1:
        fail("MH-SCHEMA-VERSION", "schema_version", "schema_version must equal 1")
    if registry.get("task_id") != REQUIRED_TASK_ID:
        fail("MH-TASK", "task_id", f"task_id must be {REQUIRED_TASK_ID}")
    if registry.get("status") != "review_pending":
        fail("MH-STATUS", "status", "the registry stays review_pending")
    if registry.get("human_acceptance") != "pending":
        fail("MH-HUMAN-ACCEPTANCE", "human_acceptance", "an agent cannot record human acceptance")
    if registry.get("data_ceiling") != "synthetic_only":
        fail("MH-DATA-CEILING", "data_ceiling", "expected synthetic_only")
    if registry.get("network_access") is not False:
        fail("MH-NETWORK", "network_access", "the harness has zero network by contract")
    if registry.get("mutates_source_tree") is not False:
        fail("MH-SOURCE-TREE", "mutates_source_tree",
             "mutations only ever touch a temporary copy")
    if registry.get("global_score_as_gate") is not False:
        fail("MH-GLOBAL-SCORE", "global_score_as_gate",
             "a single mutation score is never an approval")

    validators = registry.get("validators", [])
    validator_ids: set[str] = set()
    for validator in validators:
        location = f"validators[{validator.get('id')}]"
        missing = sorted(REQUIRED_VALIDATOR_FIELDS - set(validator))
        if missing:
            fail("MH-VALIDATOR-FIELDS", location, f"missing fields: {missing}")
            continue
        if validator["id"] in validator_ids:
            fail("MH-VALIDATOR-DUPLICATE", location, "duplicate validator id")
        validator_ids.add(validator["id"])
        if validator.get("runtime") != "python":
            fail("MH-RUNTIME", location, "only the python runtime is allowlisted")
        module = validator.get("module", "")
        if not module.startswith(MODULE_PREFIX):
            fail("MH-MODULE-ALLOWLIST", location,
                 f"module {module!r} is outside the local tools namespace")
        argv = validator.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            fail("MH-ARGV-LIST", location, "argv must be a non-empty list of strings")
        else:
            if argv[0] != "-m" or (len(argv) > 1 and argv[1] != module):
                fail("MH-ARGV-MODULE", location, "argv must run exactly the declared module")
            for item in argv:
                if any(token in item for token in ("&&", "||", ";", "|", ">", "<", "`", "$(")):
                    fail("MH-ARGV-SHELL", location, f"argv element {item!r} looks like shell syntax")
        copy_paths = validator.get("copy_paths", [])
        if not isinstance(copy_paths, list) or not copy_paths:
            fail("MH-COPY-PATHS", location, "declare which inputs are copied")
        for relative in copy_paths:
            if not isinstance(relative, str) or resolve_inside(root, relative) is None:
                fail("MH-COPY-PATH-UNSAFE", location,
                     f"copy path {relative!r} is absolute, traverses or escapes the repository")
            elif not (root / relative).is_file():
                fail("MH-COPY-PATH-MISSING", location, f"copy path does not exist: {relative}")

    mutations = registry.get("mutations", [])
    if not isinstance(mutations, list) or not mutations:
        fail("MH-MUTATIONS-MISSING", "mutations", "the registry declares no mutations")
        return sorted(set(errors))

    seen: set[str] = set()
    for mutation in mutations:
        mutation_id = mutation.get("mutation_id", "<missing>")
        location = f"mutations[{mutation_id}]"

        missing = sorted(REQUIRED_MUTATION_FIELDS - set(mutation))
        if missing:
            fail("MH-MUTATION-FIELDS", location, f"missing fields: {missing}")
        if mutation_id in seen:
            fail("MH-MUTATION-DUPLICATE", location, "duplicate mutation id")
        seen.add(mutation_id)

        for field in ("risk_refs", "control_refs", "test_refs"):
            if not mutation.get(field):
                fail("MH-MUTATION-TRACE", location, f"a mutation declares {field}")
        owner = mutation.get("owner_role")
        reviewers = mutation.get("reviewer_roles", [])
        if not owner or not reviewers:
            fail("MH-MUTATION-OWNER", location, "a mutation declares owner and reviewers")
        elif owner in set(reviewers):
            fail("MH-MUTATION-OWNER", location, "owner cannot be its own reviewer")

        if mutation.get("validator") not in validator_ids:
            fail("MH-VALIDATOR-REFERENCE", location,
                 f"unknown validator {mutation.get('validator')!r}")

        target = mutation.get("target", "")
        if not isinstance(target, str) or resolve_inside(root, target) is None:
            fail("MH-TARGET-UNSAFE", location,
                 f"target {target!r} is absolute, traverses or escapes the repository")
        else:
            absolute = root / target
            if not absolute.is_file():
                fail("MH-TARGET-MISSING", location, f"target does not exist: {target}")
            else:
                declared = mutation.get("target_sha256", "")
                if not SHA256_PATTERN.match(str(declared)):
                    fail("MH-TARGET-HASH", location, "target_sha256 is not a sha256 digest")
                else:
                    actual = sha256_file(absolute)
                    if actual != declared:
                        fail("MH-TARGET-HASH", location,
                             f"adjudicated digest drifted: recorded {declared}, actual {actual}")
            validator = next((v for v in validators if v.get("id") == mutation.get("validator")), None)
            if validator and target not in set(validator.get("copy_paths", [])):
                fail("MH-TARGET-NOT-COPIED", location,
                     "the target must be among the inputs copied for its validator")

        operator = mutation.get("operator")
        if operator not in OPERATORS:
            fail("MH-OPERATOR-ALLOWLIST", location, f"operator {operator!r} is not allowlisted")
        params = mutation.get("operator_params", {})
        if not isinstance(params, dict) or not params.get("pointer"):
            fail("MH-OPERATOR-PARAMS", location, "operator parameters need a JSON pointer")
        for key, value in (params or {}).items():
            if isinstance(value, str) and any(
                    token in value for token in ("&&", "||", ";", "`", "$(", "eval(", "import ")):
                fail("MH-OPERATOR-PARAMS", location,
                     f"parameter {key!r} looks like code, not data")

        precondition = mutation.get("precondition", {})
        if not isinstance(precondition, dict) or \
                precondition.get("baseline_must_be_clean") is not True:
            fail("MH-PRECONDITION", location,
                 "a mutation requires a clean baseline; otherwise a kill is ambiguous")

        expectation = mutation.get("expectation", {})
        kind = expectation.get("kind")
        if kind not in {"expect_findings", "expect_no_findings"}:
            fail("MH-EXPECTATION-KIND", location, f"unknown expectation kind {kind!r}")
        elif kind == "expect_findings":
            if not expectation.get("finding_codes"):
                fail("MH-EXPECTATION-CODES", location,
                     "declare the exact finding codes; a generic non-zero exit proves nothing")
            if expectation.get("exit_code") == 0:
                fail("MH-EXPECTATION-EXIT", location, "expected findings imply a non-zero exit")
        elif expectation.get("exit_code") != 0:
            fail("MH-EXPECTATION-EXIT", location, "a metamorphic control expects exit zero")

        timeout = mutation.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
            fail("MH-TIMEOUT", location, "a mutation needs a positive bounded timeout")
        output_limit = mutation.get("max_output_bytes")
        if not isinstance(output_limit, int) or output_limit <= 0 or output_limit > MAX_OUTPUT_BYTES:
            fail("MH-OUTPUT-LIMIT", location, "a mutation needs a bounded output limit")

        independence = mutation.get("independence", {})
        if not isinstance(independence, dict) or not independence.get("mode"):
            fail("MH-INDEPENDENCE", location, "declare independence or equivalence group")
        elif independence["mode"] not in {"independent", "equivalence_group"}:
            fail("MH-INDEPENDENCE", location, f"unknown mode {independence['mode']!r}")
        elif independence["mode"] == "equivalence_group" and not independence.get("group_id"):
            fail("MH-INDEPENDENCE", location, "an equivalence group needs a group id")

        if mutation.get("data_classification") != "synthetic_only":
            fail("MH-DATA-CLASSIFICATION", location, "inputs stay synthetic_only")
        if mutation.get("state") != "active":
            fail("MH-MUTATION-STATE", location,
                 f"state {mutation.get('state')!r} is not active; a skipped mutation is never a kill")
        if not mutation.get("evidence_ref"):
            fail("MH-EVIDENCE-REF", location, "a mutation declares the evidence it produces")

        for key, value in (mutation.get("result_affecting_versions") or {}).items():
            if str(value).strip().lower() in FLOATING_TOKENS:
                fail("MH-FLOATING-VERSION", location, f"version {key}={value!r} is floating")

    # Independencia: dos mutaciones independientes no pueden esperar el mismo
    # codigo sobre el mismo validador, o una regla redundante contaria dos veces.
    signatures: dict[tuple[str, str], str] = {}
    for mutation in mutations:
        if mutation.get("independence", {}).get("mode") != "independent":
            continue
        for code in mutation.get("expectation", {}).get("finding_codes", []) or []:
            key = (str(mutation.get("validator")), str(code))
            if key in signatures:
                fail("MH-REDUNDANT-CONTROL", f"mutations[{mutation.get('mutation_id')}]",
                     f"finding {code} on validator {key[0]} is already covered by "
                     f"{signatures[key]}; declare an equivalence group instead")
            else:
                signatures[key] = str(mutation.get("mutation_id"))

    for gap in registry.get("declared_gaps", []):
        location = f"declared_gaps[{gap.get('risk_id')}]"
        for field in ("risk_id", "reason", "owner_role", "gate"):
            if not gap.get(field):
                fail("MH-GAP-FIELDS", location, f"a declared gap needs {field}")
        if gap.get("blocks_gate") is not True:
            fail("MH-GAP-FIELDS", location, "a declared gap keeps its gate blocked")

    for gate in registry.get("gates", []):
        if gate.get("status") != "not_met" or \
                str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("MH-GATE-STATUS", f"gates[{gate.get('id')}]", "an agent cannot mark a gate as met")

    return sorted(set(errors))


def source_tree_digests_paths(registry: dict[str, Any]) -> list[str]:
    """Rutas del árbol fuente cuya inmutabilidad se comprueba tras cada run."""
    paths: set[str] = set()
    for validator in registry.get("validators", []):
        for relative in validator.get("copy_paths", []) or []:
            if isinstance(relative, str):
                paths.add(relative)
    for mutation in registry.get("mutations", []):
        target = mutation.get("target")
        if isinstance(target, str):
            paths.add(target)
    return sorted(paths)


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
