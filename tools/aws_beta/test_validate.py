from __future__ import annotations

import copy
import unittest

from .model import (
    CONTRACT_PATH,
    load_json,
    source_text,
    validate_contract,
    validate_plan,
    validate_sources,
)


class ClosedBetaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_json(CONTRACT_PATH)

    def mutate(self, *path: str, value: object) -> dict:
        model = copy.deepcopy(self.model)
        cursor = model
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        return model

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], validate_contract(self.model))
        self.assertEqual([], validate_sources())

    def test_real_data_cannot_be_authorized(self) -> None:
        errors = validate_contract(self.mutate("real_data_authorized", value=True))
        self.assertTrue(any("real_data_authorized" in item for item in errors))

    def test_google_cannot_be_enabled(self) -> None:
        errors = validate_contract(self.mutate("google_oidc_enabled", value=True))
        self.assertTrue(any("google_oidc_enabled" in item for item in errors))

    def test_ingress_is_exact(self) -> None:
        errors = validate_contract(self.mutate(
            "public_entry", "ingress_tcp_ports", value=[22, 80, 443]))
        self.assertTrue(any("80/443" in item for item in errors))

    def test_known_demo_users_are_forbidden(self) -> None:
        errors = validate_contract(self.mutate(
            "identity", "known_demo_users_seeded", value=True))
        self.assertTrue(any("usuarios conocidos" in item for item in errors))

    def test_gate_cannot_be_self_promoted(self) -> None:
        model = copy.deepcopy(self.model)
        model["gate_claims"][0]["status"] = "met"
        self.assertTrue(any("BETA-01" in item for item in validate_contract(model)))

    def test_source_mutation_enabling_real_data_dies(self) -> None:
        mutated = source_text() + '\nFINCILIA_REAL_DATA_ENABLED: "true"\n'
        self.assertTrue(any("patron prohibido" in item
                            for item in validate_sources(mutated)))

    def test_source_mutation_adding_ssh_dies(self) -> None:
        mutated = source_text() + '\nfrom_port   = 22\n'
        self.assertTrue(any("patron prohibido" in item
                            for item in validate_sources(mutated)))

    def test_source_mutation_local_seed_dies(self) -> None:
        mutated = source_text() + '\npython -m db.seed.local\n'
        self.assertTrue(any("patron prohibido" in item
                            for item in validate_sources(mutated)))

    def valid_plan(self) -> dict:
        tags = {
            "Project": "Fincilia", "Environment": "closed-beta",
            "DataClass": "synthetic_only", "ManagedBy": "OpenTofu",
            "Task": "FNC-BET-001",
        }
        changes = [
            {
                "address": "aws_instance.beta", "mode": "managed",
                "type": "aws_instance",
                "change": {"actions": ["create"], "after": {
                    "ami": "ami-0ae4c9718ffae6ca6", "instance_type": "t3.small",
                    "key_name": None, "monitoring": False,
                    "instance_initiated_shutdown_behavior": "stop",
                    "root_block_device": [{"encrypted": True, "volume_size": 24,
                                           "volume_type": "gp3"}],
                    "metadata_options": [{"http_tokens": "required",
                                          "http_put_response_hop_limit": 1}],
                    "credit_specification": [{"cpu_credits": "standard"}],
                    "tags": tags,
                }},
            },
            {
                "address": "aws_security_group.beta", "mode": "managed",
                "type": "aws_security_group",
                "change": {"actions": ["create"], "after": {"ingress": [
                    {"from_port": 80, "to_port": 80, "protocol": "tcp",
                     "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": []},
                    {"from_port": 443, "to_port": 443, "protocol": "tcp",
                     "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": []},
                ]}},
            },
        ]
        singleton_types = (
            "aws_eip", "aws_eip_association", "aws_iam_role",
            "aws_iam_instance_profile", "aws_budgets_budget",
        )
        for resource_type in singleton_types:
            changes.append({
                "address": f"{resource_type}.beta", "mode": "managed",
                "type": resource_type,
                "change": {"actions": ["create"], "after": {}},
            })
        for index in range(3):
            changes.append({
                "address": f"aws_cloudwatch_metric_alarm.beta[{index}]",
                "mode": "managed", "type": "aws_cloudwatch_metric_alarm",
                "change": {"actions": ["create"], "after": {}},
            })
        return {"resource_changes": changes}

    def test_minimal_safe_plan_is_valid(self) -> None:
        self.assertEqual([], validate_plan(self.valid_plan(), self.model))

    def test_plan_with_ssh_ingress_dies(self) -> None:
        plan = self.valid_plan()
        security_group = next(item for item in plan["resource_changes"]
                              if item["type"] == "aws_security_group")
        security_group["change"]["after"]["ingress"].append({
            "from_port": 22, "to_port": 22, "protocol": "tcp",
            "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": [],
        })
        self.assertTrue(any("80/443" in item
                            for item in validate_plan(plan, self.model)))

    def test_plan_with_delete_only_dies(self) -> None:
        plan = self.valid_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["delete"]
        self.assertTrue(any("borrado sin reemplazo" in item
                            for item in validate_plan(plan, self.model)))


if __name__ == "__main__":
    unittest.main()
