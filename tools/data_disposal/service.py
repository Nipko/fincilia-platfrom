from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.corpus_inventory import InventoryError, InventoryLedger
from tools.corpus_inventory.ledger import HEX64, ZONES


class DisposalError(RuntimeError):
    """La purga no puede demostrarse completa o la política no está vigente."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


@dataclass(frozen=True)
class DisposalPolicy:
    policy_id: str
    effective: bool
    retention_days: int
    backup_days: int
    delete_ledger_days: int
    synthetic_test_only: bool = False

    def validate(self) -> None:
        if not self.effective:
            raise DisposalError("retention policy is not effective")
        if not self.policy_id or any(value < 0 for value in (
            self.retention_days, self.backup_days, self.delete_ledger_days,
        )):
            raise DisposalError("retention policy fields are invalid")
        if self.delete_ledger_days <= self.backup_days:
            raise DisposalError("delete ledger must outlive every backup")


class TombstoneLedger:
    FIELDS = {
        "schema_version", "sequence", "artifact_ref", "company_ref",
        "content_sha256", "policy_id", "requested_at", "previous_sha256",
        "tombstone_sha256",
    }

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        previous: str | None = None
        for sequence, raw in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as error:
                raise DisposalError("delete ledger is invalid") from error
            if not isinstance(item, dict) or set(item) != self.FIELDS:
                raise DisposalError("delete ledger fields drifted")
            if (
                item["schema_version"] != "1.0.0"
                or item["sequence"] != sequence
                or item["previous_sha256"] != previous
                or any(not HEX64.fullmatch(str(item[key])) for key in (
                    "artifact_ref", "company_ref", "content_sha256",
                ))
            ):
                raise DisposalError("delete ledger chain drifted")
            unsigned = {key: value for key, value in item.items()
                        if key != "tombstone_sha256"}
            observed = hashlib.sha256(_canonical(unsigned)).hexdigest()
            if item["tombstone_sha256"] != observed:
                raise DisposalError("delete ledger digest mismatch")
            previous = observed
            result.append(item)
        return result

    def append(
        self, *, artifact_ref: str, company_ref: str, content_sha256: str,
        policy_id: str, requested_at: str,
    ) -> dict[str, Any]:
        existing = self.read()
        for item in existing:
            if item["artifact_ref"] == artifact_ref:
                if item["content_sha256"] != content_sha256:
                    raise DisposalError("artifact tombstone digest diverged")
                return item
        payload: dict[str, Any] = {
            "schema_version": "1.0.0",
            "sequence": len(existing) + 1,
            "artifact_ref": artifact_ref,
            "company_ref": company_ref,
            "content_sha256": content_sha256,
            "policy_id": policy_id,
            "requested_at": requested_at,
            "previous_sha256": existing[-1]["tombstone_sha256"] if existing else None,
        }
        payload["tombstone_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600,
        )
        try:
            os.write(descriptor, _canonical(payload) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.read()
        return payload


class DisposalService:
    def __init__(
        self, root: Path, inventory: InventoryLedger, policy: DisposalPolicy,
    ) -> None:
        self.root = root
        self.inventory = inventory
        self.policy = policy
        self.tombstones = TombstoneLedger(root / "archive" / "delete-ledger.ndjson")

    @staticmethod
    def _op(label: str, artifact_ref: str) -> str:
        return hashlib.sha256(f"{label}:{artifact_ref}".encode()).hexdigest()

    def purge(self, artifact_ref: str, requested_at: str) -> dict[str, Any]:
        self.policy.validate()
        events = self.inventory.read()
        related = [item for item in events if item["artifact_ref"] == artifact_ref]
        if not related:
            raise DisposalError("artifact is absent from inventory")
        last = related[-1]
        if last["state"] == "purged":
            return {
                "artifact_ref": artifact_ref,
                "state": "purged",
                "removed_copy_count": 0,
                "idempotent": True,
            }
        snapshot = self.inventory.snapshot(events)
        active_refs = list(snapshot.active_refs.get(artifact_ref, ()))
        # El registro durable ocurre antes del primer unlink. Un crash puede dejar
        # copias pendientes, pero nunca una copia eliminada sin tombstone.
        self.tombstones.append(
            artifact_ref=artifact_ref,
            company_ref=last["company_ref"],
            content_sha256=last["content_sha256"],
            policy_id=self.policy.policy_id,
            requested_at=requested_at,
        )
        self.inventory.append(
            operation_ref=self._op("tombstone", artifact_ref),
            artifact_ref=artifact_ref, company_ref=last["company_ref"],
            event="tombstone", content_sha256=last["content_sha256"],
            created_refs=[], removed_refs=[], reason_code="retention_expired",
            occurred_at=requested_at,
        )
        removed = 0
        for reference in active_refs:
            path = self.root.joinpath(*reference.split("/"))
            if path.exists():
                path.unlink()
                removed += 1
        self.inventory.append(
            operation_ref=self._op("purge", artifact_ref),
            artifact_ref=artifact_ref, company_ref=last["company_ref"],
            event="purge", content_sha256=last["content_sha256"],
            created_refs=[], removed_refs=active_refs,
            reason_code="copies_reconciled", occurred_at=requested_at,
        )
        drift = self.inventory.reconcile(self.root)
        if drift:
            raise DisposalError(f"purge reconciliation drifted: {drift}")
        return {
            "artifact_ref": artifact_ref,
            "state": "purged",
            "removed_copy_count": removed,
            "idempotent": False,
        }

    def reapply_after_restore(self, occurred_at: str) -> dict[str, Any]:
        self.policy.validate()
        tombstones = self.tombstones.read()
        removed = 0
        inventory_events = self.inventory.read()
        for tombstone in tombstones:
            digest = tombstone["content_sha256"]
            # Un derivado tiene su propio digest. El tombstone conserva el
            # artefacto y el inventario conserva todas las referencias creadas;
            # usar sólo el digest del raw resucitaría derivados desde backup.
            historical_refs = {
                reference
                for event in inventory_events
                if event["artifact_ref"] == tombstone["artifact_ref"]
                for reference in event["created_refs"]
            }
            historical_refs.add(f"backup/{digest}")
            for reference in sorted(historical_refs):
                path = self.root.joinpath(*reference.split("/"))
                if path.exists():
                    path.unlink()
                    removed += 1
            snapshot = self.inventory.snapshot()
            if snapshot.artifact_states.get(tombstone["artifact_ref"]) == "purged":
                self.inventory.append(
                    operation_ref=self._op("restore", tombstone["artifact_ref"]),
                    artifact_ref=tombstone["artifact_ref"],
                    company_ref=tombstone["company_ref"],
                    event="restore_repurge", content_sha256=digest,
                    created_refs=[], removed_refs=[],
                    reason_code="tombstone_reapplied", occurred_at=occurred_at,
                )
        drift = self.inventory.reconcile(self.root)
        if drift:
            raise DisposalError(f"restore reconciliation drifted: {drift}")
        ready = self.root / "control" / "restore-ready.json"
        ready.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema_version": "1.0.0",
            "state": "ready_after_tombstone_reconciliation",
            "tombstone_count": len(tombstones),
            "removed_copy_count": removed,
            "occurred_at": occurred_at,
        }
        ready.write_bytes(_canonical(receipt) + b"\n")
        return receipt
