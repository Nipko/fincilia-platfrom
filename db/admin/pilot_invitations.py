"""Invitaciones nominales para el piloto privado con datos reales.

El correo se solicita sin eco, se transforma inmediatamente en HMAC y nunca se
imprime ni se persiste. El codigo aparece una sola vez en stdout para entregarlo
por un canal privado distinto de la cuenta Google invitada.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import secrets
import uuid

import psycopg

from fincilia_platform.identity_refs import email_reference


def code_digest(code: str) -> str:
    return "sha256:" + hashlib.sha256(code.encode("utf-8")).hexdigest()


def create(connection: psycopg.Connection, *, email: str, hmac_key: str,
           hours: int) -> dict:
    if not 1 <= hours <= 24 * 30:
        raise ValueError("hours must be between 1 and 720")
    code = secrets.token_urlsafe(32)
    invitation_id = str(uuid.uuid4())
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        cursor.execute(
            "INSERT INTO fincilia.pilot_identity_invitation "
            "(invitation_id, code_digest, expected_email_ref, expires_at) "
            "VALUES (%s, %s, %s, %s)",
            (invitation_id, code_digest(code),
             email_reference(hmac_key, email), expires_at),
        )
    return {
        "invitation_id": invitation_id,
        "code": code,
        "expires_at": expires_at.isoformat(),
    }


def list_invitations(connection: psycopg.Connection) -> list[dict]:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        cursor.execute(
            "SELECT invitation_id::text, left(code_digest, 15), expires_at, "
            "consumed_at, revoked_at FROM fincilia.pilot_identity_invitation "
            "ORDER BY created_at DESC LIMIT 200")
        return [{
            "invitation_id": row[0],
            "digest_prefix": row[1],
            "expires_at": row[2].isoformat(),
            "consumed": row[3] is not None,
            "revoked": row[4] is not None,
        } for row in cursor.fetchall()]


def revoke(connection: psycopg.Connection, invitation_id: str) -> bool:
    canonical = str(uuid.UUID(invitation_id))
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        cursor.execute(
            "UPDATE fincilia.pilot_identity_invitation "
            "SET revoked_at = clock_timestamp() "
            "WHERE invitation_id = %s AND consumed_at IS NULL "
            "AND revoked_at IS NULL", (canonical,))
        return cursor.rowcount == 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Administra invitaciones nominales")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--hours", type=int, default=168)
    subparsers.add_parser("list")
    revoke_parser = subparsers.add_parser("revoke")
    revoke_parser.add_argument("--invitation", required=True)
    args = parser.parse_args()

    dsn = os.environ.get("FINCILIA_MIGRATOR_URL")
    if not dsn:
        raise SystemExit("FINCILIA_MIGRATOR_URL is required")
    with psycopg.connect(dsn, autocommit=False) as connection:
        if args.command == "create":
            key = os.environ.get("FINCILIA_IDENTITY_BINDING_HMAC_KEY")
            if not key or len(key) < 32:
                raise SystemExit("identity HMAC key must be injected by the secret provider")
            email = getpass.getpass("Verified Google account email: ")
            report = {"created": create(
                connection, email=email, hmac_key=key, hours=args.hours)}
        elif args.command == "list":
            report = {"invitations": list_invitations(connection)}
        else:
            report = {"invitation_id": args.invitation,
                      "revoked": revoke(connection, args.invitation)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
