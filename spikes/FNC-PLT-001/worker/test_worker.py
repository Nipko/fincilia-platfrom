import copy
import tempfile
import unittest
from pathlib import Path

from worker import process_job


class WorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.state_dir = root / "state"
        self.output_dir = root / "output"
        self.job = {
            "job_id": "30000000-0000-4000-8000-000000000001",
            "idempotency_key": "synthetic-import-001",
            "data_classification": "synthetic",
            "rows": [
                {"reference": "SYN-001", "amount_minor": 125000},
                {"reference": "SYN-002", "amount_minor": -5000},
            ],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_retry_returns_the_same_manifest_and_output(self) -> None:
        first, first_replayed = process_job(self.job, self.state_dir, self.output_dir)
        second, second_replayed = process_job(self.job, self.state_dir, self.output_dir)

        self.assertFalse(first_replayed)
        self.assertTrue(second_replayed)
        self.assertEqual(first, second)
        self.assertEqual(1, len(list(self.output_dir.glob("*.json"))))

    def test_same_key_with_different_content_is_rejected(self) -> None:
        process_job(self.job, self.state_dir, self.output_dir)
        conflict = copy.deepcopy(self.job)
        conflict["rows"][0]["amount_minor"] = 999999

        with self.assertRaisesRegex(ValueError, "different content"):
            process_job(conflict, self.state_dir, self.output_dir)

    def test_non_synthetic_job_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.job)
        invalid["data_classification"] = "customer"

        with self.assertRaisesRegex(ValueError, "synthetic jobs only"):
            process_job(invalid, self.state_dir, self.output_dir)


if __name__ == "__main__":
    unittest.main()
