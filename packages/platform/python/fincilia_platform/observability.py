"""Observabilidad estructurada con allowlist y contexto acotado.

El formatter no serializa ``record.msg``, argumentos, excepciones ni atributos
arbitrarios. Eso es intencional: un mensaje de una librería puede contener un
DSN, una URL firmada, un nombre de archivo o texto de origen. Sólo viajan campos
de este módulo y valores escalares previamente acotados.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

CORRELATION_ID = contextvars.ContextVar("fincilia_correlation_id", default=None)
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,63}$")
EVENT = re.compile(r"^[a-z][a-z0-9_.-]{2,79}$")
ALLOWED_FIELDS = frozenset({
    "request_id", "job_id", "method", "route", "status_code", "duration_ms",
    "outcome", "dependency", "environment", "release_id", "revision",
})


def valid_correlation_id(value: str | None) -> bool:
    return bool(value and IDENTIFIER.fullmatch(value))


@contextlib.contextmanager
def correlation(value: str) -> Iterator[None]:
    if not valid_correlation_id(value):
        raise ValueError("correlation identifier is not canonical")
    token = CORRELATION_ID.set(value)
    try:
        yield
    finally:
        CORRELATION_ID.reset(token)


class JsonFormatter(logging.Formatter):
    """JSON lineal sin mensaje libre, argumentos o traceback."""

    def __init__(self, service: str) -> None:
        super().__init__()
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", service):
            raise ValueError("service name is not safe for structured logs")
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "unstructured")
        if not isinstance(event, str) or not EVENT.fullmatch(event):
            event = "invalid-event"
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": self._service,
            "logger": record.name,
            "event": event,
        }
        current = CORRELATION_ID.get()
        if current:
            payload["correlation_id"] = current
        for field in sorted(ALLOWED_FIELDS):
            value = getattr(record, field, None)
            if value is None or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                payload[field] = value
            elif isinstance(value, str) and len(value) <= 160 and "\n" not in value and "\r" not in value:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"),
                          sort_keys=True)


def configure(service: str, level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, level: int, name: str, **fields: object) -> None:
    if not EVENT.fullmatch(name):
        raise ValueError("event name is not canonical")
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"observability fields are not allowlisted: {sorted(unknown)}")
    logger.log(level, "", extra={"event": name, **fields})
