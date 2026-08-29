from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


HEX64 = re.compile(r"^[0-9a-f]{64}$")
EVENTS = {
    "intake", "promotion", "rejection", "derivation", "backup",
    "tombstone", "purge", "restore_repurge", "destroy",
}
ZONES = {"quarantine", "evidence", "derived", "backup", "scratch"}
STATES = {
    "intake": "quarantined",
    "promotion": "accepted",
    "rejection": "rejected",
    "derivation": "accepted",
    "backup": "accepted",
    "tombstone": "tombstoned",
    "purge": "purged",
    "restore_repurge": "purged",
    "destroy": "purged",
}
ALLOWED_FROM = {
    "intake": {None},
    "promotion": {"quarantined"},
    "rejection": {"quarantined"},
    "derivation": {"accepted"},
    "backup": {"accepted", "rejected"},
    "tombstone": {"quarantined", "accepted", "rejected"},
    "purge": {"tombstoned"},
    "restore_repurge": {"purged"},
    "destroy": {"tombstoned", "purged"},
}
FIELDS = {
    "schema_version", "sequence", "operation_ref", "artifact_ref",
    "company_ref", "event", "state", "content_sha256", "created_refs",
    "removed_refs", "reason_code", "occurred_at", "previous_event_sha256",
    "event_sha256",
}


