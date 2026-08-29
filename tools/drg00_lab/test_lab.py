from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.data_disposal import DisposalPolicy

from .lab import AccessGrant, LabController, LabError, LabManifest, LabPolicy, opaque
from .runtime import IMAGE, validate_compose


NOW = "2026-08-29T12:00:00Z"
CSV = b"fecha,detalle,valor\n2026-01-01,Movimiento sintetico,1250.00\n"


class LabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "lab"
        self.company = opaque("synthetic-company")
        self.manifest = LabManifest(
            run_ref=opaque("synthetic-run"), company_ref=self.company,
            purpose="corpus_research", data_classification="synthetic_only",
            approved_by="SYNTHETIC-TEST-FIXTURE",
            expires_at="2026-08-30T12:00:00Z",
            identity_mode="synthetic_test_identity",
        )
        self.grant = AccessGrant(
            subject_ref=opaque("synthetic-subject"), company_ref=self.company,
            authorization_version=1, observed_version=1, active=True,
        )
        self.policy = DisposalPolicy(
            policy_id="SYNTHETIC-TEST-POLICY", effective=True,
            retention_days=0, backup_days=7, delete_ledger_days=8,
            synthetic_test_only=True,
        )
        self.lab = LabController(self.root, self.manifest, self.policy)
        self.lab.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_safe_flow_is_inventory_backed_and_destroyed(self) -> None:
        artifact = self.lab.intake(CSV, "movimientos.csv", self.grant, NOW)
        decision = self.lab.inspect(artifact, "movimientos.csv", self.grant, NOW)
        self.assertEqual("accepted", decision["outcome"])
        derived = self.lab.derive_digest_receipt(artifact, self.grant, NOW)
        self.assertEqual(64, len(derived))
        self.assertEqual(2, len(self.lab.backup(artifact, self.grant, NOW)))
        self.assertEqual(CSV, self.lab.read_object(artifact, self.company, self.grant))
        receipt = self.lab.destroy(self.grant, NOW)
        self.assertEqual(0, receipt["active_object_count"])
        self.assertEqual([], self.lab.inventory.reconcile(self.root))

    def test_sensitive_and_unscannable_content_never_reaches_evidence(self) -> None:
        pan = "4111" + "1111" + "1111" + "1111"
        artifact = self.lab.intake(
            f"cliente,tarjeta\nSintetico,{pan}\n".encode(),
            "sensible.csv", self.grant, NOW,
        )
        decision = self.lab.inspect(artifact, "sensible.csv", self.grant, NOW)
        self.assertEqual("rejected", decision["outcome"])
        self.assertIn("payment_card_number", decision["finding_kinds"])
        self.assertNotIn(pan, repr(decision))
        self.assertFalse(any((self.root / "evidence").iterdir()))

    def test_cross_company_revoked_stale_and_shared_access_fail(self) -> None:
        artifact = self.lab.intake(CSV, "movimientos.csv", self.grant, NOW)
        self.lab.inspect(artifact, "movimientos.csv", self.grant, NOW)
        bad = [
            AccessGrant(opaque("x"), opaque("other"), 1, 1, True),
            AccessGrant(opaque("x"), self.company, 1, 1, False),
            AccessGrant(opaque("x"), self.company, 2, 1, True),
            AccessGrant(opaque("x"), self.company, 1, 1, True, shared=True),
        ]
        for grant in bad:
            with self.subTest(grant=grant):
                with self.assertRaises(LabError):
                    self.lab.read_object(artifact, grant.company_ref, grant)

    def test_real_manifest_unsigned_release_and_weak_breakglass_fail(self) -> None:
        with self.assertRaises(LabError):
            LabManifest(
                run_ref=opaque("real"), company_ref=self.company,
                purpose="corpus_research", data_classification="real",
                approved_by="FOUNDER-01", expires_at=NOW,
                identity_mode="local_password",
            ).validate()
        with self.assertRaises(LabError):
            LabPolicy.authorize_release(
                signed=False, provenance_verified=True, digest_pinned=True)
        with self.assertRaises(LabError):
            LabPolicy.authorize_break_glass(
                requester_ref="a" * 64, approver_ref="a" * 64,
                post_reviewer_ref="b" * 64)

    def test_audit_and_manifest_never_copy_payload_or_filename(self) -> None:
        self.lab.intake(CSV, "nombre-sensible.csv", self.grant, NOW)
        rendered = "".join(
            path.read_text(encoding="utf-8")
            for path in (self.root / "control").iterdir() if path.is_file()
        ) + (self.root / "archive" / "audit.ndjson").read_text(encoding="utf-8")
        self.assertNotIn("nombre-sensible.csv", rendered)
        self.assertNotIn("Movimiento sintetico", rendered)
        self.assertNotIn("1250.00", rendered)

    def test_compose_contract_has_two_networkless_services(self) -> None:
        path = Path(__file__).resolve().parents[2] / "infra/drg00-lab/compose.yaml"
        self.assertEqual([], validate_compose(path))

    def test_ci_stages_the_exact_probe_image_before_networkless_execution(self) -> None:
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        pull = f"docker pull\n          {IMAGE}"
        probe = "python -m tools.drg00_drill.cli"
        self.assertEqual(1, workflow.count(pull))
        self.assertLess(workflow.index(pull), workflow.index(probe))
        self.assertNotIn("docker pull\n          python:3.12\n", workflow)


if __name__ == "__main__":
    unittest.main()
