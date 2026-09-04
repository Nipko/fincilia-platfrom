from __future__ import annotations

import argparse
import json
from pathlib import Path

from .control import (
    AwsJson,
    BootstrapControlError,
    bootstrap_and_migrate,
    prepare_runtime_secrets,
    read_tofu_output,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and bootstrap private-pilot PostgreSQL safely"
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="sa-east-1")
    parser.add_argument("--tofu-dir", required=True, type=Path)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("command", choices=("prepare-secrets", "bootstrap-migrate"))
    args = parser.parse_args(argv)
    expected = {
        "prepare-secrets": "PREPARE_RUNTIME_SECRETS",
        "bootstrap-migrate": "BOOTSTRAP_AND_MIGRATE",
    }[args.command]
    if args.confirmation != expected:
        print(json.dumps({"ok": False, "error": "confirmation_required"}))
        return 2
    try:
        aws = AwsJson(profile=args.profile, region=args.region)
        # Ambos comandos exigen el plano warm materializado pero con API y
        # worker en cero. Asi la inicializacion de secretos tampoco puede
        # ejecutarse por accidente mientras hay servicios consumiendolos.
        topology = read_tofu_output(
            directory=args.tofu_dir,
            profile=args.profile,
        )
        if args.command == "prepare-secrets":
            report = prepare_runtime_secrets(aws)
        else:
            report = bootstrap_and_migrate(aws, topology)
    except (BootstrapControlError, KeyError, TypeError, ValueError):
        print(json.dumps({"ok": False, "error": "operation_failed"}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
