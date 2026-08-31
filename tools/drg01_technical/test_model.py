from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from .model import _digest, build_evidence, load_evidence, validate_evidence


class Drg01TechnicalEvidenceTests(unittest.TestCase):
    def test_repository_evidence_is_exact(self) -> None:
        self.assertEqual([], validate_evidence(load_evidence()))

    def test_generated_evidence_has_three_bounded_controls(self) -> None:
        payload = build_evidence()
        self.assertEqual(
            {"D01-XTENANT", "D01-INGRESS", "D01-CHANNELS"},
            set(payload["technical_controls"]),
        )
        self.assertFalse(payload["real_data_authorized"])
        self.assertEqual(90, payload["executed_suite"]["tests_run"])

    def test_a_changed_result_bites(self) -> None:
        payload = copy.deepcopy(load_evidence())
        payload["executed_suite"]["failures"] = 1
        self.assertTrue(validate_evidence(payload))

    def test_a_missing_control_bites(self) -> None:
        payload = copy.deepcopy(load_evidence())
        del payload["technical_controls"]["D01-INGRESS"]
        self.assertTrue(validate_evidence(payload))

    def test_real_data_claim_bites(self) -> None:
        payload = copy.deepcopy(load_evidence())
        payload["real_data_authorized"] = True
        self.assertTrue(validate_evidence(payload))

    def test_source_digest_is_platform_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.py"
            source.write_bytes(b"first\r\nsecond\r\n")
            windows_digest = _digest(source)
            source.write_bytes(b"first\nsecond\n")
            self.assertEqual(windows_digest, _digest(source))


if __name__ == "__main__":
    unittest.main()
