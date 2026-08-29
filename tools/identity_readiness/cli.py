"""CLI live; prints only the redacted report assembled by probe.py."""

from __future__ import annotations

import argparse
import json

from .aws_cli import AwsCliCognito
from .probe import inspect_identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate live Cognito identity")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="sa-east-1")
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--domain-prefix", required=True)
    parser.add_argument("--app-origin", required=True)
    args = parser.parse_args(argv)
    try:
        cognito = AwsCliCognito(profile=args.profile, region=args.region)
        report = inspect_identity(
            cognito=cognito, user_pool_id=args.user_pool_id,
            client_id=args.client_id, domain_prefix=args.domain_prefix,
            app_origin=args.app_origin)
    except (KeyError, RuntimeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__},
                         sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
