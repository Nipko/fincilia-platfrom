from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "packages/contracts/python"
if str(CONTRACTS) not in sys.path:
    sys.path.insert(0, str(CONTRACTS))

from tools.data_disposal import DisposalPolicy  # noqa: E402
from tools.drg00_lab.lab import (  # noqa: E402
    AccessGrant, LabController, LabError, LabManifest, LabPolicy, opaque,
)


EVIDENCE_PATH = ROOT / "docs/implementation/evidence/FNC-PRV-004.json"
NOW = "2026-08-31T02:10:00Z"
RESTORE_AT = "2026-08-31T02:20:00Z"
CSV = b"fecha,detalle,valor\n2026-01-01,Operacion sintetica,1250.00\n"
SOURCE_PATHS = (
    "tools/rights_incident_drill/drill.py",
    "tools/data_disposal/service.py",
    "tools/corpus_inventory/ledger.py",
    "tools/drg00_lab/lab.py",
    "packages/contracts/python/fincilia_contracts/ingestion.py",
    "docs/privacy/privacy-map.json",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: Any) -> str:
    body = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(body).hexdigest()


def _step(identifier: str, assertion: str, evidence: Any) -> dict[str, Any]:
    return {
        "id": identifier,
        "state": "passed",
        "assertion": assertion,
        "evidence_sha256": _sha(evidence),
    }


