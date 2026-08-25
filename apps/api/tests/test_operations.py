"""Pruebas puras del centro operativo FNC-OPS-001."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid

from fincilia_api.operations import (
    OperationsQuery,
    OperationsQueryError,
    classify_state,
    decode_cursor,
    encode_cursor,
    list_operational_periods,
)


TODAY = dt.date(2026, 8, 24)
SUBJECT = str(uuid.uuid4())


class FakeCursor:
    def __init__(self, result_sets: list[list[tuple]], calls: list[tuple]) -> None:
        self.result_sets = result_sets
        self.rows: list[tuple] = []
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple) -> None:
        self.calls.append((statement, params))
        self.rows = self.result_sets.pop(0)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class FakeConnection:
    def __init__(self, *result_sets: list[tuple]) -> None:
        self.result_sets = list(result_sets)
        self.calls: list[tuple] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.result_sets, self.calls)


def item_row(*, due_on: dt.date, state: str = "pending",
             reminder: str = "due_soon", responsible: str = SUBJECT) -> tuple:
    return (
        uuid.uuid4(), uuid.uuid4(), "Banco sintetico",
        dt.date(2026, 8, 1), dt.date(2026, 8, 31), due_on,
        due_on + dt.timedelta(days=3), state, None, None,
        uuid.UUID(responsible), "Ana Demo", True, reminder, 0,
        (due_on - TODAY).days,
    )


class ClassificationTests(unittest.TestCase):
    def test_every_boundary_has_an_explicit_non_financial_state(self) -> None:
        cases = (
            ("satisfied", TODAY, TODAY, "satisfied"),
            ("waived", TODAY, TODAY, "waived"),
            ("pending", TODAY - dt.timedelta(days=5),
             TODAY - dt.timedelta(days=1), "overdue"),
            ("pending", TODAY - dt.timedelta(days=1), TODAY, "in_grace"),
            ("pending", TODAY, TODAY + dt.timedelta(days=3), "due_today"),
            ("pending", TODAY + dt.timedelta(days=7),
             TODAY + dt.timedelta(days=9), "due_soon"),
            ("pending", TODAY + dt.timedelta(days=8),
             TODAY + dt.timedelta(days=9), "upcoming"),
        )
        for stored, due, late, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, classify_state(
                    stored_state=stored, due_on=due, late_after=late,
                    today=TODAY))

    def test_query_rejects_open_ended_filters_limits_and_cursors(self) -> None:
        invalid = (
            OperationsQuery(status="fraud"),
            OperationsQuery(limit=0),
            OperationsQuery(limit=51),
            OperationsQuery(cursor="not-a-cursor"),
        )
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(OperationsQueryError):
                query.validated()

    def test_cursor_is_stable_and_contains_only_date_and_opaque_id(self) -> None:
        identifier = str(uuid.uuid4())
        encoded = encode_cursor(TODAY, identifier)
        self.assertEqual((TODAY, identifier), decode_cursor(encoded))
        self.assertNotIn("2026-08-24", encoded)


class ProjectionTests(unittest.TestCase):
    def test_projection_is_bounded_keyset_and_carries_no_money(self) -> None:
        first = item_row(due_on=TODAY + dt.timedelta(days=1))
        second = item_row(due_on=TODAY + dt.timedelta(days=2))
        summary = (2, 1, 0, 0, 0, 2, 0, 0, 0, 2,
                   first[5], second[5])
        connection = FakeConnection([summary], [first, second])

        result = list_operational_periods(
            connection, today=TODAY, subject_id=SUBJECT,
            status="attention", limit=1)

        self.assertTrue(result["has_more"])
        self.assertIsNotNone(result["next_cursor"])
        self.assertEqual(1, len(result["items"]))
        self.assertTrue(result["items"][0]["assigned_to_me"])
        self.assertEqual("2026-08-25", result["items"][0]["due_on"])
        self.assertFalse({"amount", "balance", "currency"} & result["items"][0].keys())
        self.assertEqual(2, result["summary"]["filtered_total"])
        self.assertIn("ORDER BY due_on ASC, expectation_id ASC",
                      connection.calls[1][0])
        self.assertEqual(2, connection.calls[1][1][-1])

    def test_second_page_uses_the_exact_tuple_from_the_cursor(self) -> None:
        identifier = str(uuid.uuid4())
        cursor = encode_cursor(TODAY, identifier)
        summary = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None)
        connection = FakeConnection([summary], [])
        result = list_operational_periods(
            connection, today=TODAY, subject_id=SUBJECT,
            status="all", limit=25, cursor=cursor)
        self.assertEqual([], result["items"])
        statement, params = connection.calls[1]
        self.assertIn("(due_on, expectation_id) >", statement)
        self.assertEqual(TODAY, params[2])
        self.assertEqual(identifier, params[3])


if __name__ == "__main__":
    unittest.main()
