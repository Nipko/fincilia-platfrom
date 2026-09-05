"""Proteccion de destinos, render cerrado y adaptador AWS SES.

El correo existe en claro solo entre ``decrypt`` y ``send_email`` dentro del
worker. Nunca se retorna, persiste o incorpora a excepciones. SES no ofrece una
clave de idempotencia para ``SendEmail``: un timeout queda ``uncertain`` y no se
reenvia a ciegas.
"""

from __future__ import annotations

import base64
import hashlib
import html
import re
from dataclasses import dataclass
from typing import Any, Mapping

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from .identity_refs import IdentityReferenceError, canonical_email


TEMPLATE_CODES = frozenset({
    "period_due_soon", "period_due_today", "period_in_grace", "period_overdue",
})
LOCALES = frozenset({"es-CO", "en-US"})
CONTEXT_KEYS = frozenset({"period_label", "due_on", "action_url"})
KMS_CONTEXT = {"purpose": "fincilia-notification-destination-v1"}
RETRYABLE_CODES = frozenset({
    "TooManyRequestsException", "LimitExceededException", "ThrottlingException",
    "ServiceUnavailableException", "InternalServiceErrorException",
})
ADDRESS_REF = re.compile(r"^hmac-sha256:v1:[0-9a-f]{64}$")


class DeliveryError(Exception):
    def __init__(self, code: str, failure_class: str) -> None:
        super().__init__("notification delivery failed")
        self.code = code
        self.failure_class = failure_class


@dataclass(frozen=True)
class EncryptedDestination:
    ciphertext: bytes
    address_ref: str
    kms_key_ref: str


@dataclass(frozen=True)
class RenderedMessage:
    subject: str
    text: str
    html: str


def _validate_context(context: Mapping[str, Any]) -> dict[str, str]:
    if set(context) != CONTEXT_KEYS or any(
            not isinstance(context[key], str) for key in CONTEXT_KEYS):
        raise DeliveryError("template_context_invalid", "fatal")
    period = context["period_label"]
    due_on = context["due_on"]
    action_url = context["action_url"]
    if not 3 <= len(period) <= 64 or len(due_on) != 10 \
            or not action_url.startswith("/recordatorios?empresa=") \
            or len(action_url) > 120:
        raise DeliveryError("template_context_invalid", "fatal")
    return {"period_label": period, "due_on": due_on, "action_url": action_url}


def render_message(*, template_code: str, locale: str,
                   context: Mapping[str, Any], public_origin: str) -> RenderedMessage:
    if template_code not in TEMPLATE_CODES or locale not in LOCALES \
            or not public_origin.startswith("https://") or "/" in public_origin[8:]:
        raise DeliveryError("template_configuration_invalid", "fatal")
    safe = _validate_context(context)
    url = public_origin + safe["action_url"]
    if locale == "es-CO":
        subjects = {
            "period_due_soon": "Tu ciclo contable vence pronto",
            "period_due_today": "Tu ciclo contable vence hoy",
            "period_in_grace": "Tu ciclo contable esta en gracia",
            "period_overdue": "Tu ciclo contable esta vencido",
        }
        lead = "Revisa el ciclo operativo"
        due = "Fecha esperada"
        action = "Abrir Fincilia"
        footer = "Aviso operativo; no certifica conciliacion, saldo ni cierre."
    else:
        subjects = {
            "period_due_soon": "Your accounting cycle is due soon",
            "period_due_today": "Your accounting cycle is due today",
            "period_in_grace": "Your accounting cycle is in its grace period",
            "period_overdue": "Your accounting cycle is overdue",
        }
        lead = "Review the operational cycle"
        due = "Expected date"
        action = "Open Fincilia"
        footer = "Operational notice; it does not certify reconciliation, balance, or close."
    text = (f"{lead}: {safe['period_label']}\n{due}: {safe['due_on']}\n"
            f"{action}: {url}\n\n{footer}")
    html_body = (
        "<!doctype html><html><body>"
        f"<p>{html.escape(lead)}: <strong>{html.escape(safe['period_label'])}</strong></p>"
        f"<p>{html.escape(due)}: {html.escape(safe['due_on'])}</p>"
        f"<p><a href=\"{html.escape(url, quote=True)}\">{html.escape(action)}</a></p>"
        f"<p><small>{html.escape(footer)}</small></p>"
        "</body></html>"
    )
    return RenderedMessage(subjects[template_code], text, html_body)


