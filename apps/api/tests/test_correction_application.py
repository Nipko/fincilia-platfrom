"""Pruebas puras de FNC-CLN-002."""

from __future__ import annotations

import datetime as dt
import unittest
from decimal import Decimal

from fincilia_api.correction_application import (
    ApplicationError,
    ApprovedOverlay,
    _fingerprint,
    _validate_dates,
    overlay_set_digest,
)
from fincilia_contracts.release import digest_of
from fincilia_api.corrections import complete_lineage_fields


def approved(identifier: str, *, field: str = "amount",
             digest: str = "b" * 64) -> ApprovedOverlay:
    return ApprovedOverlay(
        overlay_id=identifier, movement_id="movement", source_record_id="source",
        field=field, expected_digest="a" * 64, proposed_value="2.000000000000",
        proposed_digest=digest, sequence=1, reason_code="source_correction",
        created_by="author", reviewer_id="reviewer",
        reviewed_at=dt.datetime(2026, 8, 25, tzinfo=dt.timezone.utc))


class CorrectionApplicationTests(unittest.TestCase):
    def test_only_a_complete_ordered_lineage_path_is_applicable(self) -> None:
        stages = (
            "artifact_version", "raw_locator", "extracted_field",
            "transformed_value", "source_record_field", "financial_fact_field",
        )
        complete = [("amount", index, stage)
                    for index, stage in enumerate(stages, start=1)]
        incomplete = [("currency", index, stage)
                      for index, stage in enumerate(stages[:-1], start=1)]
        unknown = [("description", index, stage)
                   for index, stage in enumerate(stages, start=1)]
        self.assertEqual(frozenset({"amount"}),
                         complete_lineage_fields(complete + incomplete + unknown))

    def test_duplicate_or_misordered_stage_is_not_applicable(self) -> None:
        stages = (
            "artifact_version", "raw_locator", "extracted_field",
            "transformed_value", "source_record_field", "financial_fact_field",
        )
        rows = [("amount", index, stage)
                for index, stage in enumerate(stages, start=1)]
        duplicated = rows + [("amount", 6, "financial_fact_field")]
        wrong = rows[:-1] + [("amount", 6, "source_record_field")]
        self.assertEqual(frozenset(), complete_lineage_fields(duplicated))
        self.assertEqual(frozenset(), complete_lineage_fields(wrong))

    def test_overlay_set_digest_is_order_independent_and_value_free(self) -> None:
        first = approved("00000000-0000-0000-0000-000000000001")
        second = approved("00000000-0000-0000-0000-000000000002",
                          field="currency", digest="c" * 64)
        self.assertEqual(overlay_set_digest([first, second]),
                         overlay_set_digest([second, first]))
        self.assertNotIn("2.000000000000", str(first.manifest_item()))

    def test_overlay_set_digest_bites_on_identity_field_and_digest(self) -> None:
        base = overlay_set_digest([approved("00000000-0000-0000-0000-000000000001")])
        changes = (
            approved("00000000-0000-0000-0000-000000000002"),
            approved("00000000-0000-0000-0000-000000000001", field="currency"),
            approved("00000000-0000-0000-0000-000000000001", digest="c" * 64),
        )
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertNotEqual(base, overlay_set_digest([changed]))

    def test_fingerprint_is_exact_and_not_a_uniqueness_decision(self) -> None:
        movement = {
            "financial_account_id": "account", "amount": Decimal("1.20"),
            "currency_code": "COP", "direction": "outflow",
            "occurred_on": dt.date(2026, 8, 25),
            "reference_normalised": "REF-1",
        }
        expected = digest_of({
            "account": "account", "company": "company",
            "amount": "1.200000000000", "currency": "COP",
            "direction": "outflow", "occurred_on": "2026-08-25",
            "reference": "REF-1",
        })
        self.assertEqual(expected, _fingerprint("company", movement))
        changed = dict(movement, amount=Decimal("1.21"))
        self.assertNotEqual(expected, _fingerprint("company", changed))

    def test_date_order_fails_closed(self) -> None:
        valid = {
            "occurred_on": dt.date(2026, 8, 20),
            "posted_on": dt.date(2026, 8, 21),
            "value_date": None,
        }
        _validate_dates(valid)
        for field in ("posted_on", "value_date"):
            invalid = dict(valid, **{field: dt.date(2026, 8, 19)})
            with self.subTest(field=field), self.assertRaises(ApplicationError):
                _validate_dates(invalid)


if __name__ == "__main__":
    unittest.main()
