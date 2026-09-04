from __future__ import annotations

import copy
import json
import unittest

from tools.aws_pilot_control.control import (
    FOUNDATION_REQUIRED_ADDRESSES,
    RUNTIME_REQUIRED_ADDRESSES,
)

from .model import (
    CONTROL_IDS,
    FOUNDER_ID,
    ROOT,
    SUPPLY_CHAIN_EVIDENCE,
    TARGET_DRILL_EVIDENCE,
    load_model,
    report,
    validate,
    validate_isolated_environment_evidence,
    validate_supply_chain_evidence,
)


class Drg01ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_model()

    def codes(self, candidate: dict) -> set[str]:
        return {item.code for item in validate(candidate)}

    def test_repository_model_is_valid_and_closed(self) -> None:
        payload = report(self.model)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertEqual(13, payload["blocker_count"])
        self.assertEqual(["DRG-00", "DRG-01"], [item["id"] for item in payload["gates"]])
        technical = {
            item["id"]: item["state"] for item in self.model["controls"]
            if item["id"].startswith("G00-") and item["kind"] == "automated"
        }
        self.assertEqual({
            "G00-ISOLATED-ENV": "pending", "G00-INVENTORY": "passed",
            "G00-DELETE": "passed", "G00-DRILL": "passed",
            "G00-SUPPLY-CHAIN": "passed",
        }, technical)

    def supply_evidence(self) -> dict:
        return json.loads((ROOT / SUPPLY_CHAIN_EVIDENCE).read_text(encoding="utf-8"))

    def test_supply_chain_evidence_is_bound_to_current_release_inputs(self) -> None:
        self.assertEqual([], validate_supply_chain_evidence(self.supply_evidence()))

    def test_supply_chain_evidence_mutations_bite(self) -> None:
        mutations = (
            ("DRG-SUPPLY-RUN", lambda item: item["run"].update({"signer_workflow": "other"})),
            ("DRG-SUPPLY-ATTESTATION", lambda item: item["attestations"][0].update(
                {"signature_verified_outside_runner": False})),
            ("DRG-SUPPLY-SOURCE", lambda item: item["source_inputs"][0].update(
                {"sha256": "0" * 64})),
            ("DRG-SUPPLY-REVIEW", lambda item: item["independent_review"].update(
                {"state": "accepted"})),
            ("DRG-SUPPLY-DIGEST", lambda item: item.update(
                {"evidence_sha256": "0" * 64})),
        )
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                candidate = self.supply_evidence()
                mutate(candidate)
                codes = {finding.code for finding in validate_supply_chain_evidence(candidate)}
                self.assertIn(expected, codes)

    def test_supply_chain_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"]
                       if item["id"] == "G00-SUPPLY-CHAIN")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG-SUPPLY-REF", self.codes(candidate))

    def test_scope_widening_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["pilot_scope"]["maximum_companies"] = 2
        self.assertIn("DRG-SCOPE", self.codes(candidate))

    def test_external_ai_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["pilot_scope"]["disabled_capabilities"].remove("external_ai")
        self.assertIn("DRG-SCOPE", self.codes(candidate))

    def test_missing_control_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["controls"].pop()
        self.assertIn("DRG-COVERAGE", self.codes(candidate))

    def test_wrong_control_kind_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["controls"][0]["kind"] = "automated"
        self.assertIn("DRG-CONTROL-KIND", self.codes(candidate))

    def test_founder_cannot_review_himself(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = candidate["controls"][0]
        control.update({"state": "accepted", "reviewer_id": FOUNDER_ID,
                        "reviewed_at": "2026-08-28",
                        "evidence_refs": ["docs/security/DRG01_READINESS.md"]})
        self.assertIn("DRG-SOD", self.codes(candidate))

    def test_fake_technical_pass_without_evidence_bites_derivation(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-IDENTITY")
        control["state"] = "passed"
        self.assertIn("DRG-EVIDENCE", self.codes(candidate))
        self.assertFalse(report(candidate)["real_data_authorized"])

    def test_unknown_evidence_bites(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-IDENTITY")
        control.update({"state": "passed", "evidence_refs": ["docs/missing-evidence.json"]})
        self.assertIn("DRG-EVIDENCE", self.codes(candidate))

    def test_adjudicated_drg01_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-XTENANT")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG01-TECH-REF", self.codes(candidate))

    def test_rights_incident_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"] if item["id"] == "D01-RIGHTS-IR")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG01-RIGHTS-IR-REF", self.codes(candidate))

    def test_drg00_technical_control_cannot_point_to_narrative(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"]
                       if item["id"] == "G00-DRILL")
        control["evidence_refs"] = ["docs/security/DRG01_READINESS.md"]
        self.assertIn("DRG-TECH-REF", self.codes(candidate))

    def test_local_drill_cannot_pass_isolated_environment(self) -> None:
        candidate = copy.deepcopy(self.model)
        control = next(item for item in candidate["controls"]
                       if item["id"] == "G00-ISOLATED-ENV")
        control.update({
            "state": "passed",
            "evidence_refs": ["docs/implementation/evidence/FNC-QA-001.json"],
        })
        codes = self.codes(candidate)
        self.assertIn("DRG-ISOLATED-REF", codes)
        self.assertIn("DRG-ISOLATED-EVIDENCE", codes)

    def isolated_evidence(self) -> dict:
        payload = {
            "schema_version": "1.0.0",
            "task_id": "FNC-GAT-007",
            "control_id": "G00-ISOLATED-ENV",
            "state": "passed",
            "observed_at": "2026-09-03T00:00:00Z",
            "environment": "private-pilot",
            "region": "sa-east-1",
            "account_id_sha256": "1" * 64,
            "source_revision": "2" * 40,
            "data_classification": "completely_synthetic",
            "real_data_authorized": False,
            "production_authorized": False,
            "foundation": {
                "state": "complete",
                "required_count": len(FOUNDATION_REQUIRED_ADDRESSES),
                "missing": [],
            },
            "runtime_plane": {
                "state": "complete",
                "required_count": len(RUNTIME_REQUIRED_ADDRESSES),
                "missing": [],
            },
            "release_admission": {
                "source_revision": "2" * 40,
                "subject_sha256": "3" * 64,
                "signature_verified": True,
                "provenance_verified": True,
                "sbom_verified": True,
                "images_by_digest_verified": True,
            },
            "managed_identity": {
                "provider": "Amazon Cognito federated with Google",
                "mfa_configuration": "ON",
                "deletion_protection": "ACTIVE",
                "native_signup_closed": True,
                "authorization_remains_server_side": True,
            },
            "target_drill": {
                "evidence_ref": TARGET_DRILL_EVIDENCE,
                "passed_count": 12,
                "failed_count": 0,
                "networkless_worker": True,
                "cross_tenant_denied": True,
                "restore_reconciled": True,
                "logs_redacted": True,
            },
            "independent_review": {
                "state": "pending",
                "required_roles": ["Security", "Platform/SRE", "QA"],
                "agent_observation_is_not_acceptance": True,
            },
        }
        import hashlib
        payload["evidence_sha256"] = hashlib.sha256(json.dumps(
            payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        return payload

    def test_isolated_target_evidence_contract_is_strict(self) -> None:
        evidence = self.isolated_evidence()
        self.assertEqual([], validate_isolated_environment_evidence(
            evidence, verify_references=False))
        mutations = (
            ("DRG-ISOLATED-INVENTORY", lambda item: item["foundation"]["missing"].append("x")),
            ("DRG-ISOLATED-RELEASE", lambda item: item["release_admission"].update(
                {"signature_verified": False})),
            ("DRG-ISOLATED-IDENTITY", lambda item: item["managed_identity"].update(
                {"native_signup_closed": False})),
            ("DRG-ISOLATED-DRILL", lambda item: item["target_drill"].update(
                {"passed_count": 11})),
        )
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                candidate = self.isolated_evidence()
                mutate(candidate)
                self.assertIn(expected, {
                    finding.code
                    for finding in validate_isolated_environment_evidence(
                        candidate, verify_references=False)
                })

    def test_isolated_inventory_uses_the_controller_catalog(self) -> None:
        evidence = self.isolated_evidence()
        self.assertEqual(
            len(FOUNDATION_REQUIRED_ADDRESSES),
            evidence["foundation"]["required_count"],
        )
        self.assertEqual(
            len(RUNTIME_REQUIRED_ADDRESSES),
            evidence["runtime_plane"]["required_count"],
        )

    def test_drg01_cannot_open_before_drg00(self) -> None:
        candidate = copy.deepcopy(self.model)
        for control in candidate["controls"]:
            if control["gate"] == "DRG-01" and control["kind"] == "automated":
                control.update({"state": "passed", "evidence_refs": ["docs/security/DRG01_READINESS.md"]})
            elif control["gate"] == "DRG-01" and control["kind"] == "human":
                control.update({"state": "accepted", "evidence_refs": ["docs/security/DRG01_READINESS.md"],
                                "reviewer_id": "INDEPENDENT-TEST", "reviewed_at": "2026-08-28"})
        self.assertFalse(report(candidate)["real_data_authorized"])

    def test_control_inventory_matches_gate_partition(self) -> None:
        expected = set().union(*CONTROL_IDS.values())
        self.assertEqual(expected, {item["id"] for item in self.model["controls"]})


if __name__ == "__main__":
    unittest.main()
