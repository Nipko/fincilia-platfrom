"""La via de excepcion por fila, contra PostgreSQL real (FNC-P3.6, ADR-024).

El plan de V0009 explica la columna. Estas pruebas ejercen la fila que se aparta
de esa regla: que el camino la ensena en el punto exacto en que ocurrio, que
nadie publica una excepcion sobre un importe sin que la mire otra persona, y que
cambiar el plan de hoy no reinterpreta lo que se publico hace meses.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_row_overrides -v
"""

from __future__ import annotations

import contextlib
import unittest

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN
from db.tests.test_p3_vertical import (
    ESPIGA,
    OWNER,
    PREPARER,
    REVIEWER,
    VerticalHarness,
    statement_csv,
)

ANDINOS = stable_id("company", "andinos")

# El mismo fichero leido con punto decimal en vez de coma: sirve para comprobar
# que cambiar el mapeo de hoy no toca el camino de lo que se publico ayer.
MAPPING_WITH_A_DOT = {
    "columns": {"occurred_on": 0, "description": 1, "reference": 2, "amount": 3},
    "date_format": "dmy",
    "decimal_format": "dot",
    "currency": "COP",
    "direction_mode": "signed_amount",
    "header_row": 1,
    "first_data_row": 2,
    "ignored_columns": [],
}

SIX_STAGES = ["artifact_version", "raw_locator", "extracted_field",
              "transformed_value", "source_record_field", "financial_fact_field"]


def slug_of(response) -> str:
    """El codigo de un problema vive al final de su `type`, no en un campo.

    Es RFC 7807: el documento no lleva `code`, lleva un `type` que es una URI, y
    el ultimo segmento es el identificador estable.
    """
    return str(response.json()["type"]).rsplit("/", 1)[-1]


def digest_like(marker: str) -> str:
    """Una huella con la forma correcta y sintetica a gritos."""
    return (marker * 64)[:64]


@contextlib.contextmanager
def as_migrator(company_id: str = ESPIGA):
    """Cursor del migrador con el contexto de empresa puesto.

    Estas tablas llevan `FORCE ROW LEVEL SECURITY`, asi que ser el dueno no
    exime: sin `fincilia.company_id` no se ve una sola fila, que es exactamente
    lo que se quiere.
    """
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            yield cursor


class OverrideHarness(VerticalHarness):
    """Prepara un dataset y deja a mano la fila y el campo sobre los que actuar."""

    def dataset_with_a_row(self, marker: str) -> tuple[str, str, str]:
        """Devuelve `(dataset_id, source_record_id, huella publicada del importe)`."""
        artifact = self.promoted(statement_csv(marker), "extracto.csv")
        version_id = self.validated_mapping(artifact)
        dataset_id = self.prepared(artifact, version_id).json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        target = [item for item in movements if item["record_ordinal"] == 2][0]
        with as_migrator() as cursor:
            cursor.execute(
                "SELECT source_record_id, field_digests "
                "FROM fincilia.canonical_movement WHERE movement_id = %s",
                (target["movement_id"],))
            source_record_id, digests = cursor.fetchone()
        self.movement_id = target["movement_id"]
        return str(dataset_id), str(source_record_id), digests["amount"]

    def override(self, dataset_id: str, source_record_id: str, **changes):
        body = {
            "source_record_id": source_record_id,
            "field_name": "amount",
            "override_kind": "manual_correction",
            # La cuarta etapa es `transformed_value`: el punto en que el texto de
            # la celda se vuelve un decimal, que es donde una correccion manual
            # de un importe ocurre de verdad.
            "base_step_ordinal": 4,
            "original_value_digest": digest_like("a"),
            "resulting_value_digest": digest_like("b"),
            "reason_code": "SYNTHETIC-FIXTURE",
        }
        body.update(changes)
        user = body.pop("user", PREPARER)
        company = body.pop("company", ESPIGA)
        return self.client.post(
            f"/api/v1/companies/{company}/datasets/{dataset_id}/overrides",
            headers=self.auth(user), json=body)

    def approve(self, override_id: str, user: str = REVIEWER):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/overrides/{override_id}/approve",
            headers=self.auth(user))

    def publish(self, dataset_id: str, user: str = REVIEWER):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(user))

    def stages_of(self, movement_id: str, field: str = "amount") -> list[dict]:
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{movement_id}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, detail.status_code, detail.text)
        by_field = {item["field"]: item for item in detail.json()["lineage"]}
        return by_field[field]["stages"]


