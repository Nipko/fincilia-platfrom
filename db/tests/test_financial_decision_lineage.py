"""Guardas estructurales de FNC-LIN-001 contra PostgreSQL real."""

from __future__ import annotations

import unittest

import psycopg

from db.tests.test_api_authorization import MIGRATOR_DSN


class FinancialDecisionLineageSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN:
            raise unittest.SkipTest("migrator DSN is required")

    def test_every_complete_financial_entity_has_a_deferred_guard(self) -> None:
        expected = {
            "account_balance", "completeness_assessment",
            "completeness_control_result", "reconciling_item",
            "reconciliation_statement",
        }
        with psycopg.connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.relname, t.tgdeferrable, t.tginitdeferred "
                "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='fincilia' AND NOT t.tgisinternal "
                "AND t.tgname LIKE '%_complete_lineage'")
            rows = cursor.fetchall()
        self.assertEqual(expected, {row[0] for row in rows})
        self.assertTrue(all(row[1] and row[2] for row in rows))

    def test_the_only_runtime_update_is_the_statement_lineage_seal(self) -> None:
        tables = (
            "account_balance", "completeness_assessment",
            "completeness_control_result", "reconciling_item",
            "reconciliation_statement",
        )
        with psycopg.connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            observed = {}
            for table in tables:
                cursor.execute(
                    "SELECT has_column_privilege('fincilia_app', %s, "
                    "'lineage_state', 'UPDATE')",
                    (f"fincilia.{table}",))
                observed[table] = bool(cursor.fetchone()[0])
        self.assertEqual(
            {"reconciliation_statement": True},
            {table: allowed for table, allowed in observed.items() if allowed})

    def test_public_and_worker_cannot_execute_the_lineage_guards(self) -> None:
        signatures = (
            "fincilia.financial_lineage_complete(text,uuid,uuid)",
            "fincilia.enforce_complete_financial_lineage()",
        )
        with psycopg.connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            for signature in signatures:
                with self.subTest(signature=signature):
                    cursor.execute(
                        "SELECT has_function_privilege('public', %s, 'EXECUTE'), "
                        "has_function_privilege('fincilia_worker', %s, 'EXECUTE')",
                        (signature, signature))
                    self.assertEqual((False, False), cursor.fetchone())


if __name__ == "__main__":
    unittest.main()
