"""Disposable, synthetic-only idempotent worker for FNC-PLT-001."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


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


def process_job(job: dict[str, Any], state_dir: Path, output_dir: Path) -> tuple[dict[str, Any], bool]:
    if job.get("data_classification") != "synthetic":
        raise ValueError("FNC-PLT-001 accepts synthetic jobs only")
    if not isinstance(job.get("idempotency_key"), str) or not job["idempotency_key"]:
        raise ValueError("idempotency_key is required")
    if not isinstance(job.get("rows"), list):
        raise ValueError("rows must be a list")

    input_hash = sha256(canonical_json(job))
    key_hash = sha256(job["idempotency_key"].encode("utf-8"))
    manifest_path = state_dir / "idempotency" / f"{key_hash}.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hash:
            raise ValueError("idempotency key was already used with different content")
        return manifest, True

    output = {
        "synthetic": True,
        "job_id": job.get("job_id"),
        "row_count": len(job["rows"]),
        "rows_sha256": sha256(canonical_json(job["rows"])),
    }
    output_bytes = canonical_json(output)
    output_path = output_dir / f"{key_hash}.json"
    atomic_write(output_path, output_bytes)

    manifest = {
        "manifest_version": 1,
        "synthetic": True,
        "idempotency_key": job["idempotency_key"],
        "input_sha256": input_hash,
        "output_sha256": sha256(output_bytes),
        "output_file": output_path.name,
    }
    atomic_write(manifest_path, canonical_json(manifest))
    return manifest, False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(".state"))
    parser.add_argument("--output-dir", type=Path, default=Path(".output"))
    args = parser.parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    manifest, replayed = process_job(job, args.state_dir, args.output_dir)
    print(json.dumps({"replayed": replayed, "manifest": manifest}, sort_keys=True))


if __name__ == "__main__":
    main()
