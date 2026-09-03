from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Sequence
from unittest.mock import patch

from .cli import main
from .control import (
    ControlError,
    FOUNDATION_REQUIRED_ADDRESSES,
    PilotController,
    RUNTIME_REQUIRED_ADDRESSES,
    Result,
    SERVICE_NAMES,
)


IDENTITY = {"Account": "123456789012", "Arn": "redacted", "UserId": "redacted"}


class FakeRunner:
    def __init__(self, responses: list[Result]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: Sequence[str], **_: object) -> Result:
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError(f"respuesta no preparada para {argv}")
        return self.responses.pop(0)


def response(payload: object, code: int = 0) -> Result:
    return Result(code, json.dumps(payload), "")


class PilotControllerTests(unittest.TestCase):
    def controller(self, runner: FakeRunner) -> PilotController:
        return PilotController(account_id="123456789012", runner=runner)

    def test_wrong_account_is_rejected_before_other_calls(self) -> None:
        runner = FakeRunner([response({"Account": "999999999999"})])
        with self.assertRaisesRegex(ControlError, "cuenta autorizada"):
            self.controller(runner).status()
        self.assertEqual(len(runner.calls), 1)

    def test_invalid_region_and_account_format_die(self) -> None:
        with self.assertRaises(ControlError):
            PilotController(account_id="123", runner=FakeRunner([]))
        with self.assertRaises(ControlError):
            PilotController(
                account_id="123456789012", region="us-east-1", runner=FakeRunner([])
            )

    def test_status_reports_cold_without_mutations(self) -> None:
        runner = FakeRunner([
            response(IDENTITY),
            Result(254, "", "DBInstanceNotFound"),
            Result(254, "", "ClusterNotFoundException"),
            response({"NatGateways": []}),
            Result(254, "", "LoadBalancerNotFound"),
            Result(254, "", "ReplicationGroupNotFoundFault"),
            Result(1, "", "No state file was found!"),
        ])
        report = self.controller(runner).status()
        self.assertEqual(report["mode"], "cold")
        self.assertEqual(report["state_inventory"]["foundation"]["state"], "absent")
        self.assertEqual(report["state_inventory"]["runtime_plane"]["state"], "absent")
        self.assertEqual(report["isolated_environment_control"]["state"], "pending")
        self.assertFalse(report["real_data_authorized"])
        flattened = " ".join(" ".join(call) for call in runner.calls)
        self.assertNotIn("update-service", flattened)
        self.assertNotIn("apply", flattened)

    def test_status_does_not_echo_arn_or_user_id(self) -> None:
        runner = FakeRunner([
            response(IDENTITY),
            response({"DBInstances": [{"DBInstanceStatus": "stopped"}]}),
            response({"services": []}),
            response({"NatGateways": []}),
            Result(254, "", "LoadBalancerNotFound"),
            Result(254, "", "ReplicationGroupNotFoundFault"),
            Result(1, "", "No state file was found!"),
        ])
        encoded = json.dumps(self.controller(runner).status())
        self.assertNotIn("Arn", encoded)
        self.assertNotIn("UserId", encoded)

    def test_complete_state_still_cannot_accept_gate(self) -> None:
        addresses = sorted(FOUNDATION_REQUIRED_ADDRESSES | RUNTIME_REQUIRED_ADDRESSES)
        runner = FakeRunner([
            response(IDENTITY),
            response({"DBInstances": [{"DBInstanceStatus": "available"}]}),
            response({"services": [
                {"serviceName": name, "status": "ACTIVE", "desiredCount": 0,
                 "runningCount": 0}
                for name in SERVICE_NAMES
            ]}),
            response({"NatGateways": [{"NatGatewayId": "redacted"}]}),
            response({"LoadBalancers": [{"State": {"Code": "active"}}]}),
            response({"ReplicationGroups": [{"Status": "available"}]}),
            Result(0, "\n".join(addresses) + "\n", ""),
        ])
        report = self.controller(runner).status()
        self.assertEqual(report["state_inventory"]["foundation"]["state"], "complete")
        self.assertEqual(report["state_inventory"]["runtime_plane"]["state"], "complete")
        self.assertEqual(report["isolated_environment_control"]["state"], "pending")
        self.assertEqual(report["isolated_environment_control"]["blockers"], [
            "release_not_admitted_to_target",
            "target_environment_drill_not_observed",
            "independent_security_review_pending",
        ])
        self.assertFalse(report["real_data_authorized"])

    def test_partial_state_reports_exact_missing_addresses(self) -> None:
        only_vpc = "aws_vpc.pilot\nterraform_data.account_guard\n"
        runner = FakeRunner([
            response(IDENTITY),
            Result(254, "", "DBInstanceNotFound"),
            Result(254, "", "ClusterNotFoundException"),
            response({"NatGateways": []}),
            Result(254, "", "LoadBalancerNotFound"),
            Result(254, "", "ReplicationGroupNotFoundFault"),
            Result(0, only_vpc, ""),
        ])
        report = self.controller(runner).status()
        foundation = report["state_inventory"]["foundation"]
        self.assertEqual(foundation["state"], "partial")
        self.assertNotIn("aws_vpc.pilot", foundation["missing"])
        self.assertIn("aws_db_instance.pilot", foundation["missing"])

    def test_state_query_failure_does_not_masquerade_as_absence(self) -> None:
        controller = self.controller(FakeRunner([Result(2, "", "AccessDenied")]))
        with self.assertRaisesRegex(ControlError, "no se asumira ausencia"):
            controller._state_inventory()

    def test_state_inventory_rejects_duplicate_addresses(self) -> None:
        controller = self.controller(FakeRunner([
            Result(0, "aws_vpc.pilot\naws_vpc.pilot\n", "")
        ]))
        with self.assertRaisesRegex(ControlError, "duplicadas"):
            controller._state_inventory()

    def test_mode_without_apply_is_refused_without_calls(self) -> None:
        runner = FakeRunner([])
        with self.assertRaisesRegex(ControlError, "requiere --apply"):
            self.controller(runner).apply_mode("cold", apply=False)
        self.assertEqual(runner.calls, [])

    def test_cli_mode_without_apply_returns_refused(self) -> None:
        with patch("tools.aws_pilot_control.cli.PilotController") as controller:
            controller.return_value.apply_mode.side_effect = ControlError(
                "la mutacion requiere --apply"
            )
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main(["--account-id", "123456789012", "warm"]),
                    2,
                )

    def test_cold_scales_before_planning_and_applying(self) -> None:
        controller = self.controller(FakeRunner([]))
        events: list[str] = []
        controller.guard_identity = lambda: events.append("guard") or {}  # type: ignore[method-assign]
        controller._scale_services_to_zero = lambda: events.append("scale")  # type: ignore[method-assign]
        controller._load_balancer_arn = lambda: None  # type: ignore[method-assign]
        controller.plan = lambda mode: events.append(f"plan:{mode}") or {  # type: ignore[method-assign]
            "plan_file": Path("cold.tfplan")
        }
        controller._run = lambda *args, **kwargs: events.append("apply") or Result(0)  # type: ignore[method-assign]
        controller._stop_database = lambda: events.append("stop-db") or "stop_requested"  # type: ignore[method-assign]
        controller.apply_mode("cold", apply=True)
        self.assertEqual(events, ["guard", "scale", "plan:cold", "apply", "stop-db"])

    def test_cold_restores_alb_protection_when_plan_fails(self) -> None:
        controller = self.controller(FakeRunner([]))
        events: list[str] = []
        arn = "arn:aws:elasticloadbalancing:sa-east-1:123456789012:loadbalancer/app/x/y"
        controller.guard_identity = lambda: {}  # type: ignore[method-assign]
        controller._scale_services_to_zero = lambda: events.append("scale")  # type: ignore[method-assign]
        controller._load_balancer_arn = lambda: arn  # type: ignore[method-assign]
        controller._set_alb_deletion_protection = (  # type: ignore[method-assign]
            lambda _arn, enabled: events.append(f"protection:{enabled}")
        )
        controller.plan = lambda mode: (_ for _ in ()).throw(ControlError("plan fallo"))  # type: ignore[method-assign]
        with self.assertRaisesRegex(ControlError, "plan fallo"):
            controller.apply_mode("cold", apply=True)
        self.assertEqual(events, ["scale", "protection:False", "protection:True"])

    def test_warm_applies_before_starting_database(self) -> None:
        controller = self.controller(FakeRunner([]))
        events: list[str] = []
        controller.plan = lambda mode: events.append(f"plan:{mode}") or {  # type: ignore[method-assign]
            "plan_file": Path("warm.tfplan")
        }
        controller._run = lambda *args, **kwargs: events.append("apply") or Result(0)  # type: ignore[method-assign]
        controller._start_database = lambda: events.append("start-db") or "start_requested"  # type: ignore[method-assign]
        report = controller.apply_mode("warm", apply=True)
        self.assertEqual(events, ["plan:warm", "apply", "start-db"])
        self.assertEqual(report["services_desired_count"], 0)
        self.assertFalse(report["real_data_authorized"])

    def test_cold_stop_is_idempotent_when_database_absent(self) -> None:
        controller = self.controller(FakeRunner([]))
        controller._database_state = lambda: "absent"  # type: ignore[method-assign]
        self.assertEqual(controller._stop_database(), "absent")

    def test_cold_refuses_to_stop_database_in_unknown_transition(self) -> None:
        controller = self.controller(FakeRunner([]))
        controller._database_state = lambda: "backing-up"  # type: ignore[method-assign]
        with self.assertRaisesRegex(ControlError, "backing-up"):
            controller._stop_database()

    def test_service_names_are_closed_and_exact(self) -> None:
        self.assertEqual(SERVICE_NAMES, (
            "fincilia-private-pilot-application",
            "fincilia-private-pilot-worker",
        ))

    def test_scale_waits_only_for_services_that_exist(self) -> None:
        runner = FakeRunner([Result(0), Result(0)])
        controller = self.controller(runner)
        controller._describe_services = lambda: [  # type: ignore[method-assign]
            {"name": SERVICE_NAMES[0], "status": "active", "desired": 1, "running": 1},
            {"name": SERVICE_NAMES[1], "status": "absent", "desired": 0, "running": 0},
        ]
        controller._scale_services_to_zero()
        wait_call = runner.calls[-1]
        self.assertIn(SERVICE_NAMES[0], wait_call)
        self.assertNotIn(SERVICE_NAMES[1], wait_call)

    def test_safe_environment_does_not_forward_arbitrary_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "infra" / "aws" / "private-pilot").mkdir(parents=True)
            controller = PilotController(
                account_id="123456789012", runner=FakeRunner([]), root=root
            )
        allowed = set(controller.environment)
        self.assertNotIn("FINCILIA_DATABASE_URL", allowed)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", allowed)
        self.assertEqual(controller.environment["AWS_PROFILE"], "fincilia-sandbox")
        self.assertEqual(
            str(Path.home() / ".local" / "bin"),
            controller.environment["PATH"].split(os.pathsep)[0],
        )


if __name__ == "__main__":
    unittest.main()
