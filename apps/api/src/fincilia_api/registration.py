"""Registro autoservicio del proveedor local exclusivamente sintetico.

La API valida el secreto y deriva el hash antes de tocar PostgreSQL. La base
recibe solo el material derivado y ejecuta una funcion acotada: el rol runtime
no obtiene INSERT sobre ``local_credential`` ni sobre identidad global.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

import psycopg

from fincilia_platform.identity import ALGORITHM, ITERATIONS, hash_secret, new_salt


USERNAME = re.compile(r"^[a-z0-9][a-z0-9._+-]{1,90}@demo[.]local$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class RegistrationError(Exception):
    """Rechazo publico que nunca refleja credenciales ni confirma una cuenta."""

    def __init__(self, code: str, detail: str, *, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class RegisteredAccount:
    subject_id: str
    firm_id: str
    display_name: str


def normalise_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME.fullmatch(username):
        raise RegistrationError(
            "registration-unavailable",
            "use a synthetic address ending in @demo.local in this environment",
        )
    return username


def clean_name(value: str, *, kind: str, maximum: int) -> str:
    cleaned = " ".join(value.strip().split())
    if not 2 <= len(cleaned) <= maximum or CONTROL.search(cleaned):
        raise RegistrationError(
            "invalid-registration-profile",
            f"the {kind} must contain between 2 and {maximum} safe characters",
        )
    return cleaned


def validate_secret(secret: str) -> None:
    if not 14 <= len(secret) <= 128:
        raise RegistrationError(
            "weak-registration-secret",
            "the password must contain between 14 and 128 characters",
        )
    required = (
        any(character.islower() for character in secret),
        any(character.isupper() for character in secret),
        any(character.isdigit() for character in secret),
        any(not character.isalnum() for character in secret),
    )
    if not all(required):
        raise RegistrationError(
            "weak-registration-secret",
            "the password needs uppercase, lowercase, number and symbol",
        )


def register_local_account(
        connection: psycopg.Connection, *, username: str, secret: str,
        display_name: str, firm_name: str, real_data_enabled: bool,
        ) -> RegisteredAccount:
    if real_data_enabled:
        raise RegistrationError(
            "registration-unavailable",
            "local account registration is disabled when real data is enabled",
            status=503,
        )

    canonical_username = normalise_username(username)
    canonical_display_name = clean_name(
        display_name, kind="display name", maximum=200)
    canonical_firm_name = clean_name(firm_name, kind="firm name", maximum=300)
    validate_secret(secret)

    subject_id = str(uuid.uuid4())
    membership_id = str(uuid.uuid4())
    firm_id = str(uuid.uuid4())
    salt = new_salt()
    secret_hash = hash_secret(secret, salt=salt, iterations=ITERATIONS)
    identity_ref = "sha256:" + hashlib.sha256(
        canonical_username.encode("utf-8")).hexdigest()

    try:
        # Savepoint: una colision revierte los cinco INSERT y deja utilizable la
        # transaccion externa para que la ruta devuelva un error generico.
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT fincilia.register_local_account(" 
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    subject_id, membership_id, firm_id, canonical_username,
                    identity_ref, canonical_display_name, canonical_firm_name,
                    ALGORITHM, ITERATIONS, salt, secret_hash,
                ),
            )
    except psycopg.errors.UniqueViolation:
        raise RegistrationError(
            "registration-unavailable",
            "the account could not be created with the supplied details",
            status=409,
        ) from None
    except psycopg.errors.CheckViolation:
        raise RegistrationError(
            "invalid-registration-profile",
            "the account could not be created with the supplied profile",
        ) from None

    return RegisteredAccount(subject_id, firm_id, canonical_display_name)