class InventoryError(RuntimeError):
    """El inventario no puede demostrar una transición o fue alterado."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_object_ref(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and len(path.parts) == 2
        and path.parts[0] in ZONES
        and bool(HEX64.fullmatch(path.parts[1]))
        and ".." not in path.parts
    )


@dataclass(frozen=True)
class InventorySnapshot:
    artifact_states: dict[str, str]
    active_refs: dict[str, tuple[str, ...]]
    event_count: int
    head_sha256: str | None


class InventoryLedger:
    """Ledger NDJSON con cadena hash e idempotencia por operación.

    Solo conserva referencias opacas y digests. Un nombre de fichero, correo,
    empresa legible, monto o texto documental no tiene campo donde entrar.
    """

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        previous: str | None = None
        operations: set[str] = set()
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            for line_number, raw in enumerate(handle, 1):
                if not raw.endswith("\n"):
                    raise InventoryError(f"ledger line {line_number} is truncated")
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError as error:
                    raise InventoryError(f"ledger line {line_number} is invalid") from error
                self._validate_event(event, line_number, previous, operations)
                events.append(event)
                previous = event["event_sha256"]
                operations.add(event["operation_ref"])
        return events

    @staticmethod
    def _validate_event(
        event: dict[str, Any], line_number: int, previous: str | None,
        operations: set[str],
    ) -> None:
        if not isinstance(event, dict) or set(event) != FIELDS:
            raise InventoryError(f"ledger line {line_number} fields drifted")
        if event["schema_version"] != "1.0.0" or event["sequence"] != line_number:
            raise InventoryError(f"ledger line {line_number} sequence drifted")
        for field in ("operation_ref", "artifact_ref", "company_ref", "content_sha256"):
            if not isinstance(event[field], str) or not HEX64.fullmatch(event[field]):
                raise InventoryError(f"ledger line {line_number} has invalid {field}")
        if event["operation_ref"] in operations:
            raise InventoryError(f"ledger line {line_number} duplicates operation")
        if event["event"] not in EVENTS or event["state"] != STATES[event["event"]]:
            raise InventoryError(f"ledger line {line_number} has invalid event state")
        if event["previous_event_sha256"] != previous:
            raise InventoryError(f"ledger line {line_number} breaks the hash chain")
        for field in ("created_refs", "removed_refs"):
            refs = event[field]
            if (
                not isinstance(refs, list) or len(refs) != len(set(refs))
                or any(not isinstance(item, str) or not _safe_object_ref(item) for item in refs)
            ):
                raise InventoryError(f"ledger line {line_number} has unsafe object refs")
        if set(event["created_refs"]) & set(event["removed_refs"]):
            raise InventoryError(f"ledger line {line_number} creates and removes one ref")
        unsigned = {key: value for key, value in event.items() if key != "event_sha256"}
        if event["event_sha256"] != _digest(unsigned):
            raise InventoryError(f"ledger line {line_number} digest mismatch")
        if (
            not isinstance(event["reason_code"], str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{2,79}", event["reason_code"])
            or not isinstance(event["occurred_at"], str)
            or not event["occurred_at"].endswith("Z")
        ):
            raise InventoryError(f"ledger line {line_number} metadata is invalid")

    def snapshot(self, events: Iterable[dict[str, Any]] | None = None) -> InventorySnapshot:
        materialized = list(self.read() if events is None else events)
        states: dict[str, str] = {}
        refs: dict[str, set[str]] = {}
        for event in materialized:
            artifact = event["artifact_ref"]
            prior = states.get(artifact)
            if prior not in ALLOWED_FROM[event["event"]]:
                raise InventoryError(
                    f"transition {event['event']} is invalid from {prior!r}"
                )
            active = refs.setdefault(artifact, set())
            missing = set(event["removed_refs"]) - active
            if missing:
                raise InventoryError(f"event removes unknown refs: {sorted(missing)}")
            active.difference_update(event["removed_refs"])
            active.update(event["created_refs"])
            states[artifact] = event["state"]
        return InventorySnapshot(
            artifact_states=states,
            active_refs={key: tuple(sorted(value)) for key, value in refs.items()},
            event_count=len(materialized,
            ),
            head_sha256=materialized[-1]["event_sha256"] if materialized else None,
        )

    def append(
        self, *, operation_ref: str, artifact_ref: str, company_ref: str,
        event: str, content_sha256: str, created_refs: list[str] | None = None,
        removed_refs: list[str] | None = None, reason_code: str,
        occurred_at: str,
    ) -> dict[str, Any]:
        existing = self.read()
        for item in existing:
            if item["operation_ref"] == operation_ref:
                requested = (artifact_ref, company_ref, event, content_sha256)
                observed = tuple(item[key] for key in (
                    "artifact_ref", "company_ref", "event", "content_sha256"))
                if requested != observed:
                    raise InventoryError("idempotency operation diverged")
                return item
        snapshot = self.snapshot(existing)
        prior = snapshot.artifact_states.get(artifact_ref)
        if event not in EVENTS or prior not in ALLOWED_FROM[event]:
            raise InventoryError(f"transition {event!r} is invalid from {prior!r}")
        payload: dict[str, Any] = {
            "schema_version": "1.0.0",
            "sequence": len(existing) + 1,
            "operation_ref": operation_ref,
            "artifact_ref": artifact_ref,
            "company_ref": company_ref,
            "event": event,
            "state": STATES[event],
            "content_sha256": content_sha256,
            "created_refs": sorted(created_refs or []),
            "removed_refs": sorted(removed_refs or []),
            "reason_code": reason_code,
            "occurred_at": occurred_at,
            "previous_event_sha256": (
                existing[-1]["event_sha256"] if existing else None
            ),
        }
        payload["event_sha256"] = _digest(payload)
        # Validar la transición y las copias contra el estado completo antes de
        # abrir el descriptor. Si se hiciera después, un evento inválido ya
        # habría contaminado el ledger que pretendía proteger.
        self.snapshot([*existing, payload])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, _canonical(payload) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.read()
        return payload

    def reconcile(self, root: Path) -> list[str]:
        snapshot = self.snapshot()
        expected = {
            item for refs in snapshot.active_refs.values() for item in refs
        }
        observed: set[str] = set()
        for zone in sorted(ZONES):
            directory = root / zone
            if not directory.exists():
                continue
            for path in directory.iterdir():
                if path.is_file() and HEX64.fullmatch(path.name):
                    observed.add(f"{zone}/{path.name}")
        return sorted(expected ^ observed)
