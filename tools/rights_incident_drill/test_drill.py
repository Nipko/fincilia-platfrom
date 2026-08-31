from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from .drill import _source_digest, load_evidence, run_drill, validate_evidence


class RightsIncidentDrillTests(unittest.TestCase):
    def test_repository_evidence_is_exact(self) -> None:
        self.assertEqual([], validate_evidence(load_evidence()))

    def test_every_step_passes_without_authorizing_real_data(self) -> None:
        evidence = run_drill()
        self.assertEqual(12, evidence["test_count"])
        self.assertEqual(12, evidence["passed_count"])
        self.assertFalse(evidence["real_data_authorized"])
        self.assertEqual("pending_legal", evidence["notification_decision"])

    def test_a_missing_step_bites(self) -> None:
        evidence = copy.deepcopy(load_evidence())
        evidence["tests"].pop()
        self.assertTrue(validate_evidence(evidence))

    def test_a_fake_legal_decision_bites(self) -> None:
        evidence = copy.deepcopy(load_evidence())
        evidence["notification_decision"] = "not_required"
        self.assertTrue(validate_evidence(evidence))

    def test_real_data_claim_bites(self) -> None:
        evidence = copy.deepcopy(load_evidence())
        evidence["real_data_authorized"] = True
        self.assertTrue(validate_evidence(evidence))

    def test_source_digest_is_platform_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.json"
            source.write_bytes(b'{\r\n  "ok": true\r\n}\r\n')
            windows_digest = _source_digest(source)
            source.write_bytes(b'{\n  "ok": true\n}\n')
            self.assertEqual(windows_digest, _source_digest(source))


if __name__ == "__main__":
    unittest.main()
