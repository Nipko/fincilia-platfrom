from __future__ import annotations

import datetime as dt
import unittest
from decimal import Decimal

from fincilia_api.reports import (
    ReportError, ReportWindow, fixed_decimal, report_csv,
)


class ReportContractTests(unittest.TestCase):
    def test_windows_are_inclusive_and_allowlisted(self) -> None:
        window = ReportWindow.validated(
            30, dt.date(2026, 8, 24), today=dt.date(2026, 8, 24))
        self.assertEqual(dt.date(2026, 7, 26), window.start)
        self.assertEqual(dt.date(2026, 8, 25), window.end_exclusive)
        for days in (30, 90, 180, 365):
            self.assertEqual(days, ReportWindow.validated(
                days, dt.date(2026, 8, 1), today=dt.date(2026, 8, 24)).days)
        with self.assertRaises(ReportError):
            ReportWindow.validated(
                31, dt.date(2026, 8, 1), today=dt.date(2026, 8, 24))

    def test_future_and_unsupported_historical_dates_fail_closed(self) -> None:
        with self.assertRaises(ReportError):
            ReportWindow.validated(
                90, dt.date(2026, 8, 25), today=dt.date(2026, 8, 24))
        with self.assertRaises(ReportError):
            ReportWindow.validated(
                90, dt.date(1999, 12, 31), today=dt.date(2026, 8, 24))

    def test_money_never_crosses_float(self) -> None:
        self.assertEqual("1234.560000000000", fixed_decimal(Decimal("1234.56")))
        self.assertEqual("0.000000000000", fixed_decimal(0))
        with self.assertRaises(TypeError):
            fixed_decimal(1.5)  # type: ignore[arg-type]

    def test_csv_is_bom_rfc4180_and_deterministically_ordered(self) -> None:
        report = {"money_series": [{
            "month": "2026-02-01", "currency": "COP", "movement_count": 2,
            "inflow_amount": "980000.000000000000",
            "outflow_amount": "1234.560000000000",
        }]}
        payload = report_csv(report)
        self.assertTrue(payload.startswith(b"\xef\xbb\xbfmonth,currency"))
        self.assertIn(b"\r\n2026-02-01,COP,2,980000.000000000000,1234.560000000000\r\n",
                      payload)
        self.assertEqual(payload, report_csv(report))


if __name__ == "__main__":
    unittest.main()
