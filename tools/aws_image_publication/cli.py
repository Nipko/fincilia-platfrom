from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .model import (
    PublicationError,
    build_manifest,
    load_json,
    sha256_file,
    validate,
    validate_manifest,
)


def _scan_observation(
    name: str,
    release_sha: str,
    digest: str,
    scan_path: Path,
    attestation_path: Path,
) -> dict[str, Any]:
    try:
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationError(f"scan JSON invalido para {name}") from exc
    status = (scan.get("imageScanStatus") or {}).get("status")
    expected_repository = f"fincilia/private-pilot/{name}"
    image_id = scan.get("imageId") or {}
    if scan.get("repositoryName") != expected_repository or \
            image_id.get("imageDigest") != digest or \
            image_id.get("imageTag") != release_sha:
        raise PublicationError(f"scan no corresponde a imagen exacta para {name}")
    counts = (scan.get("imageScanFindings") or {}).get(
        "findingSeverityCounts", {}
    )
    if not isinstance(counts, dict):
        raise PublicationError(f"conteos de scan invalidos para {name}")
    try:
        attestation_sha = sha256_file(attestation_path)
    except OSError as exc:
        raise PublicationError(f"attestation ausente para {name}") from exc
    return {
        "name": name,
        "repository": expected_repository,
        "tag": release_sha,
        "digest": digest,
        "scan_status": status,
        "severity_counts": counts,
        "attestation_bundle_sha256": attestation_sha,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fincilia-aws-image-publication")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_command = commands.add_parser("validate")
    validate_command.add_argument("--plan", type=Path)
    manifest = commands.add_parser("manifest")
    manifest.add_argument("--release-sha", required=True)
    manifest.add_argument("--run-url", required=True)
    manifest.add_argument("--output", required=True, type=Path)
    for name in ("api", "web", "worker"):
        manifest.add_argument(f"--{name}-digest", required=True)
        manifest.add_argument(f"--{name}-scan", required=True, type=Path)
        manifest.add_argument(f"--{name}-attestation", required=True, type=Path)
    verify = commands.add_parser("verify-manifest")
    verify.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.command == "validate":
        report = validate(load_json(args.plan) if args.plan else None)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    if args.command == "verify-manifest":
        try:
            value = json.loads(args.manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
            return 1
        errors = validate_manifest(value)
        print(json.dumps({"ok": not errors, "errors": errors}, sort_keys=True))
        return 0 if not errors else 1

    try:
        observations = [
            _scan_observation(
                name,
                args.release_sha,
                getattr(args, f"{name}_digest"),
                getattr(args, f"{name}_scan"),
                getattr(args, f"{name}_attestation"),
            )
            for name in ("api", "web", "worker")
        ]
        value = build_manifest(args.release_sha, args.run_url, observations)
        _write_json(args.output, value)
    except PublicationError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "manifest": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
