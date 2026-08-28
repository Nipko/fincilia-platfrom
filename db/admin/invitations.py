"""Administracion humana de invitaciones para la beta cerrada sintetica.

Los codigos se generan con entropia criptografica, se imprimen una sola vez y
PostgreSQL conserva unicamente SHA-256. No se envian por correo ni se escriben
en logs, Git, S3 o Parameter Store.

    python -m db.admin.invitations create --hours 168 --count 3
    python -m db.admin.invitations list
    python -m db.admin.invitations revoke --invitation <UUID>
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import secrets
import uuid

import psycopg


def code_digest(code: str) -> str:
    return "sha256:" + hashlib.sha256(code.encode("utf-8")).hexdigest()


def new_code() -> str:
    return secrets.token_urlsafe(24)


def create(connection: psycopg.Connection, *, hours: int, count: int) -> list[dict]:
    if not 1 <= hours <= 24 * 30:
        raise ValueError("hours must be between 1 and 720")
    if not 1 <= count <= 50:
        raise ValueError("count must be between 1 and 50")
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)
    created: list[dict] = []
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        for _ in range(count):
            invitation_id = str(uuid.uuid4())
            code = new_code()
            cursor.execute(
                "INSERT INTO fincilia.beta_invitation "
                "(invitation_id, code_digest, expires_at) VALUES (%s, %s, %s)",
                (invitation_id, code_digest(code), expires_at),
            )
            created.append({
                "invitation_id": invitation_id,
                "code": code,
                "expires_at": expires_at.isoformat(),
            })
    return created


def list_invitations(connection: psycopg.Connection) -> list[dict]:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        cursor.execute(
            "SELECT invitation_id::text, left(code_digest, 15), expires_at, "
            "consumed_at, revoked_at FROM fincilia.beta_invitation "
            "ORDER BY created_at DESC LIMIT 200"
        )
        return [
            {
                "invitation_id": row[0],
                "digest_prefix": row[1],
                "expires_at": row[2].isoformat(),
                "consumed": row[3] is not None,
                "revoked": row[4] is not None,
            }
            for row in cursor.fetchall()
        ]


def revoke(connection: psycopg.Connection, invitation_id: str) -> bool:
    try:
        canonical = str(uuid.UUID(invitation_id))
    except ValueError as error:
        raise ValueError("invitation must be a UUID") from error
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE fincilia_identity")
        cursor.execute(
            "UPDATE fincilia.beta_invitation SET revoked_at = clock_timestamp() "
            "WHERE invitation_id = %s AND consumed_at IS NULL AND revoked_at IS NULL",
            (canonical,),
        )
        return cursor.rowcount == 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Administra invitaciones beta")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--hours", type=int, default=168)
    create_parser.add_argument("--count", type=int, default=1)
    subparsers.add_parser("list")
    revoke_parser = subparsers.add_parser("revoke")
    revoke_parser.add_argument("--invitation", required=True)
    args = parser.parse_args()

    if os.environ.get("FINCILIA_REAL_DATA_ENABLED", "false").lower() != "false":
        raise SystemExit("beta invitations require FINCILIA_REAL_DATA_ENABLED=false")
    dsn = os.environ.get("FINCILIA_MIGRATOR_URL")
    if not dsn:
        raise SystemExit("FINCILIA_MIGRATOR_URL is required")

    with psycopg.connect(dsn, autocommit=False) as connection:
        if args.command == "create":
            report = {"created": create(
                connection, hours=args.hours, count=args.count)}
        elif args.command == "list":
            report = {"invitations": list_invitations(connection)}
        else:
            report = {"invitation_id": args.invitation,
                      "revoked": revoke(connection, args.invitation)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
