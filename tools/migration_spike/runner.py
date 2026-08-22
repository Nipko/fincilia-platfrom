"""Ejecucion del laboratorio PostgreSQL del spike (FNC-DB-002).

Todo comando es una lista `argv` con `shell=False`. No hay strings de comando, no
hay `eval`, no hay scripts recibidos desde JSON y ninguna variable de entorno se
interpreta como comando.

El runner solo puede tocar UN proyecto de Compose: `fincilia-db-spike`, con el
fichero del propio spike. Cualquier otro nombre de proyecto o cualquier ruta de
Compose fuera del directorio del spike aborta antes de ejecutar nada.

Adaptadores de runtime: en Linux y en CI el binario `docker` esta en el PATH; en
un Windows con Docker dentro de WSL hay que atravesar `wsl -e`. Se prueban en
orden con un argv de sondeo fijo y se usa el primero que responde. La traduccion
de rutas de Windows a `/mnt/<unidad>` es determinista y solo se aplica al
adaptador que la declara.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - argv list, shell=False, allowlisted local commands only
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPIKE_PROJECT = "fincilia-db-spike"
CONTAINER_SQL_ROOT = "/spike/sql"
SERVICE = "postgres"

ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE",
                 "WSLENV", "LANG", "LC_ALL")

# Adaptadores allowlisted. `prefix` es lo unico que puede preceder a `compose`.
ADAPTERS: tuple[dict[str, Any], ...] = (
    {
        "id": "direct",
        "prefix": ("docker",),
        "probe": ("docker", "version", "--format", "{{.Server.Version}}"),
        "translate_paths": False,
    },
    {
        "id": "wsl",
        "prefix": ("wsl", "-e", "docker"),
        "probe": ("wsl", "-e", "docker", "version", "--format", "{{.Server.Version}}"),
        "translate_paths": True,
    },
)

DEFAULT_TIMEOUT = 180
DEFAULT_OUTPUT_CAP = 262_144


class SpikeRunnerError(Exception):
    """El laboratorio no puede operarse con seguridad."""


@dataclass
class Execution:
    """Resultado de un comando, acotado y sin payloads completos."""
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    status: str
    detail: str = ""

    def as_dict(self, *, include_output: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "status": self.status,
            "truncated": self.truncated,
        }
        if self.detail:
            payload["detail"] = self.detail
        if include_output:
            payload["stdout_tail"] = self.stdout[-800:]
            payload["stderr_tail"] = self.stderr[-800:]
        return payload


@dataclass
class CaseResult:
    case_id: str
    invariant: str
    expectation: str
    outcome: str
    detail: str
    executions: list[Execution] = field(default_factory=list)

    def as_dict(self, *, include_output: bool = False) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "invariant": self.invariant,
            "expectation": self.expectation,
            "outcome": self.outcome,
            "detail": self.detail,
            "executions": [item.as_dict(include_output=include_output)
                           for item in self.executions],
        }


def build_environment(parent: dict[str, str] | None = None) -> dict[str, str]:
    """Entorno minimo. No hereda proxies, tokens ni credenciales."""
    source = os.environ if parent is None else parent
    return {name: source[name] for name in ENV_ALLOWLIST if name in source}


def to_wsl_path(path: Path) -> str:
    """`C:\\Users\\x` -> `/mnt/c/Users/x`. Determinista y sin tocar el filesystem."""
    text = Path(path).as_posix()
    if len(text) > 1 and text[1] == ":":
        return f"/mnt/{text[0].lower()}{text[2:]}"
    return text


def host_path(adapter: dict[str, Any], path: Path) -> str:
    return to_wsl_path(path) if adapter.get("translate_paths") else Path(path).as_posix()


def run_argv(argv: list[str], *, timeout: int = DEFAULT_TIMEOUT,
             cap: int = DEFAULT_OUTPUT_CAP,
             env: dict[str, str] | None = None,
             stdin_text: str | None = None) -> Execution:
    if not argv or not all(isinstance(item, str) for item in argv):
        raise SpikeRunnerError("argv must be a non-empty list of strings")
    for item in argv:
        if any(token in item for token in ("&&", "||", ";", "`", "$(", "\n")):
            raise SpikeRunnerError(f"argv element {item!r} looks like shell syntax")
    try:
        completed = subprocess.run(  # nosec B603 - argv list, shell=False, no user input
            argv, capture_output=True, shell=False, check=False, timeout=timeout,
            env=env if env is not None else build_environment(),
            input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        )
    except subprocess.TimeoutExpired:
        return Execution(tuple(argv), None, "", "", False, "timeout",
                         "the command exceeded its timeout; the outcome is unknown")
    except (OSError, ValueError) as error:
        return Execution(tuple(argv), None, "", "", False, "unavailable",
                         type(error).__name__)
    raw_out, raw_err = completed.stdout, completed.stderr
    truncated = len(raw_out) > cap or len(raw_err) > cap
    return Execution(
        tuple(argv), completed.returncode,
        raw_out[:cap].decode("utf-8", errors="replace"),
        raw_err[:cap].decode("utf-8", errors="replace"),
        truncated, "completed",
    )


def probe_adapter(env: dict[str, str] | None = None,
                  adapters: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any] | None:
    """Primer adaptador que responde. Si ninguno responde, no hay runtime.

    `adapters` es inyectable para que las pruebas puedan comprobar el caso sin
    runtime sin depender de que la maquina lo tenga o no.
    """
    for adapter in (ADAPTERS if adapters is None else adapters):
        execution = run_argv(list(adapter["probe"]), timeout=30, env=env)
        if execution.status == "completed" and execution.exit_code == 0:
            return {**adapter, "server_version": execution.stdout.strip()[:64]}
    return None


class SpikeLab:
    """Opera exclusivamente el proyecto de Compose del spike."""

    def __init__(self, adapter: dict[str, Any], spike_root: Path,
                 compose_file: str = "compose.yaml",
                 project: str = SPIKE_PROJECT,
                 database: str = "fincilia_db_spike",
                 env: dict[str, str] | None = None) -> None:
        if project != SPIKE_PROJECT:
            raise SpikeRunnerError(
                f"refusing to operate project {project!r}; this runner only ever touches "
                f"{SPIKE_PROJECT!r}")
        resolved = (spike_root / compose_file).resolve()
        try:
            resolved.relative_to(spike_root.resolve())
        except ValueError as error:
            raise SpikeRunnerError("the compose file must live inside the spike") from error
        if not resolved.is_file():
            raise SpikeRunnerError(f"compose file not found: {resolved}")
        self.adapter = adapter
        self.spike_root = spike_root.resolve()
        self.compose_path = resolved
        self.project = project
        self.database = database
        self.env = env if env is not None else build_environment()

    # ------------------------------------------------------------------ #
    # Construccion de argv
    # ------------------------------------------------------------------ #

    def compose_argv(self, *arguments: str) -> list[str]:
        return [
            *self.adapter["prefix"], "compose",
            "-f", host_path(self.adapter, self.compose_path),
            "-p", self.project,
            *arguments,
        ]

    def psql_argv(self, role: str, script: str, variables: dict[str, str] | None = None,
                  *, single_transaction: bool = True) -> list[str]:
        if not script.startswith(CONTAINER_SQL_ROOT + "/"):
            raise SpikeRunnerError(
                f"refusing to run {script!r}: scripts live under {CONTAINER_SQL_ROOT}")
        arguments = ["exec", "-T", SERVICE, "psql",
                     "-v", "ON_ERROR_STOP=1", "-U", role, "-d", self.database,
                     "--no-psqlrc", "--quiet"]
        if single_transaction:
            arguments.append("--single-transaction")
        for key, value in sorted((variables or {}).items()):
            arguments += ["-v", f"{key}={value}"]
        arguments += ["-f", script]
        return self.compose_argv(*arguments)

    def container_script(self, relative: str) -> str:
        """`sql/cases/x.sql` -> `/spike/sql/cases/x.sql`."""
        if not relative.startswith("sql/") or ".." in Path(relative).parts:
            raise SpikeRunnerError(f"refusing script path {relative!r}")
        return f"{CONTAINER_SQL_ROOT}/{relative[len('sql/'):]}"

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #

    def config(self) -> Execution:
        return run_argv(self.compose_argv("config", "--quiet"), env=self.env, timeout=90)

    def up(self, *, fresh: bool = False) -> list[Execution]:
        executions: list[Execution] = []
        if fresh:
            executions.append(self.down())
        executions.append(run_argv(
            self.compose_argv("up", "-d", "--wait", SERVICE), env=self.env, timeout=300))
        return executions

    def down(self) -> Execution:
        # `--volumes` solo puede aplicarse aqui porque el proyecto y el fichero de
        # Compose estan fijados a los del spike y verificados en el constructor.
        return run_argv(
            self.compose_argv("down", "--volumes", "--remove-orphans"),
            env=self.env, timeout=180)

    # ------------------------------------------------------------------ #
    # Aplicacion de migraciones
    # ------------------------------------------------------------------ #

    def apply_step(self, step: dict[str, str], *, role: str = "fnc_spike_migrator",
                   driver: str = "sql/apply_one.sql",
                   override_path: str | None = None,
                   override_checksum: str | None = None) -> Execution:
        script = self.container_script(driver)
        variables = {
            "version": step["version"],
            "name": step["name"],
            "checksum": override_checksum or step["sha256"],
            "file": self.container_script(override_path or step["path"]),
        }
        return run_argv(self.psql_argv(role, script, variables), env=self.env)

    def run_case(self, relative: str, role: str,
                 variables: dict[str, str] | None = None) -> Execution:
        return run_argv(
            self.psql_argv(role, self.container_script(relative), variables),
            env=self.env)

    def apply_step_async(self, step: dict[str, str],
                         role: str = "fnc_spike_migrator") -> subprocess.Popen:
        """Lanza una aplicacion sin esperar: sirve para la carrera de migradores."""
        argv = self.psql_argv(role, self.container_script("sql/apply_one.sql"), {
            "version": step["version"], "name": step["name"],
            "checksum": step["sha256"], "file": self.container_script(step["path"]),
        })
        return subprocess.Popen(  # nosec B603 - argv list, shell=False, fixed allowlist
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, env=self.env)
