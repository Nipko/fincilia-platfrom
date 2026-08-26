"""Pruebas puras del contrato digest-only FNC-CLS-005."""

from __future__ import annotations

import copy
import unittest

from fincilia_api.close_review import (
    CloseReviewError,
    MANIFEST_SCHEMA_VERSION,
    _canonical_json,
    _date,
    _digest,
    _key,
    _uuid,
    build_manifest,
)


PERIOD = {
    "period_start": "2026-07-01",
    "period_end": "2026-07-31",
    "status": "blocked",
    "controls": [
        {"code": "quality_alerts", "state": "blocked", "count": 1,
         "detail": "Texto mutable que no se firma."},
        {"code": "expected_sources", "state": "pass", "count": 1,
         "detail": "Otra explicacion mutable."},
    ],
    "sources": [{
        "expectation_id": "11111111-1111-4111-8111-111111111111",
        "data_source_id": "22222222-2222-4222-8222-222222222222",
        "source_name": "Nombre aportado por usuario",
        "financial_account_id": "33333333-3333-4333-8333-333333333333",
        "expectation_state": "satisfied",
        "dataset_version_id": "44444444-4444-4444-8444-444444444444",
        "dataset_state": "published",
        "completeness_state": "verified",
        "lineage_state": "complete",
        "rejected_count": 0,
        "movement_count": 2,
        "prepared_at": "2026-08-01T00:00:00+00:00",
        "amount": "999999.99",
        "currency_code": "COP",
    }],
    "account_reconciliations": [{
        "financial_account_id": "33333333-3333-4333-8333-333333333333",
        "account_name": "Cuenta que no se firma",
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


class CloseReviewManifestTests(unittest.TestCase):
    def test_manifest_is_digest_only_and_has_a_closed_envelope(self) -> None:
        manifest = build_manifest(PERIOD)
        self.assertEqual(
            {"schema_version", "diagnostic_status", "controls", "sources", "accounts"},
            set(manifest))
        self.assertEqual(MANIFEST_SCHEMA_VERSION, manifest["schema_version"])
        self.assertFalse({"amount", "currency_code", "source_name", "account_name",
                          "detail", "prepared_at"} & set(all_keys(manifest)))
        self.assertNotIn("Nombre aportado", _canonical_json(manifest))
        self.assertNotIn("999999.99", _canonical_json(manifest))

    def test_manifest_order_does_not_change_the_digest(self) -> None:
        left = copy.deepcopy(PERIOD)
        right = copy.deepcopy(PERIOD)
        right["controls"].reverse()
        self.assertEqual(_digest(build_manifest(left)), _digest(build_manifest(right)))

    def test_material_change_changes_the_digest(self) -> None:
        changed = copy.deepcopy(PERIOD)
        changed["controls"][0]["count"] = 2
        self.assertNotEqual(
            _digest(build_manifest(PERIOD)), _digest(build_manifest(changed)))

    def test_mutable_explanation_does_not_change_the_digest(self) -> None:
        changed = copy.deepcopy(PERIOD)
        changed["controls"][0]["detail"] = "Una traduccion distinta."
        self.assertEqual(
            _digest(build_manifest(PERIOD)), _digest(build_manifest(changed)))

    def test_canonical_json_is_stable_and_compact(self) -> None:
        self.assertEqual('{"a":2,"b":1}', _canonical_json({"b": 1, "a": 2}))

    def test_idempotency_key_is_closed(self) -> None:
        self.assertEqual("cls005-command-0001", _key("cls005-command-0001"))
        for invalid in ("short", "x" * 129, "unsafe key with spaces"):
            with self.subTest(invalid=invalid), self.assertRaises(CloseReviewError):
                _key(invalid)

    def test_uuid_and_date_are_validated_without_echoing_input(self) -> None:
        with self.assertRaises(CloseReviewError) as uuid_error:
            _uuid("valor-secreto", field="packet_id")
        self.assertNotIn("valor-secreto", uuid_error.exception.detail)
        with self.assertRaises(CloseReviewError) as date_error:
            _date("no-es-fecha", field="period_start")
        self.assertNotIn("no-es-fecha", date_error.exception.detail)

    def test_status_never_implies_close_authority(self) -> None:
        manifest = build_manifest({**PERIOD, "status": "ready_for_review"})
        self.assertEqual("ready_for_review", manifest["diagnostic_status"])
        self.assertNotIn("close_ready", manifest)
        self.assertNotIn("can_execute_close", manifest)


if __name__ == "__main__":
    unittest.main()
