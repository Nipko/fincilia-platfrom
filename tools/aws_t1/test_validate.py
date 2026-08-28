from __future__ import annotations

import copy
import unittest
from pathlib import Path

from .model import CONTRACT_PATH, load_json, validate, validate_contract, validate_plan, validate_sources


def plan() -> dict:
    return {
        "format_version": "1.2",
        "resource_changes": [{
            "address": "aws_instance.runtime",
            "mode": "managed",
            "type": "aws_instance",
            "change": {
                "actions": ["create"],
                "after": {
                    "ami": "ami-0ae4c9718ffae6ca6",
                    "instance_type": "t3.small",
                    "key_name": None,
                    "monitoring": False,
                    "instance_initiated_shutdown_behavior": "stop",
                    "metadata_options": [{"http_tokens": "required", "http_put_response_hop_limit": 1}],
                    "root_block_device": [{"encrypted": True, "volume_type": "gp3", "volume_size": 16}],
                    "credit_specification": [{"cpu_credits": "standard"}],
                    "tags_all": {
                        "Project": "Fincilia", "Environment": "t1-remote-lab",
                        "DataClass": "synthetic_only", "ManagedBy": "OpenTofu",
                        "Task": "FNC-PLT-011",
                    },
                },
            },
        }],
    }


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_json(CONTRACT_PATH)

    def test_repository_is_valid(self) -> None:
        self.assertEqual([], validate_contract(self.model))
        self.assertEqual([], validate_sources())
        self.assertTrue(validate()["ok"])

    def test_real_data_bites(self) -> None:
        value = copy.deepcopy(self.model); value["real_data_authorized"] = True
        self.assertTrue(validate_contract(value))

    def test_runtime_size_bites(self) -> None:
        value = copy.deepcopy(self.model); value["runtime"]["instance_type"] = "t3.medium"
        self.assertTrue(validate_contract(value))

    def test_session_length_bites(self) -> None:
        value = copy.deepcopy(self.model); value["runtime"]["max_session_hours"] = 24
        self.assertTrue(validate_contract(value))

    def test_hard_cap_claim_bites(self) -> None:
        value = copy.deepcopy(self.model); value["cost_model"]["hard_cost_cap"] = True
        self.assertTrue(validate_contract(value))

    def test_autostop_is_armed_before_application_start(self) -> None:
        source = (
            Path(__file__).resolve().parents[2]
            / "infra" / "aws" / "t1" / "runtime" / "cloud-init.sh.tftpl"
        ).read_text(encoding="utf-8")
        timer = "systemctl enable --now fincilia-t1-autostop.timer"
        image_pull = "docker compose --env-file /dev/null -f /opt/fincilia/compose.yaml pull"
        application = "systemctl enable --now fincilia-t1.service"
        self.assertLess(source.index(timer), source.index(image_pull))
        self.assertLess(source.index(timer), source.index(application))


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_json(CONTRACT_PATH)

    def errors(self, value: dict) -> list[str]:
        return validate_plan(value, self.model)

    def test_valid_plan(self) -> None:
        self.assertEqual([], self.errors(plan()))

    def mutate(self, path: list, value) -> list[str]:
        candidate = plan(); target = candidate
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value
        return self.errors(candidate)

    def test_delete_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "actions"], ["delete"]))

    def test_control_preserving_instance_replacement_is_allowed(self) -> None:
        candidate = plan()
        candidate["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        self.assertEqual([], self.errors(candidate))

    def test_control_losing_instance_replacement_bites(self) -> None:
        candidate = plan()
        candidate["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        candidate["resource_changes"][0]["change"]["after"]["metadata_options"][0]["http_tokens"] = "optional"
        self.assertTrue(self.errors(candidate))

    def test_s3_update_is_allowed_but_delete_is_not(self) -> None:
        candidate = plan()
        candidate["resource_changes"].append({
            "address": "aws_s3_object.runtime[\"bootstrap.sql\"]",
            "mode": "managed",
            "type": "aws_s3_object",
            "change": {"actions": ["update"], "after": {}},
        })
        self.assertEqual([], self.errors(candidate))
        candidate["resource_changes"][1]["change"]["actions"] = ["delete"]
        self.assertTrue(self.errors(candidate))

    def test_ec2_size_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "instance_type"], "t3.medium"))

    def test_ami_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "ami"], "ami-floating"))

    def test_key_pair_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "key_name"], "ssh-key"))

    def test_monitoring_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "monitoring"], True))

    def test_shutdown_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "instance_initiated_shutdown_behavior"], "terminate"))

    def test_imdsv1_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "metadata_options", 0, "http_tokens"], "optional"))

    def test_hop_limit_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "metadata_options", 0, "http_put_response_hop_limit"], 2))

    def test_unencrypted_volume_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "root_block_device", 0, "encrypted"], False))

    def test_large_volume_bites(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "root_block_device", 0, "volume_size"], 30))

    def test_unlimited_credits_bite(self) -> None:
        self.assertTrue(self.mutate(["resource_changes", 0, "change", "after", "credit_specification", 0, "cpu_credits"], "unlimited"))

    def test_missing_tag_bites(self) -> None:
        candidate = plan(); del candidate["resource_changes"][0]["change"]["after"]["tags_all"]["DataClass"]
        self.assertTrue(self.errors(candidate))

    def test_rds_bites(self) -> None:
        candidate = plan(); candidate["resource_changes"].append({
            "address": "aws_db_instance.bad", "mode": "managed", "type": "aws_db_instance",
            "change": {"actions": ["create"], "after": {}},
        })
        self.assertTrue(self.errors(candidate))

    def test_two_instances_bite(self) -> None:
        candidate = plan(); candidate["resource_changes"].append(copy.deepcopy(candidate["resource_changes"][0]))
        self.assertTrue(self.errors(candidate))


if __name__ == "__main__":
    unittest.main()
