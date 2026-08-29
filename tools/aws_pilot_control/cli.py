from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .control import ControlError, EXIT_EXTERNAL_FAILURE, EXIT_OK, EXIT_REFUSED, PilotController


def _serializable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.name
    raise TypeError(f"tipo no serializable: {type(value).__name__}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Ciclo seguro y temporal del piloto privado Fincilia en AWS",
    )
    value.add_argument(
        "--account-id",
        default=os.environ.get("FINCILIA_PILOT_ACCOUNT_ID", ""),
        help="Cuenta AWS exacta; tambien FINCILIA_PILOT_ACCOUNT_ID",
    )
    value.add_argument("--profile", default="fincilia-sandbox")
    value.add_argument("--region", default="sa-east-1")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    plan = commands.add_parser("plan")
    plan.add_argument("mode", choices=("cold", "warm"))
    for command in ("cold", "warm"):
        mutation = commands.add_parser(command)
        mutation.add_argument(
            "--apply",
            action="store_true",
            help="Confirma explicitamente la mutacion de infraestructura",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        controller = PilotController(
            account_id=args.account_id,
            profile=args.profile,
            region=args.region,
        )
        if args.command == "status":
            report = controller.status()
        elif args.command == "plan":
            report = controller.plan(args.mode)
        else:
            report = controller.apply_mode(args.command, apply=args.apply)
        print(json.dumps(report, indent=2, sort_keys=True, default=_serializable))
        return EXIT_OK
    except ControlError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        if "requiere --apply" in str(exc) or "autorizada" in str(exc):
            return EXIT_REFUSED
        return EXIT_EXTERNAL_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
