from __future__ import annotations

import contextlib
import io
import os
import unittest

import psycopg

from .roles import (
    AUTHORITY_ROLES,
    LOGIN_ROLES,
    BootstrapError,
    RoleSecrets,
    bootstrap,
    main,
    read_environment,
)


SAFE = RoleSecrets("a" * 32, "b" * 32, "c" * 32)


class EnvironmentTests(unittest.TestCase):
    def values(self) -> dict[str, str]:
        return {
            "FINCILIA_BOOTSTRAP_DATABASE_URL": "postgresql://hidden.invalid/fincilia",
            "FINCILIA_REAL_DATA_ENABLED": "false",
            "FINCILIA_DB_APP_PASSWORD": "a" * 32,
            "FINCILIA_DB_WORKER_PASSWORD": "b" * 32,
            "FINCILIA_DB_MIGRATOR_PASSWORD": "c" * 32,
        }

    def test_requires_three_independent_long_credentials(self) -> None:
        _, secrets = read_environment(self.values())
        self.assertEqual(SAFE, secrets)
        values = self.values()
        values["FINCILIA_DB_WORKER_PASSWORD"] = values["FINCILIA_DB_APP_PASSWORD"]
        with self.assertRaises(BootstrapError):
            read_environment(values)

    def test_rejects_control_characters_and_missing_admin_dsn(self) -> None:
        values = self.values()
        values["FINCILIA_DB_APP_PASSWORD"] = "x" * 32 + "\n"
        with self.assertRaises(BootstrapError):
            read_environment(values)

    def test_accepts_libpq_environment_without_composing_a_dsn(self) -> None:
        values = self.values()
        values.pop("FINCILIA_BOOTSTRAP_DATABASE_URL")
        values.update({
            "PGHOST": "fincilia.abc.sa-east-1.rds.amazonaws.com",
            "PGPORT": "5432",
            "PGDATABASE": "fincilia_pilot",
            "PGUSER": "fincilia_pilot_admin",
            "PGPASSWORD": "hidden-admin-password-value-00001",
        })
        dsn, secrets = read_environment(values)
        self.assertEqual("", dsn)
        self.assertEqual(SAFE, secrets)
        values = self.values()
        values.pop("FINCILIA_BOOTSTRAP_DATABASE_URL")
        with self.assertRaises(BootstrapError):
            read_environment(values)

    def test_failure_output_never_echoes_environment_secrets(self) -> None:
        secret = "never-print-this-bootstrap-secret"
        original = dict(os.environ)
        output = io.StringIO()
        try:
            os.environ.clear()
            os.environ.update({
                "FINCILIA_REAL_DATA_ENABLED": "false",
                "FINCILIA_BOOTSTRAP_DATABASE_URL": secret,
                "FINCILIA_DB_APP_PASSWORD": secret,
                "FINCILIA_DB_WORKER_PASSWORD": secret,
                "FINCILIA_DB_MIGRATOR_PASSWORD": secret,
            })
            with contextlib.redirect_stdout(output):
                self.assertEqual(1, main())
        finally:
            os.environ.clear()
            os.environ.update(original)
        self.assertNotIn(secret, output.getvalue())
        self.assertEqual('{"error": "bootstrap_failed", "ok": false}\n', output.getvalue())


@unittest.skipUnless(
    os.environ.get("FINCILIA_BOOTSTRAP_TEST_URL"),
    "disposable PostgreSQL bootstrap DSN is required",
)
class PostgreSQLBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.admin_dsn = os.environ["FINCILIA_BOOTSTRAP_TEST_URL"]
        cls.secrets = RoleSecrets(
            os.environ["FINCILIA_DB_APP_PASSWORD"],
            os.environ["FINCILIA_DB_WORKER_PASSWORD"],
            os.environ["FINCILIA_DB_MIGRATOR_PASSWORD"],
        )

    def test_bootstrap_is_idempotent_and_roles_are_minimal(self) -> None:
        with psycopg.connect(self.admin_dsn) as connection:
            first = bootstrap(connection, self.secrets)
            second = bootstrap(connection, self.secrets)
            self.assertEqual(first, second)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, "
                    "rolcreaterole, rolinherit, rolreplication, rolbypassrls, "
                    "rolconnlimit, rolpassword LIKE 'SCRAM-SHA-256$%%' "
                    "FROM pg_catalog.pg_authid WHERE rolname = ANY(%s) ORDER BY rolname",
                    (list(LOGIN_ROLES + AUTHORITY_ROLES),),
                )
                rows = {row[0]: row[1:] for row in cursor.fetchall()}
                self.assertEqual(set(LOGIN_ROLES + AUTHORITY_ROLES), set(rows))
                for role in LOGIN_ROLES:
                    self.assertEqual(
                        (True, False, False, False, False, False, False, 20, True),
                        rows[role],
                    )
                for role in AUTHORITY_ROLES:
                    self.assertEqual(
                        (False, False, False, False, False, False, False, 0, None),
                        rows[role],
                    )
                cursor.execute(
                    "SELECT parent.rolname, member.rolname "
                    "FROM pg_catalog.pg_auth_members membership "
                    "JOIN pg_catalog.pg_roles parent ON parent.oid = membership.roleid "
                    "JOIN pg_catalog.pg_roles member ON member.oid = membership.member "
                    "WHERE parent.rolname = ANY(%s)",
                    (list(AUTHORITY_ROLES),),
                )
                self.assertEqual(
                    {(role, "fincilia_migrator") for role in AUTHORITY_ROLES},
                    set(cursor.fetchall()),
                )


if __name__ == "__main__":
    unittest.main()
