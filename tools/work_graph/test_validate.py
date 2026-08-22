from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from .model import parse_backlog, topological_order, validate_repository


ROOT = Path(__file__).resolve().parents[2]


class WorkGraphTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        report, findings = validate_repository(ROOT)
        self.assertEqual([], findings)
        self.assertGreaterEqual(report["task_count"], 40)
        self.assertEqual(sorted(set(report["next_candidates"])), report["next_candidates"])
        self.assertNotIn("FNC-GOV-001", report["next_candidates"])
        self.assertNotIn("FNC-GOV-003", report["next_candidates"])

    def test_duplicate_backlog_task_bites(self) -> None:
        text = "## E0\n| FNC-GOV-001 | A0 | — | Ready | x |\n| FNC-GOV-001 | A0 | — | Ready | x |"
        _, findings = parse_backlog(text)
        self.assertIn("META-DUPLICATE-TASK", {item.code for item in findings})

    def test_cycle_bites(self) -> None:
        _, cyclic = topological_order({"A": {"B"}, "B": {"A"}})
        self.assertEqual({"A", "B"}, cyclic)

    def test_route_collision_bites(self) -> None:
        config = json.loads((ROOT / "docs/implementation/work-graph.json").read_text(encoding="utf-8"))
        mutated = copy.deepcopy(config)
        mutated["active_reservations"][1]["paths"].append("tools/quality_strategy/collision")
        _, findings = validate_repository(ROOT, mutated)
        self.assertIn("META-ROUTE-COLLISION", {item.code for item in findings})

    def test_unknown_dependency_bites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/implementation/tasks").mkdir(parents=True)
            (root / "docs/implementation/handoffs").mkdir(parents=True)
            (root / "docs/implementation/BACKLOG_PHASE_0.md").write_text(
                "## E0\n| FNC-GOV-001 | A0 | ARC-999 | Ready | x |\n", encoding="utf-8"
            )
            (root / "docs/implementation/DECISION_LOG.md").write_text("", encoding="utf-8")
            (root / "docs/implementation/TRACEABILITY.md").write_text("", encoding="utf-8")
            _, findings = validate_repository(root, self._minimal_config())
            self.assertIn("META-UNKNOWN-DEPENDENCY", {item.code for item in findings})

    def test_missing_handoff_bites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/implementation/tasks").mkdir(parents=True)
            (root / "docs/implementation/handoffs").mkdir(parents=True)
            (root / "docs/implementation/BACKLOG_PHASE_0.md").write_text(
                "## E0\n| FNC-GOV-001 | A0 | — | Review | x |\n", encoding="utf-8"
            )
            (root / "docs/implementation/DECISION_LOG.md").write_text("", encoding="utf-8")
            (root / "docs/implementation/TRACEABILITY.md").write_text("", encoding="utf-8")
            config = self._minimal_config()
            _, findings = validate_repository(root, config)
            self.assertIn("META-HANDOFF-MISSING", {item.code for item in findings})

    def test_unknown_status_bites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/implementation/tasks").mkdir(parents=True)
            (root / "docs/implementation/handoffs").mkdir(parents=True)
            (root / "docs/implementation/BACKLOG_PHASE_0.md").write_text(
                "## E0\n| FNC-GOV-001 | A0 | — | Impossible | x |\n", encoding="utf-8"
            )
            (root / "docs/implementation/DECISION_LOG.md").write_text("", encoding="utf-8")
            (root / "docs/implementation/TRACEABILITY.md").write_text("", encoding="utf-8")
            config = self._minimal_config()
            config["states"] = ["ready"]
            _, findings = validate_repository(root, config)
            self.assertIn("META-UNKNOWN-STATUS", {item.code for item in findings})

    def test_human_gate_cannot_be_agent_accepted(self) -> None:
        config = json.loads((ROOT / "docs/implementation/work-graph.json").read_text(encoding="utf-8"))
        mutated = copy.deepcopy(config)
        mutated["human_gates"][0]["agent_may_accept"] = True
        _, findings = validate_repository(ROOT, mutated)
        self.assertIn("META-HUMAN-GATE", {item.code for item in findings})

    @staticmethod
    def _minimal_config() -> dict[str, object]:
        return {
            "sources": {
                "backlog": "docs/implementation/BACKLOG_PHASE_0.md",
                "decisions": "docs/implementation/DECISION_LOG.md",
                "traceability": "docs/implementation/TRACEABILITY.md",
                "task_directory": "docs/implementation/tasks",
                "handoff_directory": "docs/implementation/handoffs"
            },
            "states": ["proposed", "review_pending", "ready"],
            "artifact_available_states": ["review_pending"],
            "aggregate_dependencies": [],
            "human_gates": [],
            "active_reservations": []
        }


if __name__ == "__main__":
    unittest.main()
