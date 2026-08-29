from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .ledger import InventoryError, InventoryLedger


DIGEST = "a" * 64
ARTIFACT = "b" * 64
COMPANY = "c" * 64
OP1 = "1" * 64
OP2 = "2" * 64
NOW = "2026-08-29T12:00:00Z"


class InventoryLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = InventoryLedger(self.root / "inventory.ndjson")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def intake(self) -> dict:
        return self.ledger.append(
            operation_ref=OP1, artifact_ref=ARTIFACT, company_ref=COMPANY,
            event="intake", content_sha256=DIGEST,
            created_refs=[f"quarantine/{DIGEST}"], removed_refs=[],
            reason_code="synthetic_intake", occurred_at=NOW,
        )

    def test_chain_and_minimized_snapshot(self) -> None:
        first = self.intake()
        second = self.ledger.append(
            operation_ref=OP2, artifact_ref=ARTIFACT, company_ref=COMPANY,
            event="promotion", content_sha256=DIGEST,
            created_refs=[f"evidence/{DIGEST}"],
            removed_refs=[f"quarantine/{DIGEST}"],
            reason_code="content_inspected", occurred_at=NOW,
        )
        self.assertEqual(first["event_sha256"], second["previous_event_sha256"])
        snapshot = self.ledger.snapshot()
        self.assertEqual("accepted", snapshot.artifact_states[ARTIFACT])
        self.assertEqual((f"evidence/{DIGEST}",), snapshot.active_refs[ARTIFACT])
        rendered = self.ledger.path.read_text(encoding="utf-8")
        for forbidden in ("archivo.csv", "correo@ejemplo.test", "Pago proveedor"):
            self.assertNotIn(forbidden, rendered)

    def test_tamper_is_detected(self) -> None:
        self.intake()
        line = json.loads(self.ledger.path.read_text(encoding="utf-8"))
        line["reason_code"] = "silently_changed"
        self.ledger.path.write_text(json.dumps(line) + "\n", encoding="utf-8")
        with self.assertRaises(InventoryError):
            self.ledger.read()

    def test_transition_and_unknown_removal_fail_closed(self) -> None:
        with self.assertRaises(InventoryError):
            self.ledger.append(
                operation_ref=OP1, artifact_ref=ARTIFACT, company_ref=COMPANY,
                event="promotion", content_sha256=DIGEST,
                created_refs=[], removed_refs=[], reason_code="invalid_transition",
                occurred_at=NOW,
            )
        self.intake()
        with self.assertRaises(InventoryError):
            self.ledger.append(
                operation_ref=OP2, artifact_ref=ARTIFACT, company_ref=COMPANY,
                event="promotion", content_sha256=DIGEST,
                created_refs=[f"evidence/{DIGEST}"],
                removed_refs=[f"scratch/{DIGEST}"],
                reason_code="unknown_copy", occurred_at=NOW,
            )

    def test_operation_is_idempotent_but_divergence_is_not(self) -> None:
        first = self.intake()
        replay = self.intake()
        self.assertEqual(first, replay)
        with self.assertRaises(InventoryError):
            self.ledger.append(
                operation_ref=OP1, artifact_ref="d" * 64, company_ref=COMPANY,
                event="intake", content_sha256=DIGEST,
                created_refs=[f"quarantine/{DIGEST}"], removed_refs=[],
                reason_code="synthetic_intake", occurred_at=NOW,
            )

    def test_reconcile_detects_missing_and_untracked_objects(self) -> None:
        self.intake()
        (self.root / "quarantine").mkdir()
        self.assertEqual([f"quarantine/{DIGEST}"], self.ledger.reconcile(self.root))
        (self.root / "quarantine" / DIGEST).write_bytes(b"synthetic")
        (self.root / "scratch").mkdir()
        (self.root / "scratch" / ("d" * 64)).write_bytes(b"synthetic")
        self.assertEqual([f"scratch/{'d' * 64}"], self.ledger.reconcile(self.root))


if __name__ == "__main__":
    unittest.main()
