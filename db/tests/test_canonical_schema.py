"""Persistencia del mapeo y del movimiento canonico, contra PostgreSQL real.

Lo que se comprueba aqui son propiedades del motor, no del codigo que lo llama:
que un UPDATE este denegado, que una clave foranea compuesta rechace la fila de
otra empresa, o que una restriccion unica impida publicar dos veces lo mismo. Un
doble de prueba diria que si a todo.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_canonical_schema -v
"""

from __future__ import annotations

import hashlib
import json
import os
import unittest
import uuid
from decimal import Decimal

import psycopg

MIGRATOR_DSN = os.environ.get("FINCILIA_MIGRATOR_URL", "")
RUNTIME_DSN = os.environ.get("FINCILIA_DATABASE_URL", "")
WORKER_DSN = os.environ.get("FINCILIA_WORKER_URL", "")

SCHEMA_VERSION = "0.1.0"

# Las trece tablas que anade V0008. `engine_release` va aparte: no lleva
# `company_id` porque una version del software no es dato de una empresa.
COMPANY_SCOPED_TABLES = (
    "financial_account", "data_source", "column_mapping", "column_mapping_version",
    "mapping_decision", "dataset_version", "reproducibility_manifest",
    "raw_record", "source_record", "canonical_movement", "movement_evidence_link",
    "lineage_node", "lineage_edge",
    # V0009
    "data_source_account", "source_cycle", "source_expectation",
    "lineage_transform_plan", "lineage_transform_step", "dataset_chunk",
)


