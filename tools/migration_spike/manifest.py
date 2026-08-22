"""Manifiesto y plan de migraciones del spike (FNC-DB-002).

El plan es una funcion pura del manifiesto: se ordena por version, nunca por el
orden del directorio. Si el orden del filesystem pudiera cambiar el plan, dos
maquinas aplicarian migraciones distintas al mismo commit.

Solo biblioteca estandar. Sin red, reloj, entorno, Git ni aleatoriedad.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK = "FNC-DB-002"
REQUIRED_PROJECT = "fincilia-db-spike"
VERSION_PATTERN = re.compile(r"^V(\d{4})$")
FILENAME_PATTERN = re.compile(r"^(V\d{4})__([a-z0-9_]+)\.sql$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Sentencias que este spike no acepta en una migracion de laboratorio: un `down`
# destructivo o un DROP sin adjudicacion contradicen la politica forward-only.
DESTRUCTIVE_PATTERNS = (
    re.compile(r"(?i)\bDROP\s+(TABLE|SCHEMA|DATABASE|COLUMN)\b"),
    re.compile(r"(?i)\bTRUNCATE\b"),
    re.compile(r"(?i)\bDELETE\s+FROM\b"),
)
# `CONCURRENTLY` no puede vivir dentro de una transaccion, asi que romperia la
# atomicidad que este spike existe para demostrar.
NON_TRANSACTIONAL_PATTERNS = (
    re.compile(r"(?i)\bCREATE\s+INDEX\s+CONCURRENTLY\b"),
    re.compile(r"(?i)\bDROP\s+INDEX\s+CONCURRENTLY\b"),
    re.compile(r"(?i)\bVACUUM\b"),
    re.compile(r"(?i)\bCREATE\s+DATABASE\b"),
)


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(raw: str) -> bool:
    """Rechaza absolutas, unidades de Windows y `..`, resuelva donde resuelva."""
    if not raw or raw.startswith(("/", "\\")):
        return False
    if len(raw) > 1 and raw[1] == ":":
        return False
    return ".." not in Path(raw).parts


def resolve_inside(root: Path, relative: str) -> Path | None:
    if not safe_relative(relative):
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def every_entry(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    driver = manifest.get("driver")
    if isinstance(driver, dict):
        entries.append(driver)
    for key in ("migrations", "bootstrap", "cases", "tampered", "failing"):
        for item in manifest.get(key, []) or []:
            if isinstance(item, dict):
                entries.append(item)
    return entries


def validate_manifest(manifest: dict[str, Any], spike_root: Path) -> list[Finding]:
    """Comprueba el manifiesto contra el arbol real del spike."""
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if manifest.get("schema_version") != 1:
        fail("MSP-SCHEMA", "schema_version", "schema_version must equal 1")
    if manifest.get("task_id") != REQUIRED_TASK:
        fail("MSP-TASK", "task_id", f"task_id must be {REQUIRED_TASK}")
    if manifest.get("data_classification") != "synthetic_only":
        fail("MSP-DATA-CEILING", "data_classification", "expected synthetic_only")
    if manifest.get("human_acceptance") != "pending":
        fail("MSP-ACCEPTANCE", "human_acceptance",
             "an agent cannot record human acceptance")
    if manifest.get("compose_project") != REQUIRED_PROJECT:
        fail("MSP-PROJECT", "compose_project",
             f"the spike operates only on project {REQUIRED_PROJECT!r}")

    # Digests y contencion de rutas.
    declared_paths: set[str] = set()
    for entry in every_entry(manifest):
        relative = entry.get("path", "")
        location = str(relative)
        if not isinstance(relative, str) or resolve_inside(spike_root, relative) is None:
            fail("MSP-PATH-UNSAFE", location,
                 "path is absolute, traverses or escapes the spike directory")
            continue
        declared_paths.add(relative)
        absolute = spike_root / relative
        if not absolute.is_file():
            fail("MSP-FILE-MISSING", location, "declared file does not exist")
            continue
        declared = entry.get("sha256", "")
        if not SHA256_PATTERN.match(str(declared)):
            fail("MSP-CHECKSUM", location, "sha256 is not a 64 character hex digest")
            continue
        actual = sha256_file(absolute)
        if actual != declared:
            fail("MSP-CHECKSUM", location,
                 f"checksum drifted: recorded {declared}, actual {actual}")

    # Ningun .sql del spike puede quedar fuera del manifiesto.
    for absolute in sorted(spike_root.rglob("*.sql")):
        if absolute.is_symlink():
            fail("MSP-PATH-UNSAFE", absolute.name, "a symlink is never a spike source")
            continue
        relative = absolute.relative_to(spike_root).as_posix()
        if relative not in declared_paths:
            fail("MSP-FILE-NOT-MANIFESTED", relative,
                 "this SQL file is not in the manifest; an unmanifested file could run "
                 "without anyone having reviewed its checksum")

    # Versiones: formato, unicidad, ausencia de huecos y nombre de fichero coherente.
    migrations = manifest.get("migrations", []) or []
    if not migrations:
        fail("MSP-EMPTY-PLAN", "migrations", "the spike declares no migration at all")
    seen: set[str] = set()
    numbers: list[int] = []
    for entry in migrations:
        version = str(entry.get("version", ""))
        location = f"migrations[{version or '?'}]"
        match = VERSION_PATTERN.match(version)
        if not match:
            fail("MSP-VERSION-FORMAT", location, "version must look like V0001")
            continue
        if version in seen:
            fail("MSP-VERSION-DUPLICATE", location,
                 "two migrations share a version; which one is head is undefined")
        seen.add(version)
        numbers.append(int(match.group(1)))
        relative = str(entry.get("path", ""))
        filename = Path(relative).name
        parsed = FILENAME_PATTERN.match(filename)
        if not parsed:
            fail("MSP-FILENAME", location, f"filename {filename!r} is not V####__name.sql")
        elif parsed.group(1) != version or parsed.group(2) != str(entry.get("name")):
            fail("MSP-FILENAME", location,
                 "filename disagrees with the declared version or name")
        if not relative.startswith("sql/migrations/"):
            fail("MSP-SQL-OUTSIDE", location,
                 "a migration must live under sql/migrations/")

    if numbers:
        expected = list(range(1, len(numbers) + 1))
        if sorted(numbers) != expected:
            fail("MSP-VERSION-GAP", "migrations",
                 f"versions must be contiguous from V0001; found {sorted(numbers)}")

    # Contenido de las migraciones: forward-only y transaccionable.
    for entry in migrations:
        relative = str(entry.get("path", ""))
        absolute = resolve_inside(spike_root, relative)
        if absolute is None or not absolute.is_file():
            continue
        text = absolute.read_text(encoding="utf-8")
        body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.search(body):
                fail("MSP-DESTRUCTIVE", relative,
                     f"destructive statement {pattern.pattern!r} without human adjudication; "
                     "this spike is forward-only")
        for pattern in NON_TRANSACTIONAL_PATTERNS:
            if pattern.search(body):
                fail("MSP-NON-TRANSACTIONAL", relative,
                     "this statement cannot run inside a transaction, so the migration "
                     "would stop being atomic")

    return sorted(set(findings))


def plan(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Plan canonico: ordenado por version, nunca por orden de directorio."""
    ordered = sorted(
        (entry for entry in manifest.get("migrations", []) or []),
        key=lambda entry: str(entry.get("version", "")),
    )
    return [{
        "version": str(entry.get("version", "")),
        "name": str(entry.get("name", "")),
        "path": str(entry.get("path", "")),
        "sha256": str(entry.get("sha256", "")),
    } for entry in ordered]


def plan_digest(steps: list[dict[str, str]]) -> str:
    canonical = json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
