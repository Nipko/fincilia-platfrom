"""FNC-SMB-006: periodos de carga y estado del recordatorio, sin base de datos."""

from __future__ import annotations

import datetime as dt
import unittest

from fincilia_api import upload_schedule
from fincilia_api.upload_schedule import (
    UploadScheduleError, change_schedule, period_for, reminder_state,
)


class UploadPeriodTests(unittest.TestCase):
    def test_weekly_periods_run_monday_to_sunday(self) -> None:
        period = period_for("weekly", dt.date(2026, 11, 4))  # miercoles
        self.assertEqual(dt.date(2026, 11, 2), period.start)
        self.assertEqual(dt.date(2026, 11, 8), period.end)
        self.assertEqual("2026-11-02 / 2026-11-08", period.label)
        self.assertEqual(period, period_for("weekly", dt.date(2026, 11, 8)))

    def test_biweekly_blocks_are_anchored_and_contiguous(self) -> None:
        first = period_for("biweekly", dt.date(2024, 1, 1))
        self.assertEqual((dt.date(2024, 1, 1), dt.date(2024, 1, 14)),
                         (first.start, first.end))
        day = dt.date(2026, 1, 1)
        previous = period_for("biweekly", day)
        for _ in range(60):
            day += dt.timedelta(days=1)
            current = period_for("biweekly", day)
            self.assertLessEqual(current.start, day)
            self.assertGreaterEqual(current.end, day)
            self.assertEqual(13, (current.end - current.start).days)
            if current != previous:
                self.assertEqual(previous.end + dt.timedelta(days=1), current.start)
            previous = current

    def test_monthly_periods_cover_the_calendar_month(self) -> None:
        february = period_for("monthly", dt.date(2028, 2, 15))
        self.assertEqual((dt.date(2028, 2, 1), dt.date(2028, 2, 29)),
                         (february.start, february.end))
        december = period_for("monthly", dt.date(2026, 12, 31))
        self.assertEqual(dt.date(2026, 12, 31), december.end)

    def test_unknown_cadence_fails_closed(self) -> None:
        with self.assertRaises(UploadScheduleError):
            period_for("daily", dt.date(2026, 11, 4))

    def test_reminder_only_inside_the_lead_window_and_never_after_upload(self) -> None:
        self.assertEqual("upcoming", reminder_state(
            "monthly", dt.date(2026, 11, 4), uploaded=False))
        self.assertEqual("due_soon", reminder_state(
            "monthly", dt.date(2026, 11, 25), uploaded=False))
        self.assertEqual("received", reminder_state(
            "monthly", dt.date(2026, 11, 25), uploaded=True))
        self.assertEqual("due_soon", reminder_state(
            "weekly", dt.date(2026, 11, 6), uploaded=False))
        self.assertEqual("upcoming", reminder_state(
            "weekly", dt.date(2026, 11, 3), uploaded=False))

    def test_external_channels_stay_off(self) -> None:
        # Gancho ADR-037: ningun adaptador externo para este recordatorio.
        self.assertEqual((), upload_schedule.EXTERNAL_CHANNELS)


class UploadScheduleCommandTests(unittest.TestCase):
    def test_only_owner_and_known_cadences_reach_the_database(self) -> None:
        with self.assertRaises(UploadScheduleError) as invalid:
            change_schedule(None, company_id="c", actor_id="a",  # type: ignore[arg-type]
                            roles=("owner",), cadence="daily")
        self.assertEqual("upload-cadence-invalid", invalid.exception.code)
        with self.assertRaises(UploadScheduleError) as refused:
            change_schedule(None, company_id="c", actor_id="a",  # type: ignore[arg-type]
                            roles=("preparer", "reviewer"), cadence="weekly")
        self.assertEqual(403, refused.exception.status)


if __name__ == "__main__":
    unittest.main()
