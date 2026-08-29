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
        self.assertEqual([], validate_sources())
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

    def test_alb_encryption_constraint_cannot_be_hidden(self) -> None:
        errors = validate_contract(self.mutate(
            "observability", "alb_access_log_encryption", value="SSE-KMS"))
        self.assertTrue(any("restriccion SSE-S3" in item for item in errors))

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
                         "deletion_window_in_days": 30,
                         "key_usage": "ENCRYPT_DECRYPT"}
            elif resource_type == "aws_lb":
                after = {
                    "internal": False, "load_balancer_type": "application",
                    "enable_deletion_protection": True,
                    "subnets": ["subnet-a", "subnet-b"],
                    "access_logs": [{"enabled": True}],
                }
            elif resource_type == "aws_cognito_user_pool":
                after = {"mfa_configuration": "ON", "deletion_protection": "ACTIVE"}
            elif resource_type == "aws_cognito_user_pool_client":
                after = {
                    "generate_secret": False,
                    "allowed_oauth_flows": ["code"],
                    "allowed_oauth_scopes": ["openid", "email", "profile"],
                }
            elif resource_type == "aws_vpc":
                after = {"cidr_block": "10.60.0.0/16"}
            elif resource_type == "aws_subnet":
                after = {"map_public_ip_on_launch": False}
            changes.append({
                "address": f"{resource_type}.fixture_{index}",
                "mode": "managed", "type": resource_type,
                "change": {"actions": ["create"], "after": after},
            })
        return {"resource_changes": changes}

    def test_minimum_safe_plan_is_valid(self) -> None:
        self.assertEqual([], validate_plan(self.valid_plan(), self.model))

    def test_provider_normalized_oidc_scope_order_is_valid(self) -> None:
        plan = self.valid_plan()
        client = next(item for item in plan["resource_changes"]
                      if item["type"] == "aws_cognito_user_pool_client")
        client["change"]["after"]["allowed_oauth_scopes"] = [
            "email", "openid", "profile",
        ]
        self.assertEqual([], validate_plan(plan, self.model))

    def test_provider_string_true_for_valkey_at_rest_is_valid(self) -> None:
        plan = self.valid_plan()
        cache = next(item for item in plan["resource_changes"]
                     if item["type"] == "aws_elasticache_replication_group")
        cache["change"]["after"]["at_rest_encryption_enabled"] = "true"
        self.assertEqual([], validate_plan(plan, self.model))

    def test_provider_string_false_for_valkey_at_rest_dies(self) -> None:
        plan = self.valid_plan()
        cache = next(item for item in plan["resource_changes"]
                     if item["type"] == "aws_elasticache_replication_group")
        cache["change"]["after"]["at_rest_encryption_enabled"] = "false"
        self.assertTrue(any("Valkey" in item
                            for item in validate_plan(plan, self.model)))

    def test_two_planned_public_subnets_satisfy_unknown_alb_ids(self) -> None:
        plan = self.valid_plan()
        load_balancer = next(item for item in plan["resource_changes"]
                             if item["type"] == "aws_lb")
        load_balancer["change"]["after"].pop("subnets")
        load_balancer["change"]["after_unknown"] = {"subnets": True}
        plan["resource_changes"].extend([
            {
                "address": f"aws_subnet.public[{index}]",
                "mode": "managed", "type": "aws_subnet",
                "change": {"actions": ["create"], "after": {
                    "map_public_ip_on_launch": False,
                }},
            }
            for index in range(2)
        ])
        self.assertEqual([], validate_plan(plan, self.model))

    def test_unknown_alb_ids_without_two_public_subnets_dies(self) -> None:
        plan = self.valid_plan()
        load_balancer = next(item for item in plan["resource_changes"]
                             if item["type"] == "aws_lb")
        load_balancer["change"]["after"].pop("subnets")
        load_balancer["change"]["after_unknown"] = {"subnets": True}
        plan["resource_changes"].append({
            "address": "aws_subnet.public[0]",
            "mode": "managed", "type": "aws_subnet",
            "change": {"actions": ["create"], "after": {
                "map_public_ip_on_launch": False,
            }},
        })
        self.assertTrue(any("dos subredes" in item
                            for item in validate_plan(plan, self.model)))

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

    def test_asymmetric_gate_key_requires_rsa_and_no_rotation(self) -> None:
        plan = self.valid_plan()
        key = next(item for item in plan["resource_changes"]
                   if item["type"] == "aws_kms_key")
        key["change"]["after"].update({
            "key_usage": "SIGN_VERIFY",
            "customer_master_key_spec": "ECC_NIST_P256",
            "enable_key_rotation": True,
        })
        errors = validate_plan(plan, self.model)
        self.assertTrue(any("RSA_2048" in item for item in errors))
        self.assertTrue(any("no admite rotacion" in item for item in errors))

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

    def test_source_mutation_enabling_real_data_dies(self) -> None:
        candidate = source_text().replace(
            'FINCILIA_REAL_DATA_ENABLED", value = "false"',
            'FINCILIA_REAL_DATA_ENABLED", value = "true"', 1)
        self.assertTrue(any("patron prohibido" in item
                            for item in validate_sources(candidate)))

    def test_source_mutation_adding_static_aws_key_dies(self) -> None:
        self.assertTrue(any("patron prohibido" in item for item in
                            validate_sources(source_text() + "\naws_access_key_id\n")))

    def test_source_mutation_adding_google_secret_to_iac_dies(self) -> None:
        candidate = source_text() + '\nresource "aws_cognito_identity_provider" "google" {}\n'
        self.assertTrue(any("patron prohibido" in item
                            for item in validate_sources(candidate)))

    def test_source_mutation_worker_default_route_dies(self) -> None:
        candidate = source_text() + (
            '\nresource "aws_route" "worker_internet" {\n'
            ' destination_cidr_block = "0.0.0.0/0"\n}\n')
        self.assertTrue(any("default route" in item
                            for item in validate_sources(candidate)))


if __name__ == "__main__":
    unittest.main()
