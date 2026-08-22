"""CLI segura de desarrollo y diagnostico local (FNC-PLT-007).

    python -m tools.dev_cli.cli doctor
    python -m tools.dev_cli.cli validate [--group core|security|data|qa|all]
    python -m tools.dev_cli.cli test [--group unit|golden|mutation|all]
    python -m tools.dev_cli.cli stack status|up|down
    python -m tools.dev_cli.cli evidence summary

Compone contratos que ya existen; no crea una segunda fuente de verdad. No
instala, no actualiza, no purga, no borra volumenes, no siembra datos, no ejecuta
migraciones de producto y no cambia ningun gate ni documento.

JSON es la representacion canonica; `--format text` es una vista, no otra verdad.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

from tools.dev_cli.process import (
    DevCliError,
    StackLock,
    build_environment,
    external_argv,
    probe_dependency,
    run,
    run_check,
)
from tools.dev_cli.registry import (
    EXIT_CHECK_FAILED,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INVALID_USAGE,
    EXIT_OK,
    EXIT_TIMEOUT,
    checks_for,
    known_groups,
    resolve_inside,
    validate_contract,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = Path("docs/platform/developer-cli.json")
MINIMUM_PYTHON = (3, 11)


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit(payload: dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for line in _as_text(payload):
        print(line)


def _as_text(payload: dict[str, Any]) -> list[str]:
    """Vista legible. Nunca contiene nada que el JSON no contenga."""
    lines: list[str] = []
    for key in ("command", "group", "ok"):
        if key in payload:
            lines.append(f"{key}: {payload[key]}")
    for row in payload.get("dependencies", []):
        lines.append(f"  dependency {row['id']:<22} {row['status']}"
                     f"{'  (required)' if row.get('required') else ''}")
    for row in payload.get("checks", []):
        lines.append(f"  check {row['check_id']:<34} {row['status']:<18} "
                     f"exit={row['exit_code']}")
    for row in payload.get("services", []):
        lines.append(f"  service {row}")
    for key in ("summary", "note", "reason"):
        if payload.get(key):
            lines.append(f"{key}: {payload[key]}")
    return lines


def load_contract(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_root(raw: str | None) -> Path:
    if raw is None:
        return REPOSITORY_ROOT
    candidate = Path(raw)
    if ".." in candidate.parts:
        raise ValueError("root must not traverse with '..'")
    if candidate.is_symlink():
        raise ValueError("root must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise ValueError(f"root is not an existing directory: {raw}")
    return resolved


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #

def command_doctor(contract: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    """Diagnostico. Sigue funcionando sin Docker: si no lo hiciera, seria inutil
    justo cuando mas falta hace."""
    contract_errors = validate_contract(contract, root)
    interpreter_ok = sys.version_info[:2] >= MINIMUM_PYTHON
    dependencies = [probe_dependency(item, root)
                    for item in contract.get("dependencies", []) or []]
    missing_required = [item["id"] for item in dependencies
                        if item["required"] and item["status"] != "available"]
    paths = []
    for relative in contract.get("expected_paths", []) or []:
        resolved = resolve_inside(root, str(relative))
        paths.append({"path": str(relative),
                      "status": "present" if resolved and resolved.exists()
                      else ("unsafe" if resolved is None else "missing")})
    missing_paths = [item["path"] for item in paths if item["status"] != "present"]

    payload = {
        "command": "doctor",
        "python": {
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "minimum": ".".join(str(part) for part in MINIMUM_PYTHON),
            "satisfied": interpreter_ok,
            "implementation": platform.python_implementation(),
        },
        "contract_valid": not contract_errors,
        "contract_errors": [item.as_dict() for item in contract_errors],
        "dependencies": dependencies,
        "optional_unavailable": sorted(item["id"] for item in dependencies
                                       if not item["required"]
                                       and item["status"] != "available"),
        "missing_required_dependencies": sorted(missing_required),
        "paths": paths,
        "missing_paths": sorted(missing_paths),
        "note": "Un doctor en verde dice que las herramientas responden, no que el "
                "repositorio este correcto. Eso lo dicen los validadores.",
        "ok": interpreter_ok and not contract_errors and not missing_required
        and not missing_paths,
    }
    if not payload["ok"] and missing_required:
        return payload, EXIT_DEPENDENCY_MISSING
    return payload, EXIT_OK if payload["ok"] else EXIT_CHECK_FAILED


# --------------------------------------------------------------------------- #
# validate / test
# --------------------------------------------------------------------------- #

def _run_group(contract: dict[str, Any], root: Path, kind: str, group: str,
               verbose: bool) -> tuple[dict[str, Any], int]:
    contract_errors = validate_contract(contract, root)
    if contract_errors:
        return {"command": kind, "group": group, "ok": False,
                "contract_errors": [item.as_dict() for item in contract_errors],
                "checks": [],
                "reason": "the contract is invalid; nothing was executed"}, \
            EXIT_INVALID_USAGE

    available = known_groups(contract, kind)
    if group != "all" and group not in available:
        return {"command": kind, "group": group, "ok": False, "checks": [],
                "known_groups": available,
                "reason": f"unknown group {group!r}"}, EXIT_INVALID_USAGE

    selected = checks_for(contract, kind, group)
    if not selected:
        return {"command": kind, "group": group, "ok": False, "checks": [],
                "reason": "no check matched; an empty run is never a pass"}, \
            EXIT_INVALID_USAGE

    dependency_index = {item.get("id"): item
                        for item in contract.get("dependencies", []) or []}
    probed: dict[str, dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []

    for check in selected:
        blocked = ""
        for dependency_id in check.get("requires", []) or []:
            if dependency_id not in probed:
                probed[dependency_id] = probe_dependency(
                    dependency_index[dependency_id], root)
            if probed[dependency_id]["status"] != "available":
                blocked = dependency_id
                break
        if blocked:
            outcomes.append({
                "check_id": check["id"], "status": "dependency_missing",
                "exit_code": None, "truncated": False, "argv": [],
                "detail": f"{blocked} is not available; the check was not executed and "
                          "an unexecuted check is never a pass",
            })
            continue
        try:
            outcome = run_check(check, root,
                                contract["environment_policy"]["env_allowlist"])
        except DevCliError as error:
            outcomes.append({"check_id": check["id"], "status": "refused",
                             "exit_code": None, "truncated": False, "argv": [],
                             "detail": str(error)})
            continue
        outcomes.append(outcome.as_dict(include_output=verbose))

    counts = {status: sum(1 for item in outcomes if item["status"] == status)
              for status in sorted({item["status"] for item in outcomes})}
    failed = [item["check_id"] for item in outcomes if item["status"] == "failed"]
    timed_out = [item["check_id"] for item in outcomes if item["status"] == "timeout"]
    missing = [item["check_id"] for item in outcomes
               if item["status"] in ("dependency_missing", "refused")]

    # Un fallo previsto sigue siendo un fallo: la nota solo ayuda a triarlo.
    expected = {str(check["id"]): str(check.get("expected_today", ""))
                for check in selected if check.get("expected_today")}
    unexpected = sorted(item for item in failed if item not in expected)

    payload = {
        "command": kind,
        "group": group,
        "executed": len(outcomes),
        "counts": counts,
        "checks": outcomes,
        "failed_checks": sorted(failed),
        "unexpected_failures": unexpected,
        "expected_failures": {item: expected[item] for item in sorted(failed)
                              if item in expected},
        "timed_out_checks": sorted(timed_out),
        "not_executed_checks": sorted(missing),
        "aggregate_score": None,
        "note": "Cada check conserva su propio resultado. Un fallo previsto sigue "
                "contando como fallo; la nota solo dice por que ya se sabia.",
        "ok": not failed and not timed_out and not missing,
    }
    if timed_out:
        return payload, EXIT_TIMEOUT
    if missing and not failed:
        return payload, EXIT_DEPENDENCY_MISSING
    return payload, EXIT_OK if payload["ok"] else EXIT_CHECK_FAILED


# --------------------------------------------------------------------------- #
# stack
# --------------------------------------------------------------------------- #

def _compose_argv(contract: dict[str, Any], root: Path, *arguments: str) -> list[str]:
    stack = contract.get("stack", {})
    compose_file = resolve_inside(root, str(stack.get("compose_file")))
    if compose_file is None or not compose_file.is_file():
        raise DevCliError("the declared compose file is missing or unsafe")
    return external_argv([
        "docker", "compose",
        "-f", compose_file.as_posix(),
        "-p", str(stack.get("compose_project")),
        *arguments,
    ])


def command_stack(contract: dict[str, Any], root: Path, action: str,
                  verbose: bool, lock_dir: Path | None = None,
                  ) -> tuple[dict[str, Any], int]:
    contract_errors = validate_contract(contract, root)
    if contract_errors:
        return {"command": f"stack {action}", "ok": False,
                "contract_errors": [item.as_dict() for item in contract_errors],
                "reason": "the contract is invalid; nothing was executed"}, \
            EXIT_INVALID_USAGE

    stack = contract.get("stack", {})
    docker = next((item for item in contract.get("dependencies", []) or []
                   if item.get("id") == "docker_daemon"), None)
    if docker is None:
        return {"command": f"stack {action}", "ok": False,
                "reason": "the contract declares no docker_daemon dependency"}, \
            EXIT_INVALID_USAGE
    probe = probe_dependency(docker, root)
    if probe["status"] != "available":
        return {"command": f"stack {action}", "ok": False, "docker": probe,
                "reason": "Docker is not available. `doctor`, `validate` and `test` "
                          "keep working without it.",
                "note": "Una herramienta ausente es un diagnostico, no un traceback."}, \
            EXIT_DEPENDENCY_MISSING

    arguments = {
        "status": ("ps", "--format", "json"),
        "up": ("up", "-d", "--wait"),
        # Nunca `--volumes` ni `--remove-orphans`: esta CLI no destruye datos locales.
        "down": ("down",),
    }[action]

    try:
        argv = _compose_argv(contract, root, *arguments)
    except DevCliError as error:
        return {"command": f"stack {action}", "ok": False, "reason": str(error)}, \
            EXIT_INVALID_USAGE

    mutating = action in ("up", "down")
    lock: StackLock | None = None
    if mutating and stack.get("lock_required"):
        lock = StackLock(lock_dir)
        try:
            lock.acquire()
        except DevCliError as error:
            return {"command": f"stack {action}", "ok": False, "reason": str(error),
                    "note": "Dos comandos mutadores no pueden correr a la vez."}, \
                EXIT_INVALID_USAGE
    try:
        outcome = run(argv, root=root, cwd=str(stack.get("cwd", ".")),
                      timeout=int(stack.get("timeout_seconds", 300)),
                      env=build_environment(contract["environment_policy"]["env_allowlist"]),
                      check_id=f"stack-{action}")
    finally:
        if lock is not None:
            lock.release()

    services: list[str] = []
    if action == "status" and outcome.status == "passed":
        for line in outcome.stdout_tail.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            services.append(f"{row.get('Service', '?')} {row.get('State', '?')}")

    payload = {
        "command": f"stack {action}",
        "compose_project": stack.get("compose_project"),
        "compose_file": stack.get("compose_file"),
        "classification": "read_only" if action == "status" else "local_reversible",
        "removes_volumes": False,
        "removes_orphans": False,
        "services": sorted(services),
        "result": outcome.as_dict(include_output=verbose),
        "note": "`down` nunca usa --volumes ni --remove-orphans: esta CLI no borra datos.",
        "ok": outcome.status == "passed",
    }
    if outcome.status == "timeout":
        return payload, EXIT_TIMEOUT
    return payload, EXIT_OK if payload["ok"] else EXIT_CHECK_FAILED


# --------------------------------------------------------------------------- #
# evidence
# --------------------------------------------------------------------------- #

def command_evidence(contract: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    """Resumen de lo declarado. No ejecuta nada y no produce evidencia nueva."""
    contract_errors = validate_contract(contract, root)
    rows: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for source in contract.get("evidence_sources", []) or []:
        relative = str(source.get("path", ""))
        resolved = resolve_inside(root, relative)
        if resolved is None or not resolved.is_file():
            unreadable.append(relative)
            continue
        try:
            document = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable.append(relative)
            continue
        gates = document.get("gates") or document.get("decision_gates") or []
        rows.append({
            "path": relative,
            "task_id": document.get("task_id") or document.get("task") or "",
            "status": document.get("status", ""),
            "human_acceptance": document.get("human_acceptance", ""),
            "data_ceiling": document.get("data_ceiling", ""),
            "gates_not_met": sorted(
                str(gate.get("id")) for gate in gates
                if isinstance(gate, dict) and gate.get("status", gate.get("state"))
                != "met"),
            "unresolved_decisions": len(document.get("unresolved_decisions", []) or []),
        })

    accepted = [row["path"] for row in rows if row["human_acceptance"] == "accepted"]
    payload = {
        "command": "evidence summary",
        "contract_valid": not contract_errors,
        "sources": sorted(rows, key=lambda row: row["path"]),
        "unreadable_sources": sorted(unreadable),
        "sources_with_human_acceptance": sorted(accepted),
        "total_unresolved_decisions": sum(row["unresolved_decisions"] for row in rows),
        "aggregate_score": None,
        "note": "Este comando lee lo que otros contratos declaran. No ejecuta nada, no "
                "acepta nada y no produce evidencia nueva.",
        "ok": not contract_errors and not unreadable,
    }
    return payload, EXIT_OK if payload["ok"] else EXIT_CHECK_FAILED


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia developer CLI")
    parser.add_argument("--root", default=None)
    parser.add_argument("--contract", default=None)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="local diagnosis; works without Docker")
    validate_parser = subparsers.add_parser("validate", help="run contract validators")
    validate_parser.add_argument("--group", default="all")
    test_parser = subparsers.add_parser("test", help="run test suites")
    test_parser.add_argument("--group", default="all")
    stack_parser = subparsers.add_parser("stack", help="local stack lifecycle")
    stack_parser.add_argument("action", choices=("status", "up", "down"))
    evidence_parser = subparsers.add_parser("evidence", help="summarise declared evidence")
    evidence_parser.add_argument("action", choices=("summary",))

    args = parser.parse_args(argv)
    _use_utf8_streams()

    try:
        root = resolve_root(args.root)
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return EXIT_INVALID_USAGE

    contract_path = Path(args.contract) if args.contract else (root / DEFAULT_CONTRACT)
    try:
        contract = load_contract(contract_path)
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": f"unreadable contract: {error}"}),
              file=sys.stderr)
        return EXIT_INVALID_USAGE

    if args.command == "doctor":
        payload, code = command_doctor(contract, root)
    elif args.command == "validate":
        payload, code = _run_group(contract, root, "validate", args.group, args.verbose)
    elif args.command == "test":
        payload, code = _run_group(contract, root, "test", args.group, args.verbose)
    elif args.command == "stack":
        payload, code = command_stack(contract, root, args.action, args.verbose)
    else:
        payload, code = command_evidence(contract, root)

    _emit(payload, args.format)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
