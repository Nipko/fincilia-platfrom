"""Frontera minima y verificable con Stripe.

Stripe aloja Checkout y Customer Portal. Fincilia nunca recibe PAN/CVV y el
resultado del navegador no activa capacidad: solo un evento con firma valida
puede materializar el estado comercial. El SDK se importa al construir el
adaptador, de modo que la aplicacion apagada no inicializa proveedor ni egress.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


STRIPE_API_VERSION = "2026-08-26.dahlia"
SUPPORTED_EVENT_TYPES = frozenset({
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
})
CHECKOUT_HOSTS = frozenset({"checkout.stripe.com"})
PORTAL_HOSTS = frozenset({"billing.stripe.com"})


class StripeGatewayError(RuntimeError):
    """Fallo allowlisted; nunca contiene cuerpo, clave ni mensaje de Stripe."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CheckoutResult:
    session_id: str
    url: str
    expires_at: int


@dataclass(frozen=True)
class PortalResult:
    url: str


@dataclass(frozen=True)
class SubscriptionSnapshot:
    customer_id: str
    subscription_id: str
    firm_id: str
    plan_code: str
    price_id: str
    status: str
    trial_end: int | None


@dataclass(frozen=True)
class VerifiedStripeEvent:
    event_id: str
    event_type: str
    created: int
    subscription: SubscriptionSnapshot | None


