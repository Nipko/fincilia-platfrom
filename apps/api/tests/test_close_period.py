"""Pruebas puras del contrato de cierre FNC-CLS-006."""

from __future__ import annotations

import copy
import datetime as dt
import unittest

from fincilia_api.close_period import (
    ClosePeriodError,
    SNAPSHOT_SCHEMA_VERSION,
    _canonical_json,
    _digest,
    _key,
    _row,
    _uuid,
    build_snapshot,
)
from fincilia_api.close_review import build_manifest


PACKET_ID = "71111111-1111-4111-8111-111111111111"
DIGEST = "a" * 64
PERIOD = {
    "period_start": "2026-07-01",
    "period_end": "2026-07-31",
    "status": "blocked",
    "controls": [
        {"code": "quality_alerts", "state": "blocked", "count": 1},
        {"code": "expected_sources", "state": "pass", "count": 1},
    ],
    "sources": [{
        "expectation_id": "11111111-1111-4111-8111-111111111111",
        "data_source_id": "22222222-2222-4222-8222-222222222222",
        "financial_account_id": "33333333-3333-4333-8333-333333333333",
        "expectation_state": "satisfied",
        "dataset_version_id": "44444444-4444-4444-8444-444444444444",
        "dataset_state": "published",
        "completeness_state": "verified",
        "lineage_state": "complete",
        "rejected_count": 0,
        "movement_count": 2,
    }],
    "account_reconciliations": [{
        "financial_account_id": "33333333-3333-4333-8333-333333333333",
        "source_count": 1,
        "assessment_count": 1,
        "statement_root_id": "55555555-5555-4555-8555-555555555555",
        "statement_id": "66666666-6666-4666-8666-666666666666",
        "statement_version": 2,
        "statement_state": "balanced",
        "statement_lineage_state": "complete",
        "coverage_state": "covered",
    }],
}


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


class AccountingPeriodContractTests(unittest.TestCase):
    def test_snapshot_is_canonical_digest_only_and_versioned(self) -> None:
        manifest = build_manifest({**PERIOD, "status": "ready_for_review"})
        packet = {"packet_id": PACKET_ID, "version": 3,
                  "manifest_digest": DIGEST}
        snapshot = build_snapshot(packet, manifest)
        self.assertEqual(SNAPSHOT_SCHEMA_VERSION, snapshot["schema_version"])
        self.assertEqual(3, snapshot["packet_version"])
        self.assertEqual(DIGEST, snapshot["manifest_digest"])
        self.assertFalse({"amount", "currency_code", "source_name", "account_name",
                          "detail", "value"} & set(all_keys(snapshot)))
        self.assertEqual(64, len(_digest(snapshot)))

    def test_snapshot_order_is_stable_but_material_state_changes_digest(self) -> None:
        manifest = build_manifest({**PERIOD, "status": "ready_for_review"})
        packet = {"packet_id": PACKET_ID, "version": 1,
                  "manifest_digest": DIGEST}
        left = build_snapshot(packet, manifest)
        reordered = copy.deepcopy(manifest)
        reordered["controls"].reverse()
        # build_manifest es quien canoniza el orden; una llamada equivalente
        # conserva la huella aunque el diagnostico original cambie de orden.
        right = build_snapshot(packet, build_manifest({
            **PERIOD, "status": "ready_for_review",
            "controls": list(reversed(PERIOD["controls"])),
        }))
        self.assertEqual(_digest(left), _digest(right))
        changed = copy.deepcopy(left)
        changed["controls"][0]["count"] += 1
        self.assertNotEqual(_digest(left), _digest(changed))
        self.assertNotEqual(_canonical_json(left), _canonical_json(changed))

    def test_reopen_status_never_erases_the_close(self) -> None:
        base = (
            PACKET_ID, dt.date(2026, 7, 1), dt.date(2026, 7, 31), 2,
            "81111111-1111-4111-8111-111111111111", DIGEST,
            SNAPSHOT_SCHEMA_VERSION, {}, "b" * 64,
            "21111111-1111-4111-8111-111111111111", "Revisor",
            dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc),
            "31111111-1111-4111-8111-111111111111", "late_evidence",
            "Evidencia tardia documentada", "41111111-1111-4111-8111-111111111111",
            "Preparador", dt.datetime(2026, 8, 2, tzinfo=dt.timezone.utc),
            "51111111-1111-4111-8111-111111111111", "approved",
            "documented_basis_confirmed", "61111111-1111-4111-8111-111111111111",
            "Aprobador", dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc),
        )
        result = _row(base)
        self.assertEqual("reopened", result["status"])
        self.assertEqual(PACKET_ID, result["close_id"])
        self.assertEqual("approved", result["reopen_request"]["decision"])

    def test_identifiers_and_idempotency_fail_without_echoing_input(self) -> None:
        with self.assertRaises(ClosePeriodError) as raised:
            _uuid("valor-protegido", field="close_id")
        self.assertNotIn("valor-protegido", raised.exception.detail)
        for invalid in ("short", "unsafe key", "x" * 129):
            with self.subTest(invalid=invalid), self.assertRaises(ClosePeriodError):
                _key(invalid)


if __name__ == "__main__":
    unittest.main()
