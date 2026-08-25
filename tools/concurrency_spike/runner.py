"""Runner confinado para el laboratorio PostgreSQL FNC-DB-004."""

from __future__ import annotations

import os
import subprocess  # nosec B404 - only fixed argv lists, never a shell
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPIKE_ROOT = ROOT / "spikes/FNC-DB-004"
PROJECT = "fincilia-concurrency-spike"
SERVICE = "postgres"
DATABASE = "fincilia_concurrency_spike"
SQL_ROOT = "/spike/sql"
OUTPUT_CAP = 131_072
ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "HOME",
                 "USERPROFILE", "WSLENV", "LANG", "LC_ALL")
ADAPTERS: tuple[dict[str, Any], ...] = (
    {"id": "direct", "prefix": ("docker",),
     "probe": ("docker", "version", "--format", "{{.Server.Version}}"),
     "translate": False},
    {"id": "wsl", "prefix": ("wsl", "-e", "docker"),
     "probe": ("wsl", "-e", "docker", "version", "--format", "{{.Server.Version}}"),
     "translate": True},
)


class RunnerError(Exception):
    """The requested operation escapes the fixed laboratory."""


@dataclass(frozen=True)
class Execution:
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    status: str
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"exit_code": self.exit_code, "status": self.status,
                "truncated": self.truncated,
                "stdout_tail": self.stdout[-600:], "stderr_tail": self.stderr[-600:]}


def environment(parent: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if parent is None else parent
    return {key: source[key] for key in ENV_ALLOWLIST if key in source}


def wsl_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) > 1 and value[1] == ":":
        return f"/mnt/{value[0].lower()}{value[2:]}"
    return value


def execute(argv: list[str], *, timeout: int = 180,
            env: dict[str, str] | None = None) -> Execution:
    if not argv or not all(isinstance(part, str) and part for part in argv):
        raise RunnerError("argv must be a non-empty list of strings")
    if any(any(marker in part for marker in ("&&", "||", ";", "`", "$(", "\n"))
           for part in argv):
        raise RunnerError("shell syntax is forbidden")
    try:
        result = subprocess.run(  # nosec B603 - allowlisted fixed argv
            argv, shell=False, capture_output=True, check=False, timeout=timeout,
            env=environment() if env is None else env,
        )
    except subprocess.TimeoutExpired:
        return Execution(tuple(argv), None, "", "", "timeout")
    except (OSError, ValueError) as error:
        return Execution(tuple(argv), None, "", type(error).__name__, "unavailable")
    truncated = len(result.stdout) > OUTPUT_CAP or len(result.stderr) > OUTPUT_CAP
    return Execution(
        tuple(argv), result.returncode,
        result.stdout[:OUTPUT_CAP].decode("utf-8", errors="replace"),
        result.stderr[:OUTPUT_CAP].decode("utf-8", errors="replace"),
        "completed", truncated,
    )


def probe_adapter(adapters: tuple[dict[str, Any], ...] = ADAPTERS) -> dict[str, Any] | None:
    for adapter in adapters:
        result = execute(list(adapter["probe"]), timeout=30)
        if result.status == "completed" and result.exit_code == 0:
            return {**adapter, "server_version": result.stdout.strip()[:64]}
    return None


class Lab:
    def __init__(self, adapter: dict[str, Any], *, root: Path = SPIKE_ROOT,
                 project: str = PROJECT) -> None:
        if project != PROJECT:
            raise RunnerError("refusing to operate outside the concurrency spike project")
        self.root = root.resolve()
        self.compose = (self.root / "compose.yaml").resolve()
        try:
            self.compose.relative_to(self.root)
        except ValueError as error:
            raise RunnerError("compose must remain inside the spike") from error
        if not self.compose.is_file():
            raise RunnerError("compose file is missing")
        self.adapter = adapter
        self.env = environment()

    def compose_argv(self, *args: str) -> list[str]:
        path = wsl_path(self.compose) if self.adapter.get("translate") else self.compose.as_posix()
        return [*self.adapter["prefix"], "compose", "-f", path, "-p", PROJECT, *args]

    def psql_argv(self, role: str, script: str,
                  variables: dict[str, str] | None = None) -> list[str]:
        if role not in {"fnc_concurrency_bootstrap", "fnc_concurrency_runtime"}:
            raise RunnerError("database role is not allowlisted")
        relative = Path(script)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".sql":
            raise RunnerError("SQL path is not confined")
        host_script = self.root / "sql" / relative
        if not host_script.is_file():
            raise RunnerError("SQL script is missing")
        argv = self.compose_argv(
            "exec", "-T", SERVICE, "psql", "-v", "ON_ERROR_STOP=1",
            "-U", role, "-d", DATABASE, "--no-psqlrc", "--quiet",
        )
        for key, value in sorted((variables or {}).items()):
            if not key.replace("_", "").isalnum() or len(value) > 100:
                raise RunnerError("psql variable is invalid")
            argv += ["-v", f"{key}={value}"]
        argv += ["-f", f"{SQL_ROOT}/{relative.as_posix()}"]
        return argv

    def command(self, *args: str, timeout: int = 180) -> Execution:
        return execute(self.compose_argv(*args), timeout=timeout, env=self.env)

    def sql(self, role: str, script: str,
            variables: dict[str, str] | None = None,
            *, timeout: int = 180) -> Execution:
        return execute(self.psql_argv(role, script, variables), timeout=timeout, env=self.env)

    def fresh(self) -> list[Execution]:
        return [
            self.command("down", "--volumes", "--remove-orphans"),
            self.command("config", "--quiet", timeout=90),
            self.command("up", "-d", "--wait", SERVICE, timeout=300),
        ]

    def cleanup(self) -> Execution:
        return self.command("down", "--volumes", "--remove-orphans")


