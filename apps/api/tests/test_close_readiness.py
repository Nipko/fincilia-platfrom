"""Pruebas puras del diagnostico previo al cierre FNC-CLS-001."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid

from fincilia_api.close_readiness import (
    CloseReadinessError,
    CloseReadinessQuery,
    MAX_EXPECTATIONS,
    _build_period,
    _period_rows,
    _row_source,
)


START = dt.date(2026, 7, 1)
END = dt.date(2026, 7, 31)


def source_row(*, expectation_state: str = "satisfied",
               dataset_state: str | None = "published",
               completeness: str | None = "verified",
               lineage: str | None = "complete",
               rejected: int = 0) -> tuple:
    artifact = uuid.uuid4() if expectation_state == "satisfied" else None
    dataset = uuid.uuid4() if dataset_state is not None else None
    return (
        uuid.uuid4(), uuid.uuid4(), "Banco sintetico", uuid.uuid4(),
        START, END, expectation_state, artifact, dataset, dataset_state,
        completeness, lineage, rejected, 2,
        dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc),
    )


def checks(dataset_id: str, **overrides) -> dict:
    item = {
        "missing_accounting_dates": 0,
        "open_candidate_ids": set(),
        "active_high_quality_ids": set(),
        "proposed_corrections": 0,
        "approved_unapplied_corrections": 0,
    }
    item.update(overrides)
    return {dataset_id: item}


def reconciled_inputs(source: dict, *, statement_state: str = "balanced",
                      statement_lineage: str = "complete",
                      statement_assessments: list[str] | None = None) -> tuple[dict, dict, dict]:
    account_id = source["financial_account_id"]
    dataset_id = source["dataset_version_id"]
    assessment_id = str(uuid.uuid4())
    assessment_checks = {(source["expectation_id"], dataset_id): {
        "assessment_id": assessment_id,
        "financial_account_id": account_id,
        "state": "verified",
        "lineage_state": "complete",
    }}
    balance_checks = {(dataset_id, account_id): [{
        "balance_type": "closing",
        "as_of_date": END,
        "lineage_state": "complete",
    }]}
    statement_checks = {(account_id, START, END): {
        "statement_root_id": str(uuid.uuid4()),
        "statement_id": str(uuid.uuid4()),
        "version": 2,
        "state": statement_state,
        "lineage_state": statement_lineage,
        "assessment_ids": statement_assessments or [assessment_id],
    }}
    return balance_checks, assessment_checks, statement_checks


class CloseReadinessTests(unittest.TestCase):
    def test_query_is_bounded(self) -> None:
        for limit in (0, 25):
            with self.subTest(limit=limit), self.assertRaises(CloseReadinessError):
                CloseReadinessQuery(limit).validated()
        self.assertEqual(24, CloseReadinessQuery(24).validated().limit)

    def test_even_complete_current_evidence_never_enables_close(self) -> None:
        source = _row_source(source_row())
        period = _build_period(
            START, END, [source], checks(source["dataset_version_id"]))

        self.assertEqual("blocked", period["status"])
        self.assertFalse(period["close_ready"])
        self.assertFalse(period["can_execute_close"])
        blocker_codes = {item["code"] for item in period["blockers"]}
        self.assertEqual(
            {"account_balances", "completeness_assessments",
             "reconciliation_statements", "reconciliation_statement_lineage"},
            blocker_codes)
        self.assertNotIn("amount", str(period).lower())
        self.assertNotIn("currency", str(period).lower())

    def test_balance_observation_without_complete_lineage_still_blocks(self) -> None:
        source = _row_source(source_row())
        key = (source["dataset_version_id"], source["financial_account_id"])
        balance_checks = {key: [{
            "balance_type": "closing",
            "as_of_date": END,
            "lineage_state": "required_pending",
        }]}
        period = _build_period(
            START, END, [source], checks(source["dataset_version_id"]),
            balance_checks)
        control = next(item for item in period["controls"]
                       if item["code"] == "account_balances")
        self.assertEqual("blocked", control["state"])
        self.assertEqual(1, control["count"])
        self.assertIn("1 observacion", control["detail"])

    def test_only_right_type_period_and_complete_lineage_pass_balance_control(self) -> None:
        source = _row_source(source_row())
        key = (source["dataset_version_id"], source["financial_account_id"])
        balance_checks = {key: [
            {"balance_type": "available", "as_of_date": END,
             "lineage_state": "complete"},
            {"balance_type": "closing", "as_of_date": END + dt.timedelta(days=1),
             "lineage_state": "complete"},
            {"balance_type": "closing", "as_of_date": END,
             "lineage_state": "complete"},
        ]}
        period = _build_period(
            START, END, [source], checks(source["dataset_version_id"]),
            balance_checks)
        control = next(item for item in period["controls"]
                       if item["code"] == "account_balances")
        self.assertEqual("pass", control["state"])
        self.assertEqual(0, control["count"])

    def test_unknown_exception_and_waiver_fail_closed(self) -> None:
        source = _row_source(source_row(
            expectation_state="waived", dataset_state=None,
            completeness=None, lineage=None))
        period = _build_period(START, END, [source], {})
        controls = {item["code"]: item for item in period["controls"]}

        self.assertEqual("blocked", controls["expectations_satisfied"]["state"])
        self.assertEqual("blocked", controls["dataset_evidence"]["state"])
        self.assertFalse(period["close_ready"])

    def test_review_quality_dates_and_corrections_are_explainable(self) -> None:
        source = _row_source(source_row(rejected=3))
        dataset_id = source["dataset_version_id"]
        period = _build_period(START, END, [source], checks(
            dataset_id,
            missing_accounting_dates=2,
            open_candidate_ids={"candidate-a", "candidate-b"},
            active_high_quality_ids={"issue-a"},
            proposed_corrections=1,
            approved_unapplied_corrections=2,
        ))
        controls = {item["code"]: item for item in period["controls"]}

        self.assertEqual(3, controls["rejected_rows"]["count"])
        self.assertEqual(2, controls["accounting_dates"]["count"])
        self.assertEqual(2, controls["reconciliation_reviews"]["count"])
        self.assertEqual(1, controls["quality_alerts"]["count"])
        self.assertEqual(3, controls["pending_corrections"]["count"])
        self.assertTrue(all(controls[code]["state"] == "blocked" for code in (
            "rejected_rows", "accounting_dates", "reconciliation_reviews",
            "quality_alerts", "pending_corrections")))

    def test_dataset_selection_is_declared_not_presented_as_completeness(self) -> None:
        source = _row_source(source_row(dataset_state="validated"))
        self.assertEqual(
            "published_then_validated_then_latest_for_satisfied_artifact",
            source["selection_rule"])
        period = _build_period(
            START, END, [source], checks(source["dataset_version_id"]))
        controls = {item["code"]: item for item in period["controls"]}
        self.assertEqual("blocked", controls["published_datasets"]["state"])

    def test_complete_reconciliation_is_ready_only_for_human_review(self) -> None:
        source = _row_source(source_row())
        balances, assessments, statements = reconciled_inputs(source)
        period = _build_period(
            START, END, [source], checks(source["dataset_version_id"]),
            balances, assessments, statements)
        controls = {item["code"]: item for item in period["controls"]}

        self.assertEqual("ready_for_review", period["status"])
        self.assertEqual([], period["blockers"])
        self.assertEqual("pass", controls["completeness_assessments"]["state"])
        self.assertEqual("pass", controls["reconciliation_statements"]["state"])
        self.assertEqual("unavailable", controls["product_close"]["state"])
        self.assertFalse(period["close_ready"])
        self.assertFalse(period["can_execute_close"])
        self.assertNotIn("amount", str(period).lower())
        self.assertNotIn("currency", str(period).lower())

    def test_stale_or_incomplete_statement_fails_closed(self) -> None:
        source = _row_source(source_row())
        balances, assessments, statements = reconciled_inputs(
            source, statement_assessments=[str(uuid.uuid4())])
        stale = _build_period(
            START, END, [source], checks(source["dataset_version_id"]),
            balances, assessments, statements)
        self.assertEqual("blocked", stale["status"])
        self.assertEqual(
            "stale_inputs", stale["account_reconciliations"][0]["coverage_state"])

        current_assessment_id = next(iter(assessments.values()))["assessment_id"]
        _, _, pending_lineage = reconciled_inputs(
            source, statement_lineage="required_pending",
            statement_assessments=[current_assessment_id])
        incomplete = _build_period(
            START, END, [source], checks(source["dataset_version_id"]),
            balances, assessments, pending_lineage)
        self.assertEqual("blocked", incomplete["status"])
        self.assertEqual(
            "covered",
            incomplete["account_reconciliations"][0]["coverage_state"])
        controls = {item["code"]: item for item in incomplete["controls"]}
        self.assertEqual(
            "blocked", controls["reconciliation_statement_lineage"]["state"])

    def test_a_period_window_cannot_hide_sources_by_silent_truncation(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.rows: list[tuple] = []
                self.calls = 0

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def execute(self, _statement: str, _params: tuple) -> None:
                self.calls += 1
                self.rows = ([(START, END)] if self.calls == 1
                             else [source_row()] * (MAX_EXPECTATIONS + 1))

            def __iter__(self):
                return iter(self.rows)

        cursor = Cursor()

        class Connection:
            def cursor(self):
                return cursor

        with self.assertRaisesRegex(CloseReadinessError, "more than 1200"):
            _period_rows(Connection(), 12)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