def new_id() -> str:
    # uuid4 solo genera identificadores de fixtures; ninguna decision depende de el.
    return str(uuid.uuid4())


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Fixture:
    """Una cadena completa: empresa, artefacto, ejecucion, mapeo y dataset.

    Se construye con el rol migrator porque sembrar exige escribir en tablas que
    el runtime no puede tocar; lo que se afirma despues se afirma **desde el rol
    que corresponde**, que es donde esta la prueba.
    """

    def __init__(self, cursor, *, company_id: str, release_id: str) -> None:
        self.cursor = cursor
        self.company_id = company_id
        self.release_id = release_id

    def artifact(self, *, uploader: str, source_id: str | None = None,
                 suffix: str = "") -> str:
        if source_id is None:
            source_id = self.data_source()
        artifact_id = new_id()
        content = digest(f"artifact:{artifact_id}{suffix}")
        self.cursor.execute(
            "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
            "data_source_id, filename, byte_size, content_sha256, media_type, "
            "zone, object_key, status, uploaded_by) VALUES (%s, %s, %s, %s, 128, "
            "%s, 'text/csv', 'raw', %s, 'stored', %s)",
            (artifact_id, self.company_id, source_id,
             f"extracto-{artifact_id[:8]}.csv",
             content, f"company/{self.company_id}/{content[:2]}/{content}", uploader))
        return artifact_id

    def run(self, artifact_id: str) -> str:
        run_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.processing_run (run_id, company_id, artifact_id, "
            "kind, status, started_at, finished_at, result) VALUES (%s, %s, %s, "
            "'profile', 'succeeded', now(), now(), '{}'::jsonb)",
            (run_id, self.company_id, artifact_id))
        return run_id

    def data_source(self) -> str:
        source_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.data_source (data_source_id, company_id, "
            "source_family, display_name) VALUES (%s, %s, 'bank_account', %s)",
            (source_id, self.company_id, f"fuente {source_id[:8]}"))
        return source_id

    def account(self) -> str:
        account_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.financial_account (account_id, company_id, "
            "account_family, display_name, identifier_token, identifier_last4, "
            "currency_code) VALUES (%s, %s, 'bank_account', %s, %s, '4417', 'COP')",
            (account_id, self.company_id, f"cuenta {account_id[:8]}",
             f"token-{account_id}"))
        return account_id

    def mapping_version(self, *, artifact_id: str, source_id: str, author: str,
                        validator: str | None = None) -> str:
        mapping_id = new_id()
        version_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.column_mapping (mapping_id, company_id, "
            "data_source_id, display_name, created_by) VALUES (%s, %s, %s, %s, %s)",
            (mapping_id, self.company_id, source_id, f"mapeo {mapping_id[:8]}", author))
        state = "draft" if validator is None else "validated"
        self.cursor.execute(
            "INSERT INTO fincilia.column_mapping_version (mapping_version_id, "
            "company_id, mapping_id, version_number, artifact_id, definition, "
            "definition_digest, source_schema_digest, state, created_by, "
            "validated_by, validated_at) VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, "
            "%s, %s, CASE WHEN %s::uuid IS NULL THEN NULL ELSE now() END)",
            (version_id, self.company_id, mapping_id, artifact_id,
             json.dumps({"columns": {"occurred_on": 0, "description": 1, "amount": 2}}),
             digest(f"definition:{version_id}"), digest(f"schema:{artifact_id}"),
             state, author, validator, validator))
        return version_id

    def plan(self, mapping_version_id: str) -> str:
        """Un plan de linaje minimo. Publicar sin el esta prohibido por CHECK."""
        plan_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.lineage_transform_plan (plan_id, company_id, "
            "mapping_version_id, engine_release_id, plan_digest, "
            "canonical_schema_version, field_count) VALUES (%s, %s, %s, %s, %s, "
            "%s, 1) ON CONFLICT (mapping_version_id, engine_release_id) DO NOTHING "
            "RETURNING plan_id",
            (plan_id, self.company_id, mapping_version_id, self.release_id,
             digest(f"plan:{mapping_version_id}"), SCHEMA_VERSION))
        row = self.cursor.fetchone()
        if row is not None:
            return str(row[0])
        self.cursor.execute(
            "SELECT plan_id FROM fincilia.lineage_transform_plan "
            "WHERE mapping_version_id = %s AND engine_release_id = %s",
            (mapping_version_id, self.release_id))
        return str(self.cursor.fetchone()[0])

    def dataset(self, *, run_id: str, artifact_id: str, mapping_version_id: str,
                preparer: str, state: str = "draft",
                validator: str | None = None, publisher: str | None = None) -> str:
        dataset_id = new_id()
        plan_id = self.plan(mapping_version_id)
        self.cursor.execute(
            "INSERT INTO fincilia.dataset_version (dataset_version_id, company_id, "
            "processing_run_id, mapping_version_id, artifact_id, engine_release_id, "
            "lineage_plan_id, canonical_schema_version, state, prepared_by, "
            "validated_by, validated_at, published_by, published_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "CASE WHEN %s::uuid IS NULL THEN NULL ELSE now() END, %s, "
            "CASE WHEN %s::uuid IS NULL THEN NULL ELSE now() END)",
            (dataset_id, self.company_id, run_id, mapping_version_id, artifact_id,
             self.release_id, plan_id, SCHEMA_VERSION, state, preparer, validator,
             validator, publisher, publisher))
        return dataset_id

    def raw_record(self, *, artifact_id: str, run_id: str, ordinal: int = 1) -> str:
        raw_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.raw_record (raw_record_id, company_id, artifact_id, "
            "processing_run_id, record_ordinal, origin_locator, raw_values, "
            "values_digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (raw_id, self.company_id, artifact_id, run_id, ordinal,
             json.dumps({"locator_kind": "tabular_delimited",
                         "artifact_sha256": digest(artifact_id),
                         "record_ordinal": ordinal, "byte_start": 0, "byte_end": 42,
                         "field_count": 3}),
             json.dumps(["2026-02-01", "Pago proveedor", "1.234,56"]),
             digest(f"row:{raw_id}")))
        return raw_id

    def source_record(self, *, dataset_id: str, source_id: str, raw_id: str) -> str:
        record_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.source_record (source_record_id, company_id, "
            "dataset_version_id, data_source_id, raw_record_id, record_family, "
            "source_payload, engine_release_id, canonical_schema_version) "
            "VALUES (%s, %s, %s, %s, %s, 'bank_statement_line', %s, %s, %s)",
            (record_id, self.company_id, dataset_id, source_id, raw_id,
             json.dumps({"occurred_on": "2026-02-01", "amount": "1234.56"}),
             self.release_id, SCHEMA_VERSION))
        return record_id

    def movement(self, *, dataset_id: str, record_id: str, account_id: str,
                 amount: str = "1234.560000000000", reference: str | None = None,
                 direction: str = "outflow") -> str:
        movement_id = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.canonical_movement (movement_id, company_id, "
            "dataset_version_id, source_record_id, financial_account_id, amount, "
            "currency_code, direction, description, reference_original, "
            "reference_normalised, occurred_on, dedupe_fingerprint, "
            "engine_release_id, canonical_schema_version) VALUES (%s, %s, %s, %s, "
            "%s, %s, 'COP', %s, 'Pago proveedor', %s, %s, DATE '2026-02-01', %s, "
            "%s, %s)",
            (movement_id, self.company_id, dataset_id, record_id, account_id, amount,
             direction, reference, reference, digest(f"movement:{movement_id}"),
             self.release_id, SCHEMA_VERSION))
        return movement_id


