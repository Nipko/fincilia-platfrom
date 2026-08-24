"""Pruebas puras del CSV canonico FNC-EXP-001."""

from __future__ import annotations

import csv
import datetime as dt
import io
import unittest
import uuid
from decimal import Decimal
from unittest.mock import ANY, patch

from fincilia_api.exports import (
    CSV_HEADERS,
    ExportError,
    csv_chunks,
    preflight_export,
    spreadsheet_safe,
)


DATASET_ID = str(uuid.uuid4())


def published_dataset(**overrides):
    value = {
        "dataset_version_id": DATASET_ID,
        "state": "published",
        "completeness_state": "verified",
        "lineage_state": "complete",
        "record_count": 2,
        "movement_count": 2,
        "rejected_count": 0,
        "canonical_schema_version": "1.0.0",
        "manifest": {
            "reproduction_key": "a" * 64,
            "reproducible": True,
        },
    }
    value.update(overrides)
    return value


def row(*, ordinal=1, description="Comision cafe", reference="REF-01"):
    return (
        ordinal,
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        dt.date(2026, 2, 13),
        dt.date(2026, 2, 14),
        None,
        None,
        Decimal("1234.56"),
        "COP",
        "inflow",
        "payment",
        description,
        reference,
        "confirmed",
        "1.0.0",
        "fnc-p3-mapping-0.1.0",
        "complete",
    )


class ExportPreflightTests(unittest.TestCase):
    def test_only_a_fully_published_dataset_is_eligible(self) -> None:
        with patch("fincilia_api.exports.datasets.load_dataset",
                   return_value=published_dataset()) as loaded:
            descriptor = preflight_export(object(), DATASET_ID)
        loaded.assert_called_once_with(ANY, DATASET_ID)
        self.assertEqual(2, descriptor.row_count)
        self.assertEqual("fincilia-canonico-" + DATASET_ID[:12] + ".csv",
                         descriptor.filename)

    def test_every_incomplete_axis_fails_closed(self) -> None:
        cases = (
            {"state": "validated"},
            {"completeness_state": "mismatch"},
            {"lineage_state": "invalidated"},
            {"rejected_count": 1},
            {"record_count": 3},
            {"manifest": None},
            {"manifest": {"reproduction_key": "a" * 64,
                          "reproducible": False}},
        )
        for changes in cases:
            with self.subTest(changes=changes), patch(
                    "fincilia_api.exports.datasets.load_dataset",
                    return_value=published_dataset(**changes)):
                with self.assertRaises(ExportError) as raised:
                    preflight_export(object(), DATASET_ID)
                self.assertEqual("dataset-export-unavailable",
                                 raised.exception.code)

    def test_unknown_is_neutral(self) -> None:
        with patch("fincilia_api.exports.datasets.load_dataset", return_value=None):
            with self.assertRaises(ExportError) as raised:
                preflight_export(object(), DATASET_ID)
        self.assertEqual("dataset-unknown", raised.exception.code)


class CsvTests(unittest.TestCase):
    def decode(self, rows, *, batch_size=1):
        payload = b"".join(csv_chunks(rows, batch_size=batch_size))
        return payload, list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))

    def test_money_dates_unicode_quotes_and_newlines_are_exact(self) -> None:
        payload, parsed = self.decode([
            row(description='Comision "cafe"\r\nBogota', reference="Ñ-01"),
        ])
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(list(CSV_HEADERS), parsed[0])
        self.assertEqual("1234.560000000000", parsed[1][6])
        self.assertEqual("2026-02-13", parsed[1][2])
        self.assertEqual('Comision "cafe"\r\nBogota', parsed[1][10])
        self.assertEqual("Ñ-01", parsed[1][11])

    def test_formula_prefixes_are_text_and_numeric_columns_are_untouched(self) -> None:
        for hostile in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "  =1+1"):
            with self.subTest(hostile=hostile):
                _payload, parsed = self.decode([
                    row(description=hostile, reference=hostile),
                ])
                self.assertEqual("'" + hostile, parsed[1][10])
                self.assertEqual("'" + hostile, parsed[1][11])
                self.assertEqual("1234.560000000000", parsed[1][6])

    def test_same_dataset_rows_produce_identical_bytes_across_batch_sizes(self) -> None:
        rows = [row(ordinal=1), row(ordinal=2, description="Segunda")]
        one, _ = self.decode(rows, batch_size=1)
        many, _ = self.decode(rows, batch_size=100)
        self.assertEqual(one, many)
        self.assertEqual(1, one.count(b"\xef\xbb\xbf"))

    def test_empty_export_still_has_a_single_header(self) -> None:
        _payload, parsed = self.decode([], batch_size=2)
        self.assertEqual([list(CSV_HEADERS)], parsed)

    def test_batch_size_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            list(csv_chunks([], batch_size=0))

    def test_safe_text_leaves_regular_values_and_nulls_alone(self) -> None:
        self.assertEqual("", spreadsheet_safe(None))
        self.assertEqual("Pago sintetico", spreadsheet_safe("Pago sintetico"))


if __name__ == "__main__":
    unittest.main()
