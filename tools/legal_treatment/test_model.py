"""Pruebas adversariales del paquete jurídico previo a datos reales."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from .cli import MODEL, PRIVACY, main
from .model import report, validate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class LegalTreatmentModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = _load(MODEL)
        self.privacy = _load(PRIVACY)

    def assertMutationDies(self, mutation, expected_code: str) -> None:  # noqa: N802
        candidate = copy.deepcopy(self.model)
        mutation(candidate)
        codes = {finding.code for finding in validate(candidate, self.privacy)}
        self.assertIn(expected_code, codes)

    def test_baseline_is_valid_without_authorizing_real_data(self) -> None:
        payload = report(self.model, self.privacy)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["ready_for_lawyer_review"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertFalse(payload["human_approval"])
        self.assertIsNone(payload["aggregate_score"])

    def test_dynamic_activity_counts_are_exact(self) -> None:
        payload = report(self.model, self.privacy)
        self.assertEqual(11, payload["covered_activities"])
        self.assertEqual({"DRG-00": 5, "DRG-01": 6}, payload["activities_by_gate"])
        self.assertEqual(16, payload["pending_sections"])

    def test_status_cannot_be_completed_by_an_agent(self) -> None:
        self.assertMutationDies(lambda value: value.__setitem__("status", "approved"), "LEG-STATUS")

    def test_real_data_flag_cannot_be_enabled(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("real_data_authorized", True), "LEG-REAL-DATA")

    def test_data_ceiling_cannot_be_raised(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("data_ceiling", "real_research"), "LEG-REAL-DATA")

    def test_template_cannot_claim_legal_advice(self) -> None:
        self.assertMutationDies(lambda value: value.__setitem__("legal_advice", True), "LEG-ADVICE")

    def test_official_source_rejects_impersonating_hostname(self) -> None:
        self.assertMutationDies(
            lambda value: value["official_sources"][0].__setitem__(
                "url", "https://evilsic.gov.co/copied"
            ),
            "LEG-SOURCE-URL",
        )

    def test_official_source_rejects_credentials_in_url(self) -> None:
        self.assertMutationDies(
            lambda value: value["official_sources"][0].__setitem__(
                "url", "https://user:pass@www.sic.gov.co/content"
            ),
            "LEG-SOURCE-URL",
        )

    def test_official_source_rejects_embedded_copy(self) -> None:
        self.assertMutationDies(
            lambda value: value["official_sources"][0].__setitem__("full_text", "copied"),
            "LEG-SOURCE-SCHEMA",
        )

    def test_required_section_cannot_be_removed(self) -> None:
        self.assertMutationDies(
            lambda value: value["required_sections"].pop(), "LEG-SECTION-COVERAGE")

    def test_required_section_cannot_be_preapproved(self) -> None:
        self.assertMutationDies(
            lambda value: value["required_sections"][0].__setitem__("state", "approved"),
            "LEG-SECTION-STATE",
        )

    def test_activity_cannot_be_omitted(self) -> None:
        self.assertMutationDies(
            lambda value: value["activity_coverage"].pop(), "LEG-ACTIVITY-COVERAGE")

    def test_activity_gate_must_follow_privacy_map(self) -> None:
        self.assertMutationDies(
            lambda value: value["activity_coverage"][0].__setitem__("target_gate", "DRG-00"),
            "LEG-ACTIVITY-GATE",
        )

    def test_activity_role_cannot_be_adjudicated(self) -> None:
        self.assertMutationDies(
            lambda value: value["activity_coverage"][0].__setitem__(
                "fincilia_role", "processor"
            ),
            "LEG-ROLE",
        )

    def test_new_privacy_activity_is_discovered_dynamically(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        source = copy.deepcopy(privacy["processing_activities"][0])
        source["id"] = "PA-DYNAMIC-TEST"
        source["target_gate"] = "DRG-00"
        privacy["processing_activities"].append(source)
        codes = {finding.code for finding in validate(self.model, privacy)}
        self.assertIn("LEG-ACTIVITY-COVERAGE", codes)

    def test_blocking_decision_cannot_be_removed(self) -> None:
        self.assertMutationDies(
            lambda value: value["blocking_decisions"].pop(), "LEG-DECISION-COVERAGE")

    def test_blocking_decision_cannot_be_selected(self) -> None:
        self.assertMutationDies(
            lambda value: value["blocking_decisions"][0].update(
                {"state": "accepted", "selected_value": "provider-x"}
            ),
            "LEG-DECISION-PREMATURE",
        )

    def test_legal_role_cannot_be_filled_by_agent(self) -> None:
        self.assertMutationDies(
            lambda value: value["legal_decisions"].__setitem__("fincilia_role", "processor"),
            "LEG-CONCLUSION-PREMATURE",
        )

    def test_region_cannot_be_filled_by_agent(self) -> None:
        self.assertMutationDies(
            lambda value: value["legal_decisions"].__setitem__("region", "sa-east-1"),
            "LEG-CONCLUSION-PREMATURE",
        )

    def test_provider_cannot_be_filled_by_agent(self) -> None:
        self.assertMutationDies(
            lambda value: value["legal_decisions"].__setitem__("provider", "provider-x"),
            "LEG-CONCLUSION-PREMATURE",
        )

    def test_retention_cannot_be_filled_by_agent(self) -> None:
        self.assertMutationDies(
            lambda value: value["legal_decisions"]["retention_durations"].__setitem__(
                "financial", "10 years"
            ),
            "LEG-CONCLUSION-PREMATURE",
        )

    def test_lawyer_identity_cannot_be_self_asserted(self) -> None:
        self.assertMutationDies(
            lambda value: value["human_review"].update(
                {"state": "approved", "reviewer_id": "FOUNDER-01"}
            ),
            "LEG-HUMAN-REVIEW",
        )

    def test_signoff_cannot_be_preapproved(self) -> None:
        self.assertMutationDies(
            lambda value: value["required_signoffs"][0].update(
                {"state": "approved", "reviewer_id": "FOUNDER-01"}
            ),
            "LEG-SIGNOFF-PREMATURE",
        )

    def test_gate_cannot_be_authorized(self) -> None:
        self.assertMutationDies(
            lambda value: value["gate_claims"][2].update(
                {"status": "met", "authorized": True}
            ),
            "LEG-GATE-PREMATURE",
        )

    def test_cli_reports_operational_error_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text("{", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["validate", "--model", str(invalid)])
        self.assertEqual(2, code)
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_cli_validate_passes_review_packet_only(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["validate"])
        payload = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertTrue(payload["ready_for_lawyer_review"])
        self.assertFalse(payload["real_data_authorized"])


if __name__ == "__main__":
    unittest.main()
