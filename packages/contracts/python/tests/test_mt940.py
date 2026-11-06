"""Contrato del lector MT940 (ADR-039 §5). Extractos sinteticos en memoria."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

from fincilia_contracts.mt940 import (MT940Error, looks_like_mt940, parse_mt940)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import structured_factory as factory  # noqa: E402


class StatementReadingTests(unittest.TestCase):
    def test_a_balanced_statement_reads_every_movement(self) -> None:
        result = parse_mt940(factory.mt940())
        self.assertEqual("complete", result.status)
        self.assertEqual("balanced", result.balance_check)
        statement = result.statements[0]
        self.assertEqual("SYN-STMT-0001", statement.transaction_reference)
        self.assertEqual("SYN-CTA-0001", statement.account)
        self.assertEqual("00001/001", statement.statement_number)
        self.assertEqual(3, len(statement.transactions))

    def test_marks_dates_and_references_are_read(self) -> None:
        first, second, third = parse_mt940(factory.mt940()).statements[0].transactions
        self.assertEqual(("2026-03-02", "2026-03-02", "C", "inflow"),
                         (first.value_date, first.entry_date, first.mark, first.direction))
        self.assertEqual(Decimal("150000"), first.amount)
        self.assertEqual("NTRF", first.type_code)
        self.assertEqual("SYN-REF-0001", first.customer_reference)
        self.assertEqual("SYN-BNK-0001", first.bank_reference)
        self.assertEqual("FNC-SYN abono cliente", first.supplementary)
        self.assertEqual("FNC-SYN Cliente Cascada 001 pago factura SYN-FE-0001",
                         first.information)
        self.assertIsNone(second.entry_date)
        self.assertEqual(("D", "outflow", "NONREF"),
                         (second.mark, second.direction, second.customer_reference))
        # El reverso de un credito saca dinero.
        self.assertEqual(("RC", "outflow"), (third.mark, third.direction))

    def test_amounts_are_exact_decimals(self) -> None:
        statement = parse_mt940(factory.mt940()).statements[0]
        self.assertIsInstance(statement.opening.amount, Decimal)
        self.assertEqual(Decimal("1000000"), statement.opening.amount)
        self.assertEqual(Decimal("80000"), statement.balance_check.movements)

    def test_lineage_names_statement_tag_and_line(self) -> None:
        statement = parse_mt940(factory.mt940()).statements[0]
        lineage = statement.transactions[0].lineage
        self.assertEqual({"locator_kind": "mt940_tag", "statement_index": 1,
                          "tag": "61", "line_number": 5,
                          "information_lines": [7]}, lineage)
        self.assertEqual(4, statement.opening.lineage["line_number"])

    def test_the_swift_envelope_is_accepted(self) -> None:
        result = parse_mt940(factory.mt940(envelope=True))
        self.assertEqual("balanced", result.balance_check)

    def test_several_statements_are_checked_one_by_one(self) -> None:
        payload = factory.mt940() + factory.mt940(closing="C260331COP1080001,00")
        result = parse_mt940(payload)
        self.assertEqual(["balanced", "mismatch"],
                         [item.balance_check.status for item in result.statements])
        self.assertEqual("mismatch", result.balance_check)


class BalanceCheckTests(unittest.TestCase):
    def test_a_mismatch_is_reported_never_passed(self) -> None:
        result = parse_mt940(factory.mt940(closing="C260331COP1090000,00"))
        statement = result.statements[0]
        self.assertEqual("mismatch", statement.balance_check.status)
        self.assertEqual(Decimal("10000"), statement.balance_check.difference)
        self.assertEqual("partial", result.status)
        self.assertIn("balance_mismatch", {item.code for item in statement.findings})

    def test_a_missing_closing_balance_is_incomplete(self) -> None:
        payload = b"\r\n".join(line for line in factory.mt940().split(b"\r\n")
                               if not line.startswith(b":62F:"))
        result = parse_mt940(payload)
        self.assertEqual("incomplete", result.statements[0].balance_check.status)
        self.assertNotEqual("balanced", result.balance_check)

    def test_a_malformed_amount_makes_the_check_incomplete(self) -> None:
        for raw in ("50.000,00", "50000.00", "5O000,00"):
            with self.subTest(raw=raw):
                result = parse_mt940(factory.mt940(second_amount=raw))
                statement = result.statements[0]
                self.assertEqual("incomplete", statement.balance_check.status)
                self.assertEqual(2, len(statement.transactions))
                codes = {item.code for item in statement.findings}
                self.assertTrue(codes & {"malformed_amount", "malformed_statement_line"})

    def test_currencies_that_differ_are_not_compared(self) -> None:
        result = parse_mt940(factory.mt940(closing="C260331USD1080000,00"))
        self.assertEqual("currency_mismatch", result.statements[0].balance_check.status)

    def test_the_manifest_carries_no_references(self) -> None:
        manifest = str(parse_mt940(factory.mt940()).manifest())
        for value in ("SYN-CTA-0001", "SYN-REF-0001", "1000000"):
            self.assertNotIn(value, manifest)


class StructureTests(unittest.TestCase):
    def test_garbage_outside_tags_is_refused(self) -> None:
        with self.assertRaises(MT940Error):
            parse_mt940(b"esto no es un extracto\r\n:20:SYN\r\n")

    def test_a_tag_before_the_reference_is_refused(self) -> None:
        with self.assertRaises(MT940Error):
            parse_mt940(b":25:SYN-CTA-0001\r\n:20:SYN\r\n")

    def test_an_overlong_line_is_refused(self) -> None:
        with self.assertRaises(MT940Error):
            parse_mt940(b":20:SYN\r\n:86:" + b"x" * 600 + b"\r\n")

    def test_binary_and_empty_input_are_refused(self) -> None:
        for payload in (b"", b":20:\x00\r\n"):
            with self.subTest(payload=payload):
                with self.assertRaises(MT940Error):
                    parse_mt940(payload)


class SniffingTests(unittest.TestCase):
    def test_mt940_is_recognised_by_content(self) -> None:
        self.assertTrue(looks_like_mt940(factory.mt940()))
        self.assertTrue(looks_like_mt940(factory.mt940(envelope=True)))

    def test_lookalikes_are_not_mt940(self) -> None:
        self.assertFalse(looks_like_mt940(b"fecha,valor\r\n:20:x\r\n"))
        self.assertFalse(looks_like_mt940(b":20:SYN\r\n:86:solo texto\r\n"))


if __name__ == "__main__":
    unittest.main()
