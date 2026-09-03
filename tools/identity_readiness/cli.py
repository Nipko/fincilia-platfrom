"""CLI live; prints only the redacted report assembled by probe.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aws_cli import AwsCliCognito
from .probe import inspect_identity
from .tofu import discover_identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate live Cognito identity")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="sa-east-1")
    selectors = parser.add_argument_group("identity selectors")
    selectors.add_argument("--user-pool-id")
    selectors.add_argument("--client-id")
    selectors.add_argument("--domain-prefix")
    selectors.add_argument(
        "--tofu-dir",
        help="discover selectors from adjudicated OpenTofu outputs without printing them",
    )
    parser.add_argument("--app-origin", required=True)
    args = parser.parse_args(argv)
    try:
        direct = (args.user_pool_id, args.client_id, args.domain_prefix)
        if args.tofu_dir:
            if any(direct):
                raise ValueError("choose OpenTofu discovery or direct selectors")
            discovered = discover_identity(
                directory=Path(args.tofu_dir),
                profile=args.profile,
                region=args.region,
            )
        elif all(direct):
            discovered = {
                "user_pool_id": args.user_pool_id,
                "client_id": args.client_id,
                "domain_prefix": args.domain_prefix,
            }
        else:
            raise ValueError("identity selectors are incomplete")
        cognito = AwsCliCognito(profile=args.profile, region=args.region)
        report = inspect_identity(
            cognito=cognito, user_pool_id=discovered["user_pool_id"],
            client_id=discovered["client_id"],
            domain_prefix=discovered["domain_prefix"],
            app_origin=args.app_origin)
    except (KeyError, RuntimeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__},
                         sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
