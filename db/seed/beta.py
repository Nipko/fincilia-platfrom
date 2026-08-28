"""Semilla minima de la beta cerrada, sin usuarios ni empresas conocidas.

Solo registra la version reproducible del motor en estado ``draft``. Las cuentas
entran mediante invitaciones de un uso y las empresas se crean por el flujo del
producto. Aprobar la release sigue siendo una accion humana explicita.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import psycopg

from fincilia_contracts.release import (
    CANONICAL_SCHEMA_VERSION,
    ENGINE_COMPONENTS,
    ENGINE_RELEASE_KEY,
)


NAMESPACE = uuid.UUID("5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e")


def release_id() -> str:
    return str(uuid.uuid5(NAMESPACE, f"engine_release:{ENGINE_RELEASE_KEY}"))


def seed(dsn: str) -> dict[str, object]:
    with psycopg.connect(dsn, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.engine_release (release_id, release_key, "
                "canonical_schema_version, classification, state, components) "
                "VALUES (%s, %s, %s, 'neutral', 'draft', %s) "
                "ON CONFLICT (release_key) DO NOTHING",
                (
                    release_id(),
                    ENGINE_RELEASE_KEY,
                    CANONICAL_SCHEMA_VERSION,
                    json.dumps(list(ENGINE_COMPONENTS)),
                ),
            )
            created = cursor.rowcount == 1
        connection.commit()
    return {
        "ok": True,
        "release_key": ENGINE_RELEASE_KEY,
        "state": "draft",
        "created": created,
        "contains_users": False,
        "contains_companies": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia closed beta seed")
    parser.add_argument("--dsn", default=os.environ.get("FINCILIA_MIGRATOR_URL", ""))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if os.environ.get("FINCILIA_REAL_DATA_ENABLED", "false").lower() != "false":
        print(json.dumps({"ok": False, "error": "beta seed requires real data disabled"}),
              file=sys.stderr)
        return 2
    if not args.dsn:
        print(json.dumps({"ok": False, "error": "--dsn or FINCILIA_MIGRATOR_URL required"}),
              file=sys.stderr)
        return 2
    try:
        report = seed(args.dsn)
    except psycopg.Error as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
