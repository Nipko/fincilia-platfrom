"""Tokens de sesion locales, firmados con HMAC-SHA256.

No es un JWT ni pretende serlo: no hay `alg` en la cabecera, y por tanto no hay
ataque de confusion de algoritmo ni un `alg: none` que aceptar por descuido. El
algoritmo lo decide el servidor y no viaja en el token.

Lo que el token dice es **quien** es el sujeto y **cuando** se emitio. No dice a
que empresa puede entrar ni con que rol: eso se resuelve contra la base en cada
peticion. Un token que llevara permisos seguiria siendo valido despues de
revocarlos.
"""

from __future__ import annotations

import base64
import hmac
import json
import secrets
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

TOKEN_VERSION = "fnc1"
SEPARATOR = "."


class TokenError(ValueError):
    """El token no es utilizable. Nunca se dice por que, al portador."""


@dataclass(frozen=True)
class Claims:
    subject_id: str
    issuer: str
    audience: str
    issued_at: int
    expires_at: int
    token_id: str

    def as_payload(self) -> dict[str, Any]:
        return {"v": TOKEN_VERSION, "sub": self.subject_id, "iss": self.issuer,
                "aud": self.audience, "iat": self.issued_at,
                "exp": self.expires_at, "jti": self.token_id}


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except Exception as error:  # noqa: BLE001 - cualquier fallo es token invalido
        raise TokenError("malformed token") from error


def _sign(payload: str, key: str) -> str:
    return _b64encode(hmac.new(key.encode("utf-8"), payload.encode("ascii"),
                               sha256).digest())


def issue(subject_id: str, *, key: str, issuer: str, audience: str,
          issued_at: int, ttl_seconds: int, token_id: str | None = None) -> str:
    if not subject_id:
        raise TokenError("a token always names a subject")
    if ttl_seconds <= 0:
        raise TokenError("a token that never expires is not a session")
    claims = Claims(subject_id, issuer, audience, issued_at,
                    issued_at + ttl_seconds, token_id or secrets.token_hex(16))
    payload = _b64encode(json.dumps(claims.as_payload(), sort_keys=True,
                                    separators=(",", ":")).encode("utf-8"))
    return payload + SEPARATOR + _sign(payload, key)


def verify(token: str, *, key: str, issuer: str, audience: str, now: int) -> Claims:
    """Devuelve las reclamaciones si el token es valido; si no, `TokenError`.

    Se comprueba la firma **antes** de leer el contenido: interpretar un payload
    sin verificar es tratar como dato de confianza algo que escribio el portador.
    """
    if not isinstance(token, str) or token.count(SEPARATOR) != 1:
        raise TokenError("malformed token")
    payload, signature = token.split(SEPARATOR)
    if not payload or not signature:
        raise TokenError("malformed token")
    if not hmac.compare_digest(_sign(payload, key), signature):
        raise TokenError("bad signature")

    try:
        body = json.loads(_b64decode(payload))
    except (ValueError, UnicodeDecodeError) as error:
        raise TokenError("malformed token") from error
    if not isinstance(body, dict) or body.get("v") != TOKEN_VERSION:
        raise TokenError("unsupported token version")

    for field in ("sub", "iss", "aud", "iat", "exp", "jti"):
        if field not in body:
            raise TokenError("incomplete token")
    if not isinstance(body["iat"], int) or not isinstance(body["exp"], int):
        raise TokenError("malformed token")
    if body["iss"] != issuer or body["aud"] != audience:
        # Un token emitido para otro servicio no vale aqui aunque este firmado
        # con la misma clave.
        raise TokenError("wrong issuer or audience")
    if body["exp"] <= now:
        raise TokenError("expired token")
    if body["iat"] > now + 60:
        # Un token del futuro es un reloj mal puesto o un token fabricado; en
        # ambos casos no se acepta.
        raise TokenError("token issued in the future")
    if body["exp"] <= body["iat"]:
        raise TokenError("malformed token")
    return Claims(str(body["sub"]), str(body["iss"]), str(body["aud"]),
                  int(body["iat"]), int(body["exp"]), str(body["jti"]))
