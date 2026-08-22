"""Pruebas del plan de migracion que no necesitan base de datos.

El aplicador tiene dos mitades: decidir **que** se va a aplicar y **como** se
aplica. La segunda solo se puede probar contra PostgreSQL real y vive en
`test_tenancy_isolation`. La primera es determinista y se prueba aqui, porque un
plan mal ordenado o un checksum que cambia con el checkout rompen antes de que
nadie llegue a mirar la base.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db.migrate.apply import (MIGRATIONS_DIR, MigrationError, discover,
                              sha256_text)


class PlanTests(unittest.TestCase):
    def scratch(self, names: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp())
        for name, body in names.items():
            (root / name).write_text(body, encoding="utf-8")
        return root

    def test_the_real_plan_is_discoverable(self) -> None:
        plan = discover()
        self.assertGreaterEqual(len(plan), 1)
        self.assertEqual("V0001", plan[0].version)
        for item in plan:
            self.assertRegex(item.checksum, r"^[0-9a-f]{64}$")

    def test_the_plan_orders_by_version_not_by_directory(self) -> None:
        # Diez migraciones ordenadas como texto ponen V0010 antes que V0002.
        root = self.scratch({f"V{index:04d}__step.sql": f"SELECT {index};"
                             for index in range(1, 11)})
        self.assertEqual([f"V{index:04d}" for index in range(1, 11)],
                         [item.version for item in discover(root)])

    def test_a_hole_in_the_sequence_bites(self) -> None:
        root = self.scratch({"V0001__a.sql": "SELECT 1;", "V0003__c.sql": "SELECT 3;"})
        with self.assertRaises(MigrationError):
            discover(root)

    def test_a_badly_named_file_bites(self) -> None:
        root = self.scratch({"V0001__a.sql": "SELECT 1;", "fix.sql": "SELECT 2;"})
        with self.assertRaises(MigrationError):
            discover(root)

    def test_an_uppercase_name_bites(self) -> None:
        root = self.scratch({"V0001__Identity.sql": "SELECT 1;"})
        with self.assertRaises(MigrationError):
            discover(root)

    def test_an_empty_directory_is_an_empty_plan(self) -> None:
        self.assertEqual([], discover(self.scratch({})))

    def test_the_checksum_survives_a_windows_checkout(self) -> None:
        # Mismo contenido, otro final de linea: si el checksum cambiara, un
        # checkout en Windows abortaria contra una base migrada en Linux.
        unix = self.scratch({"V0001__a.sql": "SELECT 1;\nSELECT 2;\n"})
        windows = self.scratch({"V0001__a.sql": "SELECT 1;\r\nSELECT 2;\r\n"})
        old_mac = self.scratch({"V0001__a.sql": "SELECT 1;\rSELECT 2;\r"})
        self.assertEqual(sha256_text(unix / "V0001__a.sql"),
                         sha256_text(windows / "V0001__a.sql"))
        self.assertEqual(sha256_text(unix / "V0001__a.sql"),
                         sha256_text(old_mac / "V0001__a.sql"))

    def test_the_checksum_still_changes_with_the_content(self) -> None:
        one = self.scratch({"V0001__a.sql": "SELECT 1;\n"})
        two = self.scratch({"V0001__a.sql": "SELECT 2;\n"})
        self.assertNotEqual(sha256_text(one / "V0001__a.sql"),
                            sha256_text(two / "V0001__a.sql"))

    def test_a_migration_is_hashed_by_content_not_by_name(self) -> None:
        root = self.scratch({"V0001__a.sql": "SELECT 1;\n", "V0002__b.sql": "SELECT 1;\n"})
        plan = discover(root)
        self.assertEqual(plan[0].checksum, plan[1].checksum)

    def test_the_shipped_migrations_live_where_the_contract_says(self) -> None:
        self.assertTrue(MIGRATIONS_DIR.is_dir())
        self.assertEqual("migrations", MIGRATIONS_DIR.name)


if __name__ == "__main__":
    unittest.main()
