from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from .model import (
    CONTRACT_PATH,
    T0_SOURCE_ROOTS,
    load_json,
    validate,
    validate_contract,
    validate_plan,
    validate_sources,
)


def valid_plan(resource_type: str = "aws_vpc") -> dict:
    return {
        "format_version": "1.2",
        "resource_changes": [{
            "address": "aws_vpc.t0",
            "mode": "managed",
            "type": resource_type,
            "change": {
                "actions": ["create"],
                "after": {
                    "tags": {
                        "Project": "Fincilia",
                        "Environment": "t0-synthetic",
                        "DataClass": "synthetic_only",
                        "ManagedBy": "OpenTofu",
                        "Task": "FNC-PLT-010",
                    }
                },
            },
        }],
    }


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_json(CONTRACT_PATH)

    def test_repository_contract_and_sources_are_valid(self) -> None:
        self.assertEqual([], validate_contract(self.contract))
        self.assertEqual([], validate_sources())
        self.assertTrue(validate()["ok"])

    def test_rejects_real_data(self) -> None:
        value = copy.deepcopy(self.contract)
        value["real_data_authorized"] = True
        self.assertTrue(validate_contract(value))

    def test_rejects_external_ai(self) -> None:
        value = copy.deepcopy(self.contract)
        value["external_ai_authorized"] = True
        self.assertTrue(validate_contract(value))

    def test_rejects_runtime(self) -> None:
        value = copy.deepcopy(self.contract)
        value["apply_scope"]["runtime_enabled"] = True
        self.assertTrue(validate_contract(value))

    def test_rejects_wrong_region(self) -> None:
        value = copy.deepcopy(self.contract)
        value["region"] = "us-east-1"
        self.assertTrue(validate_contract(value))

    def test_rejects_relaxed_budget(self) -> None:
        value = copy.deepcopy(self.contract)
        value["cost_control"]["gross_monthly_budget_usd"] = 10
        self.assertTrue(validate_contract(value))

    def test_rejects_organizations(self) -> None:
        value = copy.deepcopy(self.contract)
        value["cost_control"]["organizations_forbidden"] = False
        self.assertTrue(validate_contract(value))

    def test_rejects_allowlist_overlap(self) -> None:
        value = copy.deepcopy(self.contract)
        value["apply_scope"]["allowed_resource_types"].append("aws_instance")
        self.assertTrue(validate_contract(value))

    def test_sibling_runtime_module_does_not_contaminate_t0_sources(self) -> None:
        sibling_source = Path(__file__).resolve().parents[2] / "infra" / "aws" / "t1" / "compute.tf"
        self.assertIn('resource "aws_instance"', sibling_source.read_text(encoding="utf-8"))
        self.assertEqual([], validate_sources())

    def test_forbidden_resource_inside_explicit_t0_root_still_fails(self) -> None:
        canonical = "\n".join(
            source.read_text(encoding="utf-8")
            for root in T0_SOURCE_ROOTS
            for source in sorted(root.rglob("*.tf"))
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.tf"
            source.write_text(
                canonical + '\nresource "aws_instance" "forbidden" {}\n',
                encoding="utf-8",
            )
            errors = validate_sources(Path(directory))
        self.assertTrue(any("EC2" in error for error in errors))


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_json(CONTRACT_PATH)

    def test_accepts_allowlisted_create(self) -> None:
        self.assertEqual([], validate_plan(valid_plan(), self.contract))

    def test_accepts_allowlisted_noop(self) -> None:
        plan = valid_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["no-op"]
        self.assertEqual([], validate_plan(plan, self.contract))

    def test_accepts_provider_default_tags_from_tags_all(self) -> None:
        plan = valid_plan()
        after = plan["resource_changes"][0]["change"]["after"]
        after["tags_all"] = after.pop("tags")
        self.assertEqual([], validate_plan(plan, self.contract))

    def test_rejects_ec2(self) -> None:
        self.assertTrue(validate_plan(valid_plan("aws_instance"), self.contract))

    def test_rejects_rds(self) -> None:
        self.assertTrue(validate_plan(valid_plan("aws_db_instance"), self.contract))

    def test_rejects_unknown_resource(self) -> None:
        self.assertTrue(validate_plan(valid_plan("aws_lambda_function"), self.contract))

    def test_rejects_delete(self) -> None:
        plan = valid_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["delete"]
        self.assertTrue(validate_plan(plan, self.contract))

    def test_rejects_replace(self) -> None:
        plan = valid_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        self.assertTrue(validate_plan(plan, self.contract))

    def test_rejects_missing_tag(self) -> None:
        plan = valid_plan()
        del plan["resource_changes"][0]["change"]["after"]["tags"]["DataClass"]
        self.assertTrue(validate_plan(plan, self.contract))

    def test_ignores_data_source_reads(self) -> None:
        plan = valid_plan()
        plan["resource_changes"].append({
            "address": "data.aws_caller_identity.current",
            "mode": "data",
            "type": "aws_caller_identity",
            "change": {"actions": ["read"], "after": {}},
        })
        self.assertEqual([], validate_plan(plan, self.contract))

    def test_rejects_plan_without_format(self) -> None:
        plan = valid_plan()
        del plan["format_version"]
        self.assertTrue(validate_plan(plan, self.contract))

    def test_rejects_empty_plan(self) -> None:
        plan = {"format_version": "1.2", "resource_changes": []}
        self.assertTrue(validate_plan(plan, self.contract))

    def test_cli_input_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertFalse(validate(path)["ok"])

    def test_accepts_serialized_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(valid_plan()), encoding="utf-8")
            self.assertTrue(validate(path)["ok"])


if __name__ == "__main__":
    unittest.main()
