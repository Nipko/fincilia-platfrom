"""Protocolo de despacho: privilegios, arriendos, recuperacion y carta muerta.

Todo se comprueba contra PostgreSQL real y **conectandose como cada rol**. Un
privilegio negativo afirmado desde otro rol no prueba nada: si estas pruebas
usaran el rol del migrador para comprobar que la API no puede escribir en la
cola, pasarian aunque la API pudiera.

Los escenarios de caida no simulan una caida con un `mock`: reproducen el estado
que una caida deja en la base -- un arriendo abierto que nadie cierra -- y
comprueban que el sistema se recupera desde ahi. Es el unico modo de probar que
un trabajo no queda invisible para siempre, que es exactamente lo que pasaba.
"""

from __future__ import annotations

import os
import unittest
import uuid

import psycopg

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
APP_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")

NAMESPACE = uuid.UUID("5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e")
SANDBOX_A = str(uuid.uuid5(NAMESPACE, "company:sandbox_a"))
SANDBOX_B = str(uuid.uuid5(NAMESPACE, "company:sandbox_b"))
ANA = str(uuid.uuid5(NAMESPACE, "subject:ana"))

LEASE = 60


def connect(dsn: str, company: str | None = None) -> psycopg.Connection:
    connection = psycopg.connect(dsn, autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                       (company or "",))
    return connection


class DispatchProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (MIGRATOR_DSN and APP_DSN and WORKER_DSN):
            raise unittest.SkipTest("migrator, app and worker DSNs are required")
        from db.seed.local import DEFAULT_SECRET, seed
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.artifacts: list[tuple[str, str]] = []

    @classmethod
    def tearDownClass(cls) -> None:
        # Se limpia con el migrador, que es el unico que puede: ni la API ni el
        # worker pueden borrar evidencia ni historial, y esta bien que no puedan.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company, artifact in cls.artifacts:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    cursor.execute(
                        "DELETE FROM fincilia.dispatch_pointer WHERE run_id IN "
                        "(SELECT run_id FROM fincilia.processing_run WHERE artifact_id = %s)",
                        (artifact,))
                    cursor.execute(
                        "DELETE FROM fincilia.dead_letter_item WHERE work_id IN "
                        "(SELECT run_id FROM fincilia.processing_run WHERE artifact_id = %s)",
                        (artifact,))
                    cursor.execute(
                        "DELETE FROM fincilia.run_attempt WHERE run_id IN "
                        "(SELECT run_id FROM fincilia.processing_run WHERE artifact_id = %s)",
                        (artifact,))
                    cursor.execute(
                        "DELETE FROM fincilia.processing_run WHERE artifact_id = %s",
                        (artifact,))
                    cursor.execute(
                        "DELETE FROM fincilia.source_artifact WHERE artifact_id = %s",
                        (artifact,))

    # ------------------------------------------------------------- utilidades #

    def artifact(self, company: str = SANDBOX_A) -> str:
        """Un artefacto sintetico, creado con el rol que si puede crearlos."""
        artifact_id = str(uuid.uuid4())
        digest = uuid.uuid4().hex + uuid.uuid4().hex
        with connect(MIGRATOR_DSN, company) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                "filename, byte_size, content_sha256, media_type, zone, object_key, "
                "status, uploaded_by) VALUES (%s, %s, 'x.csv', 10, %s, 'text/csv', "
                "'raw', %s, 'stored', %s)",
                (artifact_id, company, digest, f"k/{digest}", ANA))
        type(self).artifacts.append((company, artifact_id))
        return artifact_id

    def enqueue(self, artifact_id: str, company: str = SANDBOX_A,
                kind: str = "profile") -> str:
        with connect(APP_DSN, company) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT fincilia.enqueue_processing_run(%s, %s, %s)::text",
                           (company, artifact_id, kind))
            return cursor.fetchone()[0]

    def claim(self, worker: str = "w1", lease: int = LEASE):
        with connect(WORKER_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT run_id::text, company_id::text, artifact_id::text, kind, "
                "attempt, lease_token::text FROM fincilia.claim_next_run(%s, %s)",
                (worker, lease))
            return cursor.fetchone()

    def finish(self, run_id: str, token: str, company: str = SANDBOX_A, *,
               result: str | None = None, error: str | None = None,
               failure: str | None = None) -> str:
        with connect(WORKER_DSN, company) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT fincilia.finish_run(%s, %s, %s::jsonb, %s, %s)",
                           (run_id, token, result, error, failure))
            return cursor.fetchone()[0]

    def run_row(self, run_id: str, company: str = SANDBOX_A) -> dict:
        with connect(MIGRATOR_DSN, company) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, attempt, error_code, failure_class, lease_token, "
                "started_at, finished_at FROM fincilia.processing_run WHERE run_id = %s",
                (run_id,))
            row = cursor.fetchone()
        self.assertIsNotNone(row, "the run disappeared")
        return dict(zip(("status", "attempt", "error_code", "failure_class",
                         "lease_token", "started_at", "finished_at"), row))

    def pointer_count(self, run_id: str) -> int:
        with connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.dispatch_pointer "
                           "WHERE run_id = %s", (run_id,))
            return cursor.fetchone()[0]

    def expire_lease(self, run_id: str, company: str = SANDBOX_A) -> None:
        """Lo que deja una caida: arriendo abierto que nadie va a cerrar."""
        with connect(MIGRATOR_DSN, company) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE fincilia.processing_run "
                "SET lease_expires_at = now() - interval '1 minute' WHERE run_id = %s",
                (run_id,))
            cursor.execute(
                "UPDATE fincilia.dispatch_pointer "
                "SET available_at = now() - interval '1 minute' WHERE run_id = %s",
                (run_id,))

    # ------------------------------------------------------------ privilegios #

    def test_the_api_has_no_privilege_at_all_on_the_dispatch_table(self) -> None:
        with connect(APP_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            for statement, params in (
                    ("SELECT count(*) FROM fincilia.dispatch_pointer", ()),
                    ("INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind) "
                     "VALUES (gen_random_uuid(), %s, 'profile')", (SANDBOX_A,)),
                    ("UPDATE fincilia.dispatch_pointer SET available_at = now()", ()),
                    ("DELETE FROM fincilia.dispatch_pointer", ())):
                with self.subTest(verb=statement.split()[0]):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement, params)

    def test_the_api_cannot_rewrite_a_credential(self) -> None:
        # El defecto mas serio que corrige V0005: con UPDATE y sin RLS, el rol de
        # la API podia reescribir el hash de cualquier sujeto y entrar como el.
        with connect(APP_DSN) as connection, connection.cursor() as cursor:
            for statement in (
                    "UPDATE fincilia.local_credential SET secret_hash = repeat('0', 64)",
                    "INSERT INTO fincilia.local_credential (subject_id, username, "
                    "algorithm, iterations, salt, secret_hash) VALUES "
                    "(gen_random_uuid(), 'x@y.z', 'pbkdf2_sha256', 200000, "
                    "repeat('a', 32), repeat('b', 64))"):
                with self.subTest(verb=statement.split()[0]):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement)

    def test_the_api_can_still_read_a_credential_to_authenticate(self) -> None:
        with connect(APP_DSN) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.local_credential")
            self.assertGreaterEqual(cursor.fetchone()[0], 1)

    def test_the_api_cannot_write_the_queue_directly(self) -> None:
        with connect(APP_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("UPDATE fincilia.processing_run SET status = 'succeeded'")

    def test_the_worker_holds_no_identity_privilege(self) -> None:
        # El worker procesa ficheros; no autoriza a nadie.
        with connect(WORKER_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            for table in ("subject", "local_credential", "membership", "company_grant",
                          "identity_binding", "firm"):
                with self.subTest(table=table):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(f"SELECT count(*) FROM fincilia.{table}")

    def test_the_worker_cannot_touch_the_queue_except_through_its_functions(self) -> None:
        with connect(WORKER_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("UPDATE fincilia.processing_run SET status = 'succeeded'")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("SELECT count(*) FROM fincilia.dispatch_pointer")

    def test_no_runtime_role_can_disable_row_level_security(self) -> None:
        for dsn, label in ((APP_DSN, "app"), (WORKER_DSN, "worker")):
            with self.subTest(role=label):
                with connect(dsn, SANDBOX_A) as connection, connection.cursor() as cursor:
                    with self.assertRaises(psycopg.Error):
                        cursor.execute(
                            "ALTER TABLE fincilia.processing_run DISABLE ROW LEVEL SECURITY")

    def test_public_cannot_execute_the_dispatch_functions(self) -> None:
        # Un `REVOKE` de quien no es dueno no falla: avisa y no hace nada. La
        # primera version de V0005 dejo asi las cuatro funciones abiertas a PUBLIC,
        # y solo lo delato consultar el ACL real.
        # PUBLIC es la entrada del ACL **sin concesionario**: empieza por `=`. La
        # del propietario es `fincilia_dispatch=X/...` y no cuenta.
        with connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT p.proname, p.proacl IS NULL AS sin_acl, "
                "  EXISTS (SELECT 1 FROM unnest(coalesce(p.proacl, ARRAY[]::aclitem[])) a "
                "          WHERE a::text LIKE '=%%') AS publico "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'fincilia'")
            rows = cursor.fetchall()
        self.assertEqual(4, len(rows))
        for name, missing_acl, public in rows:
            with self.subTest(function=name):
                self.assertFalse(missing_acl, f"{name} has no ACL, so PUBLIC may execute it")
                self.assertFalse(public, f"{name} is executable by PUBLIC")

    def test_the_dispatch_owner_cannot_create_anything(self) -> None:
        with connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_schema_privilege('fincilia_dispatch', 'fincilia', 'CREATE')")
            self.assertFalse(cursor.fetchone()[0])

    def test_future_tables_get_no_automatic_grant(self) -> None:
        with connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_default_acl d "
                "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
                "WHERE n.nspname = 'fincilia' AND d.defaclobjtype = 'r' "
                "AND array_to_string(d.defaclacl, ' ') LIKE '%fincilia_app%'")
            self.assertEqual(0, cursor.fetchone()[0])

    # -------------------------------------------------------------- integridad #

    def test_a_pointer_cannot_name_another_companys_run(self) -> None:
        run_id = self.enqueue(self.artifact(SANDBOX_A), SANDBOX_A)
        with connect(MIGRATOR_DSN, SANDBOX_B) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM fincilia.dispatch_pointer WHERE run_id = %s",
                           (run_id,))
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                cursor.execute(
                    "INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind) "
                    "VALUES (%s, %s, 'profile')", (run_id, SANDBOX_B))

    def test_enqueueing_for_another_company_is_refused(self) -> None:
        artifact = self.artifact(SANDBOX_A)
        with connect(APP_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("SELECT fincilia.enqueue_processing_run(%s, %s, 'profile')",
                               (SANDBOX_B, artifact))

    def test_enqueueing_an_invisible_artifact_is_refused(self) -> None:
        foreign = self.artifact(SANDBOX_B)
        with connect(APP_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("SELECT fincilia.enqueue_processing_run(%s, %s, 'profile')",
                               (SANDBOX_A, foreign))

    def test_enqueueing_twice_yields_one_live_run(self) -> None:
        artifact = self.artifact()
        first = self.enqueue(artifact)
        second = self.enqueue(artifact)
        self.assertEqual(first, second)
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM fincilia.processing_run "
                "WHERE artifact_id = %s AND status IN ('queued','running')", (artifact,))
            self.assertEqual(1, cursor.fetchone()[0])

    # ------------------------------------------------- arriendo y recuperacion #

    def test_a_claim_returns_only_what_the_worker_needs(self) -> None:
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        self.assertIsNotNone(claimed)
        self.assertEqual(run_id, claimed[0])
        self.assertEqual(SANDBOX_A, claimed[1])
        self.assertEqual(1, claimed[4])
        self.assertTrue(claimed[5])
        self.assertEqual("running", self.run_row(run_id)["status"])

    def test_two_concurrent_claims_produce_one_winner(self) -> None:
        run_id = self.enqueue(self.artifact())
        first = self.claim_this(run_id, "w1")
        second = self.claim("w2")
        self.assertEqual(run_id, first[0])
        # El segundo no ve el mismo trabajo: el arriendo del primero sigue vivo.
        self.assertTrue(second is None or second[0] != run_id)

    def test_a_finished_run_leaves_no_pointer(self) -> None:
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        self.assertEqual("succeeded", self.finish(run_id, claimed[5], result='{"a":1}'))
        self.assertEqual(0, self.pointer_count(run_id))
        self.assertEqual("succeeded", self.run_row(run_id)["status"])

    def test_a_worker_that_dies_before_starting_loses_nothing(self) -> None:
        # Reclamado y muerto: el arriendo vence y otro lo recupera.
        run_id = self.enqueue(self.artifact())
        self.claim_this(run_id, "murio")
        self.expire_lease(run_id)
        recovered = self.claim_this(run_id, "vivo")
        self.assertEqual(run_id, recovered[0])
        self.assertEqual(2, recovered[4], "the recovery consumes one real attempt")
        self.assertEqual("running", self.run_row(run_id)["status"])

    def test_a_worker_that_dies_while_running_is_recovered(self) -> None:
        run_id = self.enqueue(self.artifact())
        first = self.claim_this(run_id, "murio")
        self.expire_lease(run_id)
        recovered = self.claim("vivo")
        self.assertEqual(run_id, recovered[0])
        self.assertNotEqual(first[5], recovered[5], "a new lease means a new token")
        # Y el intento abandonado quedo cerrado en el historial, no en curso.
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT outcome, reason_code FROM fincilia.run_attempt "
                "WHERE run_id = %s ORDER BY attempt_number", (run_id,))
            attempts = cursor.fetchall()
        self.assertEqual(("abandoned", "lease_expired"), attempts[0])
        self.assertEqual("running", attempts[1][0])

    def test_a_stale_worker_cannot_finish_after_recovery(self) -> None:
        # El caso que hacia perder trabajos: el worker viejo revive y escribe.
        run_id = self.enqueue(self.artifact())
        stale = self.claim_this(run_id, "viejo")
        self.expire_lease(run_id)
        fresh = self.claim_this(run_id, "nuevo")
        self.assertEqual("stale_lease", self.finish(run_id, stale[5], result='{"a":1}'))
        self.assertEqual("running", self.run_row(run_id)["status"])
        self.assertEqual(1, self.pointer_count(run_id), "the pointer must survive")
        # Y el que si tiene el arriendo puede cerrarlo.
        self.assertEqual("succeeded", self.finish(run_id, fresh[5], result='{"a":1}'))

    def test_a_stale_worker_cannot_finish_after_the_run_is_closed(self) -> None:
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        self.finish(run_id, claimed[5], result='{"a":1}')
        self.assertEqual("stale_lease", self.finish(run_id, claimed[5], error="x_error",
                                                    failure="retryable"))
        self.assertEqual("succeeded", self.run_row(run_id)["status"])
        self.assertIsNone(self.run_row(run_id)["error_code"])

    def test_a_retryable_failure_returns_the_job_to_the_queue(self) -> None:
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        self.assertEqual("requeued", self.finish(run_id, claimed[5],
                                                 error="evidence_unreadable",
                                                 failure="retryable"))
        row = self.run_row(run_id)
        self.assertEqual("queued", row["status"])
        self.assertEqual(2, row["attempt"])
        self.assertIsNone(row["error_code"], "a requeued job carries no failure")
        self.assertEqual(1, self.pointer_count(run_id))

    def test_a_fatal_failure_is_terminal_without_retries(self) -> None:
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        self.assertEqual("failed", self.finish(run_id, claimed[5], error="unprofilable",
                                               failure="fatal"))
        row = self.run_row(run_id)
        self.assertEqual("failed", row["status"])
        self.assertEqual("unprofilable", row["error_code"])
        self.assertEqual(0, self.pointer_count(run_id))

    def test_exhausting_the_attempts_produces_a_dead_letter(self) -> None:
        run_id = self.enqueue(self.artifact())
        # Un solo intento permitido: agotarlo es un fallo, no cinco vueltas de
        # bucle sobre una cola que otras pruebas comparten.
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fincilia.processing_run SET max_attempts = 1 "
                           "WHERE run_id = %s", (run_id,))
        claimed = self.claim_this(run_id)
        self.assertEqual("dead_letter",
                         self.finish(run_id, claimed[5], error="evidence_unreadable",
                                     failure="retryable"))
        row = self.run_row(run_id)
        self.assertEqual("failed", row["status"])
        self.assertEqual("attempts_exhausted", row["error_code"])
        self.assertEqual(0, self.pointer_count(run_id),
                         "an exhausted job leaves no pointer behind")
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT failure_class, reason_code, attempt_count, resolution_state, "
                "payload_reference, work_class FROM fincilia.dead_letter_item "
                "WHERE work_id = %s", (run_id,))
            item = cursor.fetchone()
        self.assertIsNotNone(item, "an exhausted job must be visible as a dead letter")
        self.assertEqual("attempts_exhausted", item[1])
        self.assertEqual(1, item[2])
        # Una **referencia** al contenido, nunca el contenido.
        self.assertRegex(item[4], r"^[0-9a-f]{64}$")
        self.assertEqual("stateless_job", item[5])

    def claim_this(self, run_id: str, worker: str = "w1", limit: int = 24):
        """Reclama hasta dar con el trabajo de esta prueba.

        La cola es global -- lo tiene que ser, o un planificador entre empresas no
        podria descubrir trabajo -- y otras pruebas y el propio producto encolan
        en ella. Lo que sale primero no tiene por que ser lo de esta prueba.

        Lo ajeno se aparta quedandose reclamado: su arriendo lo mantiene fuera del
        reparto durante los proximos sesenta segundos, que es mas de lo que dura
        cualquier prueba de este fichero. Devolverlo a la cola lo unico que
        conseguiria es volver a sacarlo en la vuelta siguiente.
        """
        for _ in range(limit):
            claimed = self.claim(worker)
            self.assertIsNotNone(claimed, "the queue went empty before the target run")
            if claimed[0] == run_id:
                return claimed
        self.fail("the target run never came out of the queue")

    def expire_pointer(self, run_id: str) -> None:
        """Adelanta la espera del reintento, para no dormir en una prueba."""
        with connect(MIGRATOR_DSN) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fincilia.dispatch_pointer "
                           "SET available_at = now() - interval '1 second' "
                           "WHERE run_id = %s", (run_id,))

    def test_no_job_can_stay_running_without_a_lease(self) -> None:
        # El invariante que lo resume: `running` y arriendo son un solo hecho.
        run_id = self.enqueue(self.artifact())
        claimed = self.claim_this(run_id)
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "UPDATE fincilia.processing_run SET lease_token = NULL, "
                    "lease_expires_at = NULL WHERE run_id = %s", (run_id,))
        self.finish(run_id, claimed[5], result='{"a":1}')

    def test_revoking_authorization_stops_a_queued_job(self) -> None:
        # El contrato declara `authorization_version_on_work`. Sin esto, revocar
        # un acceso no detiene lo que ya estaba en cola.
        run_id = self.enqueue(self.artifact())
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fincilia.authorization_version "
                           "SET version = version + 1 WHERE company_id = %s", (SANDBOX_A,))
        # `claim_this` no vale aqui: este trabajo **nunca** debe salir reclamado.
        # La cola es global, asi que se saca trabajo hasta que el planificador
        # llegue a el, y al llegar tiene que terminarlo, no tomarlo.
        for _ in range(24):
            claimed = self.claim()
            self.assertTrue(claimed is None or claimed[0] != run_id,
                            "a job whose authorization changed must not be claimed")
            if claimed is None or self.run_row(run_id)["status"] != "queued":
                break
        row = self.run_row(run_id)
        self.assertEqual("failed", row["status"])
        self.assertEqual("authorization_changed", row["error_code"])
        self.assertEqual(0, self.pointer_count(run_id))
        with connect(MIGRATOR_DSN, SANDBOX_A) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fincilia.authorization_version "
                           "SET version = version - 1 WHERE company_id = %s", (SANDBOX_A,))

    def test_work_from_two_companies_is_claimed_with_its_own_context(self) -> None:
        first = self.enqueue(self.artifact(SANDBOX_A), SANDBOX_A)
        second = self.enqueue(self.artifact(SANDBOX_B), SANDBOX_B)
        seen = {}
        # La cola es global: hay que sacar trabajo hasta encontrar los dos, y cada
        # uno tiene que venir con **su** empresa, no con la del otro.
        for _ in range(24):
            claimed = self.claim()
            if claimed is None:
                break
            seen[claimed[0]] = claimed[1]
            if first in seen and second in seen:
                break
        self.assertEqual(SANDBOX_A, seen.get(first))
        self.assertEqual(SANDBOX_B, seen.get(second))

    def test_the_claim_does_not_leak_the_company_context_to_the_caller(self) -> None:
        # `Database.session()` fija el contexto una vez al abrir la transaccion y
        # no lo vuelve a mirar: un contexto filtrado reetiquetaria en silencio
        # cuanto viniera despues.
        self.enqueue(self.artifact())
        with connect(WORKER_DSN) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM fincilia.claim_next_run('w', %s)", (LEASE,))
            cursor.fetchall()
            cursor.execute("SELECT coalesce(current_setting('fincilia.company_id', true), '')")
            self.assertEqual("", cursor.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
