"""Frontera HTTP de billing sin red ni proveedor real."""

from __future__ import annotations

import contextlib
import types
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from fincilia_api import billing, routes
from fincilia_api.security import Principal, ProblemError
from fincilia_api.stripe_billing import (
    CheckoutResult,
    PortalResult,
    StripeGatewayError,
    SubscriptionSnapshot,
    VerifiedStripeEvent,
)
from fincilia_platform.tokens import Claims


FIRM = "00000000-0000-4000-8000-000000000010"
SUBJECT = "00000000-0000-4000-8000-000000000020"
KEY = "00000000-0000-4000-8000-000000000030"


class FakeDatabase:
    @contextlib.contextmanager
    def session(self, **_scope):
        yield object()


class FakeGateway:
    def __init__(self) -> None:
        self.checkout_calls: list[dict] = []
        self.portal_calls: list[dict] = []
        self.verified: VerifiedStripeEvent | Exception | None = None
        self.raw: tuple[bytes, str] | None = None

    def create_checkout(self, **kwargs):
        self.checkout_calls.append(kwargs)
        return CheckoutResult(
            "cs_test_FNCBIL002HTTP", "https://checkout.stripe.com/c/pay/synthetic",
            1_800_000_000)

    def create_portal(self, **kwargs):
        self.portal_calls.append(kwargs)
        return PortalResult("https://billing.stripe.com/p/session/synthetic")

    def verify_and_resolve(self, payload: bytes, signature: str):
        self.raw = (payload, signature)
        if isinstance(self.verified, Exception):
            raise self.verified
        return self.verified


def principal() -> Principal:
    return Principal(
        subject_id=SUBJECT, display_name="Synthetic Manager",
        claims=Claims(SUBJECT, "test", "test", 1, 2, "synthetic"),
    )


def make_client(gateway: FakeGateway, *, enabled: bool = True) -> TestClient:
    app = FastAPI()

    @app.exception_handler(ProblemError)
    async def problem_error_handler(_request, error: ProblemError) -> JSONResponse:
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.as_dict(),
            media_type="application/problem+json",
        )

    app.include_router(routes.router)
    app.state.settings = types.SimpleNamespace(payments_enabled=enabled)
    app.state.database = FakeDatabase()
    app.state.payment_gateway = gateway
    app.dependency_overrides[routes.principal_dependency] = principal
    return TestClient(app)