def _mapping(value: object, *, code: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise StripeGatewayError(code)


def _nonempty(value: object, *, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise StripeGatewayError(code)
    return value


def _provider_url(value: object, hosts: frozenset[str], code: str) -> str:
    url = _nonempty(value, code=code)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username:
        raise StripeGatewayError(code)
    return url


class StripePaymentGateway:
    """Adaptador SDK con API fijada, retries acotados y respuestas minimizadas."""

    def __init__(self, *, secret_key: str, webhook_secret: str,
                 public_origin: str, automatic_tax_enabled: bool = False,
                 client: object | None = None,
                 webhook_constructor: Callable[..., object] | None = None) -> None:
        if client is None or webhook_constructor is None:
            import stripe  # type: ignore[import-not-found]

            client = client or stripe.StripeClient(
                secret_key, stripe_version=STRIPE_API_VERSION,
                max_network_retries=2)
            webhook_constructor = webhook_constructor or stripe.Webhook.construct_event
        self._client = client
        self._construct_event = webhook_constructor
        self._webhook_secret = webhook_secret
        self._origin = public_origin.rstrip("/")
        self._automatic_tax = automatic_tax_enabled

    def create_checkout(self, *, price_id: str, firm_id: str, plan_code: str,
                        plan_version_id: str, idempotency_key: str,
                        customer_id: str | None) -> CheckoutResult:
        metadata = {
            "fincilia_firm_id": firm_id,
            "fincilia_plan_code": plan_code,
            "fincilia_plan_version_id": plan_version_id,
        }
        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": firm_id,
            "metadata": metadata,
            "subscription_data": {"metadata": metadata},
            "success_url": f"{self._origin}/cuenta?checkout=success",
            "cancel_url": f"{self._origin}/cuenta?checkout=cancel",
        }
        if customer_id:
            params["customer"] = customer_id
        if self._automatic_tax:
            params["automatic_tax"] = {"enabled": True}
        try:
            session = self._client.v1.checkout.sessions.create(  # type: ignore[attr-defined]
                params, {"idempotency_key": idempotency_key})
            session_id = _nonempty(getattr(session, "id", None),
                                   code="stripe-checkout-invalid-response")
            if not session_id.startswith("cs_"):
                raise StripeGatewayError("stripe-checkout-invalid-response")
            url = _provider_url(getattr(session, "url", None), CHECKOUT_HOSTS,
                                "stripe-checkout-invalid-response")
            expires_at = getattr(session, "expires_at", None)
            if not isinstance(expires_at, int) or expires_at <= 0:
                raise StripeGatewayError("stripe-checkout-invalid-response")
            return CheckoutResult(session_id, url, expires_at)
        except StripeGatewayError:
            raise
        except Exception as error:  # noqa: BLE001 - frontera de proveedor
            raise StripeGatewayError("stripe-checkout-unavailable") from error

    def create_portal(self, *, customer_id: str,
                      idempotency_key: str) -> PortalResult:
        try:
            session = self._client.v1.billing_portal.sessions.create(  # type: ignore[attr-defined]
                {"customer": customer_id,
                 "return_url": f"{self._origin}/cuenta"},
                {"idempotency_key": idempotency_key})
            return PortalResult(_provider_url(
                getattr(session, "url", None), PORTAL_HOSTS,
                "stripe-portal-invalid-response"))
        except StripeGatewayError:
            raise
        except Exception as error:  # noqa: BLE001 - frontera de proveedor
            raise StripeGatewayError("stripe-portal-unavailable") from error

    def verify_and_resolve(self, payload: bytes,
                           signature_header: str) -> VerifiedStripeEvent:
        """Verifica el cuerpo exacto y relee la suscripcion vigente en Stripe.

        Releer el snapshot hace que el orden de entrega de eventos no determine
        el estado final. El payload firmado sirve para localizar el recurso, no
        para confiar en un estado historico que pudo llegar tarde.
        """
        try:
            raw_event = self._construct_event(
                payload, signature_header, self._webhook_secret, tolerance=300)
        except Exception as error:  # noqa: BLE001 - la firma es frontera externa
            raise StripeGatewayError("stripe-webhook-invalid-signature") from error
        try:
            event = _mapping(raw_event, code="stripe-webhook-invalid-event")
            event_id = _nonempty(event.get("id"), code="stripe-webhook-invalid-event")
            event_type = _nonempty(event.get("type"), code="stripe-webhook-invalid-event")
            created = event.get("created")
            if not event_id.startswith("evt_") or not isinstance(created, int):
                raise StripeGatewayError("stripe-webhook-invalid-event")
            if event_type not in SUPPORTED_EVENT_TYPES:
                return VerifiedStripeEvent(event_id, event_type, created, None)
            subscription_id = self._subscription_id(event_type, event)
            if subscription_id is None:
                return VerifiedStripeEvent(event_id, event_type, created, None)
            if event_type == "customer.subscription.deleted":
                data = _mapping(
                    event.get("data"), code="stripe-webhook-invalid-event")
                subscription = _mapping(
                    data.get("object"), code="stripe-webhook-invalid-event")
            else:
                try:
                    subscription = self._client.v1.subscriptions.retrieve(  # type: ignore[attr-defined]
                        subscription_id)
                except Exception as error:  # noqa: BLE001 - proveedor externo
                    raise StripeGatewayError(
                        "stripe-webhook-resolution-unavailable") from error
            snapshot = self._snapshot(subscription)
            if snapshot.subscription_id != subscription_id:
                raise StripeGatewayError("stripe-subscription-invalid-response")
            if event_type == "customer.subscription.deleted" and snapshot.status != "canceled":
                raise StripeGatewayError("stripe-webhook-invalid-event")
            return VerifiedStripeEvent(event_id, event_type, created, snapshot)
        except StripeGatewayError:
            raise
        except Exception as error:  # noqa: BLE001 - firma/SDK no salen al cliente
            raise StripeGatewayError("stripe-webhook-invalid-event") from error

    @staticmethod
    def _subscription_id(event_type: str,
                         event: Mapping[str, Any]) -> str | None:
        data = _mapping(event.get("data"), code="stripe-webhook-invalid-event")
        obj = _mapping(data.get("object"), code="stripe-webhook-invalid-event")
        candidate: object | None
        if event_type.startswith("customer.subscription."):
            candidate = obj.get("id")
        elif event_type.startswith("checkout.session."):
            candidate = obj.get("subscription")
        else:
            candidate = obj.get("subscription")
            if candidate is None:
                parent = obj.get("parent")
                if isinstance(parent, Mapping):
                    details = parent.get("subscription_details")
                    if isinstance(details, Mapping):
                        candidate = details.get("subscription")
        if candidate is None:
            return None
        value = _nonempty(candidate, code="stripe-webhook-invalid-event")
        if not value.startswith("sub_"):
            raise StripeGatewayError("stripe-webhook-invalid-event")
        return value

    @staticmethod
    def _snapshot(value: object) -> SubscriptionSnapshot:
        subscription = _mapping(value, code="stripe-subscription-invalid-response")
        metadata = _mapping(
            subscription.get("metadata"), code="stripe-subscription-invalid-response")
        items = _mapping(
            subscription.get("items"), code="stripe-subscription-invalid-response")
        rows = items.get("data")
        if not isinstance(rows, list) or len(rows) != 1:
            raise StripeGatewayError("stripe-subscription-invalid-response")
        item = _mapping(rows[0], code="stripe-subscription-invalid-response")
        price = _mapping(item.get("price"), code="stripe-subscription-invalid-response")
        trial_end = subscription.get("trial_end")
        if trial_end is not None and not isinstance(trial_end, int):
            raise StripeGatewayError("stripe-subscription-invalid-response")
        customer_id = _nonempty(
            subscription.get("customer"), code="stripe-subscription-invalid-response")
        subscription_id = _nonempty(
            subscription.get("id"), code="stripe-subscription-invalid-response")
        price_id = _nonempty(
            price.get("id"), code="stripe-subscription-invalid-response")
        if (not customer_id.startswith("cus_")
                or not subscription_id.startswith("sub_")
                or not price_id.startswith("price_")):
            raise StripeGatewayError("stripe-subscription-invalid-response")
        return SubscriptionSnapshot(
            customer_id=customer_id,
            subscription_id=subscription_id,
            firm_id=_nonempty(
                metadata.get("fincilia_firm_id"), code="stripe-subscription-invalid-response"),
            plan_code=_nonempty(
                metadata.get("fincilia_plan_code"), code="stripe-subscription-invalid-response"),
            price_id=price_id,
            status=_nonempty(
                subscription.get("status"), code="stripe-subscription-invalid-response"),
            trial_end=trial_end,
        )
