"""Reglas de reconciliación de cadena de suministro (FNC-SUP-001).

Dos familias separadas a propósito:

- `validate_model` comprueba el **contrato**: que sea coherente, que no cierre
  TM-005, que no confunda un digest con una firma y que ninguna excepción viva
  sin owner, revisor, motivo, expiración y gate.
- `reconcile` comprueba el **repositorio** contra el contrato.

Un contrato válido no significa un repositorio limpio, y el CLI los reporta por
separado. Rebajar la política para que el segundo parezca verde sería el fallo
que este baseline existe para impedir.

Funciones puras. Sin red, reloj, hostname, entorno completo, Git ni aleatoriedad.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.supply_chain.discovery import (
    OCI_DIGEST,
    SEMVER_EXACT,
    SHA40,
    collect_files,
    component_dicts,
    safe_relative,
)

REQUIRED_TASK = "FNC-SUP-001"
SEVERITIES = ("critical", "high", "medium", "informational")
BLOCKING_SEVERITIES = frozenset({"critical", "high"})

COMPONENT_TYPES = (
    "github_action", "oci_image", "runtime", "package_manifest", "lockfile",
    "generated_artifact", "external_build_service",
)
EVIDENCE_STATES = (
    "observed", "digest_pinned", "source_verified_pending", "sbom_pending",
    "provenance_pending", "signature_pending",
)
# Estados que un agente NO puede declarar satisfechos: exigen verificación
# independiente fuera de este repositorio.
EVIDENCE_REQUIRING_HUMAN = (
    "source_verified_pending", "sbom_pending", "provenance_pending", "signature_pending",
)
ACCEPTED_TOKENS = frozenset({
    "accepted", "approved", "met", "resolved", "closed", "signed", "done", "complete",
    "completed", "verified",
})
OPEN_RANGE = re.compile(r"^[\^~>=<*]|[*x]$|\.\.|\s-\s")
VENDORED_TOKENS = ("node_modules", "vendor", ".venv", "site-packages", "__pycache__")

FLOATING_TAGS = frozenset({"latest", "main", "head", "stable", "current", "edge", "nightly"})


@dataclass(frozen=True, order=True)
class Finding:
    """Un hallazgo con todo lo necesario para actuar sobre él."""
    code: str
    location: str
    message: str
    severity: str = "high"
    owner_role: str = "Security"
    gate: str = "DRG-00"
    risk_refs: tuple[str, ...] = ()
    classification: str = "defect"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["risk_refs"] = list(self.risk_refs)
        return payload


# --------------------------------------------------------------------------- #
# Validación del contrato
# --------------------------------------------------------------------------- #

def validate_model(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str, severity: str = "critical") -> None:
        findings.append(Finding(code, location, message, severity, "Security", "DRG-00",
                                ("TM-005",), "model_error"))

    if model.get("schema_version") != 1:
        fail("SUP-MODEL-SCHEMA", "schema_version", "schema_version must equal 1")
    if model.get("task_id") != REQUIRED_TASK:
        fail("SUP-MODEL-TASK", "task_id", f"task_id must be {REQUIRED_TASK}")
    if model.get("status") != "review_pending":
        fail("SUP-MODEL-STATUS", "status", "the baseline stays review_pending")
    if model.get("human_acceptance") != "pending":
        fail("SUP-MODEL-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if model.get("data_ceiling") != "synthetic_only":
        fail("SUP-MODEL-DATA-CEILING", "data_ceiling", "expected synthetic_only")
    if model.get("network_access") is not False:
        fail("SUP-MODEL-NETWORK", "network_access",
             "the baseline is offline by contract; it never contacts a registry")
    if model.get("executes_discovered_components") is not False:
        fail("SUP-MODEL-EXECUTION", "executes_discovered_components",
             "a discovered action, image or package is data, never a command")
    if model.get("aggregate_score_as_gate") is not False:
        fail("SUP-MODEL-SCORE", "aggregate_score_as_gate",
             "a single supply-chain score is never an approval")

    # TM-005 no se cierra desde aquí, pase lo que pase.
    tm005 = model.get("tm_005", {})
    if not isinstance(tm005, dict):
        fail("SUP-MODEL-TM005", "tm_005", "tm_005 must be an object")
    else:
        if tm005.get("state") != "open":
            fail("SUP-TM005-CLOSED", "tm_005.state",
                 "an agent cannot mark TM-005 resolved; it needs signing and independent "
                 "verification outside this repository")
        if tm005.get("closed_by_this_tool") is not False:
            fail("SUP-TM005-CLOSED", "tm_005.closed_by_this_tool",
                 "this validator does not close TM-005")
        for field in ("owner_role", "gate", "reason"):
            if not tm005.get(field):
                fail("SUP-MODEL-TM005", f"tm_005.{field}", f"tm_005 needs {field}")

    # Un digest no acredita autoría.
    semantics = model.get("digest_semantics", {})
    if not isinstance(semantics, dict):
        fail("SUP-MODEL-DIGEST", "digest_semantics", "digest_semantics must be an object")
    else:
        for field, expected in (("proves_artifact_identity", True),
                                ("proves_author", False),
                                ("proves_signature", False),
                                ("proves_provenance", False),
                                ("substitutes_independent_verification", False)):
            if semantics.get(field) is not expected:
                fail("SUP-DIGEST-AS-PROVENANCE", f"digest_semantics.{field}",
                     f"{field} must be {str(expected).lower()}: a digest identifies the "
                     "artifact observed, it does not attest who produced it")

    declared_types = model.get("component_types", [])
    if sorted(declared_types) != sorted(COMPONENT_TYPES):
        fail("SUP-MODEL-TYPES", "component_types",
             f"component types must be exactly {sorted(COMPONENT_TYPES)}")
    declared_states = model.get("evidence_states", [])
    if sorted(declared_states) != sorted(EVIDENCE_STATES):
        fail("SUP-MODEL-EVIDENCE-STATES", "evidence_states",
             f"evidence states must be exactly {sorted(EVIDENCE_STATES)}")

    rules = model.get("discovery_rules", {})
    if not isinstance(rules, dict) or not rules:
        fail("SUP-MODEL-DISCOVERY", "discovery_rules", "declare how components are discovered")
    else:
        for name, rule in sorted(rules.items()):
            location = f"discovery_rules.{name}"
            globs = (rule or {}).get("include_globs")
            if not isinstance(globs, list) or not globs:
                fail("SUP-MODEL-DISCOVERY", location, "each rule needs include_globs")
                continue
            for glob in globs:
                if not isinstance(glob, str) or not safe_relative(glob.replace("*", "x")):
                    fail("SUP-PATH-UNSAFE", location,
                         f"glob {glob!r} is absolute or traverses outside the tree")
                if any(token in str(glob) for token in VENDORED_TOKENS):
                    fail("SUP-VENDORED-SOURCE", location,
                         f"glob {glob!r} would count a vendored or cached file as an own source")

    ownership = model.get("ownership", {})
    if not isinstance(ownership, dict):
        fail("SUP-MODEL-OWNERSHIP", "ownership", "ownership must be an object")
    else:
        for kind in COMPONENT_TYPES:
            entry = ownership.get(kind)
            if not isinstance(entry, dict):
                fail("SUP-COMPONENT-UNOWNED", f"ownership.{kind}",
                     "every component type declares owner, reviewer, risk and gate")
                continue
            for field in ("owner_role", "reviewer_roles", "risk_refs", "gate"):
                if not entry.get(field):
                    fail("SUP-COMPONENT-UNOWNED", f"ownership.{kind}.{field}",
                         f"component type {kind} needs {field}")
            owner = entry.get("owner_role")
            reviewers = entry.get("reviewer_roles") or []
            if owner and owner in set(reviewers):
                fail("SUP-COMPONENT-UNOWNED", f"ownership.{kind}.reviewer_roles",
                     "owner cannot be its own reviewer")

    for index, exception in enumerate(model.get("exceptions", []) or []):
        location = f"exceptions[{index}]"
        for field in ("id", "component", "reason", "owner_role", "reviewer_role",
                      "expires_on", "gate", "approved_by_human"):
            if not exception.get(field) and exception.get(field) is not False:
                fail("SUP-EXCEPTION-INCOMPLETE", f"{location}.{field}",
                     f"an exception needs {field}")
        if exception.get("approved_by_human") is not True:
            fail("SUP-EXCEPTION-INCOMPLETE", f"{location}.approved_by_human",
                 "an exception without human approval does not suspend a rule")

    for index, claim in enumerate(model.get("evidence_claims", []) or []):
        location = f"evidence_claims[{index}]"
        state = claim.get("state")
        if state not in EVIDENCE_STATES:
            fail("SUP-MODEL-EVIDENCE-STATES", f"{location}.state", f"unknown state {state!r}")
        if state in EVIDENCE_REQUIRING_HUMAN and claim.get("satisfied") is True:
            fail("SUP-EVIDENCE-UNSUPPORTED", f"{location}.satisfied",
                 f"{state} cannot be satisfied without verifiable evidence produced outside "
                 "this repository")
        if claim.get("satisfied") is True and not claim.get("verification_ref"):
            fail("SUP-EVIDENCE-UNSUPPORTED", f"{location}.verification_ref",
                 "a satisfied claim must point at the verification that satisfied it")

    for index, gate in enumerate(model.get("gates", []) or []):
        location = f"gates[{index}]"
        if gate.get("status") != "not_met":
            fail("SUP-MODEL-GATE", f"{location}.status", "an agent cannot mark a gate as met")
        if str(gate.get("acceptance", "")).lower() in ACCEPTED_TOKENS:
            fail("SUP-MODEL-GATE", f"{location}.acceptance",
                 "an agent cannot record gate acceptance")

    for index, gap in enumerate(model.get("declared_gaps", []) or []):
        location = f"declared_gaps[{index}]"
        for field in ("id", "reason", "owner_role", "gate"):
            if not gap.get(field):
                fail("SUP-MODEL-GAP", f"{location}.{field}", f"a declared gap needs {field}")
        if gap.get("blocks_gate") is not True:
            fail("SUP-MODEL-GAP", f"{location}.blocks_gate",
                 "a declared gap keeps its gate blocked")

    if not model.get("anti_promises"):
        fail("SUP-MODEL-ANTI-PROMISES", "anti_promises",
             "state plainly what this baseline does not prove")

    return sorted(set(findings))


# --------------------------------------------------------------------------- #
# Reconciliación del repositorio
# --------------------------------------------------------------------------- #

def _owner_of(model: dict[str, Any], kind: str) -> tuple[str, str, tuple[str, ...]]:
    entry = (model.get("ownership") or {}).get(kind) or {}
    return (
        entry.get("owner_role") or "UNASSIGNED",
        entry.get("gate") or "DRG-00",
        tuple(entry.get("risk_refs") or ()),
    )


def _exempt(model: dict[str, Any], code: str, reference: str) -> bool:
    """Una excepción solo suspende una regla si está completa y aprobada por un humano."""
    for exception in model.get("exceptions", []) or []:
        if exception.get("approved_by_human") is not True:
            continue
        if exception.get("rule") == code and exception.get("component") == reference:
            return True
    return False


def check_actions(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "github_action")
    for component in component_dicts(inventory, "github_action"):
        location = f"{component['path']}:{component['line']}"
        reference = component["reference"]
        if component["attributes"].get("form") != "registry":
            continue
        ref = component["attributes"].get("ref", "")
        if not ref:
            reason = "the reference carries no @ref at all"
        elif SHA40.match(ref):
            continue
        elif re.fullmatch(r"[0-9a-f]{7,39}", ref):
            reason = f"short commit sha {ref!r}; only a full 40-character sha is immutable"
        elif ref.startswith("v") or SEMVER_EXACT.match(ref.lstrip("v")):
            reason = f"tag {ref!r}; a tag can be moved to a different commit"
        else:
            reason = f"branch or floating reference {ref!r}"
        if _exempt(model, "SUP-ACTION-UNPINNED", reference):
            continue
        findings.append(Finding(
            "SUP-ACTION-UNPINNED", location,
            f"{reference} is not pinned to a full commit sha: {reason}",
            "critical", owner, gate, risks, "defect"))
    return findings


def check_images(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "oci_image")
    for component in component_dicts(inventory, "oci_image"):
        location = f"{component['path']}:{component['line']}"
        reference = component["reference"]
        if OCI_DIGEST.match(reference):
            continue
        if _exempt(model, "SUP-IMAGE-UNPINNED", reference):
            continue
        tag = reference.split("@", 1)[0].rsplit(":", 1)[-1] if ":" in reference else ""
        if "@" not in reference:
            reason = (f"floating tag {tag!r}" if tag in FLOATING_TAGS
                      else "no @sha256 digest, so the bytes can change under the same name")
        else:
            reason = "the digest is not a well-formed sha256 of 64 hex characters"
        findings.append(Finding(
            "SUP-IMAGE-UNPINNED", location,
            f"{reference} is not pinned by digest: {reason}",
            "critical", owner, gate, risks, "defect"))
    return findings


def check_runtimes(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "runtime")
    for component in component_dicts(inventory, "runtime"):
        location = f"{component['path']}:{component['line']}"
        value = component["reference"]
        identifier = component["identifier"]
        if identifier == "runs-on":
            # Un runner hosted no es inmutable ni con etiqueta exacta; se exige al
            # menos una etiqueta versionada y se declara como gap, no como pin.
            if value.endswith("-latest"):
                findings.append(Finding(
                    "SUP-RUNTIME-FLOATING", location,
                    f"runner label {value!r} floats; GitHub moves it without notice",
                    "high", owner, gate, risks, "defect"))
            continue
        lowered = value.strip().lower()
        if lowered in {"latest", "current", "stable", "main", "head", "lts", "*", "x"}:
            findings.append(Finding(
                "SUP-RUNTIME-FLOATING", location,
                f"{identifier} is {value!r}, a floating token; the same commit would build "
                "against a different runtime tomorrow",
                "high", owner, gate, risks, "defect"))
            continue
        if OPEN_RANGE.search(value) or not SEMVER_EXACT.match(value):
            findings.append(Finding(
                "SUP-RUNTIME-FLOATING", location,
                f"{identifier} is {value!r}, which is an open range or not an exact version",
                "high", owner, gate, risks, "defect"))
    return findings


def check_manifests_and_lockfiles(model: dict[str, Any],
                                  inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "package_manifest")
    lock_owner, lock_gate, lock_risks = _owner_of(model, "lockfile")

    manifests = component_dicts(inventory, "package_manifest")
    lockfiles = component_dicts(inventory, "lockfile")
    lock_by_scope: dict[str, list[dict[str, Any]]] = {}
    for lockfile in lockfiles:
        lock_by_scope.setdefault(lockfile["attributes"].get("scope", ""), []).append(lockfile)
    manifest_scopes = {Path(item["path"]).parent.as_posix() for item in manifests}

    for manifest in manifests:
        scope = Path(manifest["path"]).parent.as_posix()
        location = manifest["path"]
        siblings = lock_by_scope.get(scope, [])
        declared = int(manifest["attributes"].get("declared_dependencies", "0") or 0)
        # Un paquete interno sin dependencias no tiene arbol que fijar. Exigirle un
        # lockfile vacio seria ruido, y el ruido acaba silenciando la regla entera.
        if not siblings and declared > 0:
            findings.append(Finding(
                "SUP-MANIFEST-NO-LOCKFILE", location,
                f"{manifest['reference']} declares {declared} dependencies without a "
                "lockfile in its own directory; the resolved tree is not reproducible",
                "critical", owner, gate, risks, "defect"))
        if manifest["attributes"].get("parse") == "failed":
            findings.append(Finding(
                "SUP-MANIFEST-NO-LOCKFILE", location,
                "the manifest could not be parsed, so its dependency surface is unknown",
                "critical", owner, gate, risks, "defect"))

    for scope, siblings in sorted(lock_by_scope.items()):
        ecosystems = {item["attributes"].get("ecosystem") for item in siblings}
        if len(ecosystems) > 1:
            findings.append(Finding(
                "SUP-LOCKFILE-ORPHAN", scope,
                f"incompatible lockfiles coexist in the same scope: {sorted(ecosystems)}; "
                "which one resolves the tree is undefined",
                "high", lock_owner, lock_gate, lock_risks, "defect"))
        if scope not in manifest_scopes:
            findings.append(Finding(
                "SUP-LOCKFILE-ORPHAN", siblings[0]["path"],
                "lockfile without a manifest in its own directory; its scope is undefined",
                "high", lock_owner, lock_gate, lock_risks, "defect"))
        for lockfile in siblings:
            if lockfile["attributes"].get("ecosystem") == "python"                     and lockfile["attributes"].get("hashes") != "yes":
                findings.append(Finding(
                    "SUP-LOCKFILE-NO-HASHES", lockfile["path"],
                    "a pinned Python lockfile without --hash entries fixes the version "
                    "but not the bytes: a compromised mirror could serve a different "
                    "wheel under the same version",
                    "high", lock_owner, lock_gate, lock_risks, "defect"))
            if lockfile["detail"] == "unparseable":
                findings.append(Finding(
                    "SUP-LOCKFILE-ORPHAN", lockfile["path"],
                    "the lockfile could not be parsed, so it pins nothing verifiable",
                    "high", lock_owner, lock_gate, lock_risks, "defect"))
    return findings


def check_install_commands(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "external_build_service")
    manifests = component_dicts(inventory, "package_manifest")
    lifecycle_scopes = {
        Path(item["path"]).parent.as_posix()
        for item in manifests if item["attributes"].get("lifecycle_scripts")
    }
    for command in component_dicts(inventory, "external_build_service"):
        location = f"{command['path']}:{command['line']}"
        if command["attributes"].get("bounded") != "yes":
            findings.append(Finding(
                "SUP-INSTALL-UNBOUNDED", location,
                f"{command['reference']!r} resolves dependencies without a lockfile-bound "
                "install; calling it reproducible would be false",
                "high", owner, gate, risks, "defect"))
        if lifecycle_scopes and command["attributes"].get("ignore_scripts") != "yes":
            findings.append(Finding(
                "SUP-LIFECYCLE-SCRIPTS", location,
                "an install runs without --ignore-scripts while a manifest in this repository "
                f"declares lifecycle scripts ({sorted(lifecycle_scopes)}); arbitrary code would "
                "execute during CI install",
                "high", owner, gate, risks, "defect"))
    return findings


def check_update_monitoring(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    """Un manifest o una imagen que nadie vigila es una fuente no inventariada."""
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "generated_artifact")
    monitors = component_dicts(inventory, "generated_artifact")
    monitored: dict[str, set[str]] = {}
    for monitor in monitors:
        ecosystem = monitor["attributes"].get("ecosystem", "")
        directory = monitor["attributes"].get("directory", "/").strip("/")
        monitored.setdefault(ecosystem, set()).add(directory)
    if not monitors:
        return findings

    # El ecosistema del manifest y el del monitor no se llaman igual: Dependabot
    # dice `pip` donde el manifest dice `python`. Compararlos sin traducir haria
    # que un alcance vigilado pareciera desatendido.
    monitor_ecosystem = {"npm": "npm", "python": "pip"}
    scopes: dict[tuple[str, str], None] = {}
    for manifest in component_dicts(inventory, "package_manifest"):
        ecosystem = str(manifest["attributes"].get("ecosystem", "unknown"))
        scopes[(ecosystem, Path(manifest["path"]).parent.as_posix())] = None
    for ecosystem, scope in sorted(scopes):
        expected = monitor_ecosystem.get(ecosystem)
        if expected is None:
            findings.append(Finding(
                "SUP-UPDATES-UNMONITORED", scope,
                f"ecosystem {ecosystem!r} has no known update monitor mapping",
                "medium", owner, gate, risks, "coverage_gap"))
            continue
        if scope not in monitored.get(expected, set()):
            findings.append(Finding(
                "SUP-UPDATES-UNMONITORED", scope,
                f"{expected} scope {scope!r} has no update monitor entry; its "
                "dependencies age without anyone being told",
                "medium", owner, gate, risks, "coverage_gap"))
    # Un hallazgo por alcance, no por linea: repetir el mismo hueco una vez por
    # imagen inflaria el conteo y sugeriria mas trabajo del que hay.
    docker_scopes = sorted({
        Path(image["path"]).parent.as_posix()
        for image in component_dicts(inventory, "oci_image")
        if image["attributes"].get("form") == "declared"
    })
    for scope in docker_scopes:
        if scope not in monitored.get("docker", set()):
            findings.append(Finding(
                "SUP-UPDATES-UNMONITORED", scope,
                f"docker scope {scope!r} has no update monitor entry; a pinned digest never "
                "moves, which is exactly why someone has to be told when it should",
                "medium", owner, gate, risks, "coverage_gap"))
    return findings


def check_inventory_completeness(model: dict[str, Any], root: Path,
                                 inventory: dict[str, Any]) -> list[Finding]:
    """Ficheros que declaran dependencias y para los que no hay extractor."""
    findings: list[Finding] = []
    owner, gate, risks = _owner_of(model, "package_manifest")
    watch = list((model.get("inventory_completeness") or {}).get("watch_globs", []))
    known = {item["path"] for item in inventory.get("components", [])}
    known |= {item["path"] for item in inventory.get("scanned_files", [])}
    for relative in collect_files(root, watch):
        posix = relative.as_posix()
        if posix in known:
            continue
        findings.append(Finding(
            "SUP-SOURCE-NOT-INVENTORIED", posix,
            "this file declares a dependency surface that no extractor understands; the "
            "inventory would look complete while missing an entire ecosystem",
            "high", owner, gate, risks, "coverage_gap"))
    return findings


def check_scan_integrity(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in inventory.get("unscannable_files", []):
        findings.append(Finding(
            "SUP-YAML-UNSCANNABLE", entry["path"],
            f"the line scanner cannot resolve {entry.get('constructs', entry.get('reason'))}; "
            "reporting a partial inventory as complete would be worse than reporting nothing",
            "critical", "Platform", "DRG-00", ("TM-005",), "scanner_limit"))
    for path in inventory.get("unsafe_paths", []):
        findings.append(Finding(
            "SUP-PATH-UNSAFE", path,
            "absolute path, internal traversal or symlink escaping the tree",
            "critical", "Security", "DRG-00", ("TM-005",), "defect"))
    return findings


def check_provenance_evidence(model: dict[str, Any], inventory: dict[str, Any]) -> list[Finding]:
    """Lo que falta para poder afirmar procedencia. Es un gap, no un defecto."""
    findings: list[Finding] = []
    pending = [claim for claim in model.get("evidence_claims", []) or []
               if claim.get("satisfied") is not True]
    if not pending:
        return findings
    external = len(component_dicts(inventory, "github_action")) + \
        len(component_dicts(inventory, "oci_image"))
    for claim in pending:
        findings.append(Finding(
            "SUP-PROVENANCE-PENDING", f"evidence_claims[{claim.get('id')}]",
            f"{claim.get('state')} for {external} external components: {claim.get('reason', '')}",
            "high", claim.get("owner_role") or "Security", claim.get("gate") or "DRG-00",
            tuple(claim.get("risk_refs") or ("TM-005",)), "declared_gap"))
    return findings


def reconcile(model: dict[str, Any], root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    findings: list[Finding] = []
    findings += check_scan_integrity(model, inventory)
    findings += check_actions(model, inventory)
    findings += check_images(model, inventory)
    findings += check_runtimes(model, inventory)
    findings += check_manifests_and_lockfiles(model, inventory)
    findings += check_install_commands(model, inventory)
    findings += check_update_monitoring(model, inventory)
    findings += check_inventory_completeness(model, root, inventory)
    findings += check_provenance_evidence(model, inventory)

    ordered = sorted(set(findings))
    # El bloqueo se rige por la severidad declarada, no por una nota agregada ni
    # por la clasificacion: un gap declarado sigue bloqueando su gate. Que la
    # procedencia no este demostrada no deja de ser bloqueante por estar previsto.
    blocking = [item for item in ordered if item.severity in BLOCKING_SEVERITIES]
    return {
        "findings": [item.as_dict() for item in ordered],
        "finding_count": len(ordered),
        "blocking_findings": [item.as_dict() for item in blocking],
        "blocking_count": len(blocking),
        "counts_by_code": {
            code: sum(1 for item in ordered if item.code == code)
            for code in sorted({item.code for item in ordered})
        },
        "counts_by_severity": {
            level: sum(1 for item in ordered if item.severity == level)
            for level in SEVERITIES if any(item.severity == level for item in ordered)
        },
        "counts_by_owner": {
            role: sum(1 for item in ordered if item.owner_role == role)
            for role in sorted({item.owner_role for item in ordered})
        },
        "counts_by_gate": {
            gate: sum(1 for item in ordered if item.gate == gate)
            for gate in sorted({item.gate for item in ordered})
        },
        "counts_by_classification": {
            kind: sum(1 for item in ordered if item.classification == kind)
            for kind in sorted({item.classification for item in ordered})
        },
    }
