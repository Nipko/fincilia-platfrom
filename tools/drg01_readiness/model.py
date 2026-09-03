from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs/security/drg01-readiness.json"
FOUNDER_ID = "FOUNDER-01"
GATE_ORDER = ("DRG-00", "DRG-01")
CONTROL_IDS = {
    "DRG-00": {
        "G00-LEGAL", "G00-RETENTION", "G00-REGION", "G00-ISOLATED-ENV",
        "G00-INVENTORY", "G00-DELETE", "G00-DRILL", "G00-SUPPLY-CHAIN",
        "G00-INDEPENDENT-REVIEW",
    },
    "DRG-01": {
        "D01-DRG00", "D01-IDENTITY", "D01-XTENANT", "D01-INGRESS",
        "D01-CHANNELS", "D01-CLOUD-CONTROLS", "D01-RESTORE", "D01-PCI",
        "D01-RIGHTS-IR", "D01-PENTEST", "D01-DPA-SUBPROCESSORS",
        "D01-INDEPENDENT-REVIEW",
    },
}
HUMAN_IDS = {
    "G00-LEGAL", "G00-RETENTION", "G00-REGION", "G00-INDEPENDENT-REVIEW",
    "D01-PCI", "D01-PENTEST", "D01-DPA-SUBPROCESSORS",
    "D01-INDEPENDENT-REVIEW",
}
PREREQUISITE_IDS = {"D01-DRG00"}
ALLOWED_DOCUMENTS = ["csv", "xlsx", "pdf"]
DRG00_TECHNICAL_EVIDENCE = "docs/implementation/evidence/FNC-QA-001.json"
DRG00_DRILL_EVIDENCE_IDS = {
    "G00-ISOLATED-ENV", "G00-INVENTORY", "G00-DELETE", "G00-DRILL",
}
DRG00_SHARED_TECHNICAL_IDS = {"G00-INVENTORY", "G00-DELETE", "G00-DRILL"}
ISOLATED_ENV_EVIDENCE = "docs/implementation/evidence/FNC-GAT-007.json"
TARGET_DRILL_EVIDENCE = (
    "docs/implementation/evidence/FNC-GAT-007-TARGET-DRILL.json"
)
DRG01_TECHNICAL_EVIDENCE = "docs/implementation/evidence/FNC-GAT-006.json"
DRG01_ADJUDICATED_IDS = {"D01-XTENANT", "D01-INGRESS", "D01-CHANNELS"}
RIGHTS_INCIDENT_EVIDENCE = "docs/implementation/evidence/FNC-PRV-004.json"
SUPPLY_CHAIN_EVIDENCE = "docs/implementation/evidence/FNC-GAT-005-SUPPLY-CHAIN.json"
SUPPLY_CHAIN_SIGNER = (
    "github.com/Nipko/fincilia-platfrom/.github/workflows/release-candidate.yml"
)
PROHIBITED_DATA = [
    "payment_card", "payroll", "government_identity", "health", "credentials",
]
DISABLED_CAPABILITIES = [
    "external_ai", "email_ingest", "sftp", "api_connectors", "webhooks",
    "automatic_close",
]


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _inside_evidence(reference: str) -> bool:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        (ROOT / path).resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return (ROOT / path).exists()


def _control_satisfied(control: dict[str, Any], drg00_ready: bool) -> bool:
    kind = control.get("kind")
    if kind == "human":
        return (
            control.get("state") == "accepted"
            and bool(control.get("evidence_refs"))
            and control.get("reviewer_id") not in {None, "", FOUNDER_ID}
            and bool(control.get("reviewed_at"))
        )
    if kind == "automated":
        return control.get("state") == "passed" and bool(control.get("evidence_refs"))
    if kind == "prerequisite":
        return control.get("state") == "passed" and drg00_ready
    return False


