"""Adaptador Cognito OIDC para identidades nominales del piloto.

El navegador nunca entrega claims aceptados por la API. El backend canjea el
codigo con PKCE contra el endpoint exacto y pide a Cognito que valide el access
token mediante ``GetUser``. Del ID token recibido directamente en ese canje solo
se usa el nonce y se cruzan issuer/audience/sub; el ``sub`` autoritativo es el
que devuelve Cognito. Correo y sub se convierten en HMAC antes de PostgreSQL.
"""

from __future__ import annotations

import base64
import hmac
import json
import re
import time
import uuid
from dataclasses import dataclass

import boto3
import httpx
import psycopg
from botocore.exceptions import BotoCoreError, ClientError

from fincilia_platform.settings import ApiSettings
from fincilia_platform.identity_refs import (
    IdentityReferenceError,
    email_reference,
    hmac_reference,
)

from .registration import RegistrationError, clean_name
from .repository import Subject


CODE = re.compile(r"^[A-Za-z0-9._~-]{16,2048}$")
VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")
JWT_PART = re.compile(r"^[A-Za-z0-9_-]+$")
COGNITO_SUB = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
MAX_TOKEN_RESPONSE_BYTES = 16_384
MAX_JWT_BYTES = 16_384
MAX_ACCESS_TOKEN_BYTES = 16_384
TERMS_VERSION = "terms-2026-08-29"
PRIVACY_VERSION = "privacy-2026-08-29"


class OidcError(Exception):
    """Rechazo generico: nunca incorpora codigo, token, sub o correo."""

    def __init__(self, code: str = "managed-sign-in-unavailable", *,
                 status: int = 401) -> None:
        super().__init__("managed sign-in could not be completed")
        self.code = code
        self.status = status


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    external_subject_ref: str
    verified_email_ref: str
    display_name: str


@dataclass(frozen=True)
class ManagedAccount:
    subject_id: str
    display_name: str
    status: str
    created: bool = False

    @property
    def active(self) -> bool:
        return self.status == "active"


