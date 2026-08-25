"""Pruebas puras de observaciones de saldo FNC-CLS-002."""

from __future__ import annotations

import datetime as dt
import unittest
import uuid
from contextlib import nullcontext
from decimal import Decimal
from unittest.mock import patch

from fincilia_api.balances import BalanceError, create_balance


COMPANY = str(uuid.uuid4())
SUBJECT = str(uuid.uuid4())
SOURCE_RECORD = str(uuid.uuid4())
ACCOUNT = str(uuid.uuid4())
RELEASE = str(uuid.uuid4())


def evidence(*, values: list[str] | None = None,
             decimal_format: str = "comma", date_format: str = "dmy") -> dict:
    return {
        "source_record_id": SOURCE_RECORD,
        "company_id": COMPANY,
        "data_source_id": str(uuid.uuid4()),
        "engine_release_id": RELEASE,
        "canonical_schema_version": "0.1.0",
        "raw_values": values or ["31/07/2026", "Saldo", "-1.234,50"],
        "definition": {"decimal_format": decimal_format, "date_format": date_format},
        "financial_account_id": ACCOUNT,
        "currency_code": "COP",
        "account_name": "Cuenta sintetica",
        "source_name": "Extracto sintetico",
        "source_timezone": "America/Bogota",
    }


class Cursor:
    def __init__(self, *, stored_key: str | None = None, replay: bool = False) -> None:
        self.current = None
        self.insert_params = None
        self.stored_key = stored_key
        self.replay = replay
        self.balance_id = uuid.uuid4()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple) -> None:
        if statement.startswith("SELECT pg_advisory_xact_lock"):
            self.current = (None,)
            return
        if statement.startswith("SELECT balance_id FROM fincilia.account_balance"):
            self.current = (self.balance_id,) if self.replay else None
            return
        if statement.startswith("INSERT INTO fincilia.account_balance"):
            self.insert_params = params
            self.current = None
            return
        if statement.startswith("SELECT b.balance_id"):
            amount = self.insert_params[5] if self.insert_params is not None else "-1234.500000000000"
            observed_at = (self.insert_params[7] if self.insert_params is not None
                           else dt.datetime(2026, 8, 1, 4, 59, 59, 999999,
                                            tzinfo=dt.timezone.utc))
            self.current = (
                uuid.uuid4(), ACCOUNT, "Cuenta sintetica", SOURCE_RECORD,
                "Extracto sintetico", 7, "closing",
                Decimal(amount), "COP", observed_at,
                "America/Bogota", 2, 0, "complete",
                dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc),
            )
            return
        if statement.startswith("SELECT observation_key"):
            fallback = (self.insert_params[12] if self.insert_params is not None
                        else "1" * 64)
            self.current = (self.stored_key or fallback,)
            return
        raise AssertionError(statement)

    def fetchone(self):
        return self.current


class Connection:
    def __init__(self, cursor: Cursor) -> None:
        self._cursor = cursor

    def cursor(self) -> Cursor:
        return self._cursor

    def transaction(self):
        return nullcontext()


class BalanceTests(unittest.TestCase):
    def test_unknown_type_and_negative_coordinates_fail_before_reading(self) -> None:
        with self.assertRaisesRegex(BalanceError, "not supported"):
            create_balance(Connection(Cursor()), company_id=COMPANY,
                           subject_id=SUBJECT, source_record_id=SOURCE_RECORD,
                           balance_type="estimated", amount_field_index=2,
                           as_of_field_index=0)
        with self.assertRaisesRegex(BalanceError, "non-negative"):
            create_balance(Connection(Cursor()), company_id=COMPANY,
                           subject_id=SUBJECT, source_record_id=SOURCE_RECORD,
                           balance_type="closing", amount_field_index=-1,
                           as_of_field_index=0)

    def test_float_like_ambiguity_and_out_of_range_cells_fail_closed(self) -> None:
        with patch("fincilia_api.balances._load_evidence", return_value=evidence(
                values=["31/07/2026", "1,23,45"])):
            with self.assertRaisesRegex(BalanceError, "versioned mapping"):
                create_balance(Connection(Cursor()), company_id=COMPANY,
                               subject_id=SUBJECT, source_record_id=SOURCE_RECORD,
                               balance_type="closing", amount_field_index=1,
                               as_of_field_index=0)
        with patch("fincilia_api.balances._load_evidence", return_value=evidence()):
            with self.assertRaisesRegex(BalanceError, "does not exist"):
                create_balance(Connection(Cursor()), company_id=COMPANY,
                               subject_id=SUBJECT, source_record_id=SOURCE_RECORD,
                               balance_type="closing", amount_field_index=9,
                               as_of_field_index=0)

    @patch("fincilia_api.balances.financial_lineage.materialize_balance")
    def test_server_derives_signed_exact_money_currency_instant_and_lineage(
            self, materialize) -> None:
        cursor = Cursor()
        with patch("fincilia_api.balances._load_evidence", return_value=evidence()):
            result = create_balance(
                Connection(cursor), company_id=COMPANY, subject_id=SUBJECT,
                source_record_id=SOURCE_RECORD, balance_type="closing",
                amount_field_index=2, as_of_field_index=0)

        self.assertEqual("-1234.500000000000", result["amount"])
        self.assertEqual("COP", result["currency_code"])
        self.assertEqual("complete", result["lineage_state"])
        self.assertEqual("2026-08-01T04:59:59.999999+00:00", result["as_of"])
        self.assertFalse(result["proves_completeness"])
        self.assertFalse(result["proves_reconciliation"])
        self.assertFalse(result["replayed"])
        assert cursor.insert_params is not None
        self.assertEqual(2, cursor.insert_params[9])
        self.assertEqual(0, cursor.insert_params[10])
        materialize.assert_called_once()

    @patch("fincilia_api.balances.financial_lineage.materialize_balance")
    def test_exact_replay_returns_same_observation_and_divergence_conflicts(
            self, materialize) -> None:
        replay = Cursor(replay=True)
        with patch("fincilia_api.balances._load_evidence", return_value=evidence()), \
                patch("fincilia_api.balances.digest_of", return_value="1" * 64):
            result = create_balance(
                Connection(replay), company_id=COMPANY, subject_id=SUBJECT,
                source_record_id=SOURCE_RECORD, balance_type="closing",
                amount_field_index=2, as_of_field_index=0)
        self.assertTrue(result["replayed"])
        materialize.assert_not_called()

        divergent = Cursor(replay=True, stored_key="0" * 64)
        with patch("fincilia_api.balances._load_evidence", return_value=evidence()), \
                patch("fincilia_api.balances.digest_of", return_value="1" * 64):
            with self.assertRaisesRegex(BalanceError, "another observation"):
                create_balance(
                    Connection(divergent), company_id=COMPANY, subject_id=SUBJECT,
                    source_record_id=SOURCE_RECORD, balance_type="closing",
                    amount_field_index=2, as_of_field_index=0)


if __name__ == "__main__":
    unittest.main()
