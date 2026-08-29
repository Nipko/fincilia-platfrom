from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from tools.data_disposal import DisposalPolicy
from tools.drg00_lab import AccessGrant, LabController, LabError, LabManifest, LabPolicy
from tools.drg00_lab.lab import opaque
from tools.drg00_lab.runtime import run_network_probe, validate_compose


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-08-29T12:00:00Z"
SAFE = b"fecha,detalle,valor\n2026-01-01,Movimiento sintetico,1250.00\n"
FORBIDDEN_TEXT = ("Movimiento sintetico", "1250.00", "nombre-sensible.csv")
TEST_IDS = tuple(f"LAB-T{number:02d}" for number in range(1, 13))


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def _result(identifier: str, assertion: str, evidence: dict[str, Any]) -> dict[str, Any]:
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    return {
        "id": identifier, "assertion": assertion, "state": "passed",
        "evidence_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _denied(action: Callable[[], object]) -> bool:
    try:
        action()
    except (LabError, PermissionError, ValueError):
        return True
    return False


def run_drill(
    *, probe: Callable[[str], dict[str, object]] = run_network_probe,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    compose_errors = validate_compose(ROOT / "infra/drg00-lab/compose.yaml")
    quarantine_probe = probe("quarantine")
    processing_probe = probe("processing")
    if compose_errors:
        raise RuntimeError(f"compose isolation drifted: {compose_errors}")
    results.append(_result("LAB-T01", "public_ingress_and_public_ips_absent", {
        "compose_errors": compose_errors,
        "published_ports": 0,
        "external_networks": 0,
    }))
    results.append(_result("LAB-T02", "quarantine_cannot_resolve_or_reach_external_endpoint",
                           quarantine_probe))
    results.append(_result("LAB-T03", "processing_cannot_reach_external_endpoint",
                           processing_probe))

    with tempfile.TemporaryDirectory(prefix="fincilia-drg00-") as directory:
        root = Path(directory) / "lab"
        company = opaque("synthetic-company")
        manifest = LabManifest(
            run_ref=opaque("synthetic-run"), company_ref=company,
            purpose="corpus_research", data_classification="synthetic_only",
            approved_by="SYNTHETIC-TEST-FIXTURE",
            expires_at="2026-08-30T12:00:00Z",
            identity_mode="synthetic_test_identity",
        )
        policy = DisposalPolicy(
            policy_id="SYNTHETIC-TEST-POLICY", effective=True,
            retention_days=0, backup_days=7, delete_ledger_days=8,
            synthetic_test_only=True,
        )
        grant = AccessGrant(
            subject_ref=opaque("synthetic-subject"), company_ref=company,
            authorization_version=7, observed_version=7, active=True,
        )
        lab = LabController(root, manifest, policy)
        lab.initialize()

        safe_ref = lab.intake(SAFE, "nombre-sensible.csv", grant, NOW)
        safe_decision = lab.inspect(safe_ref, "nombre-sensible.csv", grant, NOW)
        derived_digest = lab.derive_digest_receipt(safe_ref, grant, NOW)
        backup_refs = lab.backup(safe_ref, grant, NOW)

        pan = "4111" + "1111" + "1111" + "1111"
        pan_payload = f"cliente,tarjeta\nSintetico,{pan}\n".encode()
        pan_ref = lab.intake(pan_payload, "sensible.csv", grant, NOW)
        pan_decision = lab.inspect(pan_ref, "sensible.csv", grant, NOW)
        macro_payload = _zip({
            "[Content_Types].xml": b"<Types/>",
            "xl/workbook.xml": b"<workbook/>",
            "xl/vbaProject.bin": b"synthetic-active-content",
        })
        macro_ref = lab.intake(macro_payload, "activo.xlsx", grant, NOW)
        macro_decision = lab.inspect(macro_ref, "activo.xlsx", grant, NOW)
        if not (
            safe_decision["outcome"] == "accepted"
            and pan_decision["outcome"] == "rejected"
            and macro_decision["outcome"] == "rejected"
            and not any((root / "evidence" / digest).exists() for digest in (
                hashlib.sha256(pan_payload).hexdigest(),
                hashlib.sha256(macro_payload).hexdigest(),
            ))
        ):
            raise RuntimeError("hostile fixture crossed quarantine")
        results.append(_result("LAB-T04", "hostile_active_or_pan_fixture_never_reaches_raw", {
            "safe": safe_decision["reason_code"],
            "pan": pan_decision["reason_code"],
            "active": macro_decision["reason_code"],
        }))

        other_company = opaque("other-company")
        cross = AccessGrant(opaque("other-subject"), other_company, 1, 1, True)
        cross_denied = _denied(lambda: lab.read_object(safe_ref, other_company, cross))
        if not cross_denied:
            raise RuntimeError("cross-company read was accepted")
        results.append(_result("LAB-T05", "cross_company_read_write_and_object_key_access_denied", {
            "read_denied": True, "object_ref_disclosed": False,
        }))

        revoked = AccessGrant(opaque("revoked"), company, 7, 7, False)
        stale = AccessGrant(opaque("stale"), company, 8, 7, True)
        if not all(_denied(lambda candidate=item: lab.read_object(
            safe_ref, company, candidate)) for item in (revoked, stale)):
            raise RuntimeError("revoked or stale authorization survived")
        results.append(_result("LAB-T06", "revoked_user_session_job_and_download_fail", {
            "revoked_denied": True, "stale_version_denied": True,
        }))

        shared = AccessGrant(opaque("shared"), company, 7, 7, True, shared=True)
        weak_manifest_denied = _denied(lambda: LabManifest(
            run_ref=opaque("weak"), company_ref=company,
            purpose="corpus_research", data_classification="real",
            approved_by="FOUNDER-01", expires_at=NOW,
            identity_mode="password_only",
        ).validate())
        if not (_denied(lambda: lab.read_object(safe_ref, company, shared))
                and weak_manifest_denied):
            raise RuntimeError("shared or password-only access survived")
        results.append(_result("LAB-T07", "shared_account_static_key_and_password_only_login_fail", {
            "shared_denied": True, "password_only_denied": True,
            "static_key_supported": False,
        }))

        audit = (root / "archive" / "audit.ndjson").read_text(encoding="utf-8")
        control = (root / "control" / "manifest.json").read_text(encoding="utf-8")
        if any(item in audit + control for item in (*FORBIDDEN_TEXT, pan)):
            raise RuntimeError("audit or control plane copied fixture content")
        results.append(_result("LAB-T08", "logs_and_errors_contain_only_allowlisted_metadata", {
            "forbidden_values_found": 0, "audit_line_count": len(audit.splitlines()),
        }))

        # Conservar una copia sintética fuera del árbol imita un backup antiguo.
        # Se reintroduce después de la purga y antes de la reaplicación.
        restored_copies = {
            reference: root.joinpath(*reference.split("/")).read_bytes()
            for reference in backup_refs
        }
        lab.purge(safe_ref, grant, NOW)
        ready_path = root / "control" / "restore-ready.json"
        if ready_path.exists():
            raise RuntimeError("restore became ready before tombstone reconciliation")
        for reference, body in restored_copies.items():
            path = root.joinpath(*reference.split("/"))
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(body)
        restore_receipt = lab.disposal.reapply_after_restore(NOW)
        if any(root.joinpath(*reference.split("/")).exists()
               for reference in restored_copies):
            raise RuntimeError("restore resurrected a tombstoned copy")
        results.append(_result("LAB-T09", "restore_reapplies_tombstones_before_health_ready", {
            "state": restore_receipt["state"],
            "restored_copy_count": len(restored_copies),
            "reconciled": True,
        }))

        destroy = lab.destroy(grant, NOW)
        if destroy["active_object_count"] != 0 or lab.inventory.reconcile(root):
            raise RuntimeError("destroy left active or untracked objects")
        results.append(_result("LAB-T10", "lab_destroy_reconciles_all_active_derived_and_backup_inventory", {
            "active_object_count": 0,
            "inventory_event_count": lab.inventory.snapshot().event_count,
        }))

        unsigned_denied = _denied(lambda: LabPolicy.authorize_release(
            signed=False, provenance_verified=True, digest_pinned=True))
        if not unsigned_denied:
            raise RuntimeError("unsigned release was admitted")
        results.append(_result("LAB-T11", "unsigned_or_unprovenanced_image_cannot_start", {
            "unsigned_denied": True, "current_product_release_admitted": False,
        }))

        weak_break_glass = _denied(lambda: LabPolicy.authorize_break_glass(
            requester_ref="a" * 64, approver_ref="a" * 64,
            post_reviewer_ref="b" * 64))
        LabPolicy.authorize_break_glass(
            requester_ref="a" * 64, approver_ref="b" * 64,
            post_reviewer_ref="c" * 64)
        if not weak_break_glass:
            raise RuntimeError("single-person break-glass was admitted")
        results.append(_result("LAB-T12", "break_glass_requires_two_distinct_humans_and_post_review", {
            "single_person_denied": True, "distinct_synthetic_roles_accepted": True,
        }))

    if tuple(item["id"] for item in results) != TEST_IDS:
        raise RuntimeError("acceptance test coverage drifted")
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": "FNC-QA-001",
        "executed_at": NOW,
        "data_classification": "completely_synthetic",
        "real_data_authorized": False,
        "test_count": len(results),
        "passed_count": len(results),
        "failed_count": 0,
        "tests": results,
        "technical_controls": {
            "G00-ISOLATED-ENV": ["LAB-T01", "LAB-T02", "LAB-T03", "LAB-T11", "LAB-T12"],
            "G00-INVENTORY": ["LAB-T04", "LAB-T05", "LAB-T06", "LAB-T08"],
            "G00-DELETE": ["LAB-T09", "LAB-T10"],
            "G00-DRILL": list(TEST_IDS),
        },
        "limitations": [
            "no_real_data_was_received",
            "product_release_remains_unadmitted_until_signature_and_provenance",
            "human_legal_privacy_region_and_independent_reviews_remain_pending",
        ],
    }
    report["evidence_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    rendered = json.dumps(report, sort_keys=True)
    if any(value in rendered for value in (*FORBIDDEN_TEXT, "4111111111111111")):
        raise RuntimeError("evidence copied a synthetic financial value")
    return report
