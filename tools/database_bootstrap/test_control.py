from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from .control import (
    APP_KEY_FIELDS,
    GATE_FIELDS,
    AwsJson,
    BootstrapControlError,
    bootstrap_and_migrate,
    prepare_runtime_secrets,
    read_tofu_output,
)


class AwsRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, arguments, **kwargs):
        payload = json.loads(kwargs["input"])
        self.calls.append((arguments, payload))
        operation = arguments[2]
        if operation == "describe-db-instances":
            value = {
                "DBInstances": [{
                    "DBName": "fincilia_pilot",
                    "DBInstanceStatus": "available",
                    "PubliclyAccessible": False,
                    "StorageEncrypted": True,
                    "Endpoint": {
                        "Address": "private-db.example.rds.amazonaws.com",
                        "Port": 5432,
                    },
                }]
            }
            return subprocess.CompletedProcess(arguments, 0, json.dumps(value), "")
        if operation == "get-secret-value":
            return subprocess.CompletedProcess(
                arguments, 1, "", "ResourceNotFoundException"
            )
        return subprocess.CompletedProcess(arguments, 0, "{}", "")


class SecretPreparationTests(unittest.TestCase):
    def test_new_values_use_stdin_never_argv_or_report(self) -> None:
        runner = AwsRunner()
        aws = AwsJson(profile="fincilia-sandbox", runner=runner)
        report = prepare_runtime_secrets(aws)
        self.assertTrue(report["ok"])
        self.assertTrue(report["credentials_generated"])
        self.assertFalse(report["credentials_exposed"])
        put_calls = [call for call in runner.calls if call[0][2] == "put-secret-value"]
        self.assertEqual(4, len(put_calls))
        role_values = json.loads(put_calls[0][1]["SecretString"])
        self.assertEqual(3, len(set(role_values.values())))
        for arguments, payload in put_calls:
            serialized_arguments = " ".join(arguments)
            for secret in role_values.values():
                self.assertNotIn(secret, serialized_arguments)
            self.assertEqual("file:///dev/stdin", arguments[8])
            self.assertIn("SecretString", payload)
        self.assertNotIn(next(iter(role_values.values())), json.dumps(report))

        application = json.loads(put_calls[1][1]["SecretString"])
        self.assertEqual(
            {"FINCILIA_DATABASE_URL", *APP_KEY_FIELDS, *GATE_FIELDS},
            set(application),
        )
        self.assertTrue(application["FINCILIA_DATABASE_URL"].endswith(
            "/fincilia_pilot?sslmode=require&connect_timeout=10"
        ))
        for field in GATE_FIELDS:
            self.assertEqual("disabled", application[field])

    def test_existing_credentials_and_gate_values_are_preserved(self) -> None:
        class Existing(AwsRunner):
            def __init__(self) -> None:
                super().__init__()
                self.roles = {
                    "FINCILIA_DB_APP_PASSWORD": "A" * 40,
                    "FINCILIA_DB_WORKER_PASSWORD": "B" * 40,
                    "FINCILIA_DB_MIGRATOR_PASSWORD": "C" * 40,
                }

            def __call__(self, arguments, **kwargs):
                if arguments[2] != "get-secret-value":
                    return super().__call__(arguments, **kwargs)
                payload = json.loads(kwargs["input"])
                self.calls.append((arguments, payload))
                name = payload["SecretId"]
                if name.endswith("database-roles-v1"):
                    value = self.roles
                elif name.endswith("application-runtime-v1"):
                    value = {
                        **{field: f"existing-{field}-material-000000000000" for field in APP_KEY_FIELDS},
                        **{field: f"signed-{field}" for field in GATE_FIELDS},
                    }
                elif name.endswith("worker-runtime-v1"):
                    value = {
                        "FINCILIA_DATA_GATE_ATTESTATION": "worker-attestation",
                        "FINCILIA_DATA_GATE_SIGNATURE": "worker-signature",
                    }
                else:
                    value = {}
                return subprocess.CompletedProcess(
                    arguments, 0, json.dumps({"SecretString": json.dumps(value)}), ""
                )

        runner = Existing()
        report = prepare_runtime_secrets(AwsJson(profile="fincilia-sandbox", runner=runner))
        puts = {
            call[1]["SecretId"]: json.loads(call[1]["SecretString"])
            for call in runner.calls if call[0][2] == "put-secret-value"
        }
        self.assertFalse(report["credentials_generated"])
        self.assertEqual(
            runner.roles,
            puts["fincilia/private-pilot/database-roles-v1"],
        )
        application = puts["fincilia/private-pilot/application-runtime-v1"]
        for field in APP_KEY_FIELDS:
            self.assertEqual(f"existing-{field}-material-000000000000", application[field])
        for field in GATE_FIELDS:
            self.assertEqual(f"signed-{field}", application[field])
        worker = puts["fincilia/private-pilot/worker-runtime-v1"]
        self.assertEqual("worker-attestation", worker["FINCILIA_DATA_GATE_ATTESTATION"])
        self.assertEqual("worker-signature", worker["FINCILIA_DATA_GATE_SIGNATURE"])

    def test_public_or_unencrypted_database_is_refused_before_secret_writes(self) -> None:
        class Unsafe(AwsRunner):
            def __call__(self, arguments, **kwargs):
                completed = super().__call__(arguments, **kwargs)
                if arguments[2] == "describe-db-instances":
                    value = json.loads(completed.stdout)
                    value["DBInstances"][0]["PubliclyAccessible"] = True
                    return subprocess.CompletedProcess(
                        arguments, 0, json.dumps(value), ""
                    )
                return completed

        runner = Unsafe()
        with self.assertRaises(BootstrapControlError):
            prepare_runtime_secrets(AwsJson(profile="fincilia-sandbox", runner=runner))
        self.assertFalse(any(call[0][2] == "put-secret-value" for call in runner.calls))


