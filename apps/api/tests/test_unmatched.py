"""FNC-SMB-004: movimientos sin cruce vigente y resumen del periodo, sin base."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid
from decimal import Decimal

from fincilia_api import reconciliation
from fincilia_api.reconciliation import (
    CandidateQueryError, list_unmatched, reconciliation_summary,
)


LEFT = str(uuid.uuid4())
RIGHT = str(uuid.uuid4())


class ScriptedCursor:
    """Cada `execute` consume el siguiente resultado del guion."""

    def __init__(self, connection: "ScriptedConnection") -> None:
        self.connection = connection
        self.rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple) -> None:
        self.connection.calls.append((statement, params))
        self.rows = self.connection.script.pop(0)

    def __iter__(self):
        return iter(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class ScriptedConnection:
    def __init__(self, *script: list[tuple]) -> None:
        self.script = list(script)
        self.calls: list[tuple] = []

    def cursor(self) -> ScriptedCursor:
        return ScriptedCursor(self)


def dataset(dataset_id: str, completeness: str = "verified") -> tuple:
    return (uuid.UUID(dataset_id), "published", completeness, "complete", 2)


def movement(dataset_id: str, *, open_candidate: bool = False) -> tuple:
    return (uuid.uuid4(), Decimal("150000.00"), "COP", "inflow", "Abono sintetico",
            "REF-1", dt.date(2026, 2, 14), "proposed", 2, uuid.UUID(dataset_id),
            uuid.uuid4(), open_candidate)


class UnmatchedTests(unittest.TestCase):
    def test_validation_happens_before_any_query(self) -> None:
        for kwargs in ({"offset": -1}, {"offset": 10_001}, {"limit": 0},
                       {"limit": 201}):
            with self.subTest(kwargs=kwargs):
                connection = ScriptedConnection()
                with self.assertRaises(CandidateQueryError):
                    list_unmatched(connection, left_dataset_id=LEFT,
                                   right_dataset_id=RIGHT, **kwargs)
                self.assertEqual([], connection.calls)
        with self.assertRaises(CandidateQueryError):
            list_unmatched(ScriptedConnection(), left_dataset_id="no-uuid",
                           right_dataset_id=RIGHT)
        with self.assertRaises(CandidateQueryError):
            list_unmatched(ScriptedConnection(), left_dataset_id=LEFT,
                           right_dataset_id=LEFT)

    def test_ineligible_pair_is_indistinguishable_from_foreign(self) -> None:
        connection = ScriptedConnection([dataset(LEFT), dataset(RIGHT, "partial")])
        with self.assertRaises(CandidateQueryError) as raised:
            list_unmatched(connection, left_dataset_id=LEFT, right_dataset_id=RIGHT)
        self.assertEqual("candidate-scope-unavailable", raised.exception.code)
        self.assertEqual(1, len(connection.calls))

    def test_page_excludes_active_confirmations_and_honours_reversals(self) -> None:
        rows = [movement(LEFT), movement(RIGHT, open_candidate=True), movement(RIGHT)]
        connection = ScriptedConnection(
            [dataset(LEFT), dataset(RIGHT)], [(3,)], rows)
        page = list_unmatched(connection, left_dataset_id=LEFT,
                              right_dataset_id=RIGHT, limit=2)
        self.assertEqual(3, page["total"])
        self.assertTrue(page["truncated"])
        self.assertEqual(["left", "right"], [item["side"] for item in page["items"]])
        self.assertEqual("150000.000000000000", page["items"][0]["amount"])
        self.assertTrue(page["items"][1]["has_open_candidate"])
        self.assertEqual("none", page["financial_effect"])
        statement = connection.calls[2][0]
        # Una reserva cuenta solo si su decision no tiene reversion (V0069).
        self.assertIn("match_confirmation_member", statement)
        self.assertIn("NOT EXISTS (SELECT 1 FROM fincilia.match_decision_reversal", statement)
        self.assertIn("AND NOT EXISTS (SELECT 1 FROM fincilia.match_confirmation_member",
                      " ".join(statement.split()))


class SummaryTests(unittest.TestCase):
    def test_counts_only_and_reversals_are_not_matched(self) -> None:
        connection = ScriptedConnection([(10, 4, 3)], [(2,)])
        summary = reconciliation_summary(
            connection, period_start=dt.date(2026, 2, 1),
            period_end=dt.date(2026, 2, 28))
        self.assertEqual({"eligible_movements": 10, "matched": 4, "pending": 3,
                          "to_review": 2},
                         {key: summary[key] for key in (
                             "eligible_movements", "matched", "pending", "to_review")})
        self.assertIn("match_decision_reversal", connection.calls[0][0])
        for value in summary.values():
            self.assertNotIsInstance(value, float)

    def test_period_is_bounded(self) -> None:
        with self.assertRaises(CandidateQueryError):
            reconciliation_summary(ScriptedConnection(),
                                   period_start=dt.date(2026, 3, 1),
                                   period_end=dt.date(2026, 2, 1))
        with self.assertRaises(CandidateQueryError):
            reconciliation_summary(ScriptedConnection(),
                                   period_start=dt.date(2025, 1, 1),
                                   period_end=dt.date(2026, 2, 1))

    def test_active_confirmation_predicate_is_shared(self) -> None:
        self.assertIn("match_decision_reversal", reconciliation.ACTIVE_CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
