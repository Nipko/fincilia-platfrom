"""Pruebas adversariales para la matriz L-01."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from .cli import MODEL, PRIVACY, main
from .model import canonical_digest, report, validate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RetentionMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = _load(MODEL)
        self.privacy = _load(PRIVACY)

    def codes(self, model: dict | None = None, privacy: dict | None = None) -> set[str]:
        return {
            finding.code for finding in validate(
                self.model if model is None else model,
                self.privacy if privacy is None else privacy,
            )
        }

    def assertMutationDies(self, mutation, code: str) -> None:  # noqa: N802
        candidate = copy.deepcopy(self.model)
        mutation(candidate)
        self.assertIn(code, self.codes(candidate))

    def adjudicated(self) -> dict:
        candidate = copy.deepcopy(self.model)
        candidate["status"] = "adjudicated"
        for item in candidate["policy_decisions"]:
            identifier = item["policy_id"].replace("-", "_")
            item.update({
                "decision_state": "accepted_human",
                "retention_days": 365,
                "legal_basis_ref": f"EVID-BASIS-{identifier}",
                "contract_ref": f"EVID-CONTRACT-{identifier}",
                "exceptions_ref": f"EVID-EXCEPTION-{identifier}",
                "effective_at": "2026-10-01",
                "review_evidence_ref": f"EVID-REVIEW-{identifier}",
            })
        by_id = {item["policy_id"]: item for item in candidate["policy_decisions"]}
        by_id["L-01-BACKUP"]["retention_days"] = 30
        by_id["L-01-DELETE-LEDGER"]["retention_days"] = 31
        candidate["human_review"] = {
            "state": "approved_human",
            "legal_reviewer_id": "REVIEWER-LEGAL-TEST",
            "competence_ref": "EVID-COMPETENCE-LEGAL-TEST",
            "decision_ref": "EVID-DECISION-L01-TEST",
            "approved_at": "2026-09-30",
        }
        reviewers = {
            "Legal": "REVIEWER-LEGAL-TEST",
            "Privacy": "REVIEWER-PRIVACY-TEST",
            "Security": "REVIEWER-SECURITY-TEST",
            "Accounting": "REVIEWER-ACCOUNTING-TEST",
        }
        for item in candidate["required_signoffs"]:
            item.update({
                "state": "approved_human",
                "reviewer_id": reviewers[item["role"]],
                "evidence_ref": f"EVID-SIGNOFF-{item['role'].upper()}-TEST",
            })
        for item in candidate["gate_claims"]:
            if item["id"] == "L-01":
                item.update({"status": "met", "authorized": True})
        return candidate

    def test_pending_baseline_is_valid_but_authorizes_nothing(self) -> None:
        payload = report(self.model, self.privacy)
        self.assertTrue(payload["ok"])
        self.assertEqual("review_pending", payload["decision_state"])
        self.assertEqual(19, payload["policy_count"])
        self.assertEqual(19, payload["pending_policy_count"])
        self.assertEqual(0, payload["accepted_policy_count"])
        self.assertFalse(payload["human_adjudication"])
        self.assertFalse(payload["l01_met"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertFalse(payload["drg00_met"])
        self.assertIsNone(payload["aggregate_score"])

    def test_canonical_digest_is_key_order_independent(self) -> None:
        value = {"b": 2, "a": {"d": 4, "c": 3}}
        reordered = {"a": {"c": 3, "d": 4}, "b": 2}
        self.assertEqual(canonical_digest(value), canonical_digest(reordered))

    def test_fully_adjudicated_synthetic_fixture_is_structurally_valid(self) -> None:
        candidate = self.adjudicated()
        payload = report(candidate, self.privacy)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["human_adjudication"])
        self.assertTrue(payload["l01_met"])
        self.assertEqual(19, payload["accepted_policy_count"])
        self.assertEqual(30, payload["backup_days"])
        self.assertEqual(31, payload["delete_ledger_days"])
        self.assertFalse(payload["real_data_authorized"])
        self.assertFalse(payload["drg01_met"])

    def test_real_data_can_never_be_authorized(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("real_data_authorized", True), "RET-REAL-DATA")

    def test_data_ceiling_can_never_be_raised(self) -> None:
        self.assertMutationDies(
            lambda value: value.__setitem__("data_ceiling", "real_research"), "RET-REAL-DATA")

    def test_source_digest_drift_is_detected(self) -> None:
        self.assertMutationDies(
            lambda value: value["source_contract"].__setitem__("canonical_sha256", "0" * 64),
            "RET-SOURCE-FRESHNESS",
        )

    def test_new_source_policy_is_discovered_dynamically(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        extra = copy.deepcopy(privacy["retention_policies"][0])
        extra["id"] = "L-01-DYNAMIC-TEST"
        privacy["retention_policies"].append(extra)
        codes = self.codes(privacy=privacy)
        self.assertIn("RET-COVERAGE", codes)
        self.assertIn("RET-SOURCE-FRESHNESS", codes)

    def test_source_policy_duplicate_is_rejected(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        privacy["retention_policies"].append(copy.deepcopy(privacy["retention_policies"][0]))
        self.assertIn("RET-SOURCE-IDENTITY", self.codes(privacy=privacy))

    def test_matrix_policy_cannot_be_omitted(self) -> None:
        self.assertMutationDies(lambda value: value["policy_decisions"].pop(), "RET-COVERAGE")

    def test_pending_row_cannot_contain_a_duration(self) -> None:
        self.assertMutationDies(
            lambda value: value["policy_decisions"][0].__setitem__("retention_days", 30),
            "RET-PREMATURE-DECISION",
        )

    def test_pending_row_cannot_be_preaccepted(self) -> None:
        self.assertMutationDies(
            lambda value: value["policy_decisions"][0].__setitem__(
                "decision_state", "accepted_human"
            ),
            "RET-PREMATURE-DECISION",
        )

    def test_adjudicated_matrix_rejects_a_pending_row(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["decision_state"] = "pending_human"
        self.assertIn("RET-ADJUDICATION-STATE", self.codes(candidate))

    def test_adjudicated_matrix_rejects_boolean_duration(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["retention_days"] = True
        self.assertIn("RET-DURATION", self.codes(candidate))

    def test_adjudicated_matrix_rejects_zero_duration(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["retention_days"] = 0
        self.assertIn("RET-DURATION", self.codes(candidate))

    def test_adjudicated_matrix_rejects_excessive_duration(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["retention_days"] = 36501
        self.assertIn("RET-DURATION", self.codes(candidate))

    def test_adjudicated_matrix_requires_evidence(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["legal_basis_ref"] = None
        self.assertIn("RET-EVIDENCE", self.codes(candidate))

    def test_adjudicated_matrix_rejects_email_as_evidence_ref(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["contract_ref"] = "person@example.com"
        self.assertIn("RET-EVIDENCE", self.codes(candidate))

    def test_adjudicated_matrix_requires_iso_effective_date(self) -> None:
        candidate = self.adjudicated()
        candidate["policy_decisions"][0]["effective_at"] = "tomorrow"
        self.assertIn("RET-EFFECTIVE-DATE", self.codes(candidate))

    def test_delete_ledger_must_outlive_backup(self) -> None:
        candidate = self.adjudicated()
        by_id = {item["policy_id"]: item for item in candidate["policy_decisions"]}
        by_id["L-01-DELETE-LEDGER"]["retention_days"] = 30
        self.assertIn("RET-LEDGER-WINDOW", self.codes(candidate))

    def test_founder_cannot_self_approve_as_lawyer(self) -> None:
        candidate = self.adjudicated()
        candidate["human_review"]["legal_reviewer_id"] = "FOUNDER-01"
        candidate["required_signoffs"][0]["reviewer_id"] = "FOUNDER-01"
        codes = self.codes(candidate)
        self.assertIn("RET-HUMAN-REVIEW", codes)
        self.assertIn("RET-SIGNOFF", codes)

    def test_legal_signoff_must_match_reviewing_lawyer(self) -> None:
        candidate = self.adjudicated()
        candidate["required_signoffs"][0]["reviewer_id"] = "REVIEWER-OTHER-LEGAL"
        self.assertIn("RET-LEGAL-IDENTITY", self.codes(candidate))

    def test_signoff_reviewers_must_be_distinct(self) -> None:
        candidate = self.adjudicated()
        candidate["required_signoffs"][2]["reviewer_id"] = "REVIEWER-PRIVACY-TEST"
        self.assertIn("RET-SOD", self.codes(candidate))

    def test_drg00_cannot_be_opened_by_l01_matrix(self) -> None:
        candidate = self.adjudicated()
        candidate["gate_claims"][1].update({"status": "met", "authorized": True})
        self.assertIn("RET-GATE-CLAIM", self.codes(candidate))

    def test_deletion_guard_cannot_be_relaxed(self) -> None:
        self.assertMutationDies(
            lambda value: value["deletion_guards"].__setitem__(
                "restore_requires_tombstone_reapplication_before_service_reopen", False
            ),
            "RET-GUARDS",
        )

    def test_financial_clock_source_cannot_revert_to_upload_date(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        policy = next(
            item for item in privacy["retention_policies"] if item["id"] == "L-01-FINANCIAL"
        )
        policy["computation_start"] = "artifact_uploaded_at"
        self.assertIn("RET-FINANCIAL-CLOCK", self.codes(privacy=privacy))

    def test_legal_hold_source_cannot_be_relaxed(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        privacy["retention_policies"][0]["legal_hold"] = "silent_hold"
        self.assertIn("RET-SOURCE-HOLD", self.codes(privacy=privacy))

    def test_restore_source_cannot_skip_tombstone_reapplication(self) -> None:
        privacy = copy.deepcopy(self.privacy)
        privacy["deletion_state_machine"][
            "restore_requires_tombstone_reapplication_before_service_reopen"
        ] = False
        self.assertIn("RET-DELETION-GUARDS", self.codes(privacy=privacy))

    def test_cli_validate_passes_pending_packet_only(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["validate"])
        payload = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertTrue(payload["model_valid"])
        self.assertFalse(payload["human_adjudication"])
        self.assertFalse(payload["real_data_authorized"])

    def test_cli_returns_operational_error_for_invalid_json(self) -> None:
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