class TofuOutputTests(unittest.TestCase):
    def test_closed_output_is_accepted_without_exposing_identifiers(self) -> None:
        root = Path(tempfile.mkdtemp()) / "aws" / "private-pilot"
        root.mkdir(parents=True)
        value = {
            "task_definition_arn": "arn:aws:ecs:sa-east-1:123456789012:task-definition/bootstrap:1",
            "migration_definition_arn": "arn:aws:ecs:sa-east-1:123456789012:task-definition/migrator:1",
            "subnet_ids": ["subnet-12345678"],
            "security_group_id": "sg-12345678",
            "cluster_arn": "arn:aws:ecs:sa-east-1:123456789012:cluster/fincilia",
            "runtime_plane_enabled": True,
            "services_desired_count": 0,
            "real_data_authorized": False,
        }

        def runner(arguments, **kwargs):
            return subprocess.CompletedProcess(arguments, 0, json.dumps(value), "")

        self.assertEqual(value, read_tofu_output(directory=root, runner=runner))
        value["real_data_authorized"] = True
        with self.assertRaises(BootstrapControlError):
            read_tofu_output(directory=root, runner=runner)


class TaskSequenceTests(unittest.TestCase):
    def test_waiter_uses_the_two_part_aws_cli_command(self) -> None:
        seen = []

        def runner(arguments, **kwargs):
            seen.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, "", "")

        AwsJson(profile="fincilia-sandbox", runner=runner).invoke(
            "ecs",
            "wait-tasks-stopped",
            {"cluster": "cluster", "tasks": ["task"]},
            timeout=900,
        )
        arguments, kwargs = seen[0]
        self.assertEqual(["aws", "ecs", "wait", "tasks-stopped"], arguments[:4])
        self.assertEqual("file:///dev/stdin", arguments[9])
        self.assertFalse(kwargs["shell"])

    def test_bootstrap_finishes_before_migrator_and_never_uses_public_ip(self) -> None:
        class FakeAws:
            def __init__(self) -> None:
                self.calls = []
                self.counter = 0

            def invoke(self, service, operation, payload, **kwargs):
                self.calls.append((service, operation, payload, kwargs))
                if operation == "run-task":
                    self.counter += 1
                    return {"tasks": [{"taskArn": f"arn:aws:ecs:task/{self.counter}"}],
                            "failures": []}
                if operation == "describe-tasks":
                    return {"tasks": [{"containers": [{"exitCode": 0}]}]}
                return {}

        topology = {
            "task_definition_arn": "arn:aws:ecs:task-definition/bootstrap:1",
            "migration_definition_arn": "arn:aws:ecs:task-definition/migrator:1",
            "subnet_ids": ["subnet-private"],
            "security_group_id": "sg-private",
            "cluster_arn": "arn:aws:ecs:cluster/private",
            "runtime_plane_enabled": True,
            "services_desired_count": 0,
            "real_data_authorized": False,
        }
        aws = FakeAws()
        report = bootstrap_and_migrate(aws, topology)
        operations = [item[1] for item in aws.calls]
        self.assertEqual(
            ["run-task", "wait-tasks-stopped", "describe-tasks"] * 2,
            operations,
        )
        launches = [item[2] for item in aws.calls if item[1] == "run-task"]
        self.assertEqual(topology["task_definition_arn"], launches[0]["taskDefinition"])
        self.assertEqual(topology["migration_definition_arn"], launches[1]["taskDefinition"])
        for launch in launches:
            config = launch["networkConfiguration"]["awsvpcConfiguration"]
            self.assertEqual("DISABLED", config["assignPublicIp"])
            self.assertFalse(launch["enableExecuteCommand"])
        self.assertFalse(report["real_data_authorized"])


class InfrastructureContractTests(unittest.TestCase):
    def test_bootstrap_has_separate_iam_secret_and_no_service(self) -> None:
        root = Path(__file__).resolve().parents[2]
        identity = (root / "infra/aws/private-pilot/identity.tf").read_text("utf-8")
        compute = (root / "infra/aws/private-pilot/compute.tf").read_text("utf-8")
        self.assertIn('resource "aws_iam_role" "bootstrap_execution"', identity)
        self.assertIn("aws_db_instance.pilot.master_user_secret[0].secret_arn", identity)
        self.assertIn("aws_secretsmanager_secret.database_roles.arn", identity)
        self.assertIn('resource "aws_ecs_task_definition" "bootstrap"', compute)
        self.assertNotIn('resource "aws_ecs_service" "bootstrap"', compute)
        self.assertIn('value = "false"', compute)
        self.assertIn('assign_public_ip = false', (
            root / "infra/aws/private-pilot/compute.tf"
        ).read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
