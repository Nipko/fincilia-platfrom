"""Ciclos esperados: fechas deterministas y atraso calculable.

La propiedad que sostiene todo: **ninguna funcion mira el reloj**. La fecha «de
hoy» entra como argumento, porque una que la mirara daria un resultado distinto
en cada ejecucion y haria imposible probar que el atraso se calcula bien.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.cycles import (  # noqa: E402
    MAX_PERIODS,
    CycleError,
    days_late,
    next_due,
    period_end_of,
    periods_between,
    validate_cycle,
)


class MonthlyTests(unittest.TestCase):
    def test_a_month_ends_on_its_last_day_whatever_that_is(self) -> None:
        # Febrero de un ano bisiesto es la prueba que delata un `+30 dias`.
        self.assertEqual(period_end_of(date(2026, 1, 1), "monthly", None),
                         date(2026, 1, 31))
        self.assertEqual(period_end_of(date(2026, 2, 1), "monthly", None),
                         date(2026, 2, 28))
        self.assertEqual(period_end_of(date(2028, 2, 1), "monthly", None),
                         date(2028, 2, 29))
        self.assertEqual(period_end_of(date(2026, 4, 1), "monthly", None),
                         date(2026, 4, 30))

    def test_the_due_date_counts_from_the_end_of_the_period(self) -> None:
        periods = periods_between(anchor=date(2026, 1, 1), until=date(2026, 3, 1),
                                  periodicity="monthly", due_day_offset=5,
                                  grace_days=3)
        january = periods[0]
        self.assertEqual(january.period_end, date(2026, 1, 31))
        self.assertEqual(january.due_on, date(2026, 2, 5))
        self.assertEqual(january.late_after, date(2026, 2, 8))

    def test_twelve_months_produce_twelve_periods_without_gaps(self) -> None:
        periods = periods_between(anchor=date(2026, 1, 1), until=date(2026, 12, 31),
                                  periodicity="monthly")
        self.assertEqual(len(periods), 12)
        for previous, following in zip(periods, periods[1:]):
            with self.subTest(month=following.period_start.month):
                self.assertEqual((following.period_start - previous.period_end).days, 1)


class OtherCadenceTests(unittest.TestCase):
    def test_a_fortnight_is_fifteen_days(self) -> None:
        periods = periods_between(anchor=date(2026, 1, 1), until=date(2026, 1, 31),
                                  periodicity="fortnightly")
        self.assertEqual(periods[0].period_end, date(2026, 1, 15))
        self.assertEqual(periods[1].period_start, date(2026, 1, 16))

    def test_a_week_is_seven_days(self) -> None:
        periods = periods_between(anchor=date(2026, 1, 5), until=date(2026, 1, 20),
                                  periodicity="weekly")
        self.assertEqual(periods[0].period_end, date(2026, 1, 11))
        self.assertEqual([p.period_start for p in periods],
                         [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)])

    def test_a_custom_cadence_uses_its_declared_days(self) -> None:
        periods = periods_between(anchor=date(2026, 1, 1), until=date(2026, 1, 25),
                                  periodicity="custom", custom_days=10)
        self.assertEqual(periods[0].period_end, date(2026, 1, 10))
        self.assertEqual(len(periods), 3)


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.january = periods_between(
            anchor=date(2026, 1, 1), until=date(2026, 1, 31),
            periodicity="monthly", due_day_offset=5, grace_days=3)[0]

    def test_inside_the_grace_period_it_is_still_pending(self) -> None:
        # Vence el 5 y la gracia llega al 8: el 7 todavia no es un atraso.
        self.assertEqual(self.january.state_on(date(2026, 2, 5)), "pending")
        self.assertEqual(self.january.state_on(date(2026, 2, 8)), "pending")

    def test_after_the_grace_period_it_is_late(self) -> None:
        self.assertEqual(self.january.state_on(date(2026, 2, 9)), "late")

    def test_something_that_arrived_is_never_late_again(self) -> None:
        # Llego tarde, pero llego. Seguir llamandolo atrasado contaria dos veces
        # el mismo problema.
        self.assertEqual(
            self.january.state_on(date(2026, 3, 1), satisfied=True), "satisfied")

    def test_days_late_discounts_the_grace(self) -> None:
        self.assertEqual(days_late(self.january, date(2026, 2, 8)), 0)
        self.assertEqual(days_late(self.january, date(2026, 2, 9)), 1)
        self.assertEqual(days_late(self.january, date(2026, 2, 18)), 10)


class NextDueTests(unittest.TestCase):
    def test_the_next_due_is_the_first_one_still_open(self) -> None:
        period = next_due(anchor=date(2026, 1, 1), today=date(2026, 2, 20),
                          periodicity="monthly", due_day_offset=5, grace_days=3)
        self.assertIsNotNone(period)
        self.assertEqual(period.period_start, date(2026, 2, 1))
        self.assertEqual(period.due_on, date(2026, 3, 5))

    def test_the_same_arguments_always_give_the_same_answer(self) -> None:
        arguments = {"anchor": date(2026, 1, 1), "today": date(2026, 6, 15),
                     "periodicity": "monthly"}
        self.assertEqual(next_due(**arguments).as_dict(), next_due(**arguments).as_dict())


class RefusalTests(unittest.TestCase):
    def test_a_custom_cadence_without_days_is_refused(self) -> None:
        self.assertTrue(validate_cycle("custom", None, 5, 3))
        with self.assertRaises(CycleError):
            periods_between(anchor=date(2026, 1, 1), until=date(2026, 2, 1),
                            periodicity="custom")

    def test_a_named_cadence_with_days_is_refused(self) -> None:
        self.assertTrue(validate_cycle("monthly", 10, 5, 3))

    def test_an_unknown_cadence_is_refused(self) -> None:
        self.assertTrue(validate_cycle("daily", None, 5, 3))
        with self.assertRaises(CycleError):
            periods_between(anchor=date(2026, 1, 1), until=date(2026, 2, 1),
                            periodicity="daily")

    def test_offsets_out_of_range_are_refused(self) -> None:
        self.assertTrue(validate_cycle("monthly", None, 500, 3))
        self.assertTrue(validate_cycle("monthly", None, 5, -1))

    def test_a_valid_cycle_reports_nothing(self) -> None:
        self.assertEqual(validate_cycle("monthly", None, 5, 3), [])
        self.assertEqual(validate_cycle("custom", 10, 0, 0), [])

    def test_an_end_before_the_anchor_produces_no_periods(self) -> None:
        self.assertEqual(
            periods_between(anchor=date(2026, 6, 1), until=date(2026, 1, 1),
                            periodicity="monthly"), ())

    def test_the_generator_is_bounded(self) -> None:
        # Sin techo, un ancla de hace veinte anos genera doscientos cuarenta
        # periodos que nadie pidio.
        periods = periods_between(anchor=date(1990, 1, 1), until=date(2030, 1, 1),
                                  periodicity="monthly")
        self.assertEqual(len(periods), MAX_PERIODS)


if __name__ == "__main__":
    unittest.main()
