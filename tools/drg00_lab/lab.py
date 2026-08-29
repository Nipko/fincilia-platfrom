from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fincilia_contracts.ingestion import RejectedUpload, admit, decide_promotion

from tools.corpus_inventory import InventoryError, InventoryLedger
from tools.data_disposal import DisposalPolicy, DisposalService


class LabError(RuntimeError):
    """La operación no puede demostrar que conserva el aislamiento."""


def opaque(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


@dataclass(frozen=True)
class LabManifest:
    run_ref: str
    company_ref: str
    purpose: str
    data_classification: str
    approved_by: str
    expires_at: str
    identity_mode: str

    def validate(self) -> None:
        if any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
               for value in (self.run_ref, self.company_ref)):
            raise LabError("run and company references must be opaque sha256")
        if self.purpose != "corpus_research" or self.data_classification != "synthetic_only":
            raise LabError("real data remains disabled until DRG-00")
        if self.approved_by != "SYNTHETIC-TEST-FIXTURE":
            raise LabError("synthetic drill approval marker is required")
        if self.identity_mode != "synthetic_test_identity":
            raise LabError("local or shared identity cannot authorize real-data work")
        if not self.expires_at.endswith("Z"):
            raise LabError("manifest expiry must be explicit UTC")


@dataclass(frozen=True)
class AccessGrant:
    subject_ref: str
    company_ref: str
    authorization_version: int
    observed_version: int
    active: bool
    shared: bool = False

    def validate(self, company_ref: str) -> None:
        if (
            not self.active or self.shared or self.company_ref != company_ref
            or self.authorization_version != self.observed_version
        ):
            raise LabError("access grant is revoked, shared, stale or cross-company")


class LabPolicy:
    @staticmethod
    def authorize_release(*, signed: bool, provenance_verified: bool,
                          digest_pinned: bool) -> None:
        if not (signed and provenance_verified and digest_pinned):
            raise LabError("unsigned or unprovenanced workload cannot start")

    @staticmethod
    def authorize_break_glass(*, requester_ref: str, approver_ref: str,
                              post_reviewer_ref: str) -> None:
        identities = {requester_ref, approver_ref, post_reviewer_ref}
        if len(identities) != 3 or any(len(value) != 64 for value in identities):
            raise LabError("break-glass requires three distinct opaque subjects")


