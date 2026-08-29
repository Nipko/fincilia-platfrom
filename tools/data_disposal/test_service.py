from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.corpus_inventory import InventoryLedger

from .service import DisposalError, DisposalPolicy, DisposalService


DIGEST = "a" * 64
ARTIFACT = "b" * 64
COMPANY = "c" * 64
NOW = "2026-08-29T12:00:00Z"


class DisposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / DIGEST).write_bytes(b"synthetic")
        self.inventory = InventoryLedger(self.root / "control" / "inventory.ndjson")
        self.inventory.append(
            operation_ref="1" * 64, artifact_ref=ARTIFACT,
            company_ref=COMPANY, event="intake", content_sha256=DIGEST,
            created_refs=[f"quarantine/{DIGEST}"], removed_refs=[],
            reason_code="synthetic_intake", occurred_at=NOW,
        )
        (self.root / "quarantine").mkdir()
        (self.root / "quarantine" / DIGEST).write_bytes(b"synthetic")
        self.inventory.append(
            operation_ref="2" * 64, artifact_ref=ARTIFACT,
            company_ref=COMPANY, event="promotion", content_sha256=DIGEST,
            created_refs=[f"evidence/{DIGEST}"],
            removed_refs=[f"quarantine/{DIGEST}"],
            reason_code="content_inspected", occurred_at=NOW,
        )
        (self.root / "quarantine" / DIGEST).unlink()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def service(self, **changes) -> DisposalService:
        values = {
            "policy_id": "SYNTHETIC-TEST-POLICY",
            "effective": True,
            "retention_days": 0,
            "backup_days": 7,
            "delete_ledger_days": 8,
            "synthetic_test_only": True,
        }
        values.update(changes)
        return DisposalService(
            self.root, self.inventory, DisposalPolicy(**values),
        )

    def test_policy_must_be_effective_and_ledger_outlive_backup(self) -> None:
        with self.assertRaises(DisposalError):
            self.service(effective=False).purge(ARTIFACT, NOW)
        with self.assertRaises(DisposalError):
            self.service(delete_ledger_days=7).purge(ARTIFACT, NOW)

    def test_tombstone_precedes_purge_and_retry_is_idempotent(self) -> None:
        receipt = self.service().purge(ARTIFACT, NOW)
        self.assertEqual(1, receipt["removed_copy_count"])
        self.assertFalse((self.root / "evidence" / DIGEST).exists())
        events = self.inventory.read()
        self.assertEqual(["tombstone", "purge"], [item["event"] for item in events[-2:]])
        replay = self.service().purge(ARTIFACT, NOW)
        self.assertTrue(replay["idempotent"])

    def test_restore_is_not_ready_until_tombstone_is_reapplied(self) -> None:
        service = self.service()
        service.purge(ARTIFACT, NOW)
        (self.root / "backup").mkdir()
        (self.root / "backup" / DIGEST).write_bytes(b"synthetic-restored")
        self.assertFalse((self.root / "control" / "restore-ready.json").exists())
        receipt = service.reapply_after_restore(NOW)
        self.assertEqual("ready_after_tombstone_reconciliation", receipt["state"])
        self.assertFalse((self.root / "backup" / DIGEST).exists())
        self.assertTrue((self.root / "control" / "restore-ready.json").exists())

    def test_delete_ledger_tamper_is_detected(self) -> None:
        service = self.service()
        service.purge(ARTIFACT, NOW)
        path = self.root / "archive" / "delete-ledger.ndjson"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "SYNTHETIC-TEST-POLICY", "CHANGED-POLICY"), encoding="utf-8")
        with self.assertRaises(DisposalError):
            service.tombstones.read()


if __name__ == "__main__":
    unittest.main()
