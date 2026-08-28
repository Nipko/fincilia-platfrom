"""Pruebas adversariales del diseño de laboratorio aislado."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from .cli import DEFAULT_SOURCES, MODEL, main
from .model import canonical_digest, report, validate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class IsolatedLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = _load(MODEL)
        self.sources = {identifier: _load(path) for identifier, path in DEFAULT_SOURCES.items()}

    def codes(self, model: dict | None = None, sources: dict | None = None) -> set[str]:
        return {
            finding.code for finding in validate(
                self.model if model is None else model,
                self.sources if sources is None else sources,
            )
        }

    def assertMutationDies(self, mutation, code: str) -> None:  # noqa: N802
        candidate = copy.deepcopy(self.model)
        mutation(candidate)
        self.assertIn(code, self.codes(candidate))

    def test_baseline_is_design_only_and_valid(self) -> None:
        payload = report(self.model, self.sources)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["design_ready_for_independent_review"])
        self.assertFalse(payload["implemented"])
        self.assertFalse(payload["deployment_enabled"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertFalse(payload["provider_selected"])
        self.assertFalse(payload["managed_idp_selected"])
        self.assertEqual(37, payload["control_count"])
        self.assertEqual(6, payload["trust_zone_count"])
        self.assertEqual(2, payload["drg00_threat_count"])
        self.assertEqual(12, payload["acceptance_test_count"])
        self.assertEqual(0, payload["passed_test_count"])
        self.assertIsNone(payload["aggregate_score"])

    def test_canonical_digest_is_order_independent(self) -> None:
        self.assertEqual(canonical_digest({"b": 2, "a": 1}), canonical_digest({"a": 1, "b": 2}))

    def test_design_cannot_claim_approval(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("status", "approved"), "LAB-STATUS")

    def test_design_cannot_enable_deployment(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("deployment_enabled", True), "LAB-REAL-DATA")

    def test_design_cannot_raise_data_ceiling(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("data_ceiling", "real_research"), "LAB-REAL-DATA")

    def test_design_cannot_authorize_real_data(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("real_data_authorized", True), "LAB-REAL-DATA")

    def test_source_digest_drift_is_detected(self) -> None:
        self.assertMutationDies(
            lambda value: value["source_contracts"][0].__setitem__("canonical_sha256", "0" * 64),
            "LAB-SOURCE-FRESHNESS",
        )

    def test_new_drg00_threat_is_discovered_dynamically(self) -> None:
        sources = copy.deepcopy(self.sources)
        extra = copy.deepcopy(sources["THREAT"]["risks"][0])
        extra.update({"id": "TM-DYNAMIC-TEST", "target_gate": "DRG-00"})
        sources["THREAT"]["risks"].append(extra)
        codes = self.codes(sources=sources)
        self.assertIn("LAB-SOURCE-FRESHNESS", codes)
        self.assertIn("LAB-THREAT-COVERAGE", codes)

    def test_provider_cannot_be_selected_before_a02(self) -> None:
        self.assertMutationDies(
            lambda value: value["unresolved_selection"].__setitem__("provider", "provider-x"),
            "LAB-PREMATURE-SELECTION",
        )

    def test_region_cannot_be_selected_before_a02(self) -> None:
        self.assertMutationDies(
            lambda value: value["unresolved_selection"].__setitem__("region", "region-x"),
            "LAB-PREMATURE-SELECTION",
        )

    def test_idp_cannot_be_selected_silently(self) -> None:
        self.assertMutationDies(
            lambda value: value["unresolved_selection"].__setitem__("managed_idp", "idp-x"),
            "LAB-PREMATURE-SELECTION",
        )

    def test_egress_allowlist_cannot_be_opened(self) -> None:
        self.assertMutationDies(
            lambda value: value["unresolved_selection"]["egress_allowlist"].append("0.0.0.0/0"),
            "LAB-PREMATURE-SELECTION",
        )

    def test_zone_cannot_have_public_ip(self) -> None:
        self.assertMutationDies(
            lambda value: value["trust_zones"][0].__setitem__("public_ip", True),
            "LAB-PUBLIC-NETWORK",
        )

    def test_quarantine_cannot_have_egress(self) -> None:
        zone = next(index for index, item in enumerate(self.model["trust_zones"]) if item["id"] == "Z-Q")
        self.assertMutationDies(
            lambda value: value["trust_zones"][zone].__setitem__("egress", "https_only"),
            "LAB-EGRESS",
        )

    def test_processing_cannot_have_egress(self) -> None:
        zone = next(index for index, item in enumerate(self.model["trust_zones"]) if item["id"] == "Z-P")
        self.assertMutationDies(
            lambda value: value["trust_zones"][zone].__setitem__("egress", "provider_fallback"),
            "LAB-EGRESS",
        )

    def test_control_cannot_be_removed(self) -> None:
        self.assertMutationDies(
            lambda value: value["control_catalog"].pop(), "LAB-CONTROL-COVERAGE")

    def test_password_only_requirement_cannot_replace_mfa(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "IAM-03")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "password_only_allowed"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_shared_account_requirement_cannot_be_relaxed(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "IAM-02")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "shared_lab_admin_allowed"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_static_credentials_requirement_cannot_be_relaxed(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "IAM-06")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "static_access_key_allowed"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_jit_window_cannot_be_silently_extended(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "IAM-05")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "jit_privilege_maximum_24_hours"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_host_mount_requirement_cannot_be_relaxed(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "CMP-03")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "host_mount_allowed_for_debug"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_external_ai_requirement_cannot_be_relaxed(self) -> None:
        index = next(index for index, item in enumerate(self.model["control_catalog"]) if item["id"] == "DAT-07")
        self.assertMutationDies(
            lambda value: value["control_catalog"][index].__setitem__(
                "requirement", "external_ai_allowed"
            ),
            "LAB-CONTROL-SEMANTICS",
        )

    def test_control_cannot_claim_implementation(self) -> None:
        self.assertMutationDies(
            lambda value: value["control_catalog"][0].update(
                {"implemented": True, "evidence_state": "passed"}
            ),
            "LAB-PREMATURE-EVIDENCE",
        )

    def test_threat_mapping_cannot_use_unknown_control(self) -> None:
        self.assertMutationDies(
            lambda value: value["threat_coverage"][0]["control_ids"].append("MAGIC-01"),
            "LAB-THREAT-CONTROLS",
        )

    def test_threat_cannot_claim_evidence(self) -> None:
        self.assertMutationDies(
            lambda value: value["threat_coverage"][0].__setitem__("evidence_state", "passed"),
            "LAB-PREMATURE-THREAT-EVIDENCE",
        )

    def test_acceptance_test_cannot_claim_pass(self) -> None:
        self.assertMutationDies(
            lambda value: value["acceptance_tests"][0].__setitem__("state", "passed"),
            "LAB-PREMATURE-TEST",
        )

    def test_prerequisite_cannot_be_self_satisfied(self) -> None:
        self.assertMutationDies(
            lambda value: value["prerequisites"][0].__setitem__("satisfied", True),
            "LAB-PREMATURE-PREREQ",
        )

    def test_human_review_cannot_be_self_asserted(self) -> None:
        self.assertMutationDies(
            lambda value: value["human_review"].update(
                {"state": "approved", "security_reviewer_id": "FOUNDER-01"}
            ),
            "LAB-PREMATURE-REVIEW",
        )

    def test_s01_cannot_be_met_by_design(self) -> None:
        self.assertMutationDies(
            lambda value: value["gate_claims"][0].update(
                {"status": "met", "authorized": True}
            ),
            "LAB-PREMATURE-GATE",
        )

    def test_region_source_selection_invalidates_closed_posture(self) -> None:
        sources = copy.deepcopy(self.sources)
        sources["REGION"]["candidate_locations"][0]["selected"] = True
        self.assertIn("LAB-A02-SOURCE", self.codes(sources=sources))

    def test_privacy_source_opening_drg00_is_rejected(self) -> None:
        sources = copy.deepcopy(self.sources)
        gate = next(item for item in sources["PRIVACY"]["gates"] if item["id"] == "DRG-00")
        gate["status"] = "met"
        self.assertIn("LAB-PRIVACY-SOURCE", self.codes(sources=sources))

    def test_retention_source_cannot_claim_adjudication_here(self) -> None:
        sources = copy.deepcopy(self.sources)
        sources["RETENTION"]["status"] = "adjudicated"
        self.assertIn("LAB-RETENTION-SOURCE", self.codes(sources=sources))

    def test_cli_validate_passes_design_only(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["validate"])
        payload = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertTrue(payload["design_ready_for_independent_review"])
        self.assertFalse(payload["implemented"])
        self.assertFalse(payload["real_data_authorized"])

    def test_cli_invalid_json_is_operational_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text("{", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["report", "--model", str(invalid)])
        self.assertEqual(2, code)
        self.assertFalse(json.loads(output.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