class LabController:
    ZONES = ("quarantine", "evidence", "derived", "backup", "scratch",
             "archive", "control")
    AUDIT_FIELDS = {
        "schema_version", "event", "run_ref", "artifact_ref", "outcome",
        "occurred_at",
    }

    def __init__(self, root: Path, manifest: LabManifest,
                 disposal_policy: DisposalPolicy):
        manifest.validate()
        disposal_policy.validate()
        if not disposal_policy.synthetic_test_only:
            raise LabError("only the synthetic drill policy is usable before DRG-00")
        self.root = root
        self.manifest = manifest
        self.inventory = InventoryLedger(root / "control" / "inventory.ndjson")
        self.disposal = DisposalService(root, self.inventory, disposal_policy)

    def initialize(self) -> None:
        if self.root.exists() and any(self.root.iterdir()):
            raise LabError("lab root must start empty")
        for zone in self.ZONES:
            path = self.root / zone
            path.mkdir(parents=True, exist_ok=True)
            os.chmod(path, 0o700)
        manifest = {
            "schema_version": "1.0.0",
            "run_ref": self.manifest.run_ref,
            "company_ref": self.manifest.company_ref,
            "purpose": self.manifest.purpose,
            "data_classification": self.manifest.data_classification,
            "approved_by": self.manifest.approved_by,
            "expires_at": self.manifest.expires_at,
            "identity_mode": self.manifest.identity_mode,
            "network": "none",
            "real_data_authorized": False,
        }
        (self.root / "control" / "manifest.json").write_bytes(_canonical(manifest) + b"\n")

    def _audit(self, *, event: str, artifact_ref: str | None,
               outcome: str, occurred_at: str) -> None:
        payload = {
            "schema_version": "1.0.0", "event": event,
            "run_ref": self.manifest.run_ref, "artifact_ref": artifact_ref,
            "outcome": outcome, "occurred_at": occurred_at,
        }
        if set(payload) != self.AUDIT_FIELDS:
            raise LabError("audit fields drifted")
        path = self.root / "archive" / "audit.ndjson"
        descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, _canonical(payload) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _operation(label: str, artifact_ref: str) -> str:
        return opaque(f"{label}:{artifact_ref}")

    def intake(self, payload: bytes, declared_name: str, grant: AccessGrant,
               occurred_at: str) -> str:
        grant.validate(self.manifest.company_ref)
        try:
            admission = admit(payload, declared_name)
        except RejectedUpload as error:
            self._audit(event="intake", artifact_ref=None,
                        outcome="rejected_before_storage", occurred_at=occurred_at)
            raise LabError("upload rejected before storage") from error
        artifact_ref = opaque(
            f"{self.manifest.run_ref}:{self.manifest.company_ref}:"
            f"{admission.content_sha256}"
        )
        destination = self.root / "quarantine" / admission.content_sha256
        if destination.exists() and destination.read_bytes() != payload:
            raise LabError("content-addressed quarantine object diverged")
        if not destination.exists():
            descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        self.inventory.append(
            operation_ref=self._operation("intake", artifact_ref),
            artifact_ref=artifact_ref, company_ref=self.manifest.company_ref,
            event="intake", content_sha256=admission.content_sha256,
            created_refs=[f"quarantine/{admission.content_sha256}"],
            removed_refs=[], reason_code="synthetic_intake",
            occurred_at=occurred_at,
        )
        self._audit(event="intake", artifact_ref=artifact_ref,
                    outcome="quarantined", occurred_at=occurred_at)
        return artifact_ref

    def inspect(self, artifact_ref: str, declared_name: str, grant: AccessGrant,
                occurred_at: str) -> dict[str, Any]:
        grant.validate(self.manifest.company_ref)
        related = [item for item in self.inventory.read()
                   if item["artifact_ref"] == artifact_ref]
        if not related or related[-1]["state"] != "quarantined":
            raise LabError("artifact is not inspectable from quarantine")
        digest = related[-1]["content_sha256"]
        source = self.root / "quarantine" / digest
        if not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise LabError("quarantine evidence is absent or changed")
        decision = decide_promotion(source.read_bytes(), declared_name)
        if decision.promoted:
            destination = self.root / "evidence" / digest
            os.replace(source, destination)
            os.chmod(destination, 0o440)
            self.inventory.append(
                operation_ref=self._operation("promotion", artifact_ref),
                artifact_ref=artifact_ref, company_ref=self.manifest.company_ref,
                event="promotion", content_sha256=digest,
                created_refs=[f"evidence/{digest}"],
                removed_refs=[f"quarantine/{digest}"],
                reason_code=decision.reason_code, occurred_at=occurred_at,
            )
            outcome = "accepted"
        else:
            self.inventory.append(
                operation_ref=self._operation("rejection", artifact_ref),
                artifact_ref=artifact_ref, company_ref=self.manifest.company_ref,
                event="rejection", content_sha256=digest,
                created_refs=[], removed_refs=[],
                reason_code=decision.reason_code, occurred_at=occurred_at,
            )
            outcome = "rejected"
        self._audit(event="inspection", artifact_ref=artifact_ref,
                    outcome=outcome, occurred_at=occurred_at)
        return {
            "artifact_ref": artifact_ref,
            "outcome": outcome,
            "reason_code": decision.reason_code,
            "finding_kinds": sorted({item.kind for item in decision.findings}),
        }

    def derive_digest_receipt(self, artifact_ref: str, grant: AccessGrant,
                              occurred_at: str) -> str:
        grant.validate(self.manifest.company_ref)
        related = [item for item in self.inventory.read()
                   if item["artifact_ref"] == artifact_ref]
        if not related or related[-1]["state"] != "accepted":
            raise LabError("only accepted evidence can produce a derivative")
        source_digest = related[-1]["content_sha256"]
        receipt = {
            "schema_version": "1.0.0", "artifact_ref": artifact_ref,
            "source_sha256": source_digest, "transform": "digest_receipt_v1",
        }
        body = _canonical(receipt) + b"\n"
        derived_digest = hashlib.sha256(body).hexdigest()
        path = self.root / "derived" / derived_digest
        path.write_bytes(body)
        os.chmod(path, 0o440)
        self.inventory.append(
            operation_ref=self._operation("derivation", artifact_ref),
            artifact_ref=artifact_ref, company_ref=self.manifest.company_ref,
            event="derivation", content_sha256=source_digest,
            created_refs=[f"derived/{derived_digest}"], removed_refs=[],
            reason_code="digest_receipt_created", occurred_at=occurred_at,
        )
        self._audit(event="derivation", artifact_ref=artifact_ref,
                    outcome="digest_only", occurred_at=occurred_at)
        return derived_digest

    def backup(self, artifact_ref: str, grant: AccessGrant,
               occurred_at: str) -> list[str]:
        grant.validate(self.manifest.company_ref)
        snapshot = self.inventory.snapshot()
        if snapshot.artifact_states.get(artifact_ref) not in {"accepted", "rejected"}:
            raise LabError("artifact is not backup eligible")
        created: list[str] = []
        for reference in snapshot.active_refs.get(artifact_ref, ()):
            zone, digest = reference.split("/")
            if zone == "backup":
                continue
            source = self.root / zone / digest
            destination = self.root / "backup" / digest
            if not destination.exists():
                shutil.copyfile(source, destination)
                os.chmod(destination, 0o400)
                created.append(f"backup/{digest}")
        related = [item for item in self.inventory.read()
                   if item["artifact_ref"] == artifact_ref]
        self.inventory.append(
            operation_ref=self._operation("backup", artifact_ref),
            artifact_ref=artifact_ref, company_ref=self.manifest.company_ref,
            event="backup", content_sha256=related[-1]["content_sha256"],
            created_refs=created, removed_refs=[], reason_code="backup_created",
            occurred_at=occurred_at,
        )
        self._audit(event="backup", artifact_ref=artifact_ref,
                    outcome="completed", occurred_at=occurred_at)
        return created

    def purge(self, artifact_ref: str, grant: AccessGrant,
              occurred_at: str) -> dict[str, Any]:
        grant.validate(self.manifest.company_ref)
        receipt = self.disposal.purge(artifact_ref, occurred_at)
        self._audit(event="purge", artifact_ref=artifact_ref,
                    outcome="reconciled", occurred_at=occurred_at)
        return receipt

    def read_object(self, artifact_ref: str, company_ref: str,
                    grant: AccessGrant) -> bytes:
        grant.validate(company_ref)
        if company_ref != self.manifest.company_ref:
            raise LabError("cross-company object access denied")
        snapshot = self.inventory.snapshot()
        refs = snapshot.active_refs.get(artifact_ref, ())
        evidence = next((item for item in refs if item.startswith("evidence/")), None)
        if evidence is None:
            raise LabError("accepted evidence is unavailable")
        return self.root.joinpath(*evidence.split("/")).read_bytes()

    def destroy(self, grant: AccessGrant, occurred_at: str) -> dict[str, Any]:
        grant.validate(self.manifest.company_ref)
        snapshot = self.inventory.snapshot()
        for artifact_ref, state in sorted(snapshot.artifact_states.items()):
            if state != "purged":
                self.disposal.purge(artifact_ref, occurred_at)
        for zone in ("quarantine", "evidence", "derived", "backup", "scratch"):
            for path in (self.root / zone).iterdir():
                if path.is_file():
                    path.unlink()
        drift = self.inventory.reconcile(self.root)
        if drift:
            raise LabError(f"destroy reconciliation drifted: {drift}")
        receipt = {
            "schema_version": "1.0.0", "state": "destroyed",
            "active_object_count": 0, "run_ref": self.manifest.run_ref,
            "occurred_at": occurred_at,
        }
        (self.root / "control" / "destroy-receipt.json").write_bytes(
            _canonical(receipt) + b"\n"
        )
        self._audit(event="destroy", artifact_ref=None,
                    outcome="reconciled", occurred_at=occurred_at)
        return receipt
