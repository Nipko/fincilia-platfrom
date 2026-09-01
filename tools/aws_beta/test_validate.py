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

    def test_restore_alarm_stays_within_cloudwatch_week_limit(self) -> None:
        mutated = source_text().replace(
            'evaluation_periods  = 7', 'evaluation_periods  = 8', 1
        ).replace(
            'datapoints_to_alarm = 7', 'datapoints_to_alarm = 8', 1
        )
        errors = validate_sources(mutated)
        self.assertTrue(any("evaluation_periods" in item for item in errors))
        self.assertTrue(any("datapoints_to_alarm" in item for item in errors))

    def test_object_buckets_are_bootstrapped_before_worker_start(self) -> None:
        mutated = source_text().replace(
            'created = ensure_buckets(settings)', 'created = []', 1
        )
        self.assertTrue(any("ensure_buckets(settings)" in item
                            for item in validate_sources(mutated)))

    def test_uat_reset_keeps_exact_targets_backup_and_short_confirmation(self) -> None:
        source = source_text()
        mutations = (
            ('TOKEN_TTL_SECONDS=900', 'TOKEN_TTL_SECONDS=3600'),
            ('PG_VOLUME=fincilia-beta_pgdata', 'PG_VOLUME=fincilia-production_pgdata'),
            ('com.docker.compose.project', 'missing.compose.project'),
            ('latest_backup_and_restore', 'skip_backup_and_restore'),
            ('writers_are_stopped', 'assume_writers_stopped'),
            ('--cancel CONFIRMATION_TOKEN', '--cancel-without-token'),
            ('validate_plan_file', 'trust_plan_file'),
            ('stat -c %U "$PLAN_FILE"', 'assume-plan-owner'),
            ('stat -c %a "$PLAN_FILE"', 'assume-plan-mode'),
            ('resume_writers_before_cut', 'leave_writers_stopped'),
            ('trap resume_writers_before_cut ERR', 'trap - ERR'),
            ('FAILURE_MARKER=/run/fincilia-uat-reset.recovery-required',
             'FAILURE_MARKER=/run/unknown-reset-state'),
            ('state=recovery_required', 'state=ready'),
            ('restore the verified backup before reopening', 'restart partial plane'),
            ('docker volume rm "$PG_VOLUME" "$OBJECT_VOLUME"', 'docker volume prune'),
            ('reset-evidence/uat/', 'reset-evidence/unknown/'),
            ('"ssm:DeleteParameter"', '"ssm:GetParameter"'),
            ('"reset-evidence/uat/*"', '"reset-evidence/unknown/*"'),
            ('"Fincilia/UAT"', '"Fincilia/Unknown"'),
        )
        for original, replacement in mutations:
            with self.subTest(original=original):
                self.assertIn(original, source)
                errors = validate_sources(source.replace(original, replacement))
                self.assertTrue(any(original in item for item in errors), errors)

    def test_uat_reset_never_reopens_a_partial_post_cut_plane(self) -> None:
        source = source_text()
        marker = (
            "printf 'UAT reset crossed the destructive cut and remains stopped; "
            "restore the verified backup before reopening\\n' >&2"
        )
        self.assertIn(marker, source)
        mutated = source.replace(
            marker, marker + '\n  /opt/fincilia/up.sh >/dev/null 2>&1 || true', 1)
        errors = validate_sources(mutated)
        self.assertIn(
            "reset UAT no puede reabrir automaticamente tras el corte", errors)

    def test_release_updates_preserve_the_instance_and_have_rollback(self) -> None:
        mutated = source_text().replace(
            'ignore_changes = [user_data]', 'ignore_changes = []', 1
        ).replace(
            'fincilia-beta-deploy.lock', 'missing-deploy-lock', 1
        )
        errors = validate_sources(mutated)
        self.assertTrue(any("ignore_changes = [user_data]" in item
                            for item in errors))
        self.assertTrue(any("fincilia-beta-deploy.lock" in item
                            for item in errors))

    def test_restore_waits_for_the_final_database_not_pg_isready(self) -> None:
        mutated = source_text().replace(
            "psql -U postgres -d fincilia_restore",
            "pg_isready -U postgres -d fincilia_restore",
        )
        self.assertTrue(any("psql -U postgres -d fincilia_restore" in item
                            for item in validate_sources(mutated)))

    def test_restore_recreates_only_non_login_policy_roles(self) -> None:
        mutated = source_text().replace(
            'CREATE ROLE fincilia_app NOLOGIN',
            'CREATE ROLE fincilia_app LOGIN',
        ).replace(
            'CREATE ROLE fincilia_identity NOLOGIN',
            'CREATE ROLE fincilia_identity LOGIN',
        )
        errors = validate_sources(mutated)
        self.assertTrue(any('CREATE ROLE fincilia_app NOLOGIN' in item
                            for item in errors))
        self.assertTrue(any('CREATE ROLE fincilia_identity NOLOGIN' in item
                            for item in errors))

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
