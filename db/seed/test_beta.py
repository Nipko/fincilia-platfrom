from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from db.seed import beta


class BetaSeedTests(unittest.TestCase):
    def test_release_id_is_stable_and_has_no_personal_input(self) -> None:
        first = beta.release_id()
        self.assertEqual(first, beta.release_id())
        self.assertEqual(36, len(first))

    def test_main_refuses_any_non_false_real_data_flag(self) -> None:
        with patch.dict(os.environ, {
            "FINCILIA_REAL_DATA_ENABLED": "true",
            "FINCILIA_MIGRATOR_URL": "postgresql://not-used",
        }, clear=True):
            self.assertEqual(2, beta.main([]))

    def test_main_requires_explicit_dsn(self) -> None:
        with patch.dict(os.environ, {
            "FINCILIA_REAL_DATA_ENABLED": "false",
        }, clear=True):
            self.assertEqual(2, beta.main([]))


if __name__ == "__main__":
    unittest.main()