def _ok(execution: Execution, marker: str | None = None) -> bool:
    return (execution.status == "completed" and execution.exit_code == 0
            and not execution.truncated
            and (marker is None or marker in execution.stdout))


def _case_001(lab: Lab) -> dict[str, Any]:
    reset = lab.sql("fnc_concurrency_bootstrap", "reset.sql")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(
            lab.sql, "fnc_concurrency_runtime", "claim.sql",
            {"worker": worker, "lease_ms": "60000"},
        ) for worker in ("worker-a", "worker-b")]
        claims = [future.result() for future in futures]
    probe = lab.sql("fnc_concurrency_bootstrap", "probe_idem_001.sql")
    claimed = sum("CLAIMED|" in result.stdout for result in claims)
    no_claim = sum("NO_CLAIM" in result.stdout for result in claims)
    passed = _ok(reset) and all(_ok(item) for item in claims) and claimed == 1 \
        and no_claim == 1 and _ok(probe, "FNC_IDEM_001_OK")
    return {"id": "TST-IDEM-001", "ok": passed, "claimed": claimed,
            "not_claimed": no_claim, "probe": probe.as_dict()}


def _case_004(lab: Lab) -> dict[str, Any]:
    reset_failure = lab.sql("fnc_concurrency_bootstrap", "reset.sql")
    injected = lab.sql("fnc_concurrency_runtime", "claim_and_fail.sql",
                       {"worker": "worker-crash"})
    rollback = lab.sql("fnc_concurrency_bootstrap", "probe_atomic_rollback.sql")
    reset = lab.sql("fnc_concurrency_bootstrap", "reset.sql")
    committed = lab.sql("fnc_concurrency_runtime", "claim_and_commit.sql",
                        {"worker": "worker-commit"})
    pending = lab.sql("fnc_concurrency_bootstrap", "probe_pending.sql")
    delivered = lab.sql("fnc_concurrency_runtime", "deliver.sql",
                        {"dispatcher": "dispatcher-a"})
    replay = lab.sql("fnc_concurrency_runtime", "deliver.sql",
                     {"dispatcher": "dispatcher-a"})
    probe = lab.sql("fnc_concurrency_bootstrap", "probe_idem_004.sql")
    passed = (_ok(reset_failure) and injected.exit_code not in (None, 0)
              and _ok(rollback, "FNC_ATOMIC_ROLLBACK_OK") and _ok(reset)
              and _ok(committed) and "committed" in committed.stdout
              and _ok(pending, "FNC_OUTBOX_PENDING_OK")
              and _ok(delivered) and "delivered" in delivered.stdout
              and _ok(replay) and not replay.stdout.strip()
              and _ok(probe, "FNC_IDEM_004_OK"))
    return {"id": "TST-IDEM-004", "ok": passed,
            "rollback_injection_exit": injected.exit_code,
            "pending": pending.as_dict(), "probe": probe.as_dict()}


def _case_005(lab: Lab) -> dict[str, Any]:
    reset = lab.sql("fnc_concurrency_bootstrap", "reset.sql")
    first = lab.sql("fnc_concurrency_runtime", "claim.sql",
                    {"worker": "worker-old", "lease_ms": "60000"})
    expired = lab.sql("fnc_concurrency_bootstrap", "expire.sql")
    second = lab.sql("fnc_concurrency_runtime", "claim.sql",
                     {"worker": "worker-new", "lease_ms": "60000"})
    stale = lab.sql("fnc_concurrency_runtime", "stale_commit.sql",
                    {"worker": "worker-old", "token": "1"})
    current = lab.sql("fnc_concurrency_runtime", "current_commit.sql",
                      {"worker": "worker-new", "token": "2"})
    probe = lab.sql("fnc_concurrency_bootstrap", "probe_idem_005.sql")
    passed = (all(_ok(item) for item in (reset, first, expired, second, stale, current))
              and "CLAIMED|synthetic-work-001|1" in first.stdout
              and "CLAIMED|synthetic-work-001|2" in second.stdout
              and "stale_lease" in stale.stdout and "committed" in current.stdout
              and _ok(probe, "FNC_IDEM_005_OK"))
    return {"id": "TST-IDEM-005", "ok": passed,
            "stale_result": stale.stdout.strip(), "probe": probe.as_dict()}


def run(*, repeat: int = 2) -> dict[str, Any]:
    if repeat not in range(1, 6):
        raise RunnerError("repeat must be between 1 and 5")
    adapter = probe_adapter()
    if adapter is None:
        return {"ok": False, "status": "runtime_unavailable", "runs": []}
    lab = Lab(adapter)
    lifecycle = lab.fresh()
    runs: list[dict[str, Any]] = []
    payload: dict[str, Any]
    try:
        if not all(_ok(item) for item in lifecycle):
            payload = {"ok": False, "status": "startup_failed",
                       "lifecycle": [item.as_dict() for item in lifecycle], "runs": []}
        else:
            privileges = lab.sql("fnc_concurrency_bootstrap", "probe_privileges.sql")
            for number in range(1, repeat + 1):
                cases = [_case_001(lab), _case_004(lab), _case_005(lab)]
                runs.append({"iteration": number,
                             "ok": all(case["ok"] for case in cases), "cases": cases})
            payload = {
                "ok": _ok(privileges, "FNC_PRIVILEGES_OK")
                and all(item["ok"] for item in runs),
                "status": "completed", "adapter": adapter["id"],
                "server_version": adapter.get("server_version"), "runs": runs,
                "privileges": privileges.as_dict(),
            }
    finally:
        cleanup = lab.cleanup()
    payload["cleanup"] = cleanup.as_dict()
    if not _ok(cleanup):
        payload["ok"] = False
        payload["status"] = "cleanup_failed"
    return payload
