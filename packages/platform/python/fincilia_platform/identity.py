"""Proveedor de identidad tras una interfaz.

El producto no depende de como se autentica alguien, sino de que exista un
`subject_id` verificado. El proveedor local existe para que el recorrido complete
en un portatil sin cuenta externa; sustituirlo por OIDC no deberia tocar ni el
dominio ni la autorizacion.

El proveedor local **se niega a arrancar** si `real_data_enabled` esta encendido.
Un almacen de contrasenas sinteticas junto a datos reales es exactamente el modo
de fallo que hay que impedir en el constructor, no en una nota del README.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Callable, Protocol

ALGORITHM = "pbkdf2_sha256"
# Coste deliberado. Un hash barato convierte una filtracion del volumen local en
# una lista de contrasenas, aunque sean sinteticas: el habito importa.
ITERATIONS = 240_000
SALT_BYTES = 16


class AuthenticationError(Exception):
    """Las credenciales no identifican a nadie. Nunca se dice cual de las dos falla."""


@dataclass(frozen=True)
class Credential:
    """Registro almacenado. `secret_hash` nunca sale de este modulo hacia una API."""

    subject_id: str
    username: str
    algorithm: str
    iterations: int
    salt: str
    secret_hash: str


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    external_subject_ref: str
    subject_id: str


def new_salt() -> str:
    return secrets.token_hex(SALT_BYTES)


def hash_secret(secret: str, *, salt: str, iterations: int = ITERATIONS) -> str:
    if not secret:
        raise ValueError("an empty secret is not a credential")
    if iterations < 200_000:
        raise ValueError("iteration count below the floor declared in the schema")
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"),
                                  bytes.fromhex(salt), iterations)
    return derived.hex()


def verify_secret(secret: str, credential: Credential) -> bool:
    if credential.algorithm != ALGORITHM:
        # Un algoritmo desconocido no se intenta interpretar: falla cerrado.
        return False
    try:
        candidate = hash_secret(secret, salt=credential.salt,
                                iterations=credential.iterations)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, credential.secret_hash)


class IdentityProvider(Protocol):
    issuer: str

    def authenticate(self, username: str, secret: str) -> VerifiedIdentity:
        ...


class LocalIdentityProvider:
    """Identidad local con usuarios sinteticos. Solo para desarrollo."""

    issuer = "local"

    def __init__(self, lookup: Callable[[str], Credential | None], *,
                 real_data_enabled: bool = False) -> None:
        if real_data_enabled:
            raise RuntimeError(
                "the local identity provider must never run alongside real data")
        self._lookup = lookup

    def authenticate(self, username: str, secret: str) -> VerifiedIdentity:
        credential = self._lookup(username) if username else None
        if credential is None:
            # Se gasta el mismo trabajo que en un acierto: si el fallo por usuario
            # inexistente respondiera antes, el tiempo de respuesta seria un oraculo
            # de que cuentas existen.
            hash_secret(secret or "placeholder", salt=new_salt())
            raise AuthenticationError("invalid credentials")
        if not verify_secret(secret or "", credential):
            raise AuthenticationError("invalid credentials")
        return VerifiedIdentity(self.issuer, credential.username,
                                credential.subject_id)
