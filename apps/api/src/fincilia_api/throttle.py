"""Freno de intentos de autenticacion, con Valkey.

Valkey guarda estado efimero y **nunca** es autoridad financiera. Un contador de
intentos es exactamente eso: si se pierde, se pierde un freno, no un hecho.

Por eso falla abierto cuando la cache no responde. Es una decision, no un
descuido: cerrar aqui convertiria una caida de la cache en una caida del inicio
de sesion para todo el mundo, y el freno existe para encarecer la fuerza bruta,
no para ser la unica defensa. La autenticacion en si nunca depende de la cache.

La clave no lleva el usuario en claro: un volcado de la cache no deberia ser un
censo de cuentas.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger("fincilia.api.throttle")

MAX_ATTEMPTS = 10
WINDOW_SECONDS = 300
PREFIX = "fincilia:auth:attempt:"


def attempt_key(username: str) -> str:
    return PREFIX + hashlib.sha256(username.encode("utf-8")).hexdigest()[:32]


class AttemptThrottle:
    def __init__(self, client, *, max_attempts: int = MAX_ATTEMPTS,
                 window_seconds: int = WINDOW_SECONDS) -> None:
        self._client = client
        self._max = max_attempts
        self._window = window_seconds

    def exhausted(self, username: str) -> bool:
        if self._client is None:
            return False
        try:
            current = self._client.get(attempt_key(username))
        except Exception as error:  # noqa: BLE001 - la cache no bloquea el login
            logger.warning("throttle unavailable: %s", type(error).__name__)
            return False
        return current is not None and int(current) >= self._max

    def record_failure(self, username: str) -> None:
        if self._client is None:
            return
        key = attempt_key(username)
        try:
            pipeline = self._client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, self._window)
            pipeline.execute()
        except Exception as error:  # noqa: BLE001
            logger.warning("throttle unavailable: %s", type(error).__name__)

    def clear(self, username: str) -> None:
        if self._client is None:
            return
        try:
            self._client.delete(attempt_key(username))
        except Exception as error:  # noqa: BLE001
            logger.warning("throttle unavailable: %s", type(error).__name__)