class RowOverrideTests(OverrideHarness):
    """Las ocho preguntas que ADR-024 tiene que poder contestar."""

    # ------------------------------------------------------- las seis etapas #

    def test_a_field_without_an_override_shows_the_six_stages_TST_P36_018(self) -> None:
        """Sin override, el camino es el del plan compartido.

        La ausencia de excepcion no es una etapa que falte: son seis, en orden, y
        ninguna dice nada de un override.
        """
        dataset_id, _, _ = self.dataset_with_a_row("ovr-none")
        self.assertEqual(200, self.publish(dataset_id).status_code)
        stages = self.stages_of(self.movement_id)
        self.assertEqual([item["stage"] for item in stages], SIX_STAGES)
        self.assertEqual([item["override"] for item in stages], [None] * 6)

    def test_an_override_is_interleaved_where_it_happened_TST_P36_019(self) -> None:
        """Con override, las seis etapas siguen ahi y la excepcion va en su sitio.

        No al final: la pregunta que contesta un camino es en que punto exacto
        paso algo, y una anotacion al pie la deja sin contestar.
        """
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-six")
        created = self.override(dataset_id, record_id,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        approved = self.approve(created.json()["override_id"])
        self.assertEqual(200, approved.status_code, approved.text)
        sealed = self.publish(dataset_id, OWNER)
        self.assertEqual(200, sealed.status_code, sealed.text)

        stages = self.stages_of(self.movement_id)
        names = [item["stage"] for item in stages]
        # Las seis logicas siguen completas, y la excepcion se ve entre la cuarta
        # y la quinta, que es donde ocurrio.
        self.assertEqual([item for item in names if not item.endswith(":override")],
                         SIX_STAGES)
        self.assertEqual(names[4], "transformed_value:override")
        self.assertEqual(stages[4]["operation"], "overridden_by")
        self.assertEqual(stages[4]["transform_ref"],
                         "manual_correction:SYNTHETIC-FIXTURE")
        # Y sigue sin llevar el valor: solo huellas.
        self.assertEqual(len(stages[4]["identity"]["original_value_digest"]), 64)
        self.assertNotIn("-1.234,56", str(stages[4]))

    # -------------------------------------------------------------- bloqueos #

    def test_an_unapproved_override_blocks_publication_TST_P36_020(self) -> None:
        """Una excepcion sobre un importe que nadie ha mirado detiene el sello."""
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-block")
        created = self.override(dataset_id, record_id,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        self.assertIs(True, created.json()["needs_approval"])

        readiness = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, readiness.status_code, readiness.text)
        self.assertIs(False, readiness.json()["can_publish"])
        self.assertEqual(
            ["override-not-approved"],
            [item["code"] for item in readiness.json()["publish_blockers"]])

        refused = self.publish(dataset_id)
        self.assertEqual(422, refused.status_code, refused.text)
        self.assertEqual("override-not-approved", slug_of(refused))

        # Y despues de que lo mire otro, si.
        self.assertEqual(200, self.approve(created.json()["override_id"]).status_code)
        ready = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}",
            headers=self.auth(REVIEWER)).json()
        self.assertIs(True, ready["can_publish"])
        self.assertEqual([], ready["publish_blockers"])
        self.assertEqual(200, self.publish(dataset_id, OWNER).status_code)

    def test_the_author_of_an_override_cannot_approve_it_TST_P36_021(self) -> None:
        """Un override que se aprueba solo no lo ha revisado nadie."""
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-sod")
        created = self.override(dataset_id, record_id, user=OWNER,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        override_id = created.json()["override_id"]

        # Sofia tiene los dos permisos y aun asi no puede las dos cosas.
        refused = self.approve(override_id, user=OWNER)
        self.assertEqual(409, refused.status_code, refused.text)
        self.assertEqual("segregation-of-duties", slug_of(refused))

        # Y el `CHECK` de la base dice lo mismo cuando se llega por otro camino.
        with as_migrator() as cursor:
            cursor.execute("SELECT created_by FROM fincilia.lineage_row_override "
                           "WHERE override_id = %s", (override_id,))
            author = cursor.fetchone()[0]
            with self.assertRaises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "UPDATE fincilia.lineage_row_override "
                    "SET approved_by = %s, approved_at = now() "
                    "WHERE override_id = %s", (author, override_id))

    def test_an_override_cannot_reach_another_company_TST_P36_022(self) -> None:
        """La fila es de una empresa, y la excepcion tambien.

        Ana es preparadora en Andinos tambien, asi que la negativa no puede venir
        del permiso: tiene que venir de la politica de la fila.
        """
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-tenant")
        refused = self.override(dataset_id, record_id, company=ANDINOS,
                                resulting_value_digest=published)
        self.assertEqual(403, refused.status_code, refused.text)

        # Y por debajo, la clave ajena compuesta impide colgar una excepcion de
        # Andinos sobre un dataset de Espiga. Se escribe una legitima primero
        # para tomar de ella las referencias, que si existen, y el intento va con
        # otro ordinal: `uq_override_target` es un indice y los indices no
        # filtran por politica, asi que chocaria antes de llegar a la frontera
        # que se quiere probar.
        created = self.override(dataset_id, record_id,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        with as_migrator() as cursor:
            cursor.execute(
                "SELECT raw_record_id, base_plan_step_id, created_by, "
                "       engine_release_id FROM fincilia.lineage_row_override "
                "WHERE override_id = %s", (created.json()["override_id"],))
            raw_id, step_id, author, release_id = cursor.fetchone()

        with as_migrator(ANDINOS) as cursor:
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                cursor.execute(
                    "INSERT INTO fincilia.lineage_row_override (company_id, "
                    "dataset_version_id, source_record_id, raw_record_id, "
                    "field_name, base_plan_step_id, override_kind, "
                    "original_value_digest, resulting_value_digest, rule_version, "
                    "reason_code, override_ordinal, created_by, engine_release_id, "
                    "canonical_schema_version) VALUES (%s, %s, %s, %s, 'amount', "
                    "%s, 'manual_correction', %s, %s, 'x', 'y', 99, %s, %s, "
                    "'0.1.0')",
                    (ANDINOS, dataset_id, record_id, raw_id, step_id,
                     digest_like("a"), digest_like("b"), author, release_id))

    def test_a_result_the_movement_does_not_carry_blocks_TST_P36_023(self) -> None:
        """Si la huella del resultado no es la publicada, describe otra fila."""
        dataset_id, record_id, _ = self.dataset_with_a_row("ovr-digest")
        created = self.override(dataset_id, record_id,
                                resulting_value_digest=digest_like("c"))
        self.assertEqual(201, created.status_code, created.text)
        self.assertEqual(200, self.approve(created.json()["override_id"]).status_code)

        refused = self.publish(dataset_id, OWNER)
        self.assertEqual(422, refused.status_code, refused.text)
        self.assertEqual("override-not-approved", slug_of(refused))
        self.assertIn("does not carry", refused.json()["detail"])

    def test_a_rule_that_holds_for_one_row_is_reconstructible_TST_P36_024(self) -> None:
        """Una regla por fila se explica sola, sin tocar el plan de la columna.

        Es el caso que el disparador de revision de ADR-024 nombra: si existiera
        y no cupiera en ningun sitio, la premisa del ADR estaria rota.
        """
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-rule")
        created = self.override(
            dataset_id, record_id, override_kind="row_rule",
            base_step_ordinal=3, reason_code="EXCEPTIONAL-PARSE",
            resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        self.assertEqual(200, self.approve(created.json()["override_id"]).status_code)
        self.assertEqual(200, self.publish(dataset_id, OWNER).status_code)

        stages = self.stages_of(self.movement_id)
        self.assertEqual(stages[3]["stage"], "extracted_field:override")
        self.assertEqual(stages[3]["transform_ref"], "row_rule:EXCEPTIONAL-PARSE")

        # El plan de la columna no se ha tocado: las otras filas se siguen
        # leyendo como siempre.
        others = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(REVIEWER)).json()
        other = [item for item in others if item["record_ordinal"] != 2][0]
        self.assertEqual(
            [item["stage"] for item in self.stages_of(other["movement_id"])],
            SIX_STAGES)

    def test_changing_the_plan_does_not_reinterpret_history_TST_P36_025(self) -> None:
        """Lo publicado ayer se sigue explicando con las reglas de ayer.

        Se publica con un mapeo, se crea otro que lee el importe de otra forma, y
        el camino del movimiento antiguo no se mueve.
        """
        dataset_id, _, _ = self.dataset_with_a_row("ovr-history")
        self.assertEqual(200, self.publish(dataset_id).status_code)
        before = self.stages_of(self.movement_id)
        self.assertEqual(before[3]["transform_ref"], "normalise_amount:comma")

        artifact = self.promoted(statement_csv("ovr-history-2"), "extracto.csv")
        created = self.create_mapping(artifact, MAPPING_WITH_A_DOT)
        self.assertEqual(201, created.status_code, created.text)
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/"
            f"{created.json()['mapping_version_id']}/validate",
            headers=self.auth(PREPARER))

        self.assertEqual(before, self.stages_of(self.movement_id))

    def test_a_missing_stage_blocks_publication_TST_P36_026(self) -> None:
        """Quitar una etapa del plan detiene el sello.

        No hay cobertura parcial ni promedio: cinco etapas de seis no explican un
        importe, explican casi un importe. Y un override requerido que nadie ha
        aprobado bloquea por su cuenta.
        """
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-missing")
        # El override cuelga de la tercera etapa y la que se borra es la cuarta:
        # `fk_override_plan_step` es `RESTRICT`, asi que borrar justo la etapa de
        # la que cuelga no probaria que falta una, probaria que la clave ajena
        # funciona —que ya tiene su prueba—.
        created = self.override(dataset_id, record_id, base_step_ordinal=3,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        refused = self.publish(dataset_id)
        self.assertEqual(422, refused.status_code, refused.text)
        self.assertEqual("override-not-approved", slug_of(refused))

        with as_migrator() as cursor:
            cursor.execute(
                "DELETE FROM fincilia.lineage_transform_step s "
                "USING fincilia.dataset_version d "
                "WHERE d.dataset_version_id = %s AND s.plan_id = d.lineage_plan_id "
                "  AND s.canonical_field = 'amount' AND s.step_ordinal = 4",
                (dataset_id,))
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{self.movement_id}",
            headers=self.auth(REVIEWER)).json()
        self.assertIs(False, detail["lineage_complete"])
        self.assertIn("amount", detail["lineage_reason"])