def _decode_segment(segment: str) -> dict:
    if not JWT_PART.fullmatch(segment) or len(segment) > MAX_JWT_BYTES:
        raise OidcError()
    try:
        padded = segment + "=" * (-len(segment) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise OidcError() from error
    if not isinstance(value, dict):
        raise OidcError()
    return value


def _id_token_claims(token: str, *, nonce: str, issuer: str,
                     audience: str, now: int) -> dict:
    if not isinstance(token, str) or len(token) > MAX_JWT_BYTES:
        raise OidcError()
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise OidcError()
    header = _decode_segment(parts[0])
    claims = _decode_segment(parts[1])
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise OidcError()
    if (
        claims.get("iss") != issuer
        or claims.get("aud") != audience
        or claims.get("token_use") != "id"
        or not isinstance(claims.get("sub"), str)
        or not COGNITO_SUB.fullmatch(claims["sub"])
        or not isinstance(claims.get("exp"), int)
        or claims["exp"] <= now
        or claims["exp"] > now + 3600
        or not isinstance(claims.get("iat"), int)
        or claims["iat"] > now + 60
        or not isinstance(claims.get("nonce"), str)
        or not hmac.compare_digest(claims["nonce"], nonce)
    ):
        raise OidcError()
    return claims


def exchange_code(*, settings: ApiSettings, code: str, verifier: str,
                  nonce: str, http_client=None, cognito_client=None,
                  now: int | None = None) -> VerifiedIdentity:
    if not settings.oidc_enabled or not settings.identity_binding_hmac_key:
        raise OidcError(status=503)
    if not CODE.fullmatch(code) or not VERIFIER.fullmatch(verifier) \
            or not NONCE.fullmatch(nonce):
        raise OidcError()

    owns_http = http_client is None
    client = http_client or httpx.Client(timeout=8.0, follow_redirects=False)
    try:
        response = client.post(
            settings.oidc_token_endpoint,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.oidc_client_id,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": settings.oidc_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    except httpx.HTTPError as error:
        raise OidcError(status=503) from error
    finally:
        if owns_http:
            client.close()

    if response.status_code != 200 or len(response.content) > MAX_TOKEN_RESPONSE_BYTES:
        raise OidcError()
    try:
        tokens = response.json()
    except (ValueError, json.JSONDecodeError) as error:
        raise OidcError() from error
    if not isinstance(tokens, dict):
        raise OidcError()
    # Cognito emite refresh_token de forma obligatoria en Authorization Code.
    # No se copia a ninguna variable, log, respuesta, cookie ni persistencia:
    # Fincilia crea una sesion propia corta y descarta el cuerpo al retornar.
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    expires_in = tokens.get("expires_in")
    scopes = set(str(tokens.get("scope", "")).split())
    if (
        tokens.get("token_type") != "Bearer"
        or not isinstance(access_token, str)
        or not 32 <= len(access_token) <= MAX_ACCESS_TOKEN_BYTES
        or not isinstance(id_token, str)
        or not isinstance(expires_in, int)
        or not 1 <= expires_in <= 3600
        or not {"openid", "email"}.issubset(scopes)
        or not scopes.issubset({"openid", "email", "profile"})
    ):
        raise OidcError()

    timestamp = int(time.time()) if now is None else now
    claims = _id_token_claims(
        id_token, nonce=nonce, issuer=settings.oidc_issuer,
        audience=settings.oidc_client_id, now=timestamp)

    cognito = cognito_client or boto3.client(
        "cognito-idp", region_name=settings.object_region)
    try:
        user = cognito.get_user(AccessToken=access_token)
    except (BotoCoreError, ClientError) as error:
        raise OidcError() from error
    attributes = {
        item.get("Name"): item.get("Value")
        for item in user.get("UserAttributes", [])
        if isinstance(item, dict)
    }
    subject = attributes.get("sub")
    if not isinstance(subject, str) or not COGNITO_SUB.fullmatch(subject) \
            or not hmac.compare_digest(subject.casefold(), claims["sub"].casefold()):
        raise OidcError()
    email = attributes.get("email")
    if attributes.get("email_verified") != "true" or not isinstance(email, str):
        raise OidcError("verified-email-required", status=403)
    try:
        verified_email_ref = email_reference(
            settings.identity_binding_hmac_key, email)
    except IdentityReferenceError as error:
        raise OidcError() from error
    proposed_name = attributes.get("name")
    if not isinstance(proposed_name, str):
        name_parts = (
            attributes.get("given_name"), attributes.get("family_name"))
        proposed_name = " ".join(
            item for item in name_parts if isinstance(item, str) and item.strip())
    display_name = clean_name(
        proposed_name or "Persona Fincilia", kind="display name", maximum=200)
    key = settings.identity_binding_hmac_key
    return VerifiedIdentity(
        issuer=settings.oidc_issuer,
        external_subject_ref=hmac_reference(
            key, purpose="external-subject", value=f"{settings.oidc_issuer}\x00{subject}"),
        verified_email_ref=verified_email_ref,
        display_name=display_name,
    )


def resolve_account(connection: psycopg.Connection, identity: VerifiedIdentity
                    ) -> ManagedAccount | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subject_id::text, display_name, status "
            "FROM fincilia.resolve_external_identity(%s, %s)",
            (identity.issuer, identity.external_subject_ref),
        )
        row = cursor.fetchone()
    return ManagedAccount(*row, created=False) if row else None


def register_account(connection: psycopg.Connection, *, identity: VerifiedIdentity,
                     firm_name: str, terms_version: str,
                     privacy_version: str) -> ManagedAccount:
    try:
        canonical_firm = clean_name(firm_name, kind="firm name", maximum=300)
    except RegistrationError as error:
        raise OidcError("managed-registration-unavailable", status=422) from error
    if terms_version != TERMS_VERSION or privacy_version != PRIVACY_VERSION:
        raise OidcError("managed-registration-unavailable", status=422)
    subject_id = str(uuid.uuid4())
    try:
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT fincilia.register_external_account_public("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    identity.verified_email_ref, subject_id, str(uuid.uuid4()),
                    str(uuid.uuid4()), identity.issuer,
                    identity.external_subject_ref, identity.display_name,
                    canonical_firm, terms_version, privacy_version,
                ),
            )
    except psycopg.errors.UniqueViolation:
        existing = resolve_account(connection, identity)
        if existing is not None:
            return existing
        raise OidcError("managed-registration-unavailable", status=409) from None
    except (psycopg.errors.CheckViolation,
            psycopg.errors.InvalidParameterValue):
        raise OidcError("managed-registration-unavailable", status=422) from None
    return ManagedAccount(subject_id, identity.display_name, "active", created=True)
