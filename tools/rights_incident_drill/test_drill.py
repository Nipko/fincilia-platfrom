from __future__ import annotations

import copy
import unittest

from .drill import load_evidence, run_drill, validate_evidence


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


if __name__ == "__main__":
    unittest.main()