class OverrideStorageTests(OverrideHarness):
    """Lo que la tabla no deja hacer, se llegue por donde se llegue."""

    def test_an_override_is_never_edited_or_deleted_TST_P36_027(self) -> None:
        """Editarlo levanta; borrarlo no es un privilegio que el runtime tenga.

        Son dos mecanismos distintos a proposito. El disparador contesta «que
        puede cambiar» y el privilegio contesta «quien puede»; comprobar el
        segundo mirando el `CHECK` del primero dejaria sin probar justo lo que
        aguanta cuando alguien llega por otro camino.
        """
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-frozen")
        created = self.override(dataset_id, record_id,
                                resulting_value_digest=published)
        override_id = created.json()["override_id"]
        with as_migrator() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "UPDATE fincilia.lineage_row_override SET reason_code = 'otro' "
                    "WHERE override_id = %s", (override_id,))
        with as_migrator() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('fincilia_app', "
                "       'fincilia.lineage_row_override', %s)", ("DELETE",))
            self.assertIs(False, cursor.fetchone()[0])
            for privilege in ("SELECT", "INSERT", "UPDATE"):
                cursor.execute(
                    "SELECT has_table_privilege('fincilia_app', "
                    "       'fincilia.lineage_row_override', %s)", (privilege,))
                self.assertIs(True, cursor.fetchone()[0], privilege)

    def test_changing_your_mind_leaves_both_opinions_TST_P36_028(self) -> None:
        """El vigente es el ultimo; el anterior se queda donde estaba."""
        dataset_id, record_id, published = self.dataset_with_a_row("ovr-second")
        first = self.override(dataset_id, record_id,
                              resulting_value_digest=digest_like("c"))
        self.assertEqual(201, first.status_code, first.text)
        second = self.override(dataset_id, record_id,
                               resulting_value_digest=published)
        self.assertEqual(201, second.status_code, second.text)
        self.assertEqual(2, second.json()["override_ordinal"])

        current = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/overrides",
            headers=self.auth(REVIEWER)).json()
        self.assertEqual([item["override_id"] for item in current],
                         [second.json()["override_id"]])

        with as_migrator() as cursor:
            cursor.execute("SELECT count(*) FROM fincilia.lineage_row_override "
                           "WHERE dataset_version_id = %s", (dataset_id,))
            self.assertEqual(2, cursor.fetchone()[0])

    def test_an_override_that_changes_nothing_is_refused_TST_P36_029(self) -> None:
        dataset_id, record_id, _ = self.dataset_with_a_row("ovr-noop")
        same = digest_like("d")
        refused = self.override(dataset_id, record_id,
                                original_value_digest=same,
                                resulting_value_digest=same)
        self.assertEqual(422, refused.status_code, refused.text)
        self.assertEqual("override-changes-nothing", slug_of(refused))

    def test_a_field_the_plan_does_not_publish_is_refused_TST_P36_030(self) -> None:
        dataset_id, record_id, _ = self.dataset_with_a_row("ovr-stage")
        refused = self.override(dataset_id, record_id, field_name="no_existe")
        self.assertEqual(422, refused.status_code, refused.text)
        self.assertEqual("override-field-unknown", slug_of(refused))

    def test_a_published_dataset_takes_no_more_overrides_TST_P36_031(self) -> None:
        dataset_id, record_id, _ = self.dataset_with_a_row("ovr-sealed")
        self.assertEqual(200, self.publish(dataset_id).status_code)
        refused = self.override(dataset_id, record_id)
        self.assertEqual(409, refused.status_code, refused.text)
        self.assertEqual("dataset-already-published", slug_of(refused))

    def test_public_cannot_execute_the_override_trigger_TST_P36_032(self) -> None:
        """Un ACL nulo significa ejecutable por PUBLIC, y esa es la trampa."""
        with as_migrator() as cursor:
            cursor.execute(
                "SELECT has_function_privilege('public', p.oid, 'EXECUTE') "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'fincilia' "
                "  AND p.proname = 'lineage_row_override_is_append_only'")
            row = cursor.fetchone()
        self.assertIsNotNone(row, "the trigger function should exist")
        self.assertIs(False, row[0])


if __name__ == "__main__":
    unittest.main()