def _validate_drg00_technical_evidence() -> list[Finding]:
    path = ROOT / DRG00_TECHNICAL_EVIDENCE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [Finding("DRG-TECH-EVIDENCE", DRG00_TECHNICAL_EVIDENCE,
                        "technical evidence is absent or unreadable")]
    findings: list[Finding] = []
    expected_tests = [f"LAB-T{number:02d}" for number in range(1, 13)]
    tests = payload.get("tests") if isinstance(payload, dict) else None
    mappings = payload.get("technical_controls") if isinstance(payload, dict) else None
    if (
        payload.get("schema_version") != "1.0.0"
        or payload.get("task_id") != "FNC-QA-001"
        or payload.get("data_classification") != "completely_synthetic"
        or payload.get("real_data_authorized") is not False
        or payload.get("test_count") != 12
        or payload.get("passed_count") != 12
        or payload.get("failed_count") != 0
        or not isinstance(tests, list)
        or [item.get("id") for item in tests if isinstance(item, dict)] != expected_tests
        or any(item.get("state") != "passed" for item in tests if isinstance(item, dict))
        or not isinstance(mappings, dict)
        or set(mappings) != DRG00_DRILL_EVIDENCE_IDS
        or any(not value for value in mappings.values())
    ):
        findings.append(Finding(
            "DRG-TECH-EVIDENCE", DRG00_TECHNICAL_EVIDENCE,
            "technical evidence does not prove the four mapped controls"))
    claimed = payload.get("evidence_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    observed = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    if claimed != observed:
        findings.append(Finding(
            "DRG-TECH-DIGEST", DRG00_TECHNICAL_EVIDENCE,
            "technical evidence digest does not match its content"))
    return findings


def validate_isolated_environment_evidence(
    payload: dict[str, Any], *, verify_references: bool = True,
) -> list[Finding]:
    """Validate target evidence; a local synthetic drill is never sufficient."""
    findings: list[Finding] = []
    required = {
        "schema_version", "task_id", "control_id", "state", "observed_at",
        "environment", "region", "account_id_sha256", "source_revision",
        "data_classification", "real_data_authorized", "production_authorized",
        "foundation", "runtime_plane", "release_admission", "managed_identity",
        "target_drill", "independent_review", "evidence_sha256",
    }
    if set(payload) != required:
        findings.append(Finding(
            "DRG-ISOLATED-SCHEMA", ISOLATED_ENV_EVIDENCE,
            "isolated target evidence fields drifted"))
    if (
        payload.get("schema_version") != "1.0.0"
        or payload.get("task_id") != "FNC-GAT-007"
        or payload.get("control_id") != "G00-ISOLATED-ENV"
        or payload.get("state") != "passed"
        or payload.get("environment") != "private-pilot"
        or payload.get("region") != "sa-east-1"
        or payload.get("data_classification") != "completely_synthetic"
        or payload.get("real_data_authorized") is not False
        or payload.get("production_authorized") is not False
    ):
        findings.append(Finding(
            "DRG-ISOLATED-CLAIM", ISOLATED_ENV_EVIDENCE,
            "isolated evidence overclaims target, data or authorization"))
    try:
        observed = datetime.fromisoformat(
            str(payload.get("observed_at", "")).replace("Z", "+00:00")
        )
        if observed.tzinfo is None or not str(payload.get("observed_at")).endswith("Z"):
            raise ValueError
    except ValueError:
        findings.append(Finding(
            "DRG-ISOLATED-TIME", ISOLATED_ENV_EVIDENCE,
            "observed_at must be an explicit UTC instant"))
    if re.fullmatch(r"[0-9a-f]{64}", str(payload.get("account_id_sha256", ""))) is None:
        findings.append(Finding(
            "DRG-ISOLATED-IDENTITY", "account_id_sha256",
            "account identity must be represented by a sha256 digest"))
    if re.fullmatch(r"[0-9a-f]{40}", str(payload.get("source_revision", ""))) is None:
        findings.append(Finding(
            "DRG-ISOLATED-REVISION", "source_revision",
            "target evidence must identify an exact Git revision"))

    expected_inventory = {
        "foundation": (33, payload.get("foundation")),
        "runtime_plane": (10, payload.get("runtime_plane")),
    }
    for name, (count, value) in expected_inventory.items():
        if value != {"state": "complete", "required_count": count, "missing": []}:
            findings.append(Finding(
                "DRG-ISOLATED-INVENTORY", name,
                "target inventory is absent, partial or widened"))

    admission = payload.get("release_admission")
    if not isinstance(admission, dict) or set(admission) != {
        "source_revision", "subject_sha256", "signature_verified",
        "provenance_verified", "sbom_verified", "images_by_digest_verified",
    } or (
        admission.get("source_revision") != payload.get("source_revision")
        or re.fullmatch(r"[0-9a-f]{64}", str(admission.get("subject_sha256", ""))) is None
        or any(admission.get(field) is not True for field in (
            "signature_verified", "provenance_verified", "sbom_verified",
            "images_by_digest_verified",
        ))
    ):
        findings.append(Finding(
            "DRG-ISOLATED-RELEASE", "release_admission",
            "release is not exactly admitted and independently verifiable"))

    identity = payload.get("managed_identity")
    if identity != {
        "provider": "Amazon Cognito federated with Google",
        "mfa_configuration": "ON",
        "deletion_protection": "ACTIVE",
        "native_signup_closed": True,
        "authorization_remains_server_side": True,
    }:
        findings.append(Finding(
            "DRG-ISOLATED-IDENTITY", "managed_identity",
            "managed identity controls are incomplete or drifted"))

    drill = payload.get("target_drill")
    if not isinstance(drill, dict) or set(drill) != {
        "evidence_ref", "passed_count", "failed_count", "networkless_worker",
        "cross_tenant_denied", "restore_reconciled", "logs_redacted",
    } or (
        drill.get("evidence_ref") != TARGET_DRILL_EVIDENCE
        or (verify_references and not _inside_evidence(TARGET_DRILL_EVIDENCE))
        or drill.get("passed_count") != 12
        or drill.get("failed_count") != 0
        or any(drill.get(field) is not True for field in (
            "networkless_worker", "cross_tenant_denied", "restore_reconciled",
            "logs_redacted",
        ))
    ):
        findings.append(Finding(
            "DRG-ISOLATED-DRILL", "target_drill",
            "the twelve controls were not replayed successfully in the target"))

    if payload.get("independent_review") != {
        "state": "pending",
        "required_roles": ["Security", "Platform/SRE", "QA"],
        "agent_observation_is_not_acceptance": True,
    }:
        findings.append(Finding(
            "DRG-ISOLATED-REVIEW", "independent_review",
            "technical evidence must not claim independent human review"))

    claimed = payload.get("evidence_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    observed_digest = hashlib.sha256(json.dumps(
        unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if claimed != observed_digest:
        findings.append(Finding(
            "DRG-ISOLATED-DIGEST", ISOLATED_ENV_EVIDENCE,
            "isolated target evidence digest does not match its content"))
    return sorted(set(findings))


def _validate_isolated_environment_evidence() -> list[Finding]:
    path = ROOT / ISOLATED_ENV_EVIDENCE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [Finding(
            "DRG-ISOLATED-EVIDENCE", ISOLATED_ENV_EVIDENCE,
            "isolated target evidence is absent or unreadable")]
    if not isinstance(payload, dict):
        return [Finding(
            "DRG-ISOLATED-EVIDENCE", ISOLATED_ENV_EVIDENCE,
            "isolated target evidence must be an object")]
    return validate_isolated_environment_evidence(payload)


def _validate_drg01_technical_evidence() -> list[Finding]:
    try:
        from tools.drg01_technical.model import load_evidence, validate_evidence
        errors = validate_evidence(load_evidence())
    except (ImportError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors = [str(error)]
    return [
        Finding("DRG01-TECH-EVIDENCE", DRG01_TECHNICAL_EVIDENCE, error)
        for error in errors
    ]


def _validate_rights_incident_evidence() -> list[Finding]:
    try:
        from tools.rights_incident_drill.drill import load_evidence, validate_evidence
        errors = validate_evidence(load_evidence())
    except (ImportError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors = [str(error)]
    return [
        Finding("DRG01-RIGHTS-IR-EVIDENCE", RIGHTS_INCIDENT_EVIDENCE, error)
        for error in errors
    ]


@lru_cache(maxsize=1)
def _current_release_inputs() -> tuple[tuple[str, str, int], ...]:
    from tools.release_candidate.model import digest_source_input, load_contract

    contract = load_contract(ROOT)
    observed = []
    for relative in contract["source_inputs"]:
        digest, count = digest_source_input(ROOT, relative)
        observed.append((relative, digest, count))
    return tuple(observed)


def validate_supply_chain_evidence(
    payload: dict[str, Any], *, verify_current_source: bool = True,
) -> list[Finding]:
    """Validate the durable projection of an externally verified attestation.

    The Sigstore bundles remain workflow artifacts. The repository stores only
    their digests and the exact source-input inventory, so a later product
    change makes this control stale without putting large attestations in Git.
    """
    findings: list[Finding] = []
    required = {
        "schema_version", "task_id", "control_id", "state",
        "data_classification", "generated_at", "real_data_authorized",
        "production_authorized", "run", "subject", "source_inputs",
        "attestations", "independent_review", "evidence_sha256",
    }
    if set(payload) != required:
        findings.append(Finding(
            "DRG-SUPPLY-SCHEMA", SUPPLY_CHAIN_EVIDENCE,
            "supply-chain evidence fields drifted"))
    if (
        payload.get("schema_version") != "1.0.0"
        or payload.get("task_id") != "FNC-GAT-005"
        or payload.get("control_id") != "G00-SUPPLY-CHAIN"
        or payload.get("state") != "passed"
        or payload.get("data_classification") != "completely_synthetic"
        or payload.get("real_data_authorized") is not False
        or payload.get("production_authorized") is not False
    ):
        findings.append(Finding(
            "DRG-SUPPLY-CLAIM", SUPPLY_CHAIN_EVIDENCE,
            "supply-chain evidence overclaims its identity or authorization"))
    generated_at = payload.get("generated_at")
    try:
        parsed = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None or not str(generated_at).endswith("Z"):
            raise ValueError
    except ValueError:
        findings.append(Finding(
            "DRG-SUPPLY-TIME", SUPPLY_CHAIN_EVIDENCE,
            "generated_at must be an explicit UTC instant"))

    run = payload.get("run")
    run_fields = {
        "id", "url", "conclusion", "event", "source_ref",
        "source_revision", "signer_workflow", "self_hosted_runner_denied",
    }
    if not isinstance(run, dict) or set(run) != run_fields:
        findings.append(Finding(
            "DRG-SUPPLY-RUN", SUPPLY_CHAIN_EVIDENCE,
            "workflow run fields drifted"))
        run = {}
    run_id = run.get("id")
    revision = run.get("source_revision")
    if (
        not isinstance(run_id, int) or run_id <= 0
        or run.get("url") != (
            f"https://github.com/Nipko/fincilia-platfrom/actions/runs/{run_id}"
        )
        or run.get("conclusion") != "success"
        or run.get("event") != "workflow_dispatch"
        or run.get("source_ref") != "refs/heads/main"
        or not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
        or run.get("signer_workflow") != SUPPLY_CHAIN_SIGNER
        or run.get("self_hosted_runner_denied") is not True
    ):
        findings.append(Finding(
            "DRG-SUPPLY-RUN", SUPPLY_CHAIN_EVIDENCE,
            "workflow run is not the required successful OIDC source"))

    subject = payload.get("subject")
    subject_fields = {
        "name", "sha256", "size_bytes", "schema_head",
        "bundle_schema_version", "source_verified_against_checkout",
        "archive_verified_outside_runner",
    }
    if not isinstance(subject, dict) or set(subject) != subject_fields:
        findings.append(Finding(
            "DRG-SUPPLY-SUBJECT", SUPPLY_CHAIN_EVIDENCE,
            "attestation subject fields drifted"))
        subject = {}
    migration_heads = sorted(
        path.name.split("__", 1)[0]
        for path in (ROOT / "db/migrations").glob("V[0-9][0-9][0-9][0-9]__*.sql")
    )
    if (
        subject.get("name") != "fincilia-release.tar.gz"
        or not isinstance(subject.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(subject.get("sha256"))) is None
        or not isinstance(subject.get("size_bytes"), int)
        or subject.get("size_bytes", 0) <= 0
        or not migration_heads
        or subject.get("schema_head") != migration_heads[-1]
        or subject.get("bundle_schema_version") != "1.1.0"
        or subject.get("source_verified_against_checkout") is not True
        or subject.get("archive_verified_outside_runner") is not True
    ):
        findings.append(Finding(
            "DRG-SUPPLY-SUBJECT", SUPPLY_CHAIN_EVIDENCE,
            "attestation subject is incomplete, stale or unverified"))

    attestations = payload.get("attestations")
    expected_predicates = {
        "provenance": "https://slsa.dev/provenance/v1",
        "sbom": "https://spdx.dev/Document/v2.3",
    }
    if (
        not isinstance(attestations, list)
        or [item.get("id") for item in attestations if isinstance(item, dict)]
        != ["provenance", "sbom"]
    ):
        findings.append(Finding(
            "DRG-SUPPLY-ATTESTATION", SUPPLY_CHAIN_EVIDENCE,
            "provenance and SBOM attestations are required exactly once"))
        attestations = []
    attestation_fields = {
        "id", "predicate_type", "sigstore_bundle_sha256",
        "verification_output_sha256", "signature_verified_in_runner",
        "signature_verified_outside_runner",
    }
    for item in attestations:
        if (
            not isinstance(item, dict) or set(item) != attestation_fields
            or item.get("predicate_type") != expected_predicates.get(item.get("id"))
            or re.fullmatch(r"[0-9a-f]{64}", str(item.get("sigstore_bundle_sha256"))) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(item.get("verification_output_sha256"))) is None
            or item.get("signature_verified_in_runner") is not True
            or item.get("signature_verified_outside_runner") is not True
        ):
            findings.append(Finding(
                "DRG-SUPPLY-ATTESTATION", str(item.get("id")),
                "attestation is not bound and verified on both trust boundaries"))

    independent = payload.get("independent_review")
    if independent != {
        "state": "pending",
        "required_roles": ["Security", "QA"],
        "agent_observation_is_not_acceptance": True,
    }:
        findings.append(Finding(
            "DRG-SUPPLY-REVIEW", SUPPLY_CHAIN_EVIDENCE,
            "technical evidence must not claim independent human review"))

    inputs = payload.get("source_inputs")
    if verify_current_source:
        try:
            expected_inputs = [
                {"path": path, "sha256": digest, "tracked_file_count": count}
                for path, digest, count in _current_release_inputs()
            ]
            if inputs != expected_inputs:
                findings.append(Finding(
                    "DRG-SUPPLY-SOURCE", SUPPLY_CHAIN_EVIDENCE,
                    "current release inputs differ from the attested source"))
        except (ImportError, OSError, ValueError) as error:
            findings.append(Finding(
                "DRG-SUPPLY-SOURCE", SUPPLY_CHAIN_EVIDENCE,
                f"current release inputs cannot be verified: {error}"))
    elif not isinstance(inputs, list) or not inputs:
        findings.append(Finding(
            "DRG-SUPPLY-SOURCE", SUPPLY_CHAIN_EVIDENCE,
            "source input inventory is absent"))

    claimed = payload.get("evidence_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    observed = hashlib.sha256(json.dumps(
        unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if claimed != observed:
        findings.append(Finding(
            "DRG-SUPPLY-DIGEST", SUPPLY_CHAIN_EVIDENCE,
            "supply-chain evidence digest does not match its content"))
    return sorted(set(findings))


def _validate_supply_chain_evidence() -> list[Finding]:
    path = ROOT / SUPPLY_CHAIN_EVIDENCE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [Finding(
            "DRG-SUPPLY-EVIDENCE", SUPPLY_CHAIN_EVIDENCE,
            "supply-chain evidence is absent or unreadable")]
    if not isinstance(payload, dict):
        return [Finding(
            "DRG-SUPPLY-EVIDENCE", SUPPLY_CHAIN_EVIDENCE,
            "supply-chain evidence must be an object")]
    return validate_supply_chain_evidence(payload)


def validate(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    required = {
        "schema_version", "task_id", "status", "target", "data_ceiling",
        "real_data_authorized", "pilot_scope", "selected_architecture",
        "controls", "gate_claims", "human_acceptance",
        "founder_is_independent_reviewer",
    }
    if set(model) != required:
        findings.append(Finding("DRG-SCHEMA", "$", "top-level fields drifted"))
    if model.get("schema_version") != "1.0.0" or model.get("task_id") != "FNC-GAT-005":
        findings.append(Finding("DRG-IDENTITY", "$", "unsupported model identity"))
    if model.get("founder_is_independent_reviewer") is not False:
        findings.append(Finding("DRG-SOD", "founder", "Founder cannot be the independent reviewer"))

    scope = model.get("pilot_scope", {})
    if (
        scope.get("operator_mode") != "founder_first_named_users_only"
        or not isinstance(scope.get("maximum_companies"), int)
        or scope.get("maximum_companies") != 1
        or not isinstance(scope.get("maximum_users"), int)
        or not 1 <= scope.get("maximum_users", 0) <= 3
        or scope.get("allowed_document_types") != ALLOWED_DOCUMENTS
        or scope.get("prohibited_data_categories") != PROHIBITED_DATA
        or scope.get("disabled_capabilities") != DISABLED_CAPABILITIES
        or scope.get("invite_only") is not True
    ):
        findings.append(Finding("DRG-SCOPE", "pilot_scope", "first real pilot scope was widened"))

    architecture = model.get("selected_architecture", {})
    expected_architecture = {
        "provider": "AWS",
        "primary_region": "sa-east-1",
        "selection_state": "founder_direction_pending_independent_review",
        "public_web_entry": "https_only_with_waf",
        "data_stores": "private_subnets_and_customer_managed_kms",
        "management": "ssm_only_no_ssh",
        "external_ai": "disabled",
    }
    if architecture != expected_architecture:
        findings.append(Finding("DRG-ARCHITECTURE", "selected_architecture", "pilot architecture drifted"))

    controls = model.get("controls")
    if not isinstance(controls, list):
        controls = []
        findings.append(Finding("DRG-CONTROLS", "controls", "controls must be a list"))
    by_id = {item.get("id"): item for item in controls if isinstance(item, dict)}
    expected_ids = set().union(*CONTROL_IDS.values())
    if set(by_id) != expected_ids or len(controls) != len(expected_ids):
        findings.append(Finding("DRG-COVERAGE", "controls", "required control set drifted"))

    exact_fields = {
        "id", "gate", "domain", "kind", "owner_role", "reviewer_roles",
        "state", "evidence_refs", "reviewer_id", "reviewed_at",
    }
    for identifier, control in by_id.items():
        if set(control) != exact_fields:
            findings.append(Finding("DRG-CONTROL-SCHEMA", str(identifier), "control fields drifted"))
            continue
        gate = control.get("gate")
        if gate not in CONTROL_IDS or identifier not in CONTROL_IDS[gate]:
            findings.append(Finding("DRG-CONTROL-GATE", str(identifier), "control assigned to wrong gate"))
        expected_kind = "human" if identifier in HUMAN_IDS else (
            "prerequisite" if identifier in PREREQUISITE_IDS else "automated")
        if control.get("kind") != expected_kind:
            findings.append(Finding("DRG-CONTROL-KIND", str(identifier), "control kind drifted"))
        if not control.get("owner_role") or not control.get("reviewer_roles"):
            findings.append(Finding("DRG-CONTROL-OWNER", str(identifier), "owner or reviewer role missing"))
        refs = control.get("evidence_refs")
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            findings.append(Finding("DRG-EVIDENCE", str(identifier), "evidence refs must be a unique list"))
            refs = []
        for reference in refs:
            if not isinstance(reference, str) or not _inside_evidence(reference):
                findings.append(Finding("DRG-EVIDENCE", str(identifier), f"invalid evidence {reference!r}"))
        if control.get("state") in {"accepted", "passed"} and not refs:
            findings.append(Finding("DRG-EVIDENCE", str(identifier), "completed control needs reproducible evidence"))
        if control.get("state") == "pending" and (
            refs or control.get("reviewer_id") is not None or control.get("reviewed_at") is not None
        ):
            findings.append(Finding("DRG-PREMATURE-EVIDENCE", str(identifier), "pending control claims evidence or review"))
        if control.get("kind") == "human" and control.get("state") not in {"pending", "accepted"}:
            findings.append(Finding("DRG-HUMAN-STATE", str(identifier), "human control state is invalid"))
        if control.get("kind") in {"automated", "prerequisite"} and control.get("state") not in {"pending", "passed"}:
            findings.append(Finding("DRG-AUTO-STATE", str(identifier), "technical control state is invalid"))
        if control.get("state") == "accepted" and control.get("reviewer_id") == FOUNDER_ID:
            findings.append(Finding("DRG-SOD", str(identifier), "Founder cannot independently review the control"))
        if identifier in DRG00_SHARED_TECHNICAL_IDS and control.get("state") == "passed":
            if control.get("evidence_refs") != [DRG00_TECHNICAL_EVIDENCE]:
                findings.append(Finding(
                    "DRG-TECH-REF", str(identifier),
                    "DRG-00 technical controls require the adjudicated drill evidence"))
        if identifier == "G00-ISOLATED-ENV" and control.get("state") == "passed":
            if control.get("evidence_refs") != [ISOLATED_ENV_EVIDENCE]:
                findings.append(Finding(
                    "DRG-ISOLATED-REF", str(identifier),
                    "isolated environment requires evidence replayed in private-pilot"))
        if identifier in DRG01_ADJUDICATED_IDS and control.get("state") == "passed":
            if control.get("evidence_refs") != [DRG01_TECHNICAL_EVIDENCE]:
                findings.append(Finding(
                    "DRG01-TECH-REF", str(identifier),
                    "DRG-01 bounded technical controls require the adjudicated evidence"))
        if identifier == "D01-RIGHTS-IR" and control.get("state") == "passed":
            if control.get("evidence_refs") != [RIGHTS_INCIDENT_EVIDENCE]:
                findings.append(Finding(
                    "DRG01-RIGHTS-IR-REF", str(identifier),
                    "rights and incident control requires its adjudicated drill evidence"))
        if identifier == "G00-SUPPLY-CHAIN" and control.get("state") == "passed":
            if control.get("evidence_refs") != [SUPPLY_CHAIN_EVIDENCE]:
                findings.append(Finding(
                    "DRG-SUPPLY-REF", str(identifier),
                    "supply chain requires the adjudicated attestation evidence"))

    if any(by_id.get(identifier, {}).get("state") == "passed"
           for identifier in DRG00_SHARED_TECHNICAL_IDS):
        findings.extend(_validate_drg00_technical_evidence())
    if by_id.get("G00-ISOLATED-ENV", {}).get("state") == "passed":
        findings.extend(_validate_isolated_environment_evidence())
    if any(by_id.get(identifier, {}).get("state") == "passed"
           for identifier in DRG01_ADJUDICATED_IDS):
        findings.extend(_validate_drg01_technical_evidence())
    if by_id.get("D01-RIGHTS-IR", {}).get("state") == "passed":
        findings.extend(_validate_rights_incident_evidence())
    if by_id.get("G00-SUPPLY-CHAIN", {}).get("state") == "passed":
        findings.extend(_validate_supply_chain_evidence())

    drg00_ready = all(
        _control_satisfied(by_id.get(identifier, {}), False)
        for identifier in CONTROL_IDS["DRG-00"]
    )
    drg01_ready = drg00_ready and all(
        _control_satisfied(by_id.get(identifier, {}), drg00_ready)
        for identifier in CONTROL_IDS["DRG-01"]
    )
    claims = model.get("gate_claims")
    expected_claims = [
        {"id": "DRG-00", "status": "met" if drg00_ready else "not_met", "authorized": drg00_ready},
        {"id": "DRG-01", "status": "met" if drg01_ready else "not_met", "authorized": drg01_ready},
    ]
    if claims != expected_claims:
        findings.append(Finding("DRG-GATE-DERIVATION", "gate_claims", "gate claims do not match evidence"))
    expected_ceiling = "pilot_real_data" if drg01_ready else (
        "real_corpus_only" if drg00_ready else "synthetic_only")
    if model.get("data_ceiling") != expected_ceiling or model.get("real_data_authorized") is not drg01_ready:
        findings.append(Finding("DRG-DATA-DERIVATION", "data_ceiling", "data authorization does not match gates"))
    if model.get("human_acceptance") != (
        "accepted" if drg01_ready else "pending_independent_review"
    ):
        findings.append(Finding("DRG-HUMAN-DERIVATION", "human_acceptance", "human acceptance does not match gate"))
    return sorted(set(findings))


def report(model: dict[str, Any]) -> dict[str, Any]:
    findings = validate(model)
    controls = model.get("controls", []) if isinstance(model.get("controls"), list) else []
    blockers = [
        {"id": item.get("id"), "gate": item.get("gate"), "owner_role": item.get("owner_role"), "kind": item.get("kind")}
        for item in controls if item.get("state") == "pending"
    ]
    return {
        "ok": not findings,
        "model_valid": not findings,
        "real_data_authorized": model.get("real_data_authorized") is True and not findings,
        "gates": model.get("gate_claims", []),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "findings": [item.as_dict() for item in findings],
    }


def load_model() -> dict[str, Any]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