class CanonicalSchemaTests(unittest.TestCase):
    """Toda la cadena, sembrada una vez y afirmada desde cada rol."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        cls.company_a = new_id()
        cls.company_b = new_id()
        cls.firm_id = new_id()
        cls.preparer = new_id()
        cls.reviewer = new_id()
        cls.release_id = new_id()

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.firm (firm_id, legal_name) VALUES (%s, %s)",
                    (cls.firm_id, "Firma Sintetica P3"))
                for subject, name in ((cls.preparer, "Preparador"),
                                      (cls.reviewer, "Revisor")):
                    cursor.execute(
                        "INSERT INTO fincilia.subject (subject_id, subject_kind, "
                        "display_name) VALUES (%s, 'person', %s)", (subject, name))
                cursor.execute(
                    "INSERT INTO fincilia.engine_release (release_id, release_key, "
                    "canonical_schema_version, classification) VALUES (%s, %s, %s, "
                    "'neutral')",
                    (cls.release_id, f"test-release-{cls.release_id[:8]}",
                     SCHEMA_VERSION))
                for company in (cls.company_a, cls.company_b):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (company,))
                    cursor.execute(
                        "INSERT INTO fincilia.company (company_id, legal_name, "
                        "tax_id_token, country_code) VALUES (%s, %s, %s, 'CO')",
                        (company, f"Empresa P3 {company[:8]}", f"token-{company[:8]}"))
                    cursor.execute(
                        "INSERT INTO fincilia.authorization_version (company_id, "
                        "version) VALUES (%s, 1)", (company,))

    def setUp(self) -> None:
        self.connection = psycopg.connect(MIGRATOR_DSN, autocommit=True)
        self.cursor = self.connection.cursor()
        self.context(self.company_a)
        self.fixture = Fixture(self.cursor, company_id=self.company_a,
                               release_id=self.release_id)

    def tearDown(self) -> None:
        self.cursor.close()
        self.connection.close()

    def context(self, company_id: str | None) -> None:
        self.cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                            (company_id or "",))

    # ---------------------------------------------------------------- aislamiento

    def test_every_new_table_forces_row_level_security_TST_P3_001(self) -> None:
        # Sin FORCE el propietario queda exento: la politica existiria y no
        # protegeria de quien mas privilegios tiene.
        self.cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relnamespace = 'fincilia'::regnamespace AND relname = ANY(%s)",
            (list(COMPANY_SCOPED_TABLES),))
        rows = {name: (enabled, forced) for name, enabled, forced in self.cursor}
        self.assertEqual(set(rows), set(COMPANY_SCOPED_TABLES))
        for name, (enabled, forced) in sorted(rows.items()):
            with self.subTest(table=name):
                self.assertTrue(enabled, f"{name} sin RLS")
                self.assertTrue(forced, f"{name} sin FORCE")

    def test_without_company_context_nothing_is_visible_TST_P3_002(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        # `current_setting(..., true)` devuelve NULL sin contexto, la comparacion
        # es NULL y la politica falla cerrada.
        self.context(None)
        self.cursor.execute(
            "SELECT count(*) FROM fincilia.dataset_version WHERE dataset_version_id = %s",
            (dataset,))
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_a_movement_cannot_borrow_another_companys_account_TST_P3_003(self) -> None:
        # La clave foranea es compuesta: `(financial_account_id, company_id)`.
        # Sin ella bastaria con conocer el identificador de la otra empresa.
        self.context(self.company_b)
        other = Fixture(self.cursor, company_id=self.company_b,
                        release_id=self.release_id)
        foreign_account = other.account()

        self.context(self.company_a)
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        raw = self.fixture.raw_record(artifact_id=artifact, run_id=run)
        record = self.fixture.source_record(dataset_id=dataset, source_id=source,
                                            raw_id=raw)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.fixture.movement(dataset_id=dataset, record_id=record,
                                  account_id=foreign_account)

    def test_a_mapping_cannot_point_at_another_companys_artifact_TST_P3_004(self) -> None:
        self.context(self.company_b)
        other = Fixture(self.cursor, company_id=self.company_b,
                        release_id=self.release_id)
        other_source = other.data_source()
        foreign_artifact = other.artifact(uploader=self.preparer,
                                          source_id=other_source)

        self.context(self.company_a)
        source = self.fixture.data_source()
        # El guard de fuente corre antes de la FK compuesta y, bajo FORCE RLS,
        # no distingue un artefacto ajeno de uno inexistente. Esa precedencia
        # evita convertir el error en un oraculo sobre otra empresa.
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.fixture.mapping_version(artifact_id=foreign_artifact,
                                         source_id=source, author=self.preparer)
        self.assertEqual(caught.exception.diag.constraint_name,
                         "ck_mapping_artifact_source")

    # ------------------------------------------------------------- segregacion

    def test_the_publisher_cannot_be_the_author_of_the_version_TST_P3_005(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        # No se deja al codigo de la API: es un CHECK, y por tanto no hay ruta
        # —script, consola, error de programacion— que lo evite.
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.fixture.dataset(run_id=run, artifact_id=artifact,
                                 mapping_version_id=version, preparer=self.preparer,
                                 state="published", validator=self.preparer,
                                 publisher=self.preparer)
        self.assertIn("ck_dataset_publisher_is_not_author", str(caught.exception))

    def test_a_different_reviewer_may_publish_TST_P3_006(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(
            run_id=run, artifact_id=artifact, mapping_version_id=version,
            preparer=self.preparer, state="published", validator=self.preparer,
            publisher=self.reviewer)
        self.cursor.execute(
            "SELECT state, published_by FROM fincilia.dataset_version "
            "WHERE dataset_version_id = %s", (dataset,))
        state, published_by = self.cursor.fetchone()
        self.assertEqual(state, "published")
        self.assertEqual(str(published_by), self.reviewer)

    def test_published_without_a_publisher_is_refused_TST_P3_007(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.fixture.dataset(run_id=run, artifact_id=artifact,
                                 mapping_version_id=version, preparer=self.preparer,
                                 state="published", validator=self.preparer)
        self.assertIn("ck_dataset_published", str(caught.exception))

    # ------------------------------------------------------------ idempotencia

    def test_publishing_the_same_triple_twice_does_not_duplicate_TST_P3_008(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        self.fixture.dataset(run_id=run, artifact_id=artifact,
                             mapping_version_id=version, preparer=self.preparer)
        # Misma ejecucion, misma version de mapeo, misma version del motor.
        with self.assertRaises(psycopg.errors.UniqueViolation) as caught:
            self.fixture.dataset(run_id=run, artifact_id=artifact,
                                 mapping_version_id=version, preparer=self.preparer)
        self.assertIn("uq_dataset_reproduction", str(caught.exception))

    def test_reprocessing_creates_another_version_and_keeps_the_first_TST_P3_009(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        first_run = self.fixture.run(artifact)
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        first = self.fixture.dataset(run_id=first_run, artifact_id=artifact,
                                     mapping_version_id=version,
                                     preparer=self.preparer, state="published",
                                     validator=self.preparer, publisher=self.reviewer)
        # Reprocesar es otra ejecucion sobre el mismo artefacto: no sobrescribe.
        second_run = self.fixture.run(artifact)
        second = self.fixture.dataset(run_id=second_run, artifact_id=artifact,
                                      mapping_version_id=version,
                                      preparer=self.preparer)
        self.assertNotEqual(first, second)
        self.cursor.execute(
            "SELECT state FROM fincilia.dataset_version WHERE dataset_version_id = %s",
            (first,))
        self.assertEqual(self.cursor.fetchone()[0], "published")

    def test_one_source_record_yields_one_movement_per_dataset_TST_P3_010(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        account = self.fixture.account()
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        raw = self.fixture.raw_record(artifact_id=artifact, run_id=run)
        record = self.fixture.source_record(dataset_id=dataset, source_id=source,
                                            raw_id=raw)
        self.fixture.movement(dataset_id=dataset, record_id=record, account_id=account)
        with self.assertRaises(psycopg.errors.UniqueViolation) as caught:
            self.fixture.movement(dataset_id=dataset, record_id=record,
                                  account_id=account)
        self.assertIn("uq_movement_origin", str(caught.exception))

    # -------------------------------------------------------------- el dinero

    def test_two_identical_references_are_two_movements_TST_P3_011(self) -> None:
        # La referencia del proveedor **no** es unicidad economica: dos cobros
        # legitimos identicos existen, y colapsarlos seria perder dinero de vista.
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        account = self.fixture.account()
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        for ordinal in (1, 2):
            raw = self.fixture.raw_record(artifact_id=artifact, run_id=run,
                                          ordinal=ordinal)
            record = self.fixture.source_record(dataset_id=dataset, source_id=source,
                                                raw_id=raw)
            self.fixture.movement(dataset_id=dataset, record_id=record,
                                  account_id=account, reference="REF-0001")
        self.cursor.execute(
            "SELECT count(*) FROM fincilia.canonical_movement "
            "WHERE dataset_version_id = %s AND reference_normalised = 'REF-0001'",
            (dataset,))
        self.assertEqual(self.cursor.fetchone()[0], 2)

    def test_an_amount_keeps_twelve_decimals_without_rounding_TST_P3_012(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        account = self.fixture.account()
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        raw = self.fixture.raw_record(artifact_id=artifact, run_id=run)
        record = self.fixture.source_record(dataset_id=dataset, source_id=source,
                                            raw_id=raw)
        movement = self.fixture.movement(dataset_id=dataset, record_id=record,
                                         account_id=account,
                                         amount="0.000000000001")
        self.cursor.execute(
            "SELECT amount FROM fincilia.canonical_movement WHERE movement_id = %s",
            (movement,))
        self.assertEqual(self.cursor.fetchone()[0], Decimal("0.000000000001"))

    def test_a_negative_amount_is_refused_because_direction_carries_the_sign_TST_P3_013(self) -> None:
        source = self.fixture.data_source()
        artifact = self.fixture.artifact(uploader=self.preparer, source_id=source)
        run = self.fixture.run(artifact)
        account = self.fixture.account()
        version = self.fixture.mapping_version(
            artifact_id=artifact, source_id=source, author=self.preparer)
        dataset = self.fixture.dataset(run_id=run, artifact_id=artifact,
                                       mapping_version_id=version,
                                       preparer=self.preparer)
        raw = self.fixture.raw_record(artifact_id=artifact, run_id=run)
        record = self.fixture.source_record(dataset_id=dataset, source_id=source,
                                            raw_id=raw)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.fixture.movement(dataset_id=dataset, record_id=record,
                                  account_id=account, amount="-10.0")

    def test_a_currency_that_is_not_iso_is_refused_TST_P3_014(self) -> None:
        for invalid in ("pesos", "co", "COP1", "cop"):
            with self.subTest(currency=invalid):
                with self.assertRaises(psycopg.errors.CheckViolation):
                    self.cursor.execute(
                        "INSERT INTO fincilia.financial_account (account_id, "
                        "company_id, account_family, display_name, "
                        "identifier_token, currency_code) VALUES (%s, %s, "
                        "'bank_account', 'cuenta', 'token-12345678', %s)",
                        (new_id(), self.company_a, invalid))

    # ------------------------------------------------------- version del motor

    def test_a_floating_release_token_is_refused_TST_P3_015(self) -> None:
        for token in ("latest", "LATEST", "main", "head", "stable", "current"):
            with self.subTest(token=token):
                with self.assertRaises(psycopg.errors.CheckViolation):
                    self.cursor.execute(
                        "INSERT INTO fincilia.engine_release (release_id, "
                        "release_key, canonical_schema_version, classification) "
                        "VALUES (%s, %s, %s, 'neutral')",
                        (new_id(), token, SCHEMA_VERSION))

    def test_an_approved_release_needs_an_approval_reference_TST_P3_016(self) -> None:
        # Aprobar es una decision humana. El esquema no la toma; lo que hace es
        # impedir que se declare sin dejar constancia de quien la tomo.
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.cursor.execute(
                "INSERT INTO fincilia.engine_release (release_id, release_key, "
                "canonical_schema_version, classification, state) "
                "VALUES (%s, %s, %s, 'neutral', 'approved')",
                (new_id(), f"unapproved-{new_id()[:8]}", SCHEMA_VERSION))

    # ----------------------------------------------------------------- linaje

    def test_a_lineage_edge_cannot_cross_companies_TST_P3_017(self) -> None:
        self.context(self.company_b)
        foreign_node = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
            "entity_ref, engine_release_id, canonical_schema_version) "
            "VALUES (%s, %s, 'extracted_field', %s, %s, %s)",
            (foreign_node, self.company_b, new_id(), self.release_id, SCHEMA_VERSION))

        self.context(self.company_a)
        artifact = self.fixture.artifact(uploader=self.preparer)
        run = self.fixture.run(artifact)
        local_node = new_id()
        self.cursor.execute(
            "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
            "entity_ref, engine_release_id, canonical_schema_version) "
            "VALUES (%s, %s, 'source_record_field', %s, %s, %s)",
            (local_node, self.company_a, new_id(), self.release_id, SCHEMA_VERSION))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.cursor.execute(
                "INSERT INTO fincilia.lineage_edge (edge_id, company_id, "
                "from_node_id, to_node_id, operation, transform_ref, actor_kind, "
                "actor_id, workload_identity, processing_run_id, engine_release_id, "
                "canonical_schema_version) VALUES (%s, %s, %s, %s, 'derived_from', "
                "'map', 'service', %s, 'worker', %s, %s, %s)",
                (new_id(), self.company_a, foreign_node, local_node, self.preparer,
                 run, self.release_id, SCHEMA_VERSION))

    def test_a_derived_edge_must_name_its_transform_TST_P3_018(self) -> None:
        # `derived_from` significa que el valor fluyo. Sin nombrar la
        # transformacion el grafo diria «esto tiene algo que ver con aquello».
        artifact = self.fixture.artifact(uploader=self.preparer)
        run = self.fixture.run(artifact)
        nodes = []
        for node_type in ("raw_locator", "extracted_field"):
            node_id = new_id()
            nodes.append(node_id)
            self.cursor.execute(
                "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
                "entity_ref, locator, engine_release_id, canonical_schema_version) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (node_id, self.company_a, node_type, new_id(),
                 json.dumps({"record_ordinal": 1, "field_ordinal": 2}),
                 self.release_id, SCHEMA_VERSION))
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.cursor.execute(
                "INSERT INTO fincilia.lineage_edge (edge_id, company_id, "
                "from_node_id, to_node_id, operation, actor_kind, actor_id, "
                "workload_identity, processing_run_id, engine_release_id, "
                "canonical_schema_version) VALUES (%s, %s, %s, %s, 'derived_from', "
                "'service', %s, 'worker', %s, %s, %s)",
                (new_id(), self.company_a, nodes[0], nodes[1], self.preparer, run,
                 self.release_id, SCHEMA_VERSION))
        self.assertIn("ck_edge_transform", str(caught.exception))

    def test_a_cell_node_without_a_locator_is_refused_TST_P3_019(self) -> None:
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.cursor.execute(
                "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
                "entity_ref, engine_release_id, canonical_schema_version) "
                "VALUES (%s, %s, 'raw_locator', %s, %s, %s)",
                (new_id(), self.company_a, new_id(), self.release_id, SCHEMA_VERSION))
        self.assertIn("ck_lineage_locator", str(caught.exception))

    def test_a_raw_record_locator_must_carry_the_four_coordinates_TST_P3_020(self) -> None:
        artifact = self.fixture.artifact(uploader=self.preparer)
        run = self.fixture.run(artifact)
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            self.cursor.execute(
                "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                "artifact_id, processing_run_id, record_ordinal, origin_locator, "
                "raw_values, values_digest) VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
                (new_id(), self.company_a, artifact, run,
                 json.dumps({"locator_kind": "opaque"}), json.dumps(["a"]),
                 digest("x")))
        self.assertIn("ck_raw_locator", str(caught.exception))

    def test_a_spreadsheet_locator_is_typed_and_matches_the_stored_row(self) -> None:
        artifact = self.fixture.artifact(uploader=self.preparer)
        run = self.fixture.run(artifact)
        locator = {
            "locator_kind": "spreadsheet",
            "artifact_sha256": digest(artifact),
            "record_ordinal": 2,
            "row_number": 2,
            "field_count": 3,
            "workbook_identity": digest("workbook"),
            "sheet_identity": digest("sheet-1"),
            "sheet_ordinal": 1,
        }
        self.cursor.execute(
            "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
            "artifact_id, processing_run_id, record_ordinal, origin_locator, "
            "raw_values, values_digest) VALUES (%s, %s, %s, %s, 2, %s, %s, %s)",
            (new_id(), self.company_a, artifact, run, json.dumps(locator),
             json.dumps(["2026-02-01", "Pago sintetico", "1250"]), digest("xlsx-row")))

        invalid = (
            {**locator, "sheet_identity": None},
            {**locator, "row_number": 3},
            {**locator, "record_ordinal": 3},
            {**locator, "field_count": 2},
        )
        for index, candidate in enumerate(invalid, start=3):
            with self.subTest(candidate=index):
                with self.assertRaises(psycopg.errors.CheckViolation) as caught:
                    self.cursor.execute(
                        "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                        "artifact_id, processing_run_id, record_ordinal, "
                        "origin_locator, raw_values, values_digest) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (new_id(), self.company_a, artifact, run, index,
                         json.dumps(candidate), json.dumps(["a", "b", "c"]),
                         digest(f"bad-xlsx-{index}")))
                self.assertIn("ck_raw_locator", str(caught.exception))

    def test_a_pdf_locator_is_typed_bounded_and_matches_the_stored_block(self) -> None:
        artifact = self.fixture.artifact(uploader=self.preparer)
        run = self.fixture.run(artifact)
        locator = {
            "locator_kind": "pdf_text",
            "artifact_sha256": digest(artifact),
            "record_ordinal": 1,
            "field_count": 1,
            "page_number": 1,
            "block_ordinal": 1,
            "bbox": [0.1, 0.2, 0.8, 0.25],
            "confidence": 1,
            "parser_release": "pypdf-6.16.2/fincilia-pdf-1",
        }
        self.cursor.execute(
            "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
            "artifact_id, processing_run_id, record_ordinal, origin_locator, "
            "raw_values, values_digest) VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
            (new_id(), self.company_a, artifact, run, json.dumps(locator),
             json.dumps(["Texto sintetico"]), digest("pdf-block")))

        invalid = (
            {**locator, "page_number": 0},
            {**locator, "bbox": [-0.1, 0.2, 0.8, 0.25]},
            {**locator, "confidence": 1.01},
            {**locator, "field_count": 2},
        )
        for index, candidate in enumerate(invalid, start=2):
            with self.subTest(candidate=index):
                with self.assertRaises(psycopg.errors.CheckViolation) as caught:
                    self.cursor.execute(
                        "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                        "artifact_id, processing_run_id, record_ordinal, origin_locator, "
                        "raw_values, values_digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (new_id(), self.company_a, artifact, run, index,
                         json.dumps(candidate), json.dumps(["Texto sintetico"]),
                         digest(f"bad-pdf-{index}")))
                self.assertIn("ck_raw_locator", str(caught.exception))


class RuntimePrivilegeTests(unittest.TestCase):
    """Lo que cada rol **no** puede hacer, afirmado desde ese mismo rol.

    Afirmar un privilegio negativo desde el migrator no prueba nada: el migrator
    es el propietario. Estas pruebas se conectan con las credenciales reales.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")

    VERBS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES")

    def privileges(self, role: str, table: str) -> set[str]:
        # `has_table_privilege` responde lo que de verdad importa: incluye lo
        # heredado y lo concedido a PUBLIC. `information_schema` solo muestra lo
        # que el que consulta tiene derecho a ver, y podria callar una fuga.
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                granted = set()
                for verb in self.VERBS:
                    cursor.execute("SELECT has_table_privilege(%s, %s, %s)",
                                   (role, f"fincilia.{table}", verb))
                    if cursor.fetchone()[0]:
                        granted.add(verb)
                return granted

    def test_the_api_role_cannot_rewrite_a_published_movement_TST_P3_021(self) -> None:
        # Inmutable para el runtime: corregir es publicar otra version, y el
        # motor lo niega en vez de confiar en que nadie escriba el UPDATE.
        granted = self.privileges("fincilia_app", "canonical_movement")
        self.assertEqual(granted, {"SELECT", "INSERT"})

    def test_the_api_role_cannot_delete_evidence_TST_P3_022(self) -> None:
        for table in ("source_record", "raw_record", "movement_evidence_link",
                      "lineage_node", "lineage_edge", "mapping_decision"):
            with self.subTest(table=table):
                granted = self.privileges("fincilia_app", table)
                self.assertNotIn("DELETE", granted)
                self.assertNotIn("UPDATE", granted)

    def test_the_worker_role_cannot_touch_the_canonical_movement_TST_P3_023(self) -> None:
        # `module-boundaries` lo dice literalmente: los workers no publican
        # estado financiero canonico. El worker extrae filas y nada mas.
        for table in ("canonical_movement", "dataset_version", "financial_account",
                      "column_mapping_version"):
            with self.subTest(table=table):
                self.assertEqual(self.privileges("fincilia_worker", table), set())

    def test_the_worker_may_only_append_raw_records_TST_P3_024(self) -> None:
        self.assertEqual(self.privileges("fincilia_worker", "raw_record"),
                         {"SELECT", "INSERT"})

    def test_no_runtime_role_may_write_the_engine_release_TST_P3_025(self) -> None:
        # Declarar una version del motor es un acto de plataforma, no de runtime.
        for role in ("fincilia_app", "fincilia_worker"):
            with self.subTest(role=role):
                self.assertEqual(self.privileges(role, "engine_release"), {"SELECT"})


if __name__ == "__main__":
    unittest.main()
