from __future__ import annotations

import io
import json
import logging
import unittest

from fincilia_platform.observability import (
    JsonFormatter,
    correlation,
    log_event,
    valid_correlation_id,
)


class ObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(JsonFormatter("fincilia-api"))
        self.logger = logging.getLogger("fincilia.tests.observability")
        self.logger.handlers = [self.handler]
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)

    def payload(self) -> dict:
        return json.loads(self.stream.getvalue().splitlines()[-1])

    def test_only_allowlisted_fields_are_serialized(self) -> None:
        log_event(self.logger, logging.INFO, "http.request.completed",
                  request_id="request-12345678", method="GET",
                  route="/api/v1/companies/{company_id}", status_code=200,
                  duration_ms=12.5)
        payload = self.payload()
        self.assertEqual(payload["event"], "http.request.completed")
        self.assertEqual(payload["route"], "/api/v1/companies/{company_id}")
        self.assertNotIn("message", payload)

    def test_message_arguments_exception_and_unknown_extras_never_escape(self) -> None:
        secret = "Bearer synthetic-sensitive-token"
        try:
            raise RuntimeError("postgresql://user:secret@database/customer")
        except RuntimeError:
            self.logger.exception(secret, extra={"event": "worker.failure",
                                                  "forbidden": secret})
        rendered = self.stream.getvalue()
        self.assertNotIn(secret, rendered)
        self.assertNotIn("postgresql", rendered)
        self.assertNotIn("forbidden", rendered)
        self.assertEqual(self.payload()["event"], "worker.failure")

    def test_context_is_present_only_inside_scope(self) -> None:
        with correlation("request-12345678"):
            log_event(self.logger, logging.INFO, "test.inside")
        inside = self.payload()
        log_event(self.logger, logging.INFO, "test.outside")
        outside = self.payload()
        self.assertEqual(inside["correlation_id"], "request-12345678")
        self.assertNotIn("correlation_id", outside)

    def test_invalid_context_event_and_field_are_rejected(self) -> None:
        for value in (None, "short", "bad\nheader", "ü" * 20, "x" * 65):
            with self.subTest(value=value):
                self.assertFalse(valid_correlation_id(value))
        with self.assertRaises(ValueError):
            with correlation("bad\nvalue"):
                pass
        with self.assertRaises(ValueError):
            log_event(self.logger, logging.INFO, "Bad Event")
        with self.assertRaises(ValueError):
            log_event(self.logger, logging.INFO, "valid.event", body="forbidden")

    def test_long_or_multiline_allowlisted_values_are_omitted(self) -> None:
        log_event(self.logger, logging.WARNING, "http.request.completed",
                  route="x" * 161, outcome="line1\nline2")
        payload = self.payload()
        self.assertNotIn("route", payload)
        self.assertNotIn("outcome", payload)

    def test_formatter_rejects_an_unsafe_service_name(self) -> None:
        with self.assertRaises(ValueError):
            JsonFormatter("API with spaces")


if __name__ == "__main__":
    unittest.main()
