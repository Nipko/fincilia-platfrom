"""Contrato de consulta de auditoria: filtros cerrados y cursor opaco."""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

FILTER = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
CURSOR = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
OUTCOMES = frozenset({"allowed", "denied", "error"})


@dataclass(frozen=True)
class AuditCursor:
    occurred_at: datetime
    audit_event_id: str


def validate_filter(value: str | None, *, field: str) -> str | None:
    if value is None or value == "":
        return None
    if field == "outcome":
        if value not in OUTCOMES:
            raise ValueError("audit outcome is not allowlisted")
        return value
    if not FILTER.fullmatch(value):
        raise ValueError(f"audit {field} filter is invalid")
    return value


def encode_cursor(occurred_at: datetime, event_id: str) -> str:
    canonical_id = str(uuid.UUID(event_id))
    timestamp = occurred_at.astimezone(timezone.utc).isoformat()
    payload = json.dumps({"at": timestamp, "id": canonical_id},
                         separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> AuditCursor | None:
    if not value:
        return None
    if not CURSOR.fullmatch(value):
        raise ValueError("audit cursor is invalid")
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        if not isinstance(payload, dict) or set(payload) != {"at", "id"}:
            raise ValueError
        occurred_at = datetime.fromisoformat(payload["at"])
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError
        event_id = str(uuid.UUID(payload["id"]))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError,
            binascii.Error, UnicodeDecodeError):
        raise ValueError("audit cursor is invalid") from None
    return AuditCursor(occurred_at.astimezone(timezone.utc), event_id)
