"""Reglas puras de la superficie diagnostica FNC-CLS-003."""

from __future__ import annotations

import unittest
import uuid

from fincilia_api.balance_reconciliation import (
    ReconciliationError,
    _bounded,
    _control_specs,
    _uuid,
    create_item,
    create_statement,
    decide_item,
)


class NoDatabase:
    def cursor(self):  # pragma: no cover - usarla seria el fallo
        raise AssertionError("invalid input reached the database")


def evidence(**overrides):
    base = {
        "expected_controls": {"controls": ["provenance_integrity"]},
        "record_count": 3,
        "currency_code": "COP",
        "distinct_accounts": 1,
        "distinct_currencies": 1,
        "account_matches": True,
        "currency_matches": True,
    }
    return {**base, **overrides}


class BalanceReconciliationRulesTests(unittest.TestCase):
    def test_identifiers_and_limits_are_bounded_before_sql(self) -> None:
        self.assertEqual(str(uuid.UUID(int=1)), _uuid(str(uuid.UUID(int=1))))
        self.assertEqual(100, _bounded(100))
        for invalid in (True, 0, 101, "many"):
            with self.subTest(invalid=invalid), self.assertRaises(ReconciliationError):
                _bounded(invalid)  # type: ignore[arg-type]
        with self.assertRaises(ReconciliationError):
            _uuid("not-an-identifier")

    def test_provenance_is_a_positive_versioned_control(self) -> None:
        result = _control_specs(evidence())
        self.assertEqual("provenance_integrity", result[0]["type"])
        self.assertEqual("match", result[0]["outcome"])
        self.assertEqual({"value": True}, result[0]["observed"])

    def test_missing_expected_count_is_unknown_not_zero(self) -> None:
        result = _control_specs(evidence(expected_controls={}))
        count = next(item for item in result if item["type"] == "record_count")
        self.assertEqual("unknown", count["outcome"])
        self.assertIn("does not contain", count["reason"])

    def test_record_count_and_currency_mismatches_are_explicit(self) -> None:
        controls = _control_specs(evidence(
            expected_controls={
                "controls": ["record_count", "currency_consistency"],
                "record_count": 9,
            },
            currency_matches=False,
        ))
        self.assertEqual(["mismatch", "mismatch"],
                         [item["outcome"] for item in controls])

    def test_statement_requires_a_nonempty_unique_assessment_set(self) -> None:
        identifier = str(uuid.uuid4())
        for values in ([], [identifier, identifier]):
            with self.subTest(values=values), self.assertRaises(ReconciliationError):
                create_statement(
                    NoDatabase(), company_id=str(uuid.uuid4()),
                    subject_id=str(uuid.uuid4()), bank_balance_id=str(uuid.uuid4()),
                    books_balance_id=str(uuid.uuid4()), assessment_ids=values)

    def test_item_money_never_accepts_float_or_nonpositive_text(self) -> None:
        common = {
            "company_id": str(uuid.uuid4()), "subject_id": str(uuid.uuid4()),
            "statement_root_id": str(uuid.uuid4()),
            "adjustment_side": "add_to_bank", "reason_code": "documented_timing",
            "evidence_source_record_ids": [str(uuid.uuid4())],
        }
        for amount in (1.5, "0", "-1", "NaN"):
            with self.subTest(amount=amount), self.assertRaises(ReconciliationError):
                create_item(NoDatabase(), amount=amount, **common)  # type: ignore[arg-type]

    def test_item_vocabulary_is_closed(self) -> None:
        with self.assertRaises(ReconciliationError):
            create_item(
                NoDatabase(), company_id=str(uuid.uuid4()),
                subject_id=str(uuid.uuid4()), statement_root_id=str(uuid.uuid4()),
                amount="1.00", adjustment_side="change_books",
                reason_code="documented_timing",
                evidence_source_record_ids=[str(uuid.uuid4())])

    def test_decision_vocabulary_is_closed_before_reading_state(self) -> None:
        with self.assertRaises(ReconciliationError):
            decide_item(
                NoDatabase(), company_id=str(uuid.uuid4()),
                subject_id=str(uuid.uuid4()), item_root_id=str(uuid.uuid4()),
                decision="approved")


if __name__ == "__main__":
    unittest.main()
