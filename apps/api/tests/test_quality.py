"""Contrato puro del centro de calidad; PostgreSQL se cubre en db/tests."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid

from fincilia_api.quality import (BASE_RULE_VERSION, RISK_RULE_VERSION, Finding,
                                  QualityError, QualityQuery, REASONS,
                                  RULE_VERSION, RULES, _compound_findings, _issue)


class QualityContractTests(unittest.TestCase):
    def test_rule_set_is_closed_and_versioned(self) -> None:
        self.assertEqual("quality-rules-v2", RULE_VERSION)
        self.assertEqual(13, len(RULES))
        self.assertNotIn("fraud", " ".join(RULES))

    def test_existing_keys_keep_their_version_when_suite_grows(self) -> None:
        self.assertEqual(
            BASE_RULE_VERSION,
            Finding("duplicate_fingerprint", "movement", "m", "high", "m").rule_version)
        self.assertEqual(
            RISK_RULE_VERSION,
            Finding("rapid_reversal_pair", "movement", "m", "warning", "m").rule_version)

    def test_compound_signal_requires_two_distinct_indicators(self) -> None:
        only_one = Finding(
            "rapid_reversal_pair", "movement", "movement-a", "warning", "movement-a")
        second = Finding(
            "same_day_same_amount_burst", "movement", "movement-a", "warning", "movement-a")
        compound, truncated = _compound_findings({
            only_one.rule_code: [only_one], second.rule_code: [second]})
        self.assertFalse(truncated)
        self.assertEqual(1, len(compound))
        self.assertEqual("multiple_risk_indicators", compound[0].rule_code)
        self.assertEqual("high", compound[0].severity)
        self.assertEqual(2, compound[0].occurrence_count)
        self.assertEqual(
            [], _compound_findings({only_one.rule_code: [only_one]})[0])

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
