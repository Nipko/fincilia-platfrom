"""Crea y rota los roles PostgreSQL que las migraciones dan por existentes.

Las contrasenas llegan solamente por entorno y se convierten en verificadores
SCRAM en el cliente antes de ejecutar DDL. PostgreSQL nunca recibe el secreto en
claro y la salida del proceso no incluye DSN, host, usuario ni excepciones del
proveedor.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass

import psycopg
from psycopg import sql


LOCK_KEY = "fincilia_role_bootstrap_v1"
LOGIN_ROLES = ("fincilia_app", "fincilia_worker", "fincilia_migrator")
AUTHORITY_ROLES = ("fincilia_dispatch", "fincilia_identity")
PASSWORD_ENV = {
    "fincilia_app": "FINCILIA_DB_APP_PASSWORD",
    "fincilia_worker": "FINCILIA_DB_WORKER_PASSWORD",
    "fincilia_migrator": "FINCILIA_DB_MIGRATOR_PASSWORD",
}
SAFE_DATABASE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$-]{0,62}$")
SAFE_HOST = re.compile(r"^[a-z0-9.-]{1,253}$")


class BootstrapError(RuntimeError):
    """El bootstrap no puede demostrar una configuracion segura."""


@dataclass(frozen=True)
class RoleSecrets:
    app: str
    worker: str
    migrator: str

    def as_mapping(self) -> dict[str, str]:
        return {
            "fincilia_app": self.app,
            "fincilia_worker": self.worker,
            "fincilia_migrator": self.migrator,
        }


def _validate_password(value: str) -> None:
    encoded = value.encode("utf-8")
    if (
        len(encoded) < 32
        or len(encoded) > 512
        or any(ord(character) < 33 for character in value)
    ):
        raise BootstrapError("runtime role credential is invalid")


def read_environment(environment: dict[str, str] | None = None) -> tuple[str, RoleSecrets]:
    values = environment if environment is not None else os.environ
    if values.get("FINCILIA_REAL_DATA_ENABLED") != "false":
        raise BootstrapError("bootstrap requires real data to remain disabled")
    admin_dsn = values.get("FINCILIA_BOOTSTRAP_DATABASE_URL", "")
    pg_selectors = (
        values.get("PGHOST", ""),
        values.get("PGPORT", ""),
        values.get("PGDATABASE", ""),
        values.get("PGUSER", ""),
        values.get("PGPASSWORD", ""),
    )
    if (
        (not admin_dsn and not all(pg_selectors))
        or len(admin_dsn.encode("utf-8")) > 4096
        or any(len(value.encode("utf-8")) > 1024 for value in pg_selectors)
    ):
        raise BootstrapError("bootstrap database credential is missing")
    if not admin_dsn:
        host, port, database, user, password = pg_selectors
        if (
            not SAFE_HOST.fullmatch(host)
            or not host.endswith(".rds.amazonaws.com")
            or port != "5432"
            or database != "fincilia_pilot"
            or user != "fincilia_pilot_admin"
            or len(password.encode("utf-8")) < 32
            or any(ord(character) < 33 for character in password)
        ):
            raise BootstrapError("bootstrap database selector is invalid")
    secrets = RoleSecrets(
        app=values.get(PASSWORD_ENV["fincilia_app"], ""),
        worker=values.get(PASSWORD_ENV["fincilia_worker"], ""),
        migrator=values.get(PASSWORD_ENV["fincilia_migrator"], ""),
    )
    for value in secrets.as_mapping().values():
        _validate_password(value)
    if len(set(secrets.as_mapping().values())) != len(LOGIN_ROLES):
        raise BootstrapError("runtime roles require independent credentials")
    return admin_dsn, secrets


def _exists(cursor: psycopg.Cursor, role: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s", (role,))
    return cursor.fetchone() is not None


def _scram_verifier(connection: psycopg.Connection, role: str, password: str) -> str:
    encoding = connection.info.encoding
    try:
        encrypted = connection.pgconn.encrypt_password(
            password.encode(encoding), role.encode(encoding), b"scram-sha-256"
        )
    except (AttributeError, NotImplementedError, psycopg.Error) as error:
        raise BootstrapError("SCRAM password encryption is unavailable") from error
    verifier = encrypted.decode("ascii")
    if not verifier.startswith("SCRAM-SHA-256$"):
        raise BootstrapError("SCRAM password encryption was not enforced")
    return verifier


def _configure_login_role(
    connection: psycopg.Connection,
    cursor: psycopg.Cursor,
    role: str,
    password: str,
) -> None:
    verifier = _scram_verifier(connection, role, password)
    action = sql.SQL("ALTER ROLE") if _exists(cursor, role) else sql.SQL("CREATE ROLE")
    cursor.execute(
        sql.SQL(
            "{} {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20"
        ).format(action, sql.Identifier(role), sql.Literal(verifier))
    )


def _configure_authority_role(cursor: psycopg.Cursor, role: str) -> None:
    action = sql.SQL("ALTER ROLE") if _exists(cursor, role) else sql.SQL("CREATE ROLE")
    cursor.execute(
        sql.SQL(
            "{} {} NOLOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 0"
        ).format(action, sql.Identifier(role))
    )


def bootstrap(connection: psycopg.Connection, secrets: RoleSecrets) -> dict[str, object]:
    database = connection.info.dbname
    if not database or not SAFE_DATABASE.fullmatch(database):
        raise BootstrapError("database name is not safe to provision")
    mapping = secrets.as_mapping()
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))
            for role in LOGIN_ROLES:
                _configure_login_role(connection, cursor, role, mapping[role])
            for role in AUTHORITY_ROLES:
                _configure_authority_role(cursor, role)

            cursor.execute("REVOKE fincilia_dispatch FROM fincilia_app, fincilia_worker")
            cursor.execute("REVOKE fincilia_identity FROM fincilia_app, fincilia_worker")
            cursor.execute("GRANT fincilia_dispatch TO fincilia_migrator")
            cursor.execute("GRANT fincilia_identity TO fincilia_migrator")
            cursor.execute(sql.SQL("REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(database)
            ))
            cursor.execute(sql.SQL(
                "REVOKE CREATE, TEMPORARY ON DATABASE {} FROM fincilia_app, fincilia_worker"
            ).format(sql.Identifier(database)))
            cursor.execute(sql.SQL(
                "GRANT CONNECT ON DATABASE {} TO fincilia_app, fincilia_worker, fincilia_migrator"
            ).format(sql.Identifier(database)))
            cursor.execute(sql.SQL("GRANT CREATE ON DATABASE {} TO fincilia_migrator").format(
                sql.Identifier(database)
            ))
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    return {
        "ok": True,
        "database_authority": "separate_admin",
        "login_roles": list(LOGIN_ROLES),
        "authority_roles": list(AUTHORITY_ROLES),
        "password_transport": "client_generated_scram_verifier",
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        admin_dsn, secrets = read_environment()
        with psycopg.connect(admin_dsn) as connection:
            report = bootstrap(connection, secrets)
    except (BootstrapError, UnicodeError, psycopg.Error):
        print(json.dumps({"ok": False, "error": "bootstrap_failed"}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
