"""CLI del candidato de release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import ReleaseError, create_bundle, verify_bundle, verify_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fincilia-release-candidate")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--root", type=Path, default=Path.cwd())
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--revision")
    create.add_argument("--classification", choices=("neutral", "affects_results"),
                        default="neutral")
    create.add_argument("--ci-run-url", required=True)
    for name in ("api", "worker", "web"):
        create.add_argument(f"--{name}-image-id", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)

    source = sub.add_parser("verify-source")
    source.add_argument("--root", type=Path, default=Path.cwd())
    source.add_argument("--bundle", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_bundle(
                args.root, args.output,
                {name: getattr(args, f"{name}_image_id")
                 for name in ("api", "worker", "web")},
                revision=args.revision, classification=args.classification,
                ci_run_url=args.ci_run_url)
        elif args.command == "verify":
            manifest = verify_bundle(args.bundle)
        else:
            manifest = verify_source(args.root, args.bundle)
    except ReleaseError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({
        "ok": True,
        "revision": manifest["source"]["revision"],
        "schema_head": manifest["schema_head"],
        "state": manifest["state"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