class AwsKmsDestinationProtector:
    def __init__(self, client: Any, *, key_id: str) -> None:
        self._client = client
        self._key_id = key_id

    def encrypt(self, email: str, *, address_ref: str) -> EncryptedDestination:
        if not isinstance(address_ref, str) or not ADDRESS_REF.fullmatch(address_ref):
            raise DeliveryError("destination_reference_invalid", "fatal")
        try:
            canonical = canonical_email(email)
        except IdentityReferenceError as error:
            raise DeliveryError("destination_invalid", "fatal") from error
        try:
            response = self._client.encrypt(
                KeyId=self._key_id,
                Plaintext=canonical.encode("utf-8"),
                EncryptionContext={**KMS_CONTEXT, "address_ref": address_ref},
                EncryptionAlgorithm="SYMMETRIC_DEFAULT",
            )
            ciphertext = bytes(response["CiphertextBlob"])
        except (BotoCoreError, ClientError, KeyError, TypeError, ValueError) as error:
            raise DeliveryError("destination_encryption_failed", "retryable") from error
        if not 32 <= len(ciphertext) <= 6144:
            raise DeliveryError("destination_ciphertext_invalid", "fatal")
        return EncryptedDestination(ciphertext, address_ref, self._key_id)

    def decrypt(self, destination: EncryptedDestination) -> str:
        if destination.kms_key_ref != self._key_id \
                or not 32 <= len(destination.ciphertext) <= 6144 \
                or not ADDRESS_REF.fullmatch(destination.address_ref):
            raise DeliveryError("destination_ciphertext_invalid", "fatal")
        try:
            response = self._client.decrypt(
                KeyId=self._key_id,
                CiphertextBlob=destination.ciphertext,
                EncryptionContext={
                    **KMS_CONTEXT, "address_ref": destination.address_ref,
                },
                EncryptionAlgorithm="SYMMETRIC_DEFAULT",
            )
            plaintext = bytes(response["Plaintext"])
            email = canonical_email(plaintext.decode("utf-8"))
        except (BotoCoreError, ClientError, KeyError, TypeError, ValueError,
                UnicodeError, IdentityReferenceError) as error:
            raise DeliveryError("destination_decryption_failed", "fatal") from error
        return email

    @staticmethod
    def encode(destination: EncryptedDestination) -> str:
        return base64.b64encode(destination.ciphertext).decode("ascii")

    @staticmethod
    def decode(value: str, *, address_ref: str, key_ref: str) -> EncryptedDestination:
        if not isinstance(address_ref, str) or not ADDRESS_REF.fullmatch(address_ref):
            raise DeliveryError("destination_reference_invalid", "fatal")
        try:
            ciphertext = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as error:
            raise DeliveryError("destination_ciphertext_invalid", "fatal") from error
        return EncryptedDestination(ciphertext, address_ref, key_ref)


class AwsSesAdapter:
    def __init__(self, client: Any, *, from_address: str, reply_to: str,
                 configuration_set: str, public_origin: str) -> None:
        try:
            self._from = canonical_email(from_address)
            self._reply_to = canonical_email(reply_to)
        except IdentityReferenceError as error:
            raise DeliveryError("provider_configuration_invalid", "fatal") from error
        self._client = client
        self._configuration_set = configuration_set
        self._public_origin = public_origin

    def deliver(self, *, recipient: str, template_code: str, locale: str,
                context: Mapping[str, Any], idempotency_key: str) -> str:
        try:
            destination = canonical_email(recipient)
        except IdentityReferenceError as error:
            raise DeliveryError("destination_invalid", "fatal") from error
        if len(idempotency_key) != 64 or any(
                char not in "0123456789abcdef" for char in idempotency_key):
            raise DeliveryError("idempotency_key_invalid", "fatal")
        message = render_message(
            template_code=template_code, locale=locale, context=context,
            public_origin=self._public_origin)
        try:
            response = self._client.send_email(
                FromEmailAddress=self._from,
                Destination={"ToAddresses": [destination]},
                ReplyToAddresses=[self._reply_to],
                Content={"Simple": {
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": message.text, "Charset": "UTF-8"},
                        "Html": {"Data": message.html, "Charset": "UTF-8"},
                    },
                }},
                ConfigurationSetName=self._configuration_set,
                EmailTags=[{"Name": "delivery_key", "Value": idempotency_key}],
            )
            message_id = response["MessageId"]
        except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError) as error:
            raise DeliveryError("provider_outcome_unknown", "uncertain") from error
        except ClientError as error:
            provider_code = str(error.response.get("Error", {}).get("Code", ""))
            failure_class = "retryable" if provider_code in RETRYABLE_CODES else "fatal"
            safe_code = "provider_rate_limited" if failure_class == "retryable" \
                else "provider_rejected"
            raise DeliveryError(safe_code, failure_class) from error
        except (BotoCoreError, KeyError, TypeError) as error:
            raise DeliveryError("provider_outcome_unknown", "uncertain") from error
        if not isinstance(message_id, str) or not 1 <= len(message_id) <= 512:
            raise DeliveryError("provider_response_invalid", "uncertain")
        return "sha256:" + hashlib.sha256(message_id.encode("utf-8")).hexdigest()
