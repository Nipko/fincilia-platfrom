from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from .model import report, validate, validate_repository


ROOT = Path(__file__).resolve().parents[2]
MODEL = json.loads((ROOT / "docs/legal/subprocessor-register.json").read_text(encoding="utf-8"))
PUBLIC = (ROOT / MODEL["public_disclosure_path"]).read_text(encoding="utf-8")


class SubprocessorRegisterTests(unittest.TestCase):
    def codes(self, model=MODEL, public=PUBLIC) -> set[str]:
        return {item.code for item in validate(model, public)}

    def mutated(self, callback) -> dict:
        candidate = copy.deepcopy(MODEL)
        callback(candidate)
        return candidate

    def test_repository_register_is_valid_but_not_approved(self) -> None:
        self.assertEqual([], validate_repository(ROOT))
        payload = report(MODEL, PUBLIC)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider_count"], 5)
        self.assertFalse(payload["human_approval"])
        self.assertFalse(payload["real_data_authorized"])

    def test_real_data_and_external_ai_mutations_die(self) -> None:
        self.assertIn("SPR-REAL-DATA", self.codes(self.mutated(
            lambda value: value.__setitem__("real_data_authorized", True))))
        self.assertIn("SPR-EXTERNAL-AI", self.codes(self.mutated(
            lambda value: value["scope"].__setitem__("external_ai_enabled", True))))

    def test_provider_removal_or_duplicate_dies(self) -> None:
        self.assertIn("SPR-PROVIDER-SET", self.codes(self.mutated(
            lambda value: value["providers"].pop())))
        self.assertIn("SPR-PROVIDER-SET", self.codes(self.mutated(
            lambda value: value["providers"].append(copy.deepcopy(value["providers"][0])))))

    def test_any_provider_claiming_real_financial_data_dies(self) -> None:
        self.assertIn("SPR-PROVIDER-REAL-DATA", self.codes(self.mutated(
            lambda value: value["providers"][0].__setitem__(
                "currently_receives_real_financial_data", True))))

    def test_aws_region_cannot_be_overstated_or_gate_removed(self) -> None:
        self.assertIn("SPR-AWS-REGION", self.codes(self.mutated(
            lambda value: value["providers"][0].__setitem__(
                "service_region_meaning", "all_processing_and_support"))))
        self.assertIn("SPR-AWS-DATA-GATE", self.codes(self.mutated(
            lambda value: value["providers"][0].__setitem__(
                "financial_document_path", "enabled"))))

    def test_google_scope_identifier_and_boundaries_bite(self) -> None:
        self.assertIn("SPR-GOOGLE-SCOPES", self.codes(self.mutated(
            lambda value: value["providers"][1]["oidc_scopes"].append("drive.readonly"))))
        self.assertIn("SPR-GOOGLE-SUB", self.codes(self.mutated(
            lambda value: value["providers"][1].__setitem__("durable_identity_key", "email"))))
        self.assertIn("SPR-GOOGLE-BOUNDARY", self.codes(self.mutated(
            lambda value: value["providers"][1]["prohibited_data"].remove("Gmail"))))

    def test_cloudflare_proxy_namecheap_ingestion_and_github_runtime_bite(self) -> None:
        self.assertIn("SPR-CLOUDFLARE-BOUNDARY", self.codes(self.mutated(
            lambda value: value["providers"][2].__setitem__("application_proxy_enabled", True))))
        self.assertIn("SPR-NAMECHEAP-BOUNDARY", self.codes(self.mutated(
            lambda value: value["providers"][3].__setitem__("email_ingestion_to_product_enabled", True))))
        self.assertIn("SPR-GITHUB-BOUNDARY", self.codes(self.mutated(
            lambda value: value["providers"][4].__setitem__("runtime_data_path", True))))

    def test_unknown_source_and_credentialed_url_die(self) -> None:
        self.assertIn("SPR-SOURCE-REFERENCE", self.codes(self.mutated(
            lambda value: value["providers"][0].__setitem__("source_ids", ["UNKNOWN"]))))
        self.assertIn("SPR-SOURCE-OFFICIAL", self.codes(self.mutated(
            lambda value: value["sources"][0].__setitem__(
                "url", "https://user:secret@docs.aws.amazon.com/fake"))))

    def test_legal_review_or_gate_cannot_be_invented(self) -> None:
        self.assertIn("SPR-LEGAL-PENDING", self.codes(self.mutated(
            lambda value: value["legal_review"].__setitem__("dpa_sufficiency", "approved"))))
        self.assertIn("SPR-LEGAL-IDENTITY", self.codes(self.mutated(
            lambda value: value["legal_review"].__setitem__("reviewer_id", "invented"))))
        self.assertIn("SPR-GATE-PREMATURE", self.codes(self.mutated(
            lambda value: value["gate_claims"][0].update(status="met", authorized=True))))

    def test_public_disclosure_drift_dies(self) -> None:
        self.assertIn("SPR-PUBLIC-DISCLOSURE", self.codes(public=PUBLIC.replace(
            "Amazon Web Services", "Redacted Provider")))


if __name__ == "__main__":
    unittest.main()
