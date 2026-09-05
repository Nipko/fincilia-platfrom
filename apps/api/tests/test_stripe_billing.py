"""Contrato puro de Stripe: sin red, credenciales ni objetos financieros."""

from __future__ import annotations

import types
import unittest

from fincilia_api.stripe_billing import (
    StripeGatewayError,
    StripePaymentGateway,
)


class FakeEndpoint:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[object, object | None]] = []

    def create(self, params=None, options=None):
        self.calls.append((params, options))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def retrieve(self, identifier, params=None, options=None):
        self.calls.append((identifier, options))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def fake_client(*, checkout: object, portal: object,
                subscription: object) -> object:
    return types.SimpleNamespace(v1=types.SimpleNamespace(
        checkout=types.SimpleNamespace(sessions=FakeEndpoint(checkout)),
        billing_portal=types.SimpleNamespace(sessions=FakeEndpoint(portal)),
        subscriptions=FakeEndpoint(subscription),
    ))


def gateway(client: object, event: object | None = None) -> StripePaymentGateway:
    def construct(_payload, _signature, _secret, tolerance):
        if isinstance(event, Exception):
            raise event
        return event
    return StripePaymentGateway(
        secret_key="sk_test_synthetic_1234567890",
        webhook_secret="whsec_synthetic_1234567890",
        public_origin="https://fincilia.com",
        client=client,
        webhook_constructor=construct,
    )


