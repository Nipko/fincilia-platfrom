"""Synthetic-only parser boundary for FNC-PLT-005.

The worker creates a deterministic draft and an immutable manifest. It has no
database credentials and cannot publish canonical financial state.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ENGINE_RELEASE = "synthetic-tabular-parser@0.1.0"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def validate_job(job: dict[str, Any]) -> None:
    if job.get("data_classification") != "synthetic":
        raise ValueError("FNC-PLT-005 accepts synthetic data only")
    if job.get("requested_effect") not in (None, "draft"):
        raise ValueError("the parser boundary can only create drafts")
    if not isinstance(job.get("idempotency_key"), str) or not job["idempotency_key"]:
        raise ValueError("idempotency_key is required")
    if not isinstance(job.get("artifact_sha256"), str) or len(job["artifact_sha256"]) != 64:
        raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
    if not all(character in "0123456789abcdef" for character in job["artifact_sha256"]):
        raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(job.get("rows"), list):
        raise ValueError("rows must be a list")
    for row_number, row in enumerate(job["rows"], start=1):
        if not isinstance(row, dict) or not row:
            raise ValueError(f"row {row_number} must be a non-empty object")


def draft_rows(job: dict[str, Any]) -> list[dict[str, Any]]:
    draft: list[dict[str, Any]] = []
    for row_number, row in enumerate(job["rows"], start=1):
        cells = []
        for column_number, (column, value) in enumerate(sorted(row.items()), start=1):
            cells.append(
                {
                    "column": column,
                    "value": value,
                    "origin_locator": {
                        "artifact_sha256": job["artifact_sha256"],
                        "sheet": "synthetic-sheet",
                        "row": row_number,
                        "column": column_number,
                    },
                }
            )
        draft.append({"row_number": row_number, "cells": cells})
    return draft


def process_job(job: dict[str, Any], state_dir: Path, output_dir: Path) -> tuple[dict[str, Any], bool]:
    validate_job(job)
    input_digest = sha256(canonical_json(job))
    key_digest = sha256(job["idempotency_key"].encode("utf-8"))
    manifest_path = state_dir / "idempotency" / f"{key_digest}.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_digest:
            raise ValueError("idempotency key was already used with different content")
        output_path = output_dir / manifest["output_file"]
        if not output_path.exists() or sha256(output_path.read_bytes()) != manifest["output_sha256"]:
            raise ValueError("the prior draft no longer matches its manifest")
        return manifest, True

    output = {
        "artifact_sha256": job["artifact_sha256"],
        "effect": "draft",
        "engine_release": ENGINE_RELEASE,
        "row_count": len(job["rows"]),
        "rows": draft_rows(job),
        "synthetic": True,
    }
    output_bytes = canonical_json(output)
    output_file = f"{key_digest}.draft.json"
    atomic_write(output_dir / output_file, output_bytes)

    manifest = {
        "engine_release": ENGINE_RELEASE,
        "idempotency_key": job["idempotency_key"],
        "input_sha256": input_digest,
        "manifest_version": 1,
        "output_file": output_file,
        "output_sha256": sha256(output_bytes),
        "publication_authority": "none",
        "synthetic": True,
    }
    atomic_write(manifest_path, canonical_json(manifest))
    return manifest, False
