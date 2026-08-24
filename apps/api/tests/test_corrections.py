"""Pruebas puras del borde tipado de FNC-CLN-001."""

from __future__ import annotations

import unittest
from decimal import Decimal

from fincilia_api.corrections import (CorrectionError, normalise_value,
                                      validate_reason)
from fincilia_contracts.release import digest_of


class TypedCorrectionTests(unittest.TestCase):
    def test_money_is_exact_fixed_point_and_never_float(self) -> None:
        typed = normalise_value("amount", "1234.5")
        self.assertEqual("1234.500000000000", typed.canonical)
        self.assertEqual(digest_of("1234.500000000000"), typed.digest)
        for invalid in (1234.5, Decimal("1234.5"), "1e3", "0", "-1", "NaN"):
            with self.subTest(invalid=invalid), self.assertRaises(CorrectionError):
                normalise_value("amount", invalid)

    def test_money_respects_numeric_38_12(self) -> None:
        maximum = "9" * 26 + "." + "9" * 12
        self.assertEqual(maximum, normalise_value("amount", maximum).canonical)
        for invalid in ("9" * 27, "1." + "1" * 13, ".5", "1,50"):
            with self.subTest(invalid=invalid), self.assertRaises(CorrectionError):
                normalise_value("amount", invalid)

    def test_currency_and_direction_are_closed(self) -> None:
        self.assertEqual("COP", normalise_value("currency", "cop").canonical)
        self.assertEqual("outflow", normalise_value("direction", "OUTFLOW").canonical)
        for field, value in (("currency", "CO"), ("currency", "C0P"),
                             ("direction", "debit"), ("kind", "payment")):
            with self.subTest(field=field, value=value), self.assertRaises(CorrectionError):
                normalise_value(field, value)

    def test_date_is_real_iso_not_only_a_pattern(self) -> None:
        self.assertEqual("2026-02-28",
                         normalise_value("accounting_date", "2026-02-28").canonical)
        for invalid in ("28/02/2026", "2026-02-30", "2026-2-3"):
            with self.subTest(invalid=invalid), self.assertRaises(CorrectionError):
                normalise_value("posted_on", invalid)

    def test_reason_is_allowlisted_and_bounded_in_bytes(self) -> None:
        self.assertEqual(("source_correction", "dato verificado"),
                         validate_reason("source_correction", " dato verificado "))
        for code, comment in (("invented", "valid"),
                              ("source_correction", ""),
                              ("source_correction", "á" * 251)):
            with self.subTest(code=code), self.assertRaises(CorrectionError):
                validate_reason(code, comment)


if __name__ == "__main__":
    unittest.main()