class StripeGatewayTests(unittest.TestCase):
    def test_checkout_uses_one_server_price_and_no_client_amount(self) -> None:
        client = fake_client(
            checkout=types.SimpleNamespace(
                id="cs_test_synthetic123", url="https://checkout.stripe.com/c/pay/test",
                expires_at=1_800_000_000),
            portal=types.SimpleNamespace(url="https://billing.stripe.com/p/session/test"),
            subscription={})
        result = gateway(client).create_checkout(
            price_id="price_synthetic123", firm_id="firm-synthetic",
            plan_code="accountant", plan_version_id="plan-synthetic",
            idempotency_key="00000000-0000-4000-8000-000000000001",
            customer_id=None)
        self.assertEqual("cs_test_synthetic123", result.session_id)
        params, options = client.v1.checkout.sessions.calls[0]
        self.assertEqual("subscription", params["mode"])
        self.assertEqual(
            [{"price": "price_synthetic123", "quantity": 1}], params["line_items"])
        self.assertNotIn("amount", repr(params).lower())
        self.assertNotIn("currency", repr(params).lower())
        self.assertEqual("accountant", params["subscription_data"]["metadata"][
            "fincilia_plan_code"])
        self.assertNotIn("customer", params)
        self.assertEqual(
            "00000000-0000-4000-8000-000000000001",
            options["idempotency_key"])

    def test_existing_customer_and_tax_are_explicit(self) -> None:
        client = fake_client(
            checkout=types.SimpleNamespace(
                id="cs_test_synthetic123", url="https://checkout.stripe.com/c/pay/test",
                expires_at=1_800_000_000), portal=object(), subscription={})
        configured = StripePaymentGateway(
            secret_key="synthetic", webhook_secret="synthetic",
            public_origin="https://fincilia.com", automatic_tax_enabled=True,
            client=client, webhook_constructor=lambda *_args, **_kwargs: {})
        configured.create_checkout(
            price_id="price_synthetic123", firm_id="firm-synthetic",
            plan_code="starter", plan_version_id="plan-synthetic",
            idempotency_key="key", customer_id="cus_synthetic123")
        params = client.v1.checkout.sessions.calls[0][0]
        self.assertEqual("cus_synthetic123", params["customer"])
        self.assertEqual({"enabled": True}, params["automatic_tax"])

    def test_provider_redirect_is_allowlisted(self) -> None:
        client = fake_client(
            checkout=types.SimpleNamespace(
                id="cs_test_synthetic123", url="https://evil.example/collect",
                expires_at=1_800_000_000), portal=object(), subscription={})
        with self.assertRaisesRegex(StripeGatewayError,
                                    "stripe-checkout-invalid-response"):
            gateway(client).create_checkout(
                price_id="price_synthetic123", firm_id="firm-synthetic",
                plan_code="starter", plan_version_id="plan-synthetic",
                idempotency_key="key", customer_id=None)

    def test_portal_returns_only_an_allowlisted_url(self) -> None:
        client = fake_client(
            checkout=object(),
            portal=types.SimpleNamespace(
                url="https://billing.stripe.com/p/session/synthetic"),
            subscription={})
        result = gateway(client).create_portal(
            customer_id="cus_synthetic123", idempotency_key="key")
        self.assertEqual(
            "https://billing.stripe.com/p/session/synthetic", result.url)

    def test_verified_event_is_resolved_to_current_subscription(self) -> None:
        event = {
            "id": "evt_synthetic123", "type": "customer.subscription.updated",
            "created": 1_800_000_000,
            "data": {"object": {"id": "sub_synthetic123"}},
        }
        current = {
            "id": "sub_synthetic123", "customer": "cus_synthetic123",
            "status": "active", "trial_end": None,
            "metadata": {
                "fincilia_firm_id": "00000000-0000-4000-8000-000000000010",
                "fincilia_plan_code": "business",
            },
            "items": {"data": [{"price": {"id": "price_synthetic123"}}]},
        }
        client = fake_client(checkout=object(), portal=object(), subscription=current)
        verified = gateway(client, event).verify_and_resolve(b"{}", "t=1,v1=fake")
        self.assertEqual("evt_synthetic123", verified.event_id)
        self.assertEqual("active", verified.subscription.status)
        self.assertEqual("price_synthetic123", verified.subscription.price_id)
        self.assertEqual("sub_synthetic123", client.v1.subscriptions.calls[0][0])

    def test_unsubscribed_event_is_verified_but_not_resolved(self) -> None:
        event = {"id": "evt_synthetic123", "type": "charge.refunded",
                 "created": 1_800_000_000, "data": {"object": {}}}
        client = fake_client(checkout=object(), portal=object(), subscription=AssertionError())
        verified = gateway(client, event).verify_and_resolve(b"{}", "valid")
        self.assertIsNone(verified.subscription)
        self.assertEqual([], client.v1.subscriptions.calls)

    def test_bad_signature_is_a_stable_failure_without_provider_detail(self) -> None:
        client = fake_client(checkout=object(), portal=object(), subscription={})
        with self.assertRaisesRegex(
                StripeGatewayError, "stripe-webhook-invalid-signature"):
            gateway(client, ValueError("provider secret detail")).verify_and_resolve(
                b"{}", "invalid")

    def test_temporary_subscription_lookup_failure_is_retryable(self) -> None:
        event = {
            "id": "evt_synthetic123", "type": "customer.subscription.updated",
            "created": 1_800_000_000,
            "data": {"object": {"id": "sub_synthetic123"}},
        }
        client = fake_client(
            checkout=object(), portal=object(),
            subscription=TimeoutError("provider detail"))
        with self.assertRaisesRegex(
                StripeGatewayError, "stripe-webhook-resolution-unavailable"):
            gateway(client, event).verify_and_resolve(b"{}", "valid")

    def test_deleted_subscription_uses_signed_final_snapshot(self) -> None:
        deleted = {
            "id": "sub_synthetic123", "customer": "cus_synthetic123",
            "status": "canceled", "trial_end": None,
            "metadata": {
                "fincilia_firm_id": "00000000-0000-4000-8000-000000000010",
                "fincilia_plan_code": "business",
            },
            "items": {"data": [{"price": {"id": "price_synthetic123"}}]},
        }
        event = {
            "id": "evt_synthetic123", "type": "customer.subscription.deleted",
            "created": 1_800_000_000, "data": {"object": deleted},
        }
        client = fake_client(
            checkout=object(), portal=object(),
            subscription=AssertionError("must not retrieve a deleted resource"))
        verified = gateway(client, event).verify_and_resolve(b"{}", "valid")
        self.assertEqual("canceled", verified.subscription.status)
        self.assertEqual([], client.v1.subscriptions.calls)


if __name__ == "__main__":
    unittest.main()
