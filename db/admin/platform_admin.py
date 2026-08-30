"""Bootstrap operativo del primer superadmin de Fincilia.

La herramienta corre con el rol migrador y configura una referencia HMAC, no
un correo en claro. La API solo podrá reclamarla cuando Google entregue el mismo
correo verificado y PostgreSQL lo ligue al sujeto interno.

El correo se lee de ``FINCILIA_PLATFORM_BOOTSTRAP_EMAIL`` para no dejarlo en el
historial de comandos. La clave se lee de
``FINCILIA_IDENTITY_BINDING_HMAC_KEY`` y nunca se imprime.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

from fincilia_platform.identity_refs import IdentityReferenceError, email_reference


class AdminError(Exception):
    """La configuracion solicitada no es segura o no procede."""


def configure(connection: psycopg.Connection, *, email: str, key: str,
              actor: str, reference: str) -> dict:
    for label, value, low, high in (
        ("actor", actor, 3, 120), ("reference", reference, 3, 200)
    ):
        if not low <= len(value.strip()) <= high:
            raise AdminError(f"{label} must be between {low} and {high} characters")
    try:
        expected = email_reference(key, email)
    except IdentityReferenceError as error:
        raise AdminError("bootstrap identity configuration is invalid") from error

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT claimed_by::text FROM fincilia.platform_bootstrap_control "
            "WHERE singleton FOR UPDATE"
        )
        current = cursor.fetchone()
        if current is not None and current[0] is not None:
            raise AdminError("initial platform superadmin was already claimed")
        cursor.execute(
            "INSERT INTO fincilia.platform_bootstrap_control ("
            "singleton, expected_verified_email_ref, configured_by, configuration_ref"
            ") VALUES (true, %s, %s, %s) "
            "ON CONFLICT (singleton) DO UPDATE SET "
            "expected_verified_email_ref = EXCLUDED.expected_verified_email_ref, "
            "configured_by = EXCLUDED.configured_by, "
            "configuration_ref = EXCLUDED.configuration_ref, "
            "configured_at = clock_timestamp() "
            "WHERE fincilia.platform_bootstrap_control.claimed_by IS NULL",
            (expected, actor.strip(), reference.strip()),
        )
    return {"configured": True, "claimed": False,
            "identity_reference": "hmac-sha256:v1:[redacted]"}


def status(connection: psycopg.Connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT configured_at, claimed_by::text, claimed_at "
            "FROM fincilia.platform_bootstrap_control WHERE singleton"
        )
        row = cursor.fetchone()
    if row is None:
        return {"configured": False, "claimed": False}
    return {
        "configured": True,
        "configured_at": row[0].isoformat(),
        "claimed": row[1] is not None,
        "claimed_subject_id": row[1],
        "claimed_at": row[2].isoformat() if row[2] else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap del superadmin inicial")
    parser.add_argument("--dsn", default=os.environ.get("FINCILIA_MIGRATOR_URL", ""))
    commands = parser.add_subparsers(dest="command", required=True)
    configure_parser = commands.add_parser("configure")
    configure_parser.add_argument("--actor", required=True)
    configure_parser.add_argument("--ref", required=True)
    commands.add_parser("status")
    args = parser.parse_args(argv)

    if not args.dsn:
        print(json.dumps({"ok": False, "error": "migrator DSN required"}),
              file=sys.stderr)
        return 2
    try:
        with psycopg.connect(args.dsn, autocommit=False) as connection:
            if args.command == "configure":
                email = os.environ.get("FINCILIA_PLATFORM_BOOTSTRAP_EMAIL", "")
                key = os.environ.get("FINCILIA_IDENTITY_BINDING_HMAC_KEY", "")
                if not email or not key:
                    raise AdminError(
                        "FINCILIA_PLATFORM_BOOTSTRAP_EMAIL and "
                        "FINCILIA_IDENTITY_BINDING_HMAC_KEY are required"
                    )
                report = configure(connection, email=email, key=key,
                                   actor=args.actor, reference=args.ref)
            else:
                report = status(connection)
            connection.commit()
    except AdminError as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(json.dumps({"ok": False, "error": type(error).__name__}),
              file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **report}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
