"""FNC-CLS-002 contra API, PostgreSQL, RLS y evidencia reales."""

from __future__ import annotations

import os
import json
import uuid
import unittest

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import RUNTIME_DSN
from db.tests.test_p3_vertical import (
    ACCOUNT,
    ANDINOS,
    ESPIGA,
    PREPARER,
    REVIEWER,
    VerticalHarness,
    statement_csv,
)

WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")


class AccountBalanceDatabaseTests(VerticalHarness):
    def test_balance_is_evidence_bound_exact_idempotent_and_company_scoped(self) -> None:
        artifact = self.promoted(statement_csv("balance"), "saldo-sintetico.csv")
        mapping = self.validated_mapping(artifact)
        dataset = self.prepared(artifact, mapping).json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements",
            headers=self.auth(PREPARER)).json()
        source_record_id = self._source_record(movements[0]["movement_id"])

        # Validado no significa publicado: no hay evidencia elegible todavia.
        refused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balances", headers=self.auth(PREPARER),
            json={"source_record_id": source_record_id, "balance_type": "closing",
                  "amount_field_index": 3, "as_of_field_index": 0})
        self.assertEqual(403, refused.status_code, refused.text)

        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

        evidence = self.client.get(
            f"/api/v1/companies/{ESPIGA}/balances/evidence?limit=20",
            headers=self.auth(PREPARER))
        self.assertEqual(200, evidence.status_code, evidence.text)
        candidate = next(item for item in evidence.json()["items"]
                         if item["source_record_id"] == source_record_id)
        self.assertEqual(ACCOUNT, candidate["financial_account_id"])
        self.assertEqual("COP", candidate["currency_code"])
        self.assertEqual("-1.234,56", candidate["fields"][3]["value"])

        body = {"source_record_id": source_record_id, "balance_type": "closing",
                "amount_field_index": 3, "as_of_field_index": 0}
        created = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balances", headers=self.auth(PREPARER),
            json=body)
        self.assertEqual(201, created.status_code, created.text)
        balance = created.json()
        self.assertEqual("-1234.560000000000", balance["amount"])
        self.assertEqual("COP", balance["currency_code"])
        self.assertEqual("complete", balance["lineage_state"])
        self.assertFalse(balance["proves_completeness"])
        self.assertFalse(balance["proves_reconciliation"])

        replay = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balances", headers=self.auth(PREPARER),
            json=body)
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(balance["balance_id"], replay.json()["balance_id"])
        self.assertTrue(replay.json()["replayed"])

        listed = self.client.get(
            f"/api/v1/companies/{ESPIGA}/balances", headers=self.auth(REVIEWER))
        self.assertEqual(200, listed.status_code, listed.text)
        self.assertIn(balance["balance_id"],
                      {item["balance_id"] for item in listed.json()["items"]})

        # Reviewer puede leer, pero no preparar; los roles no se interpretan en
        # el navegador y la acumulacion de roles no elimina esta comprobacion.
        no_prepare = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balances", headers=self.auth(REVIEWER),
            json=body)
        self.assertEqual(403, no_prepare.status_code, no_prepare.text)

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ANDINOS,))
                cursor.execute("SELECT balance_id FROM fincilia.account_balance "
                               "WHERE balance_id = %s", (balance["balance_id"],))
                self.assertIsNone(cursor.fetchone())
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute("UPDATE fincilia.account_balance "
                                   "SET lineage_state = 'complete' WHERE balance_id = %s",
                                   (balance["balance_id"],))
                connection.rollback()

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT fincilia.financial_lineage_complete("
                    "'account_balance', %s, %s), count(*) FROM "
                    "fincilia.lineage_node WHERE company_id=%s "
                    "AND node_type='financial_fact_field' AND entity_ref=%s",
                    (ESPIGA, balance["balance_id"], ESPIGA, balance["balance_id"]))
                complete, field_count = cursor.fetchone()
                self.assertTrue(complete)
                self.assertEqual(2, field_count)

        # El rol runtime conoce todos los datos de una observacion elegible y aun
        # asi no puede autodeclararla `complete` sin materializar su grafo.
        with self.assertRaises(psycopg.errors.CheckViolation):
            with psycopg.connect(RUNTIME_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)",
                        (ESPIGA,))
                    forged = uuid.uuid4()
                    digest = uuid.uuid4().hex * 2
                    cursor.execute(
                        "INSERT INTO fincilia.account_balance (balance_id, company_id, "
                        "financial_account_id, source_record_id, balance_type, amount, "
                        "currency_code, as_of, source_timezone, amount_field_index, "
                        "as_of_field_index, field_digests, observation_key, prepared_by, "
                        "engine_release_id, canonical_schema_version, lineage_state) "
                        "SELECT %s, company_id, financial_account_id, source_record_id, "
                        "'available', amount, currency_code, as_of, source_timezone, "
                        "amount_field_index, as_of_field_index, %s::jsonb, %s, "
                        "prepared_by, engine_release_id, canonical_schema_version, "
                        "'complete' FROM fincilia.account_balance WHERE balance_id=%s",
                        (forged, json.dumps({"amount": digest, "as_of": digest}),
                         digest, balance["balance_id"]))

        events = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit?limit=50",
            headers=self.auth(REVIEWER)).json()
        observed = next(item for item in events
                        if item["action"] == "balance.observe"
                        and item["resource_ref"] == balance["balance_id"])
        rendered = str(observed)
        self.assertNotIn("1234", rendered)
        self.assertNotIn("-1.234,56", rendered)

    def test_worker_has_no_balance_table_privileges(self) -> None:
        with psycopg.connect(WORKER_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute("SELECT count(*) FROM fincilia.account_balance")
                connection.rollback()

    @staticmethod
    def _source_record(movement_id: str) -> str:
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute("SELECT source_record_id FROM fincilia.canonical_movement "
                               "WHERE movement_id = %s", (movement_id,))
                return str(cursor.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
