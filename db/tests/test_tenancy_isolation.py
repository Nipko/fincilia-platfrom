"""Pruebas de aislamiento de tenancy contra PostgreSQL real.

**No** son pruebas unitarias: exigen la base levantada y las migraciones
aplicadas. Se ejecutan asi:

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest discover -s /app/db/tests -t /app/db/tests

Lo que comprueban no se puede comprobar de otra forma: que una politica de RLS
funcione es una propiedad del motor, no del codigo que la escribe. Un mock diria
que si siempre.

Cada prueba siembra con el rol migrator y lee con el rol runtime, que es la
separacion real: el runtime nunca es propietario y por tanto **no** queda exento
de la politica aunque alguien olvide `FORCE`.
"""

from __future__ import annotations

import os
import unittest
import uuid

import psycopg

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
RUNTIME_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")

COMPANY_SCOPED_TABLES = ("company", "engagement", "company_grant",
                         "authorization_version", "audit_event")


def new_id() -> str:
    # uuid4 solo genera identificadores de fixtures; ninguna decision depende de el.
    return str(uuid.uuid4())


class TenancyIsolationTests(unittest.TestCase):
    """Dos companias sinteticas, dos contextos, cero filtraciones."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        cls.firm_id = new_id()
        cls.company_a = new_id()
        cls.company_b = new_id()
        cls.subject_a = new_id()
        cls.granter = new_id()
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.firm (firm_id, legal_name) VALUES (%s, %s)",
                    (cls.firm_id, "Firma Sintetica"))
                for subject in (cls.subject_a, cls.granter):
                    cursor.execute(
                        "INSERT INTO fincilia.subject (subject_id, subject_kind, "
                        "display_name) VALUES (%s, 'person', %s)",
                        (subject, f"sujeto {subject[:8]}"))
                for index, company in enumerate((cls.company_a, cls.company_b)):
                    # Aprovisionar tambien declara sobre que company se actua: con
                    # FORCE ROW LEVEL SECURITY el migrator no queda exento de la
                    # politica, que es justamente lo que estas pruebas comprueban.
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    cursor.execute(
                        "INSERT INTO fincilia.company (company_id, legal_name, "
                        "tax_id_token, country_code) VALUES (%s, %s, %s, 'CO')",
                        (company, f"Empresa Sintetica {index}", f"token-{company[:8]}"))
                    cursor.execute(
                        "INSERT INTO fincilia.authorization_version (company_id, version) "
                        "VALUES (%s, 1)", (company,))
                    cursor.execute(
                        "INSERT INTO fincilia.engagement (engagement_id, firm_id, "
                        "company_id, valid_from) VALUES (%s, %s, %s, DATE '2026-01-01')",
                        (new_id(), cls.firm_id, company))
                # El sujeto solo tiene grant sobre A.
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (cls.company_a,))
                cursor.execute(
                    "INSERT INTO fincilia.company_grant (grant_id, company_id, "
                    "subject_id, company_role, granted_by) "
                    "VALUES (%s, %s, %s, 'preparer', %s)",
                    (new_id(), cls.company_a, cls.subject_a, cls.granter))

    @classmethod
    def tearDownClass(cls) -> None:
        # Las pruebas siembran datos sinteticos en la base local compartida. Sin
        # limpieza, cada ejecucion deja dos companias mas y el entorno de demo deja
        # de parecerse a lo que ve un usuario.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (cls.company_a, cls.company_b):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    for table in ("audit_event", "company_grant", "engagement",
                                  "authorization_version", "company"):
                        cursor.execute(
                            "DELETE FROM fincilia.%s WHERE company_id = %%s" % table,
                            (company,))
                cursor.execute("SELECT set_config('fincilia.company_id', '', false)")
                cursor.execute("DELETE FROM fincilia.membership WHERE firm_id = %s",
                               (cls.firm_id,))
                cursor.execute("DELETE FROM fincilia.firm WHERE firm_id = %s",
                               (cls.firm_id,))
                cursor.execute(
                    "DELETE FROM fincilia.subject WHERE subject_id = ANY(%s)",
                    ([cls.subject_a, cls.granter],))

    def migrator(self, company_id: str | None = None):
        """Conexion del migrator, opcionalmente con contexto de company.

        Sin contexto, RLS niega antes de que la restriccion llegue a evaluarse:
        una prueba de UNIQUE o de CHECK sin contexto no probaria la restriccion,
        sino otra vez la politica.
        """
        connection = psycopg.connect(MIGRATOR_DSN, autocommit=True)
        if company_id is not None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (company_id,))
        return connection

    def runtime(self, company_id: str | None):
        connection = psycopg.connect(RUNTIME_DSN, autocommit=True)
        if company_id is not None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (company_id,))
        return connection

    # ------------------------------------------------------------------ #
    # Aislamiento
    # ------------------------------------------------------------------ #

    def test_a_context_sees_only_its_own_company(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT company_id::text FROM fincilia.company")
            visible = {row[0] for row in cursor.fetchall()}
        self.assertEqual(visible, {self.company_a})
        self.assertNotIn(self.company_b, visible)

    def test_every_company_scoped_table_is_isolated(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            for table in COMPANY_SCOPED_TABLES:
                with self.subTest(table=table):
                    cursor.execute(
                        f"SELECT count(*) FROM fincilia.{table} "
                        "WHERE company_id::text <> current_setting('fincilia.company_id')")
                    self.assertEqual(cursor.fetchone()[0], 0)

    def test_without_a_context_nothing_is_visible(self) -> None:
        with self.runtime(None) as connection, connection.cursor() as cursor:
            for table in COMPANY_SCOPED_TABLES:
                with self.subTest(table=table):
                    cursor.execute(f"SELECT count(*) FROM fincilia.{table}")
                    self.assertEqual(cursor.fetchone()[0], 0)

    def test_writing_into_another_company_is_denied(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "action, resource_kind, resource_ref, outcome) "
                    "VALUES (%s, %s, 'probe', 'test', 'x', 'allowed')",
                    (new_id(), self.company_b))

    def test_writing_into_the_own_company_is_allowed(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "action, resource_kind, resource_ref, outcome) "
                "VALUES (%s, %s, 'probe', 'test', 'x', 'allowed')",
                (new_id(), self.company_a))
            cursor.execute("SELECT count(*) FROM fincilia.audit_event")
            self.assertGreaterEqual(cursor.fetchone()[0], 1)

    def test_writing_without_a_context_is_denied(self) -> None:
        with self.runtime(None) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "action, resource_kind, resource_ref, outcome) "
                    "VALUES (%s, %s, 'probe', 'test', 'x', 'allowed')",
                    (new_id(), self.company_a))

    def test_a_forged_context_only_reaches_a_company_that_exists(self) -> None:
        # Fijar un company_id inventado no abre nada: la politica compara contra
        # la fila, no contra una lista de permitidos que el cliente proponga.
        with self.runtime(new_id()) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.company")
            self.assertEqual(cursor.fetchone()[0], 0)

    # ------------------------------------------------------------------ #
    # Privilegios
    # ------------------------------------------------------------------ #

    def test_the_runtime_role_is_not_privileged(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user")
            self.assertEqual(list(cursor.fetchone()), [False, False, False, False])

    def test_the_runtime_role_owns_nothing(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                "ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'fincilia' AND pg_get_userbyid(c.relowner) = current_user")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_the_runtime_role_cannot_change_the_schema(self) -> None:
        statements = (
            "CREATE TABLE fincilia.should_not_exist (id integer)",
            "ALTER TABLE fincilia.company ADD COLUMN should_not_exist text",
            "DROP TABLE fincilia.company",
        )
        for statement in statements:
            with self.subTest(statement=statement.split()[0]):
                with self.runtime(self.company_a) as connection, \
                        connection.cursor() as cursor:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement)

    def test_the_runtime_role_cannot_rewrite_the_audit_trail(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "action, resource_kind, resource_ref, outcome) "
                "VALUES (%s, %s, 'probe', 'test', 'x', 'allowed')",
                (new_id(), self.company_a))
        for statement in ("UPDATE fincilia.audit_event SET outcome = 'denied'",
                          "DELETE FROM fincilia.audit_event"):
            with self.subTest(statement=statement.split()[0]):
                with self.runtime(self.company_a) as connection, \
                        connection.cursor() as cursor:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement)

    def test_the_runtime_role_cannot_disable_row_level_security(self) -> None:
        with self.runtime(self.company_a) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("ALTER TABLE fincilia.company DISABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------ #
    # Esquema
    # ------------------------------------------------------------------ #

    def test_every_company_scoped_table_forces_row_level_security(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection, \
                connection.cursor() as cursor:
            for table in COMPANY_SCOPED_TABLES:
                with self.subTest(table=table):
                    cursor.execute(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE oid = %s::regclass", (f"fincilia.{table}",))
                    enabled, forced = cursor.fetchone()
                    self.assertTrue(enabled, f"{table} has no RLS")
                    self.assertTrue(forced, f"{table} does not FORCE RLS")

    def test_the_owner_is_also_subject_to_the_policy(self) -> None:
        # Con FORCE, ni siquiera el propietario del esquema ve otra compania sin
        # contexto. Sin FORCE, esta prueba devolveria las dos.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection, \
                connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.company")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_a_firm_cannot_hold_two_active_engagements_on_one_company(self) -> None:
        with self.migrator(self.company_a) as connection, \
                connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.UniqueViolation):
                cursor.execute(
                    "INSERT INTO fincilia.engagement (engagement_id, firm_id, "
                    "company_id, valid_from) VALUES (%s, %s, %s, DATE '2026-02-01')",
                    (new_id(), self.firm_id, self.company_a))

    def test_nobody_grants_a_role_to_themselves(self) -> None:
        with self.migrator(self.company_a) as connection, \
                connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "INSERT INTO fincilia.company_grant (grant_id, company_id, "
                    "subject_id, company_role, granted_by) "
                    "VALUES (%s, %s, %s, 'owner', %s)",
                    (new_id(), self.company_a, self.subject_a, self.subject_a))

    def test_the_schema_history_records_what_was_applied(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection, \
                connection.cursor() as cursor:
            cursor.execute(
                "SELECT version, checksum, applied_at IS NOT NULL "
                "FROM fincilia.schema_history ORDER BY version")
            rows = cursor.fetchall()
        self.assertGreaterEqual(len(rows), 1)
        for version, checksum, has_time in rows:
            self.assertRegex(version, r"^V\d{4}$")
            self.assertRegex(checksum, r"^[0-9a-f]{64}$")
            self.assertTrue(has_time)


if __name__ == "__main__":
    unittest.main()
