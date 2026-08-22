from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from parser import ENGINE_RELEASE, process_job


ARTIFACT_DIGEST = "a" * 64


def synthetic_job() -> dict:
    return {
        "artifact_sha256": ARTIFACT_DIGEST,
        "data_classification": "synthetic",
        "idempotency_key": "synthetic-import-one",
        "requested_effect": "draft",
        "rows": [
            {"date": "2026-08-01", "amount": "125000.00", "reference": "SYN-001"},
            {"date": "2026-08-02", "amount": "-5000.00", "reference": "SYN-002"},
        ],
    }


class ParserBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.state = root / "state"
        self.output = root / "output"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_creates_draft_with_engine_release_and_field_lineage(self) -> None:
        manifest, replayed = process_job(synthetic_job(), self.state, self.output)
        self.assertFalse(replayed)
        self.assertEqual(manifest["engine_release"], ENGINE_RELEASE)
        self.assertEqual(manifest["publication_authority"], "none")
        draft = json.loads((self.output / manifest["output_file"]).read_text(encoding="utf-8"))
        self.assertEqual(draft["effect"], "draft")
        self.assertEqual(draft["row_count"], 2)
        self.assertEqual(draft["rows"][0]["cells"][0]["origin_locator"]["row"], 1)
        self.assertEqual(
            draft["rows"][0]["cells"][0]["origin_locator"]["artifact_sha256"],
            ARTIFACT_DIGEST,
        )

    def test_replays_identical_job_without_new_effect(self) -> None:
        first, first_replayed = process_job(synthetic_job(), self.state, self.output)
        second, second_replayed = process_job(synthetic_job(), self.state, self.output)
        self.assertFalse(first_replayed)
        self.assertTrue(second_replayed)
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.output.glob("*.draft.json"))), 1)

    def test_rejects_key_reuse_with_different_content(self) -> None:
        process_job(synthetic_job(), self.state, self.output)
        changed = synthetic_job()
        changed["rows"][0]["amount"] = "999999.00"
        with self.assertRaisesRegex(ValueError, "different content"):
            process_job(changed, self.state, self.output)

    def test_rejects_non_synthetic_input(self) -> None:
        job = synthetic_job()
        job["data_classification"] = "financial"
        with self.assertRaisesRegex(ValueError, "synthetic data only"):
            process_job(job, self.state, self.output)

    def test_rejects_any_publication_effect(self) -> None:
        job = synthetic_job()
        job["requested_effect"] = "publish"
        with self.assertRaisesRegex(ValueError, "only create drafts"):
            process_job(job, self.state, self.output)

    def test_detects_output_tampering_before_replay(self) -> None:
        manifest, _ = process_job(synthetic_job(), self.state, self.output)
        (self.output / manifest["output_file"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            process_job(synthetic_job(), self.state, self.output)


if __name__ == "__main__":
    unittest.main()
