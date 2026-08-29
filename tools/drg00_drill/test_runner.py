from __future__ import annotations

import unittest

from .runner import TEST_IDS, run_drill


def fake_probe(service: str) -> dict[str, object]:
    return {
        "service": service, "dns_external": False, "tcp_external": False,
        "root_write": False, "tmp_write": True, "uid": 65532,
    }


class DrillTests(unittest.TestCase):
    def test_all_twelve_controls_pass_with_synthetic_fixtures(self) -> None:
        report = run_drill(probe=fake_probe)
        self.assertEqual(12, report["passed_count"])
        self.assertEqual(TEST_IDS, tuple(item["id"] for item in report["tests"]))
        self.assertFalse(report["real_data_authorized"])

    def test_evidence_contains_no_fixture_values(self) -> None:
        rendered = str(run_drill(probe=fake_probe))
        for forbidden in (
            "Movimiento sintetico", "1250.00", "4111111111111111",
            "nombre-sensible.csv",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_a_probe_that_has_egress_fails_closed(self) -> None:
        def bad_probe(service: str) -> dict[str, object]:
            if service == "quarantine":
                raise RuntimeError("isolation invariant failed")
            return fake_probe(service)

        with self.assertRaises(RuntimeError):
            run_drill(probe=bad_probe)


if __name__ == "__main__":
    unittest.main()
