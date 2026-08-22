"""Capa de proceso de la CLI de desarrollo (FNC-PLT-007).

Todo comando se ejecuta con lista `argv`, `shell=False`, cwd confinado al arbol y
entorno por allowlist. No hay strings de comando, no hay `eval`, no hay expansion
de globs y ninguna variable de entorno se interpreta como comando.

Reglas de veredicto, deliberadas:

- un timeout **no** es un PASS;
- una salida truncada **no** es un PASS: si no se pudo leer el resultado, no se sabe;
- una herramienta ausente **no** es un PASS: es un diagnostico aparte;
- un exit inesperado **no** se redondea a nada.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - argv list, shell=False, allowlisted modules only
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.dev_cli.registry import (
    ALLOWED_EXTERNAL,
    ALLOWED_MODULES,
    SHELL_TOKENS,
    resolve_inside,
)

DEFAULT_ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "HOME",
                         "USERPROFILE", "WSLENV", "LANG", "LC_ALL")
FORBIDDEN_ENV_MARKERS = ("PROXY", "TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL",
                         "AWS_", "AZURE_", "GCP_")

LOCK_NAME = "fincilia-dev-cli-stack.lock"


class DevCliError(Exception):
    """La CLI no puede ejecutar lo que se le pide con seguridad."""


@dataclass
class Outcome:
    """Resultado de un check. Sin payloads completos y sin entorno."""
    check_id: str
    status: str
    exit_code: int | None
    duration_visible: bool = True
    truncated: bool = False
    detail: str = ""
    stdout_tail: str = field(default="", repr=False)
    stderr_tail: str = field(default="", repr=False)
    argv: tuple[str, ...] = ()

    def as_dict(self, *, include_output: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "truncated": self.truncated,
            "argv": list(self.argv),
        }
        if self.detail:
            payload["detail"] = self.detail
        if include_output:
            payload["stdout_tail"] = self.stdout_tail[-600:]
            payload["stderr_tail"] = self.stderr_tail[-600:]
        return payload


def build_environment(allowlist: tuple[str, ...] | list[str] = DEFAULT_ENV_ALLOWLIST,
                      parent: dict[str, str] | None = None) -> dict[str, str]:
    """Entorno minimo, con una segunda barrera contra proxies y credenciales."""
    source = os.environ if parent is None else parent
    env: dict[str, str] = {}
    for name in allowlist:
        upper = str(name).upper()
        if any(marker in upper for marker in FORBIDDEN_ENV_MARKERS):
            continue
        if name in source:
            env[name] = source[name]
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def assert_safe_argv(argv: list[str]) -> None:
    if not argv or not all(isinstance(item, str) for item in argv):
        raise DevCliError("argv must be a non-empty list of strings")
    for item in argv:
        for token in SHELL_TOKENS:
            if token in item:
                raise DevCliError(f"argv element {item!r} contains shell syntax {token!r}")


def python_argv(module_argv: list[str]) -> list[str]:
    """Antepone el interprete actual y comprueba el allowlist de modulos."""
    assert_safe_argv(module_argv)
    if module_argv[0] != "-m" or len(module_argv) < 2:
        raise DevCliError("only `-m <module>` invocations are allowed")
    if module_argv[1] not in ALLOWED_MODULES:
        raise DevCliError(f"module {module_argv[1]!r} is not allowlisted")
    return [sys.executable, *module_argv]


def external_argv(argv: list[str]) -> list[str]:
    assert_safe_argv(argv)
    if argv[0] not in ALLOWED_EXTERNAL:
        raise DevCliError(f"external binary {argv[0]!r} is not allowlisted")
    return list(argv)


def run(argv: list[str], *, root: Path, cwd: str = ".", timeout: int = 300,
        cap: int = 262_144, env: dict[str, str] | None = None,
        check_id: str = "") -> Outcome:
    working = resolve_inside(root, cwd)
    if working is None or not working.is_dir():
        raise DevCliError(f"cwd {cwd!r} is absolute, traverses, is a symlink or is missing")
    environment = env if env is not None else build_environment()
    environment = {**environment, "PYTHONPATH": str(root.resolve())}
    try:
        completed = subprocess.run(  # nosec B603 - argv list, shell=False, allowlisted
            argv, cwd=str(working), env=environment, capture_output=True,
            shell=False, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Outcome(check_id, "timeout", None, detail=f"exceeded {timeout}s",
                       argv=tuple(argv))
    except (OSError, ValueError) as error:
        return Outcome(check_id, "dependency_missing", None,
                       detail=f"could not start: {type(error).__name__}",
                       argv=tuple(argv))
    truncated = len(completed.stdout) > cap or len(completed.stderr) > cap
    stdout = completed.stdout[:cap].decode("utf-8", errors="replace")
    stderr = completed.stderr[:cap].decode("utf-8", errors="replace")
    if truncated:
        return Outcome(check_id, "failed", completed.returncode, truncated=True,
                       detail="output truncated; the result could not be read",
                       stdout_tail=stdout, stderr_tail=stderr, argv=tuple(argv))
    status = "passed" if completed.returncode == 0 else "failed"
    return Outcome(check_id, status, completed.returncode, truncated=False,
                   detail="" if status == "passed"
                   else (stderr or stdout).strip()[-300:],
                   stdout_tail=stdout, stderr_tail=stderr, argv=tuple(argv))


def run_check(check: dict[str, Any], root: Path,
              env_allowlist: tuple[str, ...] | list[str] = DEFAULT_ENV_ALLOWLIST,
              ) -> Outcome:
    argv = python_argv(list(check.get("argv", [])))
    return run(argv, root=root, cwd=str(check.get("cwd", ".")),
               timeout=int(check.get("timeout_seconds", 300)),
               cap=int(check.get("max_output_bytes", 262_144)),
               env=build_environment(env_allowlist),
               check_id=str(check.get("id", "")))


def probe_dependency(dependency: dict[str, Any], root: Path) -> dict[str, Any]:
    """Comprueba una dependencia sin convertir su ausencia en un traceback."""
    probe = list(dependency.get("probe_argv", []))
    identifier = str(dependency.get("id", ""))
    required = bool(dependency.get("required", False))
    try:
        argv = external_argv(probe) if probe and probe[0] in ALLOWED_EXTERNAL \
            else python_argv(probe)
    except DevCliError as error:
        return {"id": identifier, "required": required, "status": "invalid_probe",
                "detail": str(error), "version": ""}
    outcome = run(argv, root=root, timeout=int(dependency.get("timeout_seconds", 30)),
                  cap=8192, check_id=identifier)
    if outcome.status == "passed":
        return {"id": identifier, "required": required, "status": "available",
                "detail": "", "version": outcome.stdout_tail.strip()[:80]}
    return {
        "id": identifier, "required": required,
        "status": "missing" if outcome.status == "dependency_missing" else "unusable",
        "detail": dependency.get("diagnosis", "") or outcome.detail,
        "version": "",
    }


class StackLock:
    """Lock local para que dos comandos mutadores no corran a la vez.

    Se crea con O_EXCL, de modo que la exclusion la garantiza el sistema de
    ficheros y no una comprobacion previa que podria perder la carrera.
    """

    def __init__(self, directory: Path | None = None, name: str = LOCK_NAME) -> None:
        base = directory if directory is not None else Path(tempfile.gettempdir())
        self.path = base / name
        self.descriptor: int | None = None

    def acquire(self) -> None:
        try:
            self.descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise DevCliError(
                f"another mutating stack command holds {self.path}. If no other run is "
                "active, remove that file by hand and try again."
            ) from error
        os.write(self.descriptor, str(os.getpid()).encode("ascii"))

    def release(self) -> None:
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "StackLock":
        self.acquire()
        return self

    def __exit__(self, *_exception: object) -> None:
        self.release()
