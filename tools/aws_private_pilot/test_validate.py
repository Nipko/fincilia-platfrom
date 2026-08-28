from __future__ import annotations

import copy
import unittest

from .model import CONTRACT_PATH, load_json, validate_contract, validate_plan


class PrivatePilotContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_json(CONTRACT_PATH)

    def mutate(self, *path: str, value: object) -> dict:
        model = copy.deepcopy(self.model)
        cursor = model
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        return model

    def test_repository_contract_is_valid_but_not_authorized(self) -> None:
        self.assertEqual([], validate_contract(self.model))
        self.assertFalse(self.model["deployment_authorized"])
        self.assertFalse(self.model["real_data_authorized"])

    def test_real_data_cannot_be_self_authorized(self) -> None:
        errors = validate_contract(self.mutate("real_data_authorized", value=True))
        self.assertTrue(any("real_data_authorized" in item for item in errors))

    def test_deployment_cannot_be_self_authorized(self) -> None:
        errors = validate_contract(self.mutate("deployment_authorized", value=True))
        self.assertTrue(any("deployment_authorized" in item for item in errors))

    def test_worker_default_route_dies(self) -> None:
        errors = validate_contract(self.mutate(
            "network", "worker_has_default_route", value=True))
        self.assertTrue(any("default route" in item for item in errors))

    def test_public_task_ip_dies(self) -> None:
        errors = validate_contract(self.mutate(
            "network", "assign_public_ip", value=True))
        self.assertTrue(any("IP publica" in item for item in errors))

    def test_extra_oidc_scope_dies(self) -> None:
        errors = validate_contract(self.mutate(
            "identity", "scopes", value=["openid", "email", "profile", "drive"]))
        self.assertTrue(any("openid email profile" in item for item in errors))

    def test_cognito_cannot_authorize_company(self) -> None:
        errors = validate_contract(self.mutate(
            "identity", "authorization_source", value="Cognito groups"))
        self.assertTrue(any("autorizacion financiera" in item for item in errors))

    def test_secret_values_cannot_enter_state(self) -> None:
        errors = validate_contract(self.mutate(
            "secrets", "values_in_iac_state", value=True))
        self.assertTrue(any("fuera de IaC" in item for item in errors))

    def test_gate_cannot_be_self_promoted(self) -> None:
        candidate = copy.deepcopy(self.model)
        candidate["gate_claims"][1]["status"] = "met"
        self.assertTrue(any("DRG-01" in item
                            for item in validate_contract(candidate)))

    def valid_plan(self) -> dict:
        changes = []
        for index, resource_type in enumerate(self.model["required_resource_types"]):
            after: dict[str, object] = {}
            if resource_type == "aws_ecs_service":
                after = {"desired_count": 0,
                         "network_configuration": [{"assign_public_ip": False}]}
            elif resource_type == "aws_db_instance":
                after = {
                    "publicly_accessible": False, "storage_encrypted": True,
                    "deletion_protection": True, "backup_retention_period": 14,
                    "manage_master_user_password": True,
                }
            elif resource_type == "aws_elasticache_replication_group":
                after = {"transit_encryption_enabled": True,
                         "at_rest_encryption_enabled": True}
            elif resource_type == "aws_s3_bucket":
                after = {"force_destroy": False}
            elif resource_type == "aws_kms_key":
                after = {"enable_key_rotation": True,
                         "deletion_window_in_days": 30}
            changes.append({
                "address": f"{resource_type}.fixture_{index}",
                "mode": "managed", "type": resource_type,
                "change": {"actions": ["create"], "after": after},
            })
        return {"resource_changes": changes}

    def test_minimum_safe_plan_is_valid(self) -> None:
        self.assertEqual([], validate_plan(self.valid_plan(), self.model))

    def test_plan_with_public_ecs_task_dies(self) -> None:
        plan = self.valid_plan()
        service = next(item for item in plan["resource_changes"]
                       if item["type"] == "aws_ecs_service")
        service["change"]["after"]["network_configuration"][0][
            "assign_public_ip"] = True
        self.assertTrue(any("assign_public_ip" in item
                            for item in validate_plan(plan, self.model)))

    def test_plan_with_unprotected_rds_dies(self) -> None:
        plan = self.valid_plan()
        database = next(item for item in plan["resource_changes"]
                        if item["type"] == "aws_db_instance")
        database["change"]["after"]["deletion_protection"] = False
        self.assertTrue(any("proteger borrado" in item
                            for item in validate_plan(plan, self.model)))

    def test_plan_with_secret_value_dies(self) -> None:
        plan = self.valid_plan()
        secret = next(item for item in plan["resource_changes"]
                      if item["type"] == "aws_secretsmanager_secret")
        secret["change"]["after"]["secret_string"] = "not-a-real-secret"
        self.assertTrue(any("valor de secreto" in item
                            for item in validate_plan(plan, self.model)))

    def test_plan_with_forbidden_instance_dies(self) -> None:
        plan = self.valid_plan()
        plan["resource_changes"].append({
            "address": "aws_instance.forbidden", "mode": "managed",
            "type": "aws_instance",
            "change": {"actions": ["create"], "after": {}},
        })
        self.assertTrue(any("tipo prohibido" in item
                            for item in validate_plan(plan, self.model)))

    def test_delete_only_dies(self) -> None:
        plan = self.valid_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["delete"]
        self.assertTrue(any("borrado sin reemplazo" in item
                            for item in validate_plan(plan, self.model)))


if __name__ == "__main__":
    unittest.main()
