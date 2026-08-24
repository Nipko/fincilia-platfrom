"""`accounting_date` no se infiere, y esta prueba existe para que siga sin hacerlo.

Cuándo ocurrió algo, cuándo se asentó y a qué periodo contable pertenece son tres
hechos distintos. Los dos primeros los trae el fichero; el tercero es una
decisión de cierre que depende del periodo abierto, de las reglas de la firma y,
a veces, de una persona.

La tentación es evidente y barata: si `accounting_date` está vacía, poner la
fecha de ocurrencia y seguir. Haría que todo cuadrara consigo mismo y movería
asientos de mes sin que nada fallara, que es la peor clase de error que puede
tener un sistema contable —el que no se nota hasta que alguien concilia meses
después.

P3.6 la deja **nula a propósito**. Se resolverá en P4 con periodo contable,
reglas y revisión humana. Mientras tanto:

* no alimenta reportes certificados;
* no alimenta cierre;
* no se infiere automáticamente de ninguna otra fecha.

Esta prueba es la que impide que el atajo entre por la puerta de atrás.
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts import mapping  # noqa: E402
from fincilia_contracts.lineage import FIELD_TYPES, build_plan  # noqa: E402
from fincilia_contracts.mapping import (  # noqa: E402
    CANONICAL_FIELDS,
    ColumnMapping,
    Movement,
    apply_row,
)

MAPPING = ColumnMapping(
    columns={"occurred_on": 0, "description": 1, "amount": 2},
    date_format="iso", decimal_format="dot", currency="COP",
    direction_mode="signed_amount", header_row=1, first_data_row=2)


class NotMappableTests(unittest.TestCase):
    def test_accounting_date_is_not_a_canonical_field_a_mapping_can_fill(self) -> None:
        # Si estuviera aqui, una columna del fichero podria declararse periodo
        # contable, y el periodo contable no sale de un extracto bancario.
        self.assertNotIn("accounting_date", CANONICAL_FIELDS)

    def test_no_canonical_field_is_an_alias_of_the_accounting_period(self) -> None:
        for field in CANONICAL_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn("accounting", field)

    def test_a_movement_produced_by_the_mapping_has_no_accounting_date(self) -> None:
        movement = apply_row(MAPPING, ["2026-02-13", "Pago", "-1234.56"], 2)
        self.assertFalse(hasattr(movement, "accounting_date"))
        self.assertNotIn("accounting_date", movement.as_dict())

    def test_the_movement_shape_declares_only_the_dates_the_file_carries(self) -> None:
        # `occurred_on` viene del fichero. `posted_on` y `value_date` los trae el
        # extracto cuando los trae. El periodo contable no lo trae nunca.
        fields = set(inspect.get_annotations(Movement))
        self.assertIn("occurred_on", fields)
        self.assertNotIn("accounting_date", fields)


class NotInferredTests(unittest.TestCase):
    def test_the_mapping_module_never_assigns_an_accounting_date(self) -> None:
        # Se lee el fuente a proposito: una asignacion nueva en cualquier rama
        # pasaria desapercibida a una prueba que solo mirara el resultado de un
        # caso feliz.
        source = inspect.getsource(mapping)
        self.assertNotIn("accounting_date", source)

    def test_the_lineage_plan_has_no_stage_for_the_accounting_period(self) -> None:
        # Si el plan lo cubriera, el linaje afirmaria que alguien lo derivo de
        # algo, y no hay nada de lo que derivarlo todavia.
        self.assertNotIn("accounting_date", FIELD_TYPES)
        steps = build_plan(MAPPING, engine_release_key="fnc-p3-mapping-0.1.0")
        self.assertNotIn("accounting_date",
                         {step.canonical_field for step in steps})

    def test_the_occurrence_date_is_not_silently_reused(self) -> None:
        # La forma concreta que tendria el atajo: copiar la ocurrencia. Si algun
        # dia alguien la escribe, esta prueba lo dice antes de que llegue a un
        # cierre.
        movement = apply_row(MAPPING, ["2026-02-13", "Pago", "-1234.56"], 2)
        rendered = movement.as_dict()
        self.assertEqual(rendered["occurred_on"], "2026-02-13")
        self.assertEqual(
            [key for key in rendered if key.endswith("_date")], [],
            "the mapping emits no date beyond the one the file carries")


if __name__ == "__main__":
    unittest.main()