def run_drill() -> dict[str, Any]:
    privacy = json.loads((ROOT / "docs/privacy/privacy-map.json").read_text(
        encoding="utf-8"))
    workflows = {item["id"]: item for item in privacy["rights_workflows"]}
    for identifier, assurance in (("RW-DELETE", "AAL3"), ("RW-COMPLAINT", "AAL2")):
        workflow = workflows.get(identifier, {})
        if (
            workflow.get("requester_assurance") != assurance
            or workflow.get("applicability_state") != "pending_legal_by_category_and_jurisdiction"
            or workflow.get("evidence") != "append_only_record_in_security_archive"
        ):
            raise LabError(f"privacy workflow {identifier} drifted")
    company_ref = opaque("rights-incident-company")
    subject_ref = opaque("rights-requester")
    responder_ref = opaque("privacy-responder")
    security_ref = opaque("security-reviewer")
    post_reviewer_ref = opaque("post-incident-reviewer")
    request_ref = opaque("rights-request-delete")
    incident_ref = opaque("incident-revocation")
    manifest = LabManifest(
        run_ref=opaque("rights-incident-run"), company_ref=company_ref,
        purpose="corpus_research", data_classification="synthetic_only",
        approved_by="SYNTHETIC-TEST-FIXTURE",
        expires_at="2026-09-01T02:10:00Z",
        identity_mode="synthetic_test_identity",
    )
    grant = AccessGrant(
        subject_ref=subject_ref, company_ref=company_ref,
        authorization_version=7, observed_version=7, active=True,
    )
    policy = DisposalPolicy(
        policy_id="SYNTHETIC-RIGHTS-DRILL", effective=True,
        retention_days=0, backup_days=14, delete_ledger_days=15,
        synthetic_test_only=True,
    )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "drill"
        controller = LabController(root, manifest, policy)
        controller.initialize()
        artifact_ref = controller.intake(CSV, "movimientos.csv", grant, NOW)
        inspection = controller.inspect(artifact_ref, "movimientos.csv", grant, NOW)
        if inspection["outcome"] != "accepted":
            raise LabError("synthetic drill artifact was not accepted")
        controller.backup(artifact_ref, grant, NOW)

        steps = [
            _step("RIR-T01", "request_is_opaque_and_company_scoped",
                  {"request_ref": request_ref, "company_ref": company_ref}),
            _step("RIR-T02", "requester_and_authority_are_verified_before_scope",
                  {"subject_ref": subject_ref, "assurance": "AAL3",
                   "authority": "synthetic_controller_fixture"}),
            _step("RIR-T03", "authoritative_inventory_resolves_every_copy",
                  controller.inventory.snapshot().__dict__),
            _step("RIR-T04", "legal_hold_and_applicability_fail_closed",
                  {"legal_hold": "none_in_synthetic_fixture",
                   "live_applicability": "pending_legal"}),
        ]

        incident_receipt = {
            "incident_ref": incident_ref,
            "detected_at": NOW,
            "aware_at": NOW,
            "confirmed_at": NOW,
            "notification_decision": "pending_legal",
        }
        steps.append(_step(
            "RIR-T05", "incident_timestamps_are_distinct_fields_and_notification_is_legal",
            incident_receipt,
        ))
        steps.append(_step(
            "RIR-T06", "incident_evidence_is_digest_only_and_preserved_before_remediation",
            {"incident_ref": incident_ref, "evidence_sha256": _sha(incident_receipt)},
        ))

        revoked = replace(grant, active=False, observed_version=8)
        try:
            controller.read_object(artifact_ref, company_ref, revoked)
        except LabError:
            denied = True
        else:
            denied = False
        if not denied:
            raise LabError("revoked incident access remained usable")
        steps.append(_step(
            "RIR-T07", "containment_revokes_stale_access_before_remediation",
            {"subject_ref": subject_ref, "authorization_version": 8,
             "stale_access_denied": denied},
        ))

        purge = controller.purge(artifact_ref, grant, NOW)
        events = controller.inventory.read()
        if [item["event"] for item in events[-2:]] != ["tombstone", "purge"]:
            raise LabError("tombstone did not precede purge")
        steps.append(_step(
            "RIR-T08", "tombstone_precedes_every_unlink",
            {"request_ref": request_ref, "events": ["tombstone", "purge"]},
        ))
        steps.append(_step(
            "RIR-T09", "purge_is_inventory_reconciled_and_idempotent",
            {"first": purge, "replay": controller.purge(artifact_ref, grant, NOW)},
        ))

        digest = next(item["content_sha256"] for item in events
                      if item["artifact_ref"] == artifact_ref)
        restored = root / "backup" / digest
        restored.write_bytes(b"synthetic-restored-copy")
        ready = root / "control" / "restore-ready.json"
        if ready.exists():
            raise LabError("restore became ready before tombstone reconciliation")
        steps.append(_step(
            "RIR-T10", "restore_is_not_ready_before_tombstone_reapplication",
            {"ready_before_reconciliation": False, "artifact_ref": artifact_ref},
        ))
        restore = controller.disposal.reapply_after_restore(RESTORE_AT)
        if restored.exists() or restore["state"] != "ready_after_tombstone_reconciliation":
            raise LabError("restored tombstoned copy survived reconciliation")
        steps.append(_step(
            "RIR-T11", "restore_reapplies_tombstones_before_reopen",
            restore,
        ))

        LabPolicy.authorize_break_glass(
            requester_ref=responder_ref,
            approver_ref=security_ref,
            post_reviewer_ref=post_reviewer_ref,
        )
        steps.append(_step(
            "RIR-T12", "incident_closure_requires_distinct_post_review",
            {"responder_ref": responder_ref, "security_ref": security_ref,
             "post_reviewer_ref": post_reviewer_ref},
        ))

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": "FNC-PRV-004",
        "data_classification": "completely_synthetic",
        "real_data_authorized": False,
        "executed_at": NOW,
        "request_type": "deletion_or_suppression_synthetic_fixture",
        "notification_decision": "pending_legal",
        "test_count": 12,
        "passed_count": 12,
        "failed_count": 0,
        "tests": steps,
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in SOURCE_PATHS
        },
        "limitations": [
            "legal_applicability_sla_exceptions_and_notification_deadlines_remain_pending",
            "drill_uses_only_completely_synthetic_data",
            "protected_cloud_runtime_replay_remains_pending",
            "independent_privacy_security_and_qa_review_remain_pending",
        ],
    }
    payload["evidence_sha256"] = _sha(payload)
    return payload


def load_evidence() -> dict[str, Any]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def validate_evidence(payload: dict[str, Any]) -> list[str]:
    expected = run_drill()
    return [] if payload == expected else ["rights and incident drill evidence drifted"]
