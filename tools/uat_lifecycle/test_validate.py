from __future__ import annotations

import copy
import json
import unittest

from tools.uat_lifecycle.validate import DEFAULT_CONTRACT, validate_contract


class UatLifecycleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))

    def test_canonical_contract_is_valid(self) -> None:
        self.assertEqual(validate_contract(self.contract), [])

    def assert_mutation_fails(self, mutate, expected: str) -> None:
        candidate = copy.deepcopy(self.contract)
        mutate(candidate)
        self.assertIn(expected, validate_contract(candidate))

    def test_uat_cannot_be_production(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["environments"]["uat"].update(production_traffic=True),
            "UAT-NOT-PRODUCTION",
        )

    def test_production_cannot_be_resettable(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["environments"]["production"].update(resettable=True),
            "PRODUCTION-NOT-RESETTABLE",
        )

    def test_resource_sharing_is_rejected(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["isolation"]["shared_resource_kinds"].append("postgresql"),
            "ENVIRONMENT-SHARED-STATE",
        )

    def test_accounts_are_not_promoted(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["promotion"].update(copy_uat_accounts=True),
            "PROMOTION-DATA-COPY:copy_uat_accounts",
        )

    def test_database_is_not_promoted(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["promotion"].update(copy_uat_database=True),
            "PROMOTION-DATA-COPY:copy_uat_database",
        )

    def test_in_place_reset_is_rejected(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"].update(strategy="truncate_tables"),
            "RESET-IN-PLACE-FORBIDDEN",
        )

    def test_web_reset_is_rejected(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"].update(web_trigger_available=True),
            "RESET-WEB-TRIGGER",
        )

    def test_long_lived_confirmation_is_rejected(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"].update(confirmation_token_ttl_seconds=901),
            "RESET-TOKEN-TTL",
        )

    def test_missing_restore_drill_is_rejected(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"]["required_preconditions"].remove("restore_drill_passed"),
            "RESET-PREFLIGHT-INCOMPLETE",
        )

    def test_bootstrap_assignment_cannot_be_copied(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"].update(bootstrap_policy="copy_previous_assignment"),
            "RESET-BOOTSTRAP-COPY",
        )

    def test_execution_cannot_be_enabled_by_contract_edit(self) -> None:
        self.assert_mutation_fails(
            lambda value: value["reset"].update(execution_state="enabled"),
            "RESET-PREMATURELY-ENABLED",
        )


if __name__ == "__main__":
    unittest.main()
