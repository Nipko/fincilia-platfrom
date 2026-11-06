"""FNC-SMB-003: senales deterministas, explicacion llana y reglas, sin float.

Logica pura: no necesita base de datos. La base reevalua las reglas con
`fincilia.normalise_match_text`; `db/tests/test_reconciliation_rules.py` prueba
que ambas normalizaciones coinciden sobre PostgreSQL real.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fincilia_api import match_signals as ms  # noqa: E402


class NormalisationTests(unittest.TestCase):
    def test_accents_case_and_punctuation_collapse(self) -> None:
        self.assertEqual("pago cliente cascada 001",
                         ms.normalise_text("  PAGO-Cliente  Cáscada/001 "))
        self.assertEqual("", ms.normalise_text(None))

    def test_counterparty_ids_ignore_check_digit_and_dots(self) -> None:
        self.assertEqual(frozenset({"900123456"}),
                         ms.counterparty_ids("Pago NIT 900.123.456-7"))
        self.assertEqual(frozenset({"FNC-SYN-NIT-0002"}),
                         ms.counterparty_ids("abono nit: FNC-SYN-NIT-0002 marzo"))
        self.assertEqual(frozenset(), ms.counterparty_ids("sin identificador"))

    def test_payment_reference_tokens(self) -> None:
        self.assertEqual(frozenset({"SYN0000001"}),
                         ms.payment_references("Transferencia BRE-B SYN-0000001"))
        self.assertEqual(frozenset({"SYN0000001"}),
                         ms.payment_references("breb SYN0000001"))

    def test_reference_contained_needs_a_whole_token(self) -> None:
        self.assertTrue(ms.reference_contained("SYN-FAC-0042",
                                               "Abono factura syn fac 0042 marzo"))
        self.assertFalse(ms.reference_contained("SYN-FAC-004",
                                                "Abono factura syn fac 0042"))
        self.assertFalse(ms.reference_contained("A1", "a1 cualquier"))


class ExplanationTests(unittest.TestCase):
    def test_tolerance_and_counterparty_read_in_plain_spanish(self) -> None:
        sentences = ms.explanation(
            ["amount_within_tolerance", "same_currency", "opposite_direction",
             "different_financial_account", "date_within_explicit_window",
             "same_counterparty_id"],
            date_distance_days=2, amount_difference=Decimal("1190.000000000000"))
        self.assertEqual([
            "Diferencia de $1.190 (posible retención o comisión)",
            "NIT del pagador coincide", "Fechas a 2 días",
            "Un ingreso frente a un egreso"], sentences)

    def test_exact_same_day(self) -> None:
        self.assertEqual(["Mismo valor", "Misma fecha"],
                         ms.explanation(["exact_amount"], date_distance_days=0,
                                        amount_difference=None))

    def test_format_cop_is_exact(self) -> None:
        self.assertEqual("$1.234.567,89", ms.format_cop(Decimal("1234567.89")))
        self.assertEqual("$0", ms.format_cop(Decimal("0")))
        with self.assertRaises(ValueError):
            ms.format_cop(Decimal("-1"))

    def test_ranking_prefers_more_signals_then_closer_dates(self) -> None:
        strong = ms.rank_key(["a", "b", "c"], 3, None, (1,))
        weak = ms.rank_key(["a", "b"], 0, None, (0,))
        near = ms.rank_key(["a", "b"], 0, Decimal("5"), (0,))
        nearer = ms.rank_key(["a", "b"], 0, Decimal("1"), (0,))
        self.assertLess(strong, weak)
        self.assertLess(nearer, near)


class RuleTests(unittest.TestCase):
    ACCOUNT = "11111111-2222-3333-4444-555555555555"

    def conditions(self, **overrides):
        raw = {"description_contains": "NIT FNC-SYN-NIT-0002",
               "financial_account_id": None, "direction": "inflow",
               "max_amount_difference": "2000", "currency": "COP"}
        raw.update(overrides)
        return ms.validated_conditions(raw)

    def test_conditions_are_normalised_and_closed(self) -> None:
        clean = self.conditions()
        self.assertEqual("nit fnc syn nit 0002", clean["description_contains"])
        self.assertEqual({"schema", "description_contains", "financial_account_id",
                          "direction", "max_amount_difference", "currency"},
                         set(clean))

    def test_float_tolerance_is_refused(self) -> None:
        with self.assertRaises(ms.RuleConditionError):
            self.conditions(max_amount_difference=1190.5)
        with self.assertRaises(ms.RuleConditionError):
            self.conditions(max_amount_difference="1e3")
        with self.assertRaises(ms.RuleConditionError):
            self.conditions(max_amount_difference="10000001")
        with self.assertRaises(ms.RuleConditionError):
            self.conditions(description_contains="--")

    def test_rule_matches_only_when_every_condition_holds(self) -> None:
        clean = self.conditions()
        bank = ms.RuleSide("Abono cliente NIT FNC-SYN-NIT-0002", self.ACCOUNT,
                           "inflow", "COP")
        invoice = ms.RuleSide("Factura SYN-FE-0001", "other", "outflow", "COP")
        self.assertTrue(ms.rule_matches(clean, bank, invoice, Decimal("1190")))
        self.assertFalse(ms.rule_matches(clean, bank, invoice, Decimal("2000.01")))
        outflow = ms.RuleSide(bank.description, self.ACCOUNT, "outflow", "COP")
        self.assertFalse(ms.rule_matches(clean, outflow, invoice, None))
        usd = ms.RuleSide(bank.description, self.ACCOUNT, "inflow", "USD")
        self.assertFalse(ms.rule_matches(clean, usd, invoice, None))
        scoped = self.conditions(financial_account_id=self.ACCOUNT.upper())
        self.assertEqual(self.ACCOUNT, scoped["financial_account_id"])
        elsewhere = ms.RuleSide(bank.description, "other-account", "inflow", "COP")
        self.assertFalse(ms.rule_matches(scoped, elsewhere, invoice, None))

    def test_suggested_pattern_prefers_the_counterparty(self) -> None:
        self.assertEqual("nit fnc syn nit 0002", ms.suggested_pattern(
            "Factura SYN-FE-0001 Cliente NIT FNC-SYN-NIT-0002", None))
        self.assertEqual("abono sintetico", ms.suggested_pattern(
            "Abono sintetico 2026-03", "REF-1"))


if __name__ == "__main__":
    unittest.main()
