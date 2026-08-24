"""Contrato del mapeo a movimientos canonicos.

Cada prueba describe una forma concreta de convertir un fichero en el dinero
equivocado. Son las que importan: un mapeo que funciona con el caso feliz y falla
con un separador de miles produce importes mil veces mayores, y el fallo no se ve
hasta el cierre.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from fincilia_contracts.mapping import (CANONICAL_FIELDS, ColumnMapping, MappingError,
                                        apply, apply_row, normalise_amount,
                                        parse_date, parse_direction, validate_mapping)
from fincilia_contracts.money import MoneyError


def mapping(**overrides) -> ColumnMapping:
    fields = {
        "columns": {"occurred_on": 0, "description": 1, "debit": 2, "credit": 3},
        "date_format": "dmy",
        "decimal_format": "comma",
        "currency": "COP",
        "direction_mode": "debit_credit_columns",
    }
    fields.update(overrides)
    return ColumnMapping(**fields)


class MappingValidationTests(unittest.TestCase):
    def test_a_complete_mapping_is_publishable(self) -> None:
        self.assertEqual([], validate_mapping(mapping()))

    def test_a_mapping_without_a_currency_cannot_publish(self) -> None:
        # Un numero sin unidad no es dinero.
        codes = [item.code for item in validate_mapping(mapping(currency=""))]
        self.assertIn("MAP-CURRENCY", codes)

    def test_an_unsupported_currency_cannot_publish(self) -> None:
        codes = [item.code for item in validate_mapping(mapping(currency="XYZ"))]
        self.assertIn("MAP-CURRENCY", codes)

    def test_a_mapping_without_a_date_column_cannot_publish(self) -> None:
        broken = mapping(columns={"description": 1, "debit": 2, "credit": 3})
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-MISSING-COLUMN", codes)

    def test_debit_credit_mode_needs_both_columns(self) -> None:
        broken = mapping(columns={"occurred_on": 0, "description": 1, "debit": 2})
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-DIRECTION-COLUMNS", codes)

    def test_debit_and_credit_cannot_be_the_same_column(self) -> None:
        broken = mapping(columns={"occurred_on": 0, "description": 1,
                                  "debit": 2, "credit": 2})
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-DIRECTION-COLUMNS", codes)

    def test_signed_amount_mode_needs_an_amount_column(self) -> None:
        broken = mapping(direction_mode="signed_amount")
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-DIRECTION-COLUMNS", codes)

    def test_explicit_direction_mode_needs_both_columns(self) -> None:
        broken = mapping(direction_mode="explicit_direction",
                         columns={"occurred_on": 0, "description": 1, "amount": 2})
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-DIRECTION-COLUMNS", codes)

    def test_an_unknown_canonical_field_cannot_publish(self) -> None:
        broken = mapping(columns={"occurred_on": 0, "description": 1, "debit": 2,
                                  "credit": 3, "inventado": 4})
        codes = [item.code for item in validate_mapping(broken)]
        self.assertIn("MAP-UNKNOWN-FIELD", codes)

    def test_every_declared_field_is_a_canonical_one(self) -> None:
        for name in mapping().columns:
            self.assertIn(name, CANONICAL_FIELDS)


class ProfileAgreementTests(unittest.TestCase):
    """El perfil marco lo ambiguo; publicar sobre eso seria elegir por la persona."""

    def profile(self, **overrides) -> dict:
        base = {
            "column_count": 4,
            "columns": [
                {"index": 0, "header": "Fecha", "inferred_type": "date_dmy",
                 "ambiguous": False},
                {"index": 1, "header": "Detalle", "inferred_type": "text",
                 "ambiguous": False},
                {"index": 2, "header": "Debito", "inferred_type": "decimal_comma",
                 "ambiguous": False},
                {"index": 3, "header": "Credito", "inferred_type": "decimal_comma",
                 "ambiguous": False},
            ],
        }
        base.update(overrides)
        return base

    def test_a_mapping_that_matches_the_profile_is_publishable(self) -> None:
        self.assertEqual([], validate_mapping(mapping(), self.profile()))

    def test_an_ambiguous_date_column_blocks_publication(self) -> None:
        profile = self.profile()
        profile["columns"][0].update(inferred_type="ambiguous_date", ambiguous=True)
        codes = [item.code for item in validate_mapping(mapping(), profile)]
        self.assertIn("MAP-AMBIGUOUS-COLUMN", codes)

    def test_an_ambiguous_amount_column_blocks_publication(self) -> None:
        profile = self.profile()
        profile["columns"][2].update(inferred_type="ambiguous_numeric", ambiguous=True)
        codes = [item.code for item in validate_mapping(mapping(), profile)]
        self.assertIn("MAP-AMBIGUOUS-COLUMN", codes)

    def test_schema_drift_invalidates_a_previous_mapping(self) -> None:
        # El fichero perdio una columna: los indices del mapeo anterior apuntan a
        # otra cosa, y nada fallaria si se publicara.
        codes = [item.code
                 for item in validate_mapping(mapping(), self.profile(column_count=3))]
        self.assertIn("MAP-SCHEMA-DRIFT", codes)

    def test_a_column_missing_from_the_profile_blocks_publication(self) -> None:
        profile = self.profile()
        profile["columns"] = profile["columns"][:3]
        codes = [item.code for item in validate_mapping(mapping(), profile)]
        self.assertIn("MAP-COLUMN-ABSENT", codes)


class DateTests(unittest.TestCase):
    def test_the_declared_format_decides(self) -> None:
        self.assertEqual("2026-03-04", parse_date("04/03/2026", "dmy"))
        self.assertEqual("2026-04-03", parse_date("04/03/2026", "mdy"))

    def test_an_iso_value_needs_an_iso_mapping(self) -> None:
        self.assertEqual("2026-01-02", parse_date("2026-01-02", "iso"))
        with self.assertRaises(MappingError):
            parse_date("2026-01-02", "dmy")

    def test_a_two_digit_year_is_never_completed(self) -> None:
        # `03/04/26` es exactamente el caso que el mandato senala: 26 puede ser
        # 1926 o 2026, y completar con una regla de siglo inventada es decidir por
        # alguien.
        with self.assertRaises(MappingError):
            parse_date("03/04/26", "dmy")

    def test_an_impossible_date_is_refused(self) -> None:
        for value, form in (("31/02/2026", "dmy"), ("13/13/2026", "dmy"),
                            ("00/01/2026", "dmy"), ("29/02/2026", "dmy")):
            with self.subTest(value=value):
                with self.assertRaises(MappingError):
                    parse_date(value, form)

    def test_a_leap_day_is_accepted_in_a_leap_year(self) -> None:
        self.assertEqual("2028-02-29", parse_date("29/02/2028", "dmy"))

    def test_an_empty_date_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            parse_date("", "dmy")


class AmountTests(unittest.TestCase):
    def test_the_colombian_convention(self) -> None:
        self.assertEqual("1250000.00", normalise_amount("1.250.000,00", "comma"))

    def test_the_anglo_convention(self) -> None:
        self.assertEqual("1250000.00", normalise_amount("1,250,000.00", "dot"))

    def test_the_same_text_reads_differently_under_each_convention(self) -> None:
        # `1.234` es mil doscientos treinta y cuatro con coma decimal, y uno coma
        # doscientos treinta y cuatro con punto decimal. Por eso lo dice el mapeo.
        self.assertEqual("1234", normalise_amount("1.234", "comma"))
        self.assertEqual("1.234", normalise_amount("1.234", "dot"))

    def test_a_value_that_contradicts_the_convention_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            normalise_amount("1,23,45", "dot")

    def test_an_empty_amount_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            normalise_amount("", "comma")

    def test_a_non_numeric_amount_is_refused(self) -> None:
        for value in ("pendiente", "1.2.3", "--5", "1e5"):
            with self.subTest(value=value):
                with self.assertRaises(MappingError):
                    normalise_amount(value, "dot")

    def test_the_amount_is_exact_and_never_a_float(self) -> None:
        row = ["02/03/2026", "Transferencia", "1.250.000,00", ""]
        movement = apply_row(mapping(), row, 2)
        self.assertIsInstance(movement.amount, Decimal)
        self.assertEqual(Decimal("1250000"), movement.amount)
        # Y se serializa en punto fijo, nunca en notacion cientifica ni en float.
        self.assertEqual("1250000.000000000000", movement.as_dict()["amount"])

    def test_a_float_is_rejected_not_converted(self) -> None:
        # La regla del modulo de dinero, comprobada desde aqui: convertir un float
        # es aceptar en silencio un valor que ya perdio precision.
        from fincilia_contracts.money import parse_money
        with self.assertRaises(MoneyError):
            parse_money(1250000.00)


class DirectionTests(unittest.TestCase):
    def test_a_debit_is_an_outflow_and_a_credit_an_inflow(self) -> None:
        debit = apply_row(mapping(), ["02/03/2026", "Pago", "1.250,00", ""], 2)
        credit = apply_row(mapping(), ["02/03/2026", "Cobro", "", "3.400,00"], 3)
        self.assertEqual("outflow", debit.direction)
        self.assertEqual("inflow", credit.direction)

    def test_a_row_that_is_both_a_debit_and_a_credit_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            apply_row(mapping(), ["02/03/2026", "Ambas", "1.250,00", "3.400,00"], 2)

    def test_a_row_with_neither_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            apply_row(mapping(), ["02/03/2026", "Ninguna", "", ""], 2)

    def test_a_sign_in_a_debit_column_is_refused(self) -> None:
        # La columna ya dice la direccion; el signo seria una segunda opinion.
        with self.assertRaises(MappingError):
            apply_row(mapping(), ["02/03/2026", "Pago", "-1.250,00", ""], 2)

    def test_the_sign_only_means_direction_when_the_mapping_says_so(self) -> None:
        signed = mapping(direction_mode="signed_amount",
                         columns={"occurred_on": 0, "description": 1, "amount": 2})
        out = apply_row(signed, ["02/03/2026", "Pago", "-1.250,00"], 2)
        self.assertEqual("outflow", out.direction)
        self.assertEqual(Decimal("1250"), out.amount, "the stored amount is positive")
        into = apply_row(signed, ["02/03/2026", "Cobro", "3.400,00"], 3)
        self.assertEqual("inflow", into.direction)

    def test_an_explicit_direction_column_is_read_not_guessed(self) -> None:
        explicit = mapping(direction_mode="explicit_direction",
                           columns={"occurred_on": 0, "description": 1,
                                    "amount": 2, "direction": 3})
        row = apply_row(explicit, ["02/03/2026", "Pago", "1.250,00", "debito"], 2)
        self.assertEqual("outflow", row.direction)

    def test_an_explicit_direction_contradicting_a_negative_amount_is_refused(self) -> None:
        explicit = mapping(direction_mode="explicit_direction",
                           columns={"occurred_on": 0, "description": 1,
                                    "amount": 2, "direction": 3})
        with self.assertRaises(MappingError):
            apply_row(explicit, ["02/03/2026", "Pago", "-1.250,00", "debito"], 2)

    def test_the_spanish_vocabulary_maps_to_the_declared_enum(self) -> None:
        for word in ("debito", "débito", "cargo", "debe"):
            with self.subTest(word=word):
                self.assertEqual("outflow", parse_direction(word))
        for word in ("credito", "crédito", "abono", "haber"):
            with self.subTest(word=word):
                self.assertEqual("inflow", parse_direction(word))

    def test_an_unreadable_direction_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            parse_direction("quiza")


class ApplyTests(unittest.TestCase):
    ROWS = [
        ["02/03/2026", "Transferencia Harinas", "1.250.000,00", ""],
        ["15/03/2026", "Consignacion Mercado", "", "3.400.000,00"],
        ["20/03/2026", "", "18.500,00", ""],
        ["31/02/2026", "Fecha imposible", "1.000,00", ""],
        ["22/03/2026", "Ambas columnas", "10,00", "20,00"],
    ]

    def test_valid_rows_are_published_and_the_rest_are_counted(self) -> None:
        result = apply(mapping(), self.ROWS)
        self.assertEqual(2, len(result.movements))
        self.assertEqual(3, len(result.rejections))
        self.assertTrue(result.publishable)

    def test_every_rejection_says_why(self) -> None:
        for rejection in apply(mapping(), self.ROWS).rejections:
            with self.subTest(row=rejection.row_number):
                self.assertTrue(rejection.detail)
                self.assertTrue(rejection.code)

    def test_row_numbers_follow_the_file_not_the_result(self) -> None:
        # Sin esto, el numero de fila de un rechazo no sirve para ir a mirarla.
        result = apply(mapping(), self.ROWS, first_row_number=2)
        self.assertEqual([2, 3], [item.row_number for item in result.movements])
        self.assertEqual([4, 5, 6], [item.row_number for item in result.rejections])

    def test_a_mapping_that_cannot_publish_never_runs(self) -> None:
        # No se procesa media entrega con un mapeo que no valida: se para antes.
        with self.assertRaises(MappingError):
            apply(mapping(currency=""), self.ROWS)

    def test_the_result_is_serialisable_and_counts_both_sides(self) -> None:
        payload = apply(mapping(), self.ROWS).as_dict()
        self.assertEqual(2, payload["accepted"])
        self.assertEqual(3, payload["rejected"])

    def test_every_movement_carries_its_currency(self) -> None:
        for movement in apply(mapping(), self.ROWS).movements:
            self.assertEqual("COP", movement.currency)

    def test_every_movement_carries_the_columns_it_came_from(self) -> None:
        # Linaje minimo: de que columna salio cada campo. Sin esto no se puede
        # volver del valor canonico a su origen.
        for movement in apply(mapping(), self.ROWS).movements:
            self.assertEqual(mapping().columns, movement.source_column)

    def test_a_zero_movement_is_refused(self) -> None:
        result = apply(mapping(), [["02/03/2026", "Cero", "0,00", ""]])
        self.assertEqual(0, len(result.movements))
        self.assertEqual(1, len(result.rejections))

    def test_the_same_input_always_gives_the_same_output(self) -> None:
        first = apply(mapping(), self.ROWS).as_dict()
        second = apply(mapping(), self.ROWS).as_dict()
        self.assertEqual(first, second)

    def test_a_short_row_is_rejected_not_padded(self) -> None:
        result = apply(mapping(), [["02/03/2026"]])
        self.assertEqual(1, len(result.rejections))


if __name__ == "__main__":
    unittest.main()
