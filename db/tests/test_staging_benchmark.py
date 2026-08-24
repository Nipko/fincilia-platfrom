"""El spike de staging seguro, ejercido contra PostgreSQL real (FNC-P3.6).

La pregunta del mandato es si conviene cambiar el `INSERT` multifila por un
`COPY` a tabla temporal, y la respuesta solo vale si las ocho propiedades de
seguridad se **demuestran** en vez de razonarse. Aqui se demuestran con pocas
filas, que es lo que cabe en la corrida bloqueante; la medida a escala la toma la
misma funcion en el carril de rendimiento.

Que esto pase no adopta la ruta B. Adoptarla es una decision que se toma leyendo
los numeros, y mientras no se tome el worker sigue con el `INSERT` multifila.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_staging_benchmark -v
"""

from __future__ import annotations

import os
import unittest

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.spikes.staging_benchmark import REQUIRED_CHECKS, run

ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")

# Suficientes filas para que las dos rutas se distingan y pocas para que la
# corrida bloqueante no se convierta en una prueba de escala.
ROWS = int(os.environ.get("FINCILIA_STAGING_SPIKE_ROWS", "5000"))


class StagingBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.result = run(ROWS, app_dsn=RUNTIME_DSN, migrator_dsn=MIGRATOR_DSN,
                         company_id=ESPIGA, other_company_id=ANDINOS)

    @classmethod
    def tearDownClass(cls) -> None:
        # Se imprime pase lo que pase: un numero que solo aparece cuando la
        # prueba pasa no sirve para decidir nada.
        print(f"\n[staging] {cls.result}", flush=True)

    def test_both_paths_write_the_same_rows_TST_P36_035(self) -> None:
        """Si escribieran distinto no habria comparacion, habria dos cosas."""
        for label in ("insert_multirow_500", "copy_through_temp_500",
                      "copy_through_temp_5000"):
            with self.subTest(path=label):
                measured = self.result[label]
                self.assertEqual(ROWS, measured["stored"])
                # Cero duplicados en las dos rutas.
                self.assertEqual(measured["stored"], measured["distinct_ordinals"])

    def test_the_temporary_table_never_weakens_isolation_TST_P36_036(self) -> None:
        """Las ocho propiedades, una a una y sin agregarlas en un solo booleano."""
        for check in REQUIRED_CHECKS:
            with self.subTest(check=check):
                self.assertIs(True, self.result["security"].get(check),
                              f"{check} is not demonstrated")

    def test_a_company_context_of_another_firm_writes_nothing_TST_P36_037(self) -> None:
        """La frontera esta en la tabla destino, no en el staging.

        La temporal no lleva politica —no puede: es de la sesion— asi que la
        unica pregunta que importa es si `INSERT ... SELECT` desde ella respeta
        la politica del destino. La respuesta tiene que ser que si.
        """
        self.assertIs(True, self.result["security"]["cross_company_refused"])
        self.assertIn("cross_company_error", self.result["security"])

    def test_the_verdict_is_reported_and_not_assumed_TST_P36_038(self) -> None:
        """La medida existe y se puede leer; adoptar o no es de una persona."""
        self.assertIn("speedup_copy_through_temp_500", self.result)
        self.assertIn("speedup_copy_through_temp_5000", self.result)
        self.assertIsInstance(self.result["security_clean"], bool)
        for label in ("insert_multirow_500", "copy_through_temp_5000"):
            self.assertGreater(self.result[label]["rows_per_second"], 0)


if __name__ == "__main__":
    unittest.main()
