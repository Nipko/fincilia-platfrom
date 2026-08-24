"""Pruebas puras del explorador read-only de candidatos FNC-REC-001."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid
from decimal import Decimal

from fincilia_api.reconciliation import (
    CandidateQuery,
    CandidateQueryError,
    ReviewQueueQuery,
    ReviewCommandError,
    RULES,
    candidate_from_row,
    decide_review,
    explore_candidates,
    list_review_queue,
    propose_review,
)


LEFT = str(uuid.uuid4())
RIGHT = str(uuid.uuid4())


def dataset_row(dataset_id: str, *, state: str = "validated",
                completeness: str = "verified",
                lineage: str = "complete") -> tuple:
    return (dataset_id, state, completeness, lineage, 3)


def candidate_row(*, amount: str = "1234.56", currency: str = "COP",
                  left_direction: str = "outflow",
                  right_direction: str = "inflow",
                  reference_match: bool = True,
                  left_ordinal: int = 1, right_ordinal: int = 2) -> tuple:
    left = (
        uuid.uuid4(), Decimal(amount), currency, left_direction,
        "Pago sintético", "REF-01", dt.date(2026, 2, 13), "proposed",
        left_ordinal,
    )
    right = (
        uuid.uuid4(), Decimal(amount), currency, right_direction,
        "Abono sintético", "REF-01", dt.date(2026, 2, 14), "confirmed",
        right_ordinal,
    )
    return left + right + (1, reference_match)


class FakeCursor:
    def __init__(self, rows: list[tuple], calls: list[tuple]) -> None:
        self.rows = rows
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple) -> None:
        self.calls.append((statement, params))

    def __iter__(self):
        return iter(self.rows)


class FakeConnection:
    def __init__(self, *result_sets: list[tuple]) -> None:
        self.result_sets = list(result_sets)
        self.calls: list[tuple] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.result_sets.pop(0), self.calls)


class CandidateQueryTests(unittest.TestCase):
    def test_query_is_bounded_and_requires_two_distinct_datasets(self) -> None:
        invalid = (
            CandidateQuery(LEFT, LEFT),
            CandidateQuery(LEFT, RIGHT, max_days=-1),
            CandidateQuery(LEFT, RIGHT, max_days=32),
            CandidateQuery(LEFT, RIGHT, offset=-1),
            CandidateQuery(LEFT, RIGHT, offset=10_001),
            CandidateQuery(LEFT, RIGHT, limit=0),
            CandidateQuery(LEFT, RIGHT, limit=201),
        )
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(CandidateQueryError):
                query.validated()

    def test_money_is_fixed_point_string_and_reference_only_explains(self) -> None:
        candidate = candidate_from_row(candidate_row(amount="1.2"))
        self.assertEqual("1.200000000000", candidate["left"]["amount"])
        self.assertEqual("1.200000000000", candidate["right"]["amount"])
        self.assertEqual(list(RULES) + ["same_normalised_reference"],
                         candidate["signals"])
        self.assertNotIn("score", candidate)
        self.assertNotIn("confidence", candidate)

    def test_reference_difference_does_not_exclude_a_candidate(self) -> None:
        candidate = candidate_from_row(candidate_row(reference_match=False))
        self.assertEqual(list(RULES), candidate["signals"])

    def test_exploration_is_paginated_deterministic_and_candidate_only(self) -> None:
        rows = [candidate_row(left_ordinal=index, right_ordinal=index + 10)
                for index in range(1, 4)]
        connection = FakeConnection(
            [dataset_row(LEFT), dataset_row(RIGHT)], rows)
        result = explore_candidates(
            connection, left_dataset_id=LEFT, right_dataset_id=RIGHT,
            max_days=7, offset=4, limit=2)

        self.assertEqual("candidate_only", result["mode"])
        self.assertFalse(result["proves_balance_reconciliation"])
        self.assertTrue(result["truncated"])
        self.assertEqual(2, len(result["candidates"]))
        statement, params = connection.calls[1]
        self.assertIn("LIMIT %s OFFSET %s", statement)
        self.assertIn("ORDER BY reference_match DESC", statement)
        self.assertEqual((RIGHT, 7, LEFT, 3, 4), params)

    def test_missing_foreign_or_ineligible_dataset_is_neutral(self) -> None:
        cases = (
            [dataset_row(LEFT)],
            [dataset_row(LEFT), dataset_row(RIGHT, state="draft")],
            [dataset_row(LEFT), dataset_row(RIGHT, completeness="mismatch")],
            [dataset_row(LEFT), dataset_row(RIGHT, lineage="invalidated")],
        )
        for found in cases:
            with self.subTest(found=found):
                connection = FakeConnection(found)
                with self.assertRaises(CandidateQueryError) as raised:
                    explore_candidates(
                        connection, left_dataset_id=LEFT,
                        right_dataset_id=RIGHT)
                self.assertEqual("candidate-scope-unavailable",
                                 raised.exception.code)

    def test_many_to_many_pairs_are_not_collapsed(self) -> None:
        repeated_left = uuid.uuid4()
        first = list(candidate_row())
        second = list(candidate_row(right_ordinal=3))
        first[0] = repeated_left
        second[0] = repeated_left
        connection = FakeConnection(
            [dataset_row(LEFT), dataset_row(RIGHT)],
            [tuple(first), tuple(second)])
        result = explore_candidates(
            connection, left_dataset_id=LEFT, right_dataset_id=RIGHT)
        self.assertEqual(2, len(result["candidates"]))
        self.assertEqual(result["candidates"][0]["left"]["movement_id"],
                         result["candidates"][1]["left"]["movement_id"])

    def test_review_rejects_unsafe_idempotency_key_before_database_work(self) -> None:
        connection = FakeConnection()
        with self.assertRaises(ReviewCommandError) as raised:
            propose_review(
                connection, company_id=LEFT, actor_id=RIGHT,
                idempotency_key="short", left_dataset_id=LEFT,
                right_dataset_id=RIGHT, left_movement_id=LEFT,
                right_movement_id=RIGHT, max_days=3)
        self.assertEqual("idempotency-key-invalid", raised.exception.code)
        self.assertEqual([], connection.calls)

    def test_review_queue_filter_and_pagination_are_closed(self) -> None:
        for query in (
            ReviewQueueQuery(status="pending"),
            ReviewQueueQuery(offset=-1),
            ReviewQueueQuery(offset=10_001),
            ReviewQueueQuery(limit=0),
            ReviewQueueQuery(limit=101),
        ):
            with self.subTest(query=query), self.assertRaises(ReviewCommandError):
                query.validated()

    def test_review_queue_is_stable_bounded_and_non_financial(self) -> None:
        now = dt.datetime(2026, 8, 24, 12, tzinfo=dt.timezone.utc)
        row = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "fnc-rec-exact-v1",
            list(RULES), 3, 1, uuid.uuid4(), "Ada Preparadora", now,
            None, None, None, None, None, None, uuid.uuid4(), uuid.uuid4(),
        )
        connection = FakeConnection([row, row])
        result = list_review_queue(
            connection, status="open", offset=4, limit=1)

        self.assertTrue(result["truncated"])
        self.assertEqual("none", result["financial_effect"])
        self.assertFalse(result["proves_balance_reconciliation"])
        self.assertEqual(1, len(result["items"]))
        self.assertIn("d.decision_id IS NULL", connection.calls[0][0])
        self.assertIn("c.proposed_at ASC", connection.calls[0][0])
        self.assertEqual((2, 4), connection.calls[0][1])
        self.assertNotIn("amount", result["items"][0])

    def test_review_rejects_non_uuid_before_database_work(self) -> None:
        connection = FakeConnection()
        with self.assertRaises(ReviewCommandError) as raised:
            propose_review(
                connection, company_id=LEFT, actor_id=RIGHT,
                idempotency_key="rec002-safe-key-0001",
                left_dataset_id="not-a-uuid", right_dataset_id=RIGHT,
                left_movement_id=LEFT, right_movement_id=RIGHT, max_days=3)
        self.assertEqual("review-request-invalid", raised.exception.code)
        self.assertEqual([], connection.calls)

    def test_decision_reason_vocabulary_is_closed(self) -> None:
        connection = FakeConnection()
        cases = (
            ("confirmed", "different_event"),
            ("rejected", "documented_transfer"),
            ("automatic", "reference_supported"),
        )
        for decision, reason in cases:
            with self.subTest(decision=decision, reason=reason):
                with self.assertRaises(ReviewCommandError) as raised:
                    decide_review(
                        connection, company_id=LEFT, actor_id=RIGHT,
                        idempotency_key="rec002-safe-key-0002",
                        candidate_id=LEFT, decision=decision,
                        reason_code=reason)
                self.assertEqual("review-decision-invalid", raised.exception.code)
        self.assertEqual([], connection.calls)


if __name__ == "__main__":
    unittest.main()
