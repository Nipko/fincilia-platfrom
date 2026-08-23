"""Plan de transformacion y reconstruccion de las seis etapas.

La prueba que sostiene a las demas es la de la cadena de tipos: si la salida de
una etapa no es la entrada de la siguiente, el camino no explica nada aunque
tenga seis filas.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.lineage import (  # noqa: E402
    STAGES,
    LineageError,
    build_plan,
    plan_digest,
    reconstruct,
    validate_plan,
)
from fincilia_contracts.mapping import ColumnMapping  # noqa: E402

RELEASE = "fnc-p3-mapping-0.1.0"

MAPPING = ColumnMapping(
    columns={"occurred_on": 0, "description": 1, "reference": 2, "amount": 3},
    date_format="dmy", decimal_format="comma", currency="COP",
    direction_mode="signed_amount", header_row=1, first_data_row=2)

LOCATOR = {
    "locator_kind": "tabular_delimited",
    "artifact_sha256": "a" * 64,
    "record_ordinal": 42,
    "byte_start": 1180,
    "byte_end": 1236,
    "field_count": 4,
}


class PlanShapeTests(unittest.TestCase):
    def test_every_mapped_field_gets_the_six_contract_stages(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        for field in MAPPING.columns:
            with self.subTest(field=field):
                chain = [s for s in steps if s.canonical_field == field]
                self.assertEqual(tuple(s.stage for s in chain), STAGES)
                self.assertEqual([s.step_ordinal for s in chain], [1, 2, 3, 4, 5, 6])

    def test_the_plan_grows_with_columns_and_not_with_rows(self) -> None:
        # Es la premisa entera del diseno: seis etapas por **columna**.
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        self.assertEqual(len(steps), 6 * len(MAPPING.columns))

    def test_the_type_chain_joins_end_to_end(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        for field in MAPPING.columns:
            chain = sorted((s for s in steps if s.canonical_field == field),
                           key=lambda s: s.step_ordinal)
            for previous, following in zip(chain, chain[1:]):
                with self.subTest(field=field, stage=following.stage):
                    self.assertEqual(previous.output_semantic_type,
                                     following.input_semantic_type)

    def test_the_convention_travels_inside_the_transformation(self) -> None:
        # `parse_date` sin mas no dice si el `02/03` era marzo o febrero, y esa es
        # la pregunta que una discrepancia contable obliga a contestar.
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        transformed = {s.canonical_field: s.transform_ref for s in steps
                       if s.stage == "transformed_value"}
        self.assertEqual(transformed["occurred_on"], "parse_date:dmy")
        self.assertEqual(transformed["amount"], "normalise_amount:comma")

    def test_a_human_decision_is_visible_in_the_path(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE,
                           decided_fields=frozenset({"occurred_on"}))
        transformed = {s.canonical_field: s.transform_ref for s in steps
                       if s.stage == "transformed_value"}
        self.assertEqual(transformed["occurred_on"], "parse_date:dmy#decided")
        self.assertEqual(transformed["amount"], "normalise_amount:comma")

    def test_the_first_stage_seals_and_the_rest_derive(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        for step in steps:
            with self.subTest(field=step.canonical_field, stage=step.stage):
                expected = ("included_in_snapshot" if step.stage == "artifact_version"
                            else "derived_from")
                self.assertEqual(step.operation, expected)
                self.assertTrue(step.transform_ref)

    def test_every_step_carries_its_versions(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        for step in steps:
            with self.subTest(field=step.canonical_field, stage=step.stage):
                self.assertTrue(step.parser_version)
                self.assertTrue(step.rule_version)
                self.assertEqual(len(step.configuration_digest), 64)

    def test_a_mapping_without_columns_has_no_lineage(self) -> None:
        empty = ColumnMapping(columns={}, date_format="iso", decimal_format="dot",
                              currency="COP", direction_mode="signed_amount")
        with self.assertRaises(LineageError):
            build_plan(empty, engine_release_key=RELEASE)


class PlanIdentityTests(unittest.TestCase):
    def test_the_same_mapping_and_release_give_the_same_digest(self) -> None:
        first = plan_digest(build_plan(MAPPING, engine_release_key=RELEASE))
        second = plan_digest(build_plan(MAPPING, engine_release_key=RELEASE))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_changing_the_convention_changes_the_plan(self) -> None:
        # Si no cambiara, dos lecturas distintas del mismo fichero compartirian
        # explicacion, y una de las dos seria mentira.
        other = ColumnMapping(**{**MAPPING.__dict__, "date_format": "mdy"})
        self.assertNotEqual(plan_digest(build_plan(MAPPING, engine_release_key=RELEASE)),
                            plan_digest(build_plan(other, engine_release_key=RELEASE)))

    def test_changing_the_engine_release_changes_the_plan(self) -> None:
        self.assertNotEqual(
            plan_digest(build_plan(MAPPING, engine_release_key=RELEASE)),
            plan_digest(build_plan(MAPPING, engine_release_key="otra-0.2.0")))

    def test_moving_a_column_changes_the_plan(self) -> None:
        moved = ColumnMapping(**{**MAPPING.__dict__,
                                 "columns": {**MAPPING.columns, "amount": 4}})
        self.assertNotEqual(plan_digest(build_plan(MAPPING, engine_release_key=RELEASE)),
                            plan_digest(build_plan(moved, engine_release_key=RELEASE)))


class ValidationTests(unittest.TestCase):
    def test_a_complete_plan_has_nothing_to_report(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        self.assertEqual(validate_plan(steps, frozenset(MAPPING.columns)), [])

    def test_a_missing_stage_blocks(self) -> None:
        # `on_incomplete: block_publication`, y sin cobertura parcial.
        steps = tuple(s for s in build_plan(MAPPING, engine_release_key=RELEASE)
                      if not (s.canonical_field == "amount" and s.stage == "extracted_field"))
        problems = validate_plan(steps, frozenset(MAPPING.columns))
        self.assertTrue(problems)
        self.assertIn("amount", problems[0])
        self.assertIn("5 of 6", problems[0])

    def test_a_field_with_no_stages_at_all_blocks(self) -> None:
        steps = tuple(s for s in build_plan(MAPPING, engine_release_key=RELEASE)
                      if s.canonical_field != "reference")
        problems = validate_plan(steps, frozenset(MAPPING.columns))
        self.assertTrue(any("reference" in problem for problem in problems))

    def test_stages_for_a_field_nobody_publishes_are_reported(self) -> None:
        steps = build_plan(MAPPING, engine_release_key=RELEASE)
        problems = validate_plan(steps, frozenset({"occurred_on", "description"}))
        self.assertTrue(any("unpublished" in problem for problem in problems))


class ReconstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steps = build_plan(MAPPING, engine_release_key=RELEASE, delimiter=";")

    def test_the_six_stages_come_back_in_order(self) -> None:
        stages = reconstruct(self.steps, canonical_field="amount",
                             origin_locator=LOCATOR, raw_record_id="raw-1",
                             source_record_id="src-1", movement_id="mov-1",
                             value_digest="c" * 64)
        self.assertEqual([s["stage"] for s in stages], list(STAGES))
        self.assertEqual([s["step_ordinal"] for s in stages], [1, 2, 3, 4, 5, 6])

    def test_the_cell_is_the_exact_coordinate(self) -> None:
        stages = reconstruct(self.steps, canonical_field="amount",
                             origin_locator=LOCATOR, raw_record_id="raw-1",
                             source_record_id="src-1", movement_id="mov-1",
                             value_digest="c" * 64)
        cell = stages[1]["identity"]["cell"]
        self.assertEqual(cell["record_ordinal"], 42)
        self.assertEqual(cell["field_ordinal"], 3)
        self.assertEqual(cell["byte_start"], 1180)
        self.assertEqual(cell["byte_end"], 1236)
        self.assertEqual(cell["artifact_sha256"], "a" * 64)

    def test_the_intermediate_stage_is_identifiable(self) -> None:
        # La pregunta que la divergencia anterior no podia contestar: en que punto
        # exacto este texto se convirtio en un decimal.
        stages = reconstruct(self.steps, canonical_field="amount",
                             origin_locator=LOCATOR, raw_record_id="raw-1",
                             source_record_id="src-1", movement_id="mov-1",
                             value_digest="c" * 64)
        transformed = stages[3]
        self.assertEqual(transformed["stage"], "transformed_value")
        self.assertEqual(transformed["input_semantic_type"], "cell_text")
        self.assertEqual(transformed["output_semantic_type"], "money_decimal")
        self.assertEqual(transformed["transform_ref"], "normalise_amount:comma")

    def test_the_terminal_stage_carries_the_digest_and_not_the_value(self) -> None:
        stages = reconstruct(self.steps, canonical_field="amount",
                             origin_locator=LOCATOR, raw_record_id="raw-1",
                             source_record_id="src-1", movement_id="mov-1",
                             value_digest="c" * 64)
        terminal = stages[5]["identity"]
        self.assertEqual(terminal["value_digest"], "c" * 64)
        rendered = str(stages)
        for value in ("1.234,56", "1234.56"):
            self.assertNotIn(value, rendered)

    def test_without_a_locator_it_refuses_instead_of_half_answering(self) -> None:
        with self.assertRaises(LineageError):
            reconstruct(self.steps, canonical_field="amount", origin_locator={},
                        raw_record_id="raw-1", source_record_id="src-1",
                        movement_id="mov-1", value_digest="c" * 64)

    def test_without_a_value_digest_it_refuses(self) -> None:
        with self.assertRaises(LineageError):
            reconstruct(self.steps, canonical_field="amount",
                        origin_locator=LOCATOR, raw_record_id="raw-1",
                        source_record_id="src-1", movement_id="mov-1",
                        value_digest=None)

    def test_a_field_the_plan_does_not_cover_refuses(self) -> None:
        with self.assertRaises(LineageError):
            reconstruct(self.steps, canonical_field="direction",
                        origin_locator=LOCATOR, raw_record_id="raw-1",
                        source_record_id="src-1", movement_id="mov-1",
                        value_digest="c" * 64)

    def test_an_old_plan_still_reconstructs_with_its_own_rules(self) -> None:
        # Una version anterior sigue siendo consultable: el plan viejo explica lo
        # que el viejo produjo, y el nuevo no lo reescribe.
        old = build_plan(ColumnMapping(**{**MAPPING.__dict__, "date_format": "mdy"}),
                         engine_release_key=RELEASE, delimiter=";")
        stages = reconstruct(old, canonical_field="occurred_on",
                             origin_locator=LOCATOR, raw_record_id="raw-1",
                             source_record_id="src-1", movement_id="mov-1",
                             value_digest="d" * 64)
        self.assertEqual(stages[3]["transform_ref"], "parse_date:mdy")


if __name__ == "__main__":
    unittest.main()
