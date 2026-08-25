"""FNC-CLS-003 contra PostgreSQL real, RLS, dinero y decisiones append-only."""

from __future__ import annotations

import json
import uuid
import datetime as dt
from decimal import Decimal

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import (
    ACCOUNT,
    ANDINOS,
    ESPIGA,
    PREPARER,
    REVIEWER,
    VerticalHarness,
    statement_csv,
)


PREPARER_ID = stable_id("subject", "ana")
REVIEWER_ID = stable_id("subject", "beto")


class BalanceReconciliationDatabaseTests(VerticalHarness):
    reconciliation_roots: set[str] = set()
    assessments: set[str] = set()
    expectations: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        # El harness vertical conoce artefactos y datasets, pero esta rebanada
        # agrega referencias RESTRICT desde estados financieros. Se retiran
        # primero y luego el harness conserva su orden de limpieza habitual.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)",
                    (ESPIGA,),
                )
                immutable_triggers = (
                    ("reconciliation_statement", "reconciliation_statement_immutable"),
                    ("reconciling_item", "reconciling_item_immutable"),
                    ("reconciliation_statement_root", "statement_root_immutable"),
                    ("completeness_control_result", "completeness_control_immutable"),
                    ("completeness_assessment", "completeness_assessment_immutable"),
                )
                for table, trigger in immutable_triggers:
                    cursor.execute(
                        f"ALTER TABLE fincilia.{table} DISABLE TRIGGER {trigger}"
                    )
                roots = list(cls.reconciliation_roots)
                assessments = list(cls.assessments)
                expectations = list(cls.expectations)
                if roots:
                    cursor.execute(
                        "DELETE FROM fincilia.reconciliation_statement "
                        "WHERE statement_root_id = ANY(%s)",
                        (roots,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.reconciling_item "
                        "WHERE statement_root_id = ANY(%s)",
                        (roots,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.reconciliation_statement_root "
                        "WHERE statement_root_id = ANY(%s)",
                        (roots,),
                    )
                if assessments:
                    cursor.execute(
                        "DELETE FROM fincilia.completeness_control_result "
                        "WHERE assessment_id = ANY(%s)",
                        (assessments,),
                    )
                    cursor.execute(
                        "DELETE FROM fincilia.completeness_assessment "
                        "WHERE assessment_id = ANY(%s)",
                        (assessments,),
                    )
                if expectations:
                    cursor.execute(
                        "DELETE FROM fincilia.source_expectation "
                        "WHERE expectation_id = ANY(%s)",
                        (expectations,),
                    )
                for table, trigger in immutable_triggers:
                    cursor.execute(
                        f"ALTER TABLE fincilia.{table} ENABLE TRIGGER {trigger}"
                    )
        super().tearDownClass()

    def _published_evidence(self) -> tuple[str, str, str, str, str]:
        artifact = self.promoted(
            statement_csv(f"statement-{uuid.uuid4().hex[:8]}"),
            f"estado-sintetico-{uuid.uuid4().hex[:8]}.csv")
        mapping = self.validated_mapping(artifact)
        dataset = self.prepared(artifact, mapping).json()["dataset_version_id"]
        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT s.source_record_id, d.artifact_id, s.data_source_id, "
                    "       s.engine_release_id, s.canonical_schema_version "
                    "FROM fincilia.source_record s "
                    "JOIN fincilia.dataset_version d "
                    "  ON d.dataset_version_id = s.dataset_version_id "
                    "WHERE s.dataset_version_id = %s "
                    "ORDER BY s.created_at LIMIT 1", (dataset,))
                source_record, artifact_id, source_id, release_id, schema = cursor.fetchone()
        return (str(dataset), str(source_record), str(artifact_id), str(source_id),
                f"{release_id}|{schema}")

    def _insert_balance(self, cursor, *, source_record: str, balance_type: str,
                        amount: str, release_id: str, schema: str) -> str:
        balance_id = str(uuid.uuid4())
        digest = uuid.uuid4().hex * 2
        cursor.execute(
            "INSERT INTO fincilia.account_balance "
            "(balance_id, company_id, financial_account_id, source_record_id, "
            " balance_type, amount, currency_code, as_of, source_timezone, "
            " amount_field_index, as_of_field_index, field_digests, "
            " observation_key, prepared_by, engine_release_id, "
            " canonical_schema_version, lineage_state) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'COP', "
            " '2026-03-31 23:59:59-05', 'America/Bogota', 3, 0, %s::jsonb, "
            " %s, %s, %s, %s, 'complete')",
            (balance_id, ESPIGA, ACCOUNT, source_record, balance_type, amount,
             json.dumps({"amount": digest, "as_of": digest}), digest,
             PREPARER_ID, release_id, schema))
        return balance_id

    def test_statement_is_exact_versioned_and_fail_closed(self) -> None:
        dataset, source_record, artifact, source, version = self._published_evidence()
        release_id, schema = version.split("|", 1)
        period_start = "2026-03-31"
        period_end_date = dt.date(2026, 3, 31) + dt.timedelta(
            days=1 + int(uuid.uuid4().hex[:5], 16) % 2500)
        period_end = period_end_date.isoformat()
        due_on = (period_end_date + dt.timedelta(days=1)).isoformat()
        late_after = (period_end_date + dt.timedelta(days=2)).isoformat()
        expectation = str(uuid.uuid4())
        assessment = str(uuid.uuid4())
        control = str(uuid.uuid4())
        root = str(uuid.uuid4())
        item_root = str(uuid.uuid4())
        confirmed_decision = str(uuid.uuid4())
        self.reconciliation_roots.add(root)
        self.assessments.add(assessment)
        self.expectations.add(expectation)

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute(
                    "INSERT INTO fincilia.source_expectation "
                    "(expectation_id, company_id, data_source_id, financial_account_id, "
                    " period_start, period_end, due_on, late_after, expected_controls, "
                    " state, satisfied_by, satisfied_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                    " %s::jsonb, 'satisfied', %s, now())",
                    (expectation, ESPIGA, source, ACCOUNT, period_start, period_end,
                     due_on, late_after,
                     json.dumps({"controls": ["provenance_integrity"]}), artifact))
                bank = self._insert_balance(
                    cursor, source_record=source_record, balance_type="closing",
                    amount="1000.000000000000", release_id=release_id, schema=schema)
                books = self._insert_balance(
                    cursor, source_record=source_record, balance_type="ledger",
                    amount="1100.000000000000", release_id=release_id, schema=schema)
                cursor.execute(
                    "INSERT INTO fincilia.completeness_assessment "
                    "(assessment_id, company_id, data_source_id, source_expectation_id, "
                    " financial_account_id, dataset_version_id, period_start, period_end, "
                    " state, assessment_key, prepared_by, engine_release_id, "
                    " canonical_schema_version, lineage_state) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'verified', %s, "
                    " %s, %s, %s, 'complete')",
                    (assessment, ESPIGA, source, expectation, ACCOUNT, dataset,
                     period_start, period_end, uuid.uuid4().hex * 2, PREPARER_ID,
                     release_id, schema))
                evidence = json.dumps([
                    {"kind": "dataset_version", "ref": dataset},
                    {"kind": "source_expectation", "ref": expectation},
                ])
                cursor.execute(
                    "INSERT INTO fincilia.completeness_control_result "
                    "(control_result_id, company_id, assessment_id, control_type, "
                    " required, outcome, expected_value, observed_value, value_type, "
                    " evidence_refs, rule_version, engine_release_id, "
                    " canonical_schema_version, lineage_state) "
                    "VALUES (%s, %s, %s, 'provenance_integrity', true, 'match', "
                    " %s::jsonb, %s::jsonb, 'boolean', %s::jsonb, "
                    " 'fnc-completeness-v1', %s, %s, 'complete')",
                    (control, ESPIGA, assessment, json.dumps({"value": True}),
                     json.dumps({"value": True}), evidence, release_id, schema))
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_statement_root "
                    "(statement_root_id, company_id, financial_account_id, period_start, "
                    " period_end, currency_code, prepared_by) "
                    "VALUES (%s, %s, %s, %s, %s, 'COP', %s)",
                    (root, ESPIGA, ACCOUNT, period_start, period_end, PREPARER_ID))

                first_statement = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_statement "
                    "(statement_id, company_id, statement_root_id, version, "
                    " financial_account_id, period_start, period_end, currency_code, "
                    " bank_closing_balance_id, books_closing_balance_id, "
                    " completeness_assessment_ids, confirmed_reconciling_item_ids, "
                    " statement_key, prepared_by, engine_release_id, "
                    " canonical_schema_version, rule_version_ids) "
                    "VALUES (%s, %s, %s, 99, %s, %s, %s, 'COP', %s, %s, "
                    " %s::uuid[], '{}'::uuid[], %s, %s, %s, %s, %s::jsonb) "
                    "RETURNING version, adjusted_bank_balance, unexplained_difference, state",
                    (first_statement, ESPIGA, root, ACCOUNT, period_start, period_end,
                     bank, books, [assessment], uuid.uuid4().hex * 2, PREPARER_ID,
                     release_id, schema, json.dumps(["fnc-balance-equation-v1"])))
                version_one = cursor.fetchone()
                self.assertEqual(1, version_one[0])
                self.assertEqual(Decimal("1000.000000000000"), version_one[1])
                self.assertEqual(Decimal("-100.000000000000"), version_one[2])
                self.assertEqual("review_required", version_one[3])

                item_evidence = json.dumps([
                    {"kind": "source_record", "ref": source_record},
                ])
                cursor.execute(
                    "INSERT INTO fincilia.reconciling_item "
                    "(item_decision_id, item_root_id, company_id, statement_root_id, "
                    " adjustment_side, amount, currency_code, reason_code, state, "
                    " evidence_refs, prepared_by, decision_version, engine_release_id, "
                    " canonical_schema_version, lineage_state) "
                    "VALUES (%s, %s, %s, %s, 'add_to_bank', 100, 'COP', "
                    " 'documented_timing', 'proposed', %s::jsonb, %s, 1, %s, %s, "
                    " 'required_pending')",
                    (item_root, item_root, ESPIGA, root, item_evidence, PREPARER_ID,
                     release_id, schema))
                cursor.execute(
                    "INSERT INTO fincilia.reconciling_item "
                    "(item_decision_id, item_root_id, company_id, statement_root_id, "
                    " adjustment_side, amount, currency_code, reason_code, state, "
                    " evidence_refs, prepared_by, approved_by, approved_at, "
                    " decision_version, engine_release_id, canonical_schema_version, "
                    " lineage_state) "
                    "VALUES (%s, %s, %s, %s, 'add_to_bank', 100, 'COP', "
                    " 'documented_timing', 'confirmed', %s::jsonb, %s, %s, now(), "
                    " 2, %s, %s, 'complete')",
                    (confirmed_decision, item_root, ESPIGA, root, item_evidence,
                     PREPARER_ID, REVIEWER_ID, release_id, schema))

                second_statement = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.reconciliation_statement "
                    "(statement_id, company_id, statement_root_id, version, "
                    " financial_account_id, period_start, period_end, currency_code, "
                    " bank_closing_balance_id, books_closing_balance_id, "
                    " completeness_assessment_ids, confirmed_reconciling_item_ids, "
                    " statement_key, prepared_by, engine_release_id, "
                    " canonical_schema_version, rule_version_ids) "
                    "VALUES (%s, %s, %s, 99, %s, %s, %s, 'COP', %s, %s, "
                    " %s::uuid[], %s::uuid[], %s, %s, %s, %s, %s::jsonb) "
                    "RETURNING version, confirmed_additions_to_bank, "
                    " adjusted_bank_balance, unexplained_difference, state, lineage_state",
                    (second_statement, ESPIGA, root, ACCOUNT, period_start, period_end,
                     bank, books, [assessment], [confirmed_decision],
                     uuid.uuid4().hex * 2, PREPARER_ID, release_id, schema,
                     json.dumps(["fnc-balance-equation-v1"])))
                version_two = cursor.fetchone()
                self.assertEqual(2, version_two[0])
                self.assertEqual(Decimal("100.000000000000"), version_two[1])
                self.assertEqual(Decimal("1100.000000000000"), version_two[2])
                self.assertEqual(Decimal("0E-12"), version_two[3])
                self.assertEqual("balanced", version_two[4])
                self.assertEqual("required_pending", version_two[5])

                cursor.execute(
                    "SELECT unexplained_difference, state FROM "
                    "fincilia.reconciliation_statement WHERE statement_id = %s",
                    (first_statement,))
                self.assertEqual((Decimal("-100.000000000000"), "review_required"),
                                 cursor.fetchone())

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ANDINOS,))
                cursor.execute(
                    "SELECT statement_id FROM fincilia.reconciliation_statement "
                    "WHERE statement_root_id = %s", (root,))
                self.assertIsNone(cursor.fetchone())
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.reconciliation_statement SET state = 'draft' "
                        "WHERE statement_root_id = %s", (root,))
                connection.rollback()

    def test_database_rejects_forged_evidence_and_false_verified_state(self) -> None:
        dataset, source_record, artifact, source, version = self._published_evidence()
        release_id, schema = version.split("|", 1)
        expectation = str(uuid.uuid4())
        assessment = str(uuid.uuid4())
        year = 2100 + int(uuid.uuid4().hex[:3], 16)
        period_start, period_end = f"{year}-01-01", f"{year}-12-31"
        self.assessments.add(assessment)
        self.expectations.add(expectation)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "INSERT INTO fincilia.source_expectation "
                    "(expectation_id, company_id, data_source_id, financial_account_id, "
                    " period_start, period_end, due_on, late_after, state, "
                    " satisfied_by, satisfied_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                    " 'satisfied', %s, now())",
                    (expectation, ESPIGA, source, ACCOUNT, period_start, period_end,
                     f"{year + 1}-01-01", f"{year + 1}-01-02", artifact))

        forged = json.dumps([
            {"kind": "dataset_version", "ref": str(uuid.uuid4())},
            {"kind": "source_expectation", "ref": expectation},
        ])
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, true)",
                            (ESPIGA,))
                        cursor.execute(
                            "INSERT INTO fincilia.completeness_assessment "
                            "(assessment_id, company_id, data_source_id, "
                            " source_expectation_id, financial_account_id, "
                            " dataset_version_id, period_start, period_end, state, "
                            " assessment_key, prepared_by, engine_release_id, "
                            " canonical_schema_version, lineage_state) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'unknown', %s, "
                            " %s, %s, %s, 'required_pending')",
                            (assessment, ESPIGA, source, expectation, ACCOUNT, dataset,
                             period_start, period_end, uuid.uuid4().hex * 2,
                             PREPARER_ID, release_id, schema))
                        cursor.execute(
                            "INSERT INTO fincilia.completeness_control_result "
                            "(company_id, assessment_id, control_type, required, outcome, "
                            " value_type, evidence_refs, rule_version, engine_release_id, "
                            " canonical_schema_version, lineage_state) "
                            "VALUES (%s, %s, 'record_count', true, 'match', 'integer', "
                            " %s::jsonb, 'v1', %s, %s, 'required_pending')",
                            (ESPIGA, assessment, forged, release_id, schema))
            self.assertEqual("ck_control_evidence_scope",
                             raised.exception.diag.constraint_name)

        # Un assessment `verified` con control required unknown sobrevive al
        # INSERT, pero no puede sobrevivir al COMMIT diferido.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, true)",
                            (ESPIGA,))
                        cursor.execute(
                            "INSERT INTO fincilia.completeness_assessment "
                            "(assessment_id, company_id, data_source_id, "
                            " source_expectation_id, financial_account_id, "
                            " dataset_version_id, period_start, period_end, state, "
                            " assessment_key, prepared_by, engine_release_id, "
                            " canonical_schema_version, lineage_state) "
                            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, "
                            " 'verified', %s, %s, %s, %s, 'required_pending') "
                            "RETURNING assessment_id",
                            (ESPIGA, source, expectation, ACCOUNT, dataset, period_start,
                             period_end, uuid.uuid4().hex * 2, PREPARER_ID,
                             release_id, schema))
                        bad_assessment = str(cursor.fetchone()[0])
                        evidence = json.dumps([
                            {"kind": "dataset_version", "ref": dataset},
                            {"kind": "source_expectation", "ref": expectation},
                        ])
                        cursor.execute(
                            "INSERT INTO fincilia.completeness_control_result "
                            "(company_id, assessment_id, control_type, required, outcome, "
                            " value_type, evidence_refs, rule_version, reason, "
                            " engine_release_id, canonical_schema_version, lineage_state) "
                            "VALUES (%s, %s, 'record_count', true, 'unknown', 'integer', "
                            " %s::jsonb, 'v1', 'expected count unavailable', %s, %s, "
                            " 'required_pending')",
                            (ESPIGA, bad_assessment, evidence, release_id, schema))
            self.assertEqual("ck_assessment_derived_state",
                             raised.exception.diag.constraint_name)


if __name__ == "__main__":
    import unittest
    unittest.main()