class BillingHttpTests(unittest.TestCase):
    def test_billing_error_can_cross_a_transaction_context(self) -> None:
        @contextlib.contextmanager
        def transaction():
            yield

        with self.assertRaisesRegex(billing.BillingError, "billing-conflict"):
            with transaction():
                raise billing.BillingError(
                    "billing-conflict", "synthetic conflict", 409)

    def test_checkout_uses_only_server_resolved_commercial_fields(self) -> None:
        gateway = FakeGateway()
        reservation = billing.CheckoutReservation(
            "00000000-0000-4000-8000-000000000040",
            "00000000-0000-4000-8000-000000000050",
            "price_FNCBIL002HTTP", None, None, "reserved")
        with (
            patch.object(routes.billing, "reserve_checkout", return_value=reservation),
            patch.object(routes.billing, "complete_checkout", return_value="ready") as complete,
            patch.object(routes.repository, "record_audit"),
            make_client(gateway) as client,
        ):
            response = client.post(
                f"/api/v1/firms/{FIRM}/billing/checkout",
                json={"plan_code": "business", "idempotency_key": KEY})
            injected = client.post(
                f"/api/v1/firms/{FIRM}/billing/checkout",
                json={"plan_code": "business", "idempotency_key": KEY,
                      "unit_amount_minor": 1, "currency": "USD"})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(
            "https://checkout.stripe.com/c/pay/synthetic",
            response.json()["checkout_url"])
        self.assertEqual(422, injected.status_code, injected.text)
        self.assertEqual("price_FNCBIL002HTTP", gateway.checkout_calls[0]["price_id"])
        self.assertNotIn("amount", repr(gateway.checkout_calls[0]).lower())
        self.assertNotIn("currency", repr(gateway.checkout_calls[0]).lower())
        complete.assert_called_once()

    def test_portal_never_exposes_the_customer_reference(self) -> None:
        gateway = FakeGateway()
        with (
            patch.object(routes.billing, "portal_customer",
                         return_value="cus_FNCBIL002HTTP"),
            patch.object(routes.repository, "record_audit"),
            make_client(gateway) as client,
        ):
            response = client.post(
                f"/api/v1/firms/{FIRM}/billing/portal",
                json={"idempotency_key": KEY})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(
            {"portal_url": "https://billing.stripe.com/p/session/synthetic"},
            response.json())
        self.assertNotIn("cus_", response.text)

    def test_signed_webhook_passes_the_exact_raw_body_to_one_transaction(self) -> None:
        gateway = FakeGateway()
        gateway.verified = VerifiedStripeEvent(
            "evt_FNCBIL002HTTP", "customer.subscription.updated", 1_800_000_000,
            SubscriptionSnapshot(
                "cus_FNCBIL002HTTP", "sub_FNCBIL002HTTP", FIRM,
                "business", "price_FNCBIL002HTTP", "active", None))
        raw = b'{"synthetic":true,"spacing":  "preserved"}'
        with (
            patch.object(routes.billing, "apply_verified_subscription",
                         return_value="materialized") as apply_snapshot,
            make_client(gateway) as client,
        ):
            response = client.post(
                "/api/v1/billing/webhooks/stripe", content=raw,
                headers={"Stripe-Signature": "t=1,v1=synthetic"})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(
            {"received": True, "outcome": "materialized"}, response.json())
        self.assertEqual((raw, "t=1,v1=synthetic"), gateway.raw)
        self.assertEqual(raw, apply_snapshot.call_args.kwargs["payload"])

    def test_webhook_distinguishes_rejection_from_retryable_provider_failure(self) -> None:
        cases = (
            ("stripe-webhook-invalid-signature", 400),
            ("stripe-webhook-resolution-unavailable", 503),
        )
        for code, expected in cases:
            with self.subTest(code=code):
                gateway = FakeGateway()
                gateway.verified = StripeGatewayError(code)
                with make_client(gateway) as client:
                    response = client.post(
                        "/api/v1/billing/webhooks/stripe", content=b"{}",
                        headers={"Stripe-Signature": "t=1,v1=synthetic"})
                self.assertEqual(expected, response.status_code, response.text)
                self.assertNotIn("provider detail", response.text)

    def test_webhook_database_outage_is_retryable(self) -> None:
        gateway = FakeGateway()
        gateway.verified = VerifiedStripeEvent(
            "evt_FNCBIL002HTTP", "customer.subscription.updated", 1_800_000_000,
            SubscriptionSnapshot(
                "cus_FNCBIL002HTTP", "sub_FNCBIL002HTTP", FIRM,
                "business", "price_FNCBIL002HTTP", "active", None))
        unavailable = billing.BillingError(
            "billing-temporarily-unavailable",
            "billing persistence is temporarily unavailable",
            503,
        )
        with (
            patch.object(routes.billing, "apply_verified_subscription",
                         side_effect=unavailable),
            make_client(gateway) as client,
        ):
            response = client.post(
                "/api/v1/billing/webhooks/stripe", content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=synthetic"})
        self.assertEqual(503, response.status_code, response.text)
        self.assertTrue(
            response.json()["type"].endswith("/billing-temporarily-unavailable"))

    def test_disabled_or_oversized_webhook_fails_before_persistence(self) -> None:
        gateway = FakeGateway()
        with make_client(gateway, enabled=False) as client:
            disabled = client.post(
                "/api/v1/billing/webhooks/stripe", content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=synthetic"})
        self.assertEqual(503, disabled.status_code, disabled.text)
        self.assertIsNone(gateway.raw)
        with make_client(gateway) as client:
            oversized = client.post(
                "/api/v1/billing/webhooks/stripe", content=b"x" * 262_145,
                headers={"Stripe-Signature": "t=1,v1=synthetic"})
        self.assertEqual(413, oversized.status_code, oversized.text)
        self.assertIsNone(gateway.raw)


if __name__ == "__main__":
    unittest.main()
