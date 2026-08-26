from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fincilia_api.audit import decode_cursor, encode_cursor, validate_filter


class AuditQueryContractTests(unittest.TestCase):
    def test_cursor_round_trips_exact_ordering_key(self) -> None:
        occurred = datetime(2026, 8, 25, 12, 30, 1, 123456,
                            tzinfo=timezone.utc)
        event_id = str(uuid.uuid4())
        decoded = decode_cursor(encode_cursor(occurred, event_id))
        self.assertEqual(occurred, decoded.occurred_at)
        self.assertEqual(event_id, decoded.audit_event_id)

    def test_cursor_rejects_malformed_or_noncanonical_payloads(self) -> None:
        for value in ("not+base64", "%%%", "e30", "a" * 257):
            with self.subTest(value=value[:12]), self.assertRaisesRegex(
                    ValueError, "cursor"):
                decode_cursor(value)

    def test_filters_are_exact_and_bounded(self) -> None:
        self.assertEqual("document.upload",
                         validate_filter("document.upload", field="action"))
        self.assertEqual("denied", validate_filter("denied", field="outcome"))
        for value, field in (("DENIED", "outcome"), ("a b", "action"),
                             ("../document", "resource_kind")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_filter(value, field=field)


if __name__ == "__main__":
    unittest.main()
