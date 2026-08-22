"""Aplicador de migraciones de Fincilia.

Implementa los invariantes que `spikes/FNC-DB-002` demostro contra PostgreSQL
real, ahora como codigo de producto:

- **una transaccion por migracion**: un fallo a mitad no deja objetos parciales ni
  fila de historial;
- **advisory lock transaccional**: dos migradores concurrentes producen una sola
  aplicacion, y el lock se libera solo al terminar;
- **checksum de contenido comprobado antes de ejecutar**: editar una migracion ya
  aplicada aborta, en vez de aplicar algo distinto de lo que se reviso;
- **`applied_at` del servidor**, no del cliente, que puede tener otro reloj;
- **forward-only**: no hay `down`. Un fallo se corrige con una migracion nueva.

Nunca corre en el arranque de la API: `startup_auto_migrate` es `false` en
`docs/database/migration-tooling.json` y un servicio que migra al arrancar migra
tantas veces como replicas tenga.

    python -m db.migrate.apply --dsn "$FINCILIA_MIGRATOR_URL"
    python -m db.migrate.apply --dsn ... --plan-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
FILENAME = re.compile(r"^(?P<version>V\d{4})__(?P<name>[a-z0-9_]+)\.sql$")
LOCK_KEY = "fincilia_schema_migration"

HISTORY_DDL = """
CREATE SCHEMA IF NOT EXISTS fincilia AUTHORIZATION CURRENT_USER;
CREATE TABLE IF NOT EXISTS fincilia.schema_history (
  version     text PRIMARY KEY,
  name        text NOT NULL,
  checksum    text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
  applied_at  timestamptz NOT NULL DEFAULT now(),
  applied_by  text NOT NULL DEFAULT current_user,
  status      text NOT NULL CHECK (status = 'applied')
);
"""


class MigrationError(RuntimeError):
    """El plan no puede aplicarse con seguridad."""


@dataclass(frozen=True, order=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str

    def as_dict(self) -> dict[str, str]:
        return {"version": self.version, "name": self.name,
                "file": self.path.name, "checksum": self.checksum}


def sha256_text(path: Path) -> str:
    # Se normalizan los finales de linea antes del hash: un checkout en Windows
    # no puede producir un checksum distinto del mismo contenido.
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Plan canonico ordenado por version, no por orden de directorio."""
    found: list[Migration] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.sql")):
        match = FILENAME.match(path.name)
        if not match:
            raise MigrationError(f"{path.name} is not named V####__name.sql")
        version = match.group("version")
        if version in seen:
            raise MigrationError(f"duplicate migration version {version}")
        seen.add(version)
        found.append(Migration(version, match.group("name"), path, sha256_text(path)))
    numbers = [int(item.version[1:]) for item in found]
    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise MigrationError(
            f"migration versions must be contiguous from V0001; found {sorted(numbers)}")
    return sorted(found)


def applied_versions(connection: psycopg.Connection) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, checksum FROM fincilia.schema_history")
        return {row[0]: row[1] for row in cursor.fetchall()}


def ensure_history(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(HISTORY_DDL)
    connection.commit()


def apply_one(connection: psycopg.Connection, migration: Migration) -> str:
    """Aplica una migracion en una sola transaccion. Devuelve el resultado."""
    with connection.transaction():
        with connection.cursor() as cursor:
            # Serializa migradores. Se libera al commit o al rollback, sin limpieza.
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))
            cursor.execute(
                "SELECT checksum FROM fincilia.schema_history WHERE version = %s",
                (migration.version,))
            row = cursor.fetchone()
            if row is not None:
                if row[0] != migration.checksum:
                    raise MigrationError(
                        f"{migration.version} was applied with checksum {row[0]} and the "
                        f"file now hashes to {migration.checksum}; editing an applied "
                        "migration is never safe")
                return "already_applied"
            cursor.execute(migration.path.read_text(encoding="utf-8"))
            cursor.execute(
                "INSERT INTO fincilia.schema_history (version, name, checksum, status) "
                "VALUES (%s, %s, %s, 'applied')",
                (migration.version, migration.name, migration.checksum))
    return "applied"


def run(dsn: str, *, directory: Path = MIGRATIONS_DIR,
        plan_only: bool = False) -> dict[str, object]:
    plan = discover(directory)
    if plan_only:
        return {"plan": [item.as_dict() for item in plan], "applied": [],
                "already_applied": [], "head": plan[-1].version if plan else None,
                "mutated": False, "ok": True}

    applied: list[str] = []
    skipped: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as connection:
        ensure_history(connection)
        known = applied_versions(connection)
        for migration in plan:
            recorded = known.get(migration.version)
            if recorded is not None and recorded != migration.checksum:
                raise MigrationError(
                    f"{migration.version} was applied with a different checksum; "
                    "an applied migration is immutable")
            outcome = apply_one(connection, migration)
            (applied if outcome == "applied" else skipped).append(migration.version)
    return {
        "plan": [item.as_dict() for item in plan],
        "applied": applied,
        "already_applied": skipped,
        "head": plan[-1].version if plan else None,
        "mutated": bool(applied),
        "ok": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia schema migrator")
    parser.add_argument("--dsn", default=None,
                        help="DSN del rol migrator; nunca el del runtime")
    parser.add_argument("--plan-only", action="store_true",
                        help="muestra el plan canonico sin tocar la base")
    parser.add_argument("--migrations", default=str(MIGRATIONS_DIR))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if not args.plan_only and not args.dsn:
        print(json.dumps({"ok": False, "error": "--dsn is required to apply"}),
              file=sys.stderr)
        return 2
    try:
        report = run(args.dsn or "", directory=Path(args.migrations),
                     plan_only=args.plan_only)
    except (MigrationError, psycopg.Error) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
