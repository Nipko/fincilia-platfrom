"""Contrato puro del centro de calidad; PostgreSQL se cubre en db/tests."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid

from fincilia_api.quality import (Finding, QualityError, QualityQuery, REASONS,
                                  RULE_VERSION, RULES, _issue)


class QualityContractTests(unittest.TestCase):
    def test_rule_set_is_closed_and_versioned(self) -> None:
        self.assertEqual("quality-rules-v1", RULE_VERSION)
        self.assertEqual(8, len(RULES))
        self.assertNotIn("fraud", " ".join(RULES))

    def test_finding_key_is_deterministic_without_becoming_identity(self) -> None:
        finding = Finding(
            "duplicate_fingerprint", "dataset", str(uuid.uuid4()), "high",
            "transient-source-discriminator", 2)
        self.assertEqual(finding.issue_key, finding.issue_key)
        self.assertEqual(64, len(finding.issue_key))
        self.assertNotIn("transient", finding.issue_key)

    def test_rule_and_scope_change_the_key(self) -> None:
        scope = str(uuid.uuid4())
        first = Finding("duplicate_fingerprint", "dataset", scope, "high", "a")
        second = Finding(
            "reference_amount_conflict", "dataset", scope, "warning", "a")
        third = Finding("duplicate_fingerprint", "dataset", scope, "high", "b")
        self.assertEqual(3, len({first.issue_key, second.issue_key, third.issue_key}))

    def test_every_filter_is_fail_closed(self) -> None:
        invalid = (
            {"status": "pending"}, {"severity": "critical"},
            {"rule": "anything"}, {"offset": -1}, {"offset": 10_001},
            {"limit": 0}, {"limit": 101},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(QualityError):
                QualityQuery(**values).validated()

    def test_supported_filters_validate(self) -> None:
        self.assertEqual(
            QualityQuery(status="all", severity="warning",
                         rule="lineage_invalidated", offset=10, limit=100),
            QualityQuery(status="all", severity="warning",
                         rule="lineage_invalidated", offset=10,
                         limit=100).validated())

    def test_reason_sets_keep_acknowledgement_and_terminal_actions_distinct(self) -> None:
        self.assertEqual(frozenset(("investigate",)), REASONS["acknowledged"])
        self.assertTrue(REASONS["resolved"].isdisjoint(REASONS["dismissed"]))
        self.assertTrue(REASONS["acknowledged"].isdisjoint(REASONS["resolved"]))

    def test_public_issue_never_contains_money_or_source_values(self) -> None:
        now = dt.datetime(2026, 8, 24, tzinfo=dt.timezone.utc)
        row = (
            uuid.uuid4(), "amount_outlier_10x_median", RULE_VERSION,
            "movement", uuid.uuid4(), "warning", "open", 1,
            None, None, None, None, None, now, now, now,
        )
        payload = _issue(row)
        self.assertEqual("none", payload["financial_effect"])
        self.assertFalse(payload["proves_fraud"])
        forbidden = {"amount", "median", "description", "reference", "fingerprint"}
        self.assertTrue(forbidden.isdisjoint(payload))


if __name__ == "__main__":
    unittest.main()
