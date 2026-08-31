from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from .cli import main
from .model import (
    CONTRACT_PATH,
    EXPECTED_SUBJECT,
    PublicationError,
    build_manifest,
    load_json,
    validate_contract,
    validate_manifest,
    validate_plan,
    validate_sources,
)


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
RUN_URL = "https://github.com/Nipko/fincilia-platfrom/actions/runs/123"


class PublicationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_json(CONTRACT_PATH)

    def mutate(self, *path: str, value: object) -> dict:
        model = copy.deepcopy(self.model)
        cursor = model
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        return model

    def test_repository_contract_and_sources_are_valid(self) -> None:
        self.assertEqual([], validate_contract(self.model))
        self.assertEqual([], validate_sources())

    def test_execution_and_real_data_cannot_be_self_authorized(self) -> None:
        for field in (
            "execution_authorized", "deployment_authorized", "real_data_authorized"
        ):
            errors = validate_contract(self.mutate(field, value=True))
            self.assertTrue(any(field in item for item in errors))

    def test_immutable_subject_bites_name_only_or_wildcard_trust(self) -> None:
        for subject in (
            "repo:Nipko/fincilia-platfrom:environment:private-pilot",
            "repo:Nipko@16093741/fincilia-platfrom@1342497632:*",
        ):
            errors = validate_contract(
                self.mutate("github", "immutable_subject", value=subject)
            )
            self.assertTrue(any("inmutable" in item for item in errors))

    def test_wrong_audience_or_account_bites(self) -> None:
        self.assertTrue(validate_contract(
            self.mutate("github", "audience", value="api://anything")
        ))
        self.assertTrue(validate_contract(
            self.mutate("aws", "account_id", value="000000000000")
        ))

    def test_static_keys_and_long_session_bite(self) -> None:
        self.assertTrue(validate_contract(
            self.mutate("aws", "static_access_keys_allowed", value=True)
        ))
        self.assertTrue(validate_contract(
            self.mutate("aws", "maximum_session_seconds", value=43200)
        ))

    def test_extra_ecr_permission_or_resource_bites(self) -> None:
        model = copy.deepcopy(self.model)
        model["iam"]["repository_actions"].append("ecr:DeleteRepository")
        self.assertTrue(any("acciones ECR" in item for item in validate_contract(model)))
        model = copy.deepcopy(self.model)
        model["iam"]["repository_arns"].append("*")
        self.assertTrue(any("recursos ECR" in item for item in validate_contract(model)))

    def test_unpinned_action_bites(self) -> None:
        errors = validate_contract(self.mutate(
            "actions", "actions/attest", value="v4"
        ))
        self.assertTrue(any("SHA" in item for item in errors))

    def test_automatic_trigger_or_static_key_in_workflow_bites(self) -> None:
        errors = validate_sources(
            workflow="workflow_dispatch:\npull_request:\nAWS_ACCESS_KEY_ID\n",
            infra="",
        )
        self.assertTrue(any("pull_request" in item for item in errors))
        self.assertTrue(any("AWS_ACCESS_KEY_ID" in item for item in errors))

    def test_stringlike_delete_and_wildcard_policy_bite(self) -> None:
        errors = validate_sources(
            workflow="",
            infra=(
                "StringLike\n"
                "ecr:DeleteRepository\n"
                'actions = ["ecr:*"]\n'
            ),
        )
        self.assertTrue(any("StringLike" in item for item in errors))
        self.assertTrue(any("DeleteRepository" in item for item in errors))
        self.assertTrue(any('ecr:*' in item for item in errors))

    def test_unlisted_ecr_action_in_source_bites(self) -> None:
        from .model import INFRA_PATH, WORKFLOW_PATH

        infra = INFRA_PATH.read_text(encoding="utf-8") + \
            '\nactions = ["ecr:SetRepositoryPolicy"]\n'
        errors = validate_sources(
            workflow=WORKFLOW_PATH.read_text(encoding="utf-8"), infra=infra
        )
        self.assertTrue(any("adicionales" in item for item in errors))

    def valid_plan(self) -> dict:
        account = "632144225293"
        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Principal": {
                    "Federated": (
                        f"arn:aws:iam::{account}:oidc-provider/"
                        "token.actions.githubusercontent.com"
                    )
                },
                "Condition": {"StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": EXPECTED_SUBJECT,
                }},
            }],
        }
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ecr:GetAuthorizationToken",
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": self.model["iam"]["repository_actions"],
                    "Resource": self.model["iam"]["repository_arns"],
                },
            ],
        }
        return {"resource_changes": [
            {
                "address": "aws_iam_openid_connect_provider.github",
                "mode": "managed",
                "change": {"actions": ["create"], "after": {
                    "url": "https://token.actions.githubusercontent.com",
                    "client_id_list": ["sts.amazonaws.com"],
                }},
            },
            {
                "address": "aws_iam_role.github_ecr_publisher",
                "mode": "managed",
                "change": {"actions": ["create"], "after": {
                    "name": "fincilia-private-pilot-ecr-publisher",
                    "max_session_duration": 3600,
                    "assume_role_policy": json.dumps(trust),
                }},
            },
            {
                "address": "aws_iam_role_policy.github_ecr_publisher",
                "mode": "managed",
                "change": {"actions": ["create"], "after": {
                    "policy": json.dumps(policy),
                }},
            },
        ]}

    def test_exact_oidc_and_ecr_plan_is_valid(self) -> None:
        self.assertEqual([], validate_plan(self.valid_plan()))

    def test_provider_deferred_policies_are_valid_only_when_marked_unknown(self) -> None:
        plan = self.valid_plan()
        role = plan["resource_changes"][1]["change"]
        role["after"].pop("assume_role_policy")
        role["after_unknown"] = {"assume_role_policy": True}
        policy = plan["resource_changes"][2]["change"]
        policy["after"].pop("policy")
        policy["after_unknown"] = {"policy": True}
        self.assertEqual([], validate_plan(plan))

        role["after_unknown"] = {}
        self.assertTrue(any("trust policy" in item for item in validate_plan(plan)))

    def test_missing_or_deleted_control_plane_resource_bites(self) -> None:
        plan = self.valid_plan()
        plan["resource_changes"] = plan["resource_changes"][1:]
        self.assertTrue(any("openid" in item for item in validate_plan(plan)))
        plan = self.valid_plan()
        plan["resource_changes"][1]["change"]["actions"] = ["delete"]
        self.assertTrue(any("no puede borrarse" in item for item in validate_plan(plan)))

    def test_plan_subject_audience_and_duration_mutations_bite(self) -> None:
        plan = self.valid_plan()
        trust = json.loads(plan["resource_changes"][1]["change"]["after"][
            "assume_role_policy"
        ])
        trust["Statement"][0]["Condition"]["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ] = "repo:Nipko/fincilia-platfrom:*"
        plan["resource_changes"][1]["change"]["after"][
            "assume_role_policy"
        ] = json.dumps(trust)
        self.assertTrue(any("trust policy" in item for item in validate_plan(plan)))

        plan = self.valid_plan()
        plan["resource_changes"][0]["change"]["after"]["client_id_list"] = [
            "other"
        ]
        self.assertTrue(any("audience" in item for item in validate_plan(plan)))

        plan = self.valid_plan()
        plan["resource_changes"][1]["change"]["after"][
            "max_session_duration"
        ] = 43200
        self.assertTrue(any("duracion" in item for item in validate_plan(plan)))

    def test_plan_extra_permission_or_repository_bites(self) -> None:
        plan = self.valid_plan()
        policy = json.loads(plan["resource_changes"][2]["change"]["after"][
            "policy"
        ])
        policy["Statement"][1]["Action"].append("ecr:DeleteRepository")
        plan["resource_changes"][2]["change"]["after"]["policy"] = json.dumps(
            policy
        )
        self.assertTrue(any("policy ECR" in item for item in validate_plan(plan)))

        plan = self.valid_plan()
        policy = json.loads(plan["resource_changes"][2]["change"]["after"][
            "policy"
        ])
        policy["Statement"][1]["Resource"].append("*")
        plan["resource_changes"][2]["change"]["after"]["policy"] = json.dumps(
            policy
        )
        self.assertTrue(any("policy ECR" in item for item in validate_plan(plan)))


class PublicationManifestTests(unittest.TestCase):
    def observation(self, name: str, **overrides: object) -> dict:
        value = {
            "name": name,
            "repository": f"fincilia/private-pilot/{name}",
            "tag": SHA,
            "digest": DIGEST,
            "scan_status": "COMPLETE",
            "severity_counts": {"CRITICAL": 0, "HIGH": 1},
            "attestation_bundle_sha256": "c" * 64,
        }
        value.update(overrides)
        return value

    def observations(self) -> list[dict]:
        return [self.observation(name) for name in ("api", "web", "worker")]

    def test_complete_manifest_is_canonical_and_not_deployable(self) -> None:
        manifest = build_manifest(SHA, RUN_URL, self.observations())
        self.assertEqual([], validate_manifest(manifest))
        self.assertTrue(manifest["complete"])
        self.assertFalse(manifest["deployable"])
        self.assertFalse(manifest["real_data_authorized"])
        self.assertEqual(["api", "web", "worker"], [
            item["name"] for item in manifest["images"]
        ])

    def test_partial_duplicate_or_unknown_image_bites(self) -> None:
        for observations in (
            self.observations()[:2],
            [self.observation("api"), self.observation("api"), self.observation("web")],
            [self.observation("api"), self.observation("web"), {"name": "other"}],
        ):
            with self.assertRaises(PublicationError):
                build_manifest(SHA, RUN_URL, observations)

    def test_tag_repository_and_digest_are_exact(self) -> None:
        cases = (
            self.observation("api", tag="short"),
            self.observation("api", repository="other/api"),
            self.observation("api", digest="sha256:bad"),
        )
        for bad in cases:
            with self.assertRaises(PublicationError):
                build_manifest(
                    SHA, RUN_URL,
                    [bad, self.observation("web"), self.observation("worker")],
                )

    def test_incomplete_scan_or_critical_finding_bites(self) -> None:
        for bad in (
            self.observation("api", scan_status="IN_PROGRESS"),
            self.observation("api", severity_counts={"CRITICAL": 1}),
        ):
            with self.assertRaises(PublicationError):
                build_manifest(
                    SHA, RUN_URL,
                    [bad, self.observation("web"), self.observation("worker")],
                )

    def test_boolean_or_negative_count_bites(self) -> None:
        for count in (True, -1, 1.5):
            bad = self.observation("api", severity_counts={"CRITICAL": count})
            with self.assertRaises(PublicationError):
                build_manifest(
                    SHA, RUN_URL,
                    [bad, self.observation("web"), self.observation("worker")],
                )

    def test_extra_manifest_field_bites(self) -> None:
        manifest = build_manifest(SHA, RUN_URL, self.observations())
        manifest["approved"] = True
        self.assertTrue(validate_manifest(manifest))

    def test_cli_builds_and_verifies_manifest_from_scan_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "manifest.json"
            arguments = [
                "manifest", "--release-sha", SHA, "--run-url", RUN_URL,
                "--output", str(output),
            ]
            for name in ("api", "web", "worker"):
                scan = root / f"{name}-scan.json"
                scan.write_text(json.dumps({
                    "repositoryName": f"fincilia/private-pilot/{name}",
                    "imageId": {"imageDigest": DIGEST, "imageTag": SHA},
                    "imageScanStatus": {"status": "COMPLETE"},
                    "imageScanFindings": {
                        "findingSeverityCounts": {"CRITICAL": 0, "LOW": 2}
                    },
                }), encoding="utf-8")
                attestation = root / f"{name}.sigstore.json"
                attestation.write_text(f"attestation-{name}\n", encoding="utf-8")
                arguments.extend([
                    f"--{name}-digest", DIGEST,
                    f"--{name}-scan", str(scan),
                    f"--{name}-attestation", str(attestation),
                ])
            self.assertEqual(0, main(arguments))
            self.assertEqual(0, main([
                "verify-manifest", "--manifest", str(output)
            ]))

    def test_cli_refuses_missing_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan = root / "scan.json"
            scan.write_text(json.dumps({
                "repositoryName": "fincilia/private-pilot/api",
                "imageId": {"imageDigest": DIGEST, "imageTag": SHA},
                "imageScanStatus": {"status": "COMPLETE"},
                "imageScanFindings": {"findingSeverityCounts": {}},
            }), encoding="utf-8")
            arguments = [
                "manifest", "--release-sha", SHA, "--run-url", RUN_URL,
                "--output", str(root / "manifest.json"),
            ]
            for name in ("api", "web", "worker"):
                arguments.extend([
                    f"--{name}-digest", DIGEST,
                    f"--{name}-scan", str(scan),
                    f"--{name}-attestation", str(root / "missing"),
                ])
            self.assertEqual(1, main(arguments))

    def test_cli_refuses_scan_for_different_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan = root / "scan.json"
            scan.write_text(json.dumps({
                "repositoryName": "fincilia/private-pilot/api",
                "imageId": {
                    "imageDigest": "sha256:" + "d" * 64,
                    "imageTag": SHA,
                },
                "imageScanStatus": {"status": "COMPLETE"},
                "imageScanFindings": {"findingSeverityCounts": {}},
            }), encoding="utf-8")
            attestation = root / "attestation.json"
            attestation.write_text("synthetic\n", encoding="utf-8")
            arguments = [
                "manifest", "--release-sha", SHA, "--run-url", RUN_URL,
                "--output", str(root / "manifest.json"),
            ]
            for name in ("api", "web", "worker"):
                arguments.extend([
                    f"--{name}-digest", DIGEST,
                    f"--{name}-scan", str(scan),
                    f"--{name}-attestation", str(attestation),
                ])
            self.assertEqual(1, main(arguments))

    def test_subject_constant_is_the_immutable_repository_environment(self) -> None:
        self.assertEqual(
            "repo:Nipko@16093741/fincilia-platfrom@1342497632:"
            "environment:private-pilot",
            EXPECTED_SUBJECT,
        )


if __name__ == "__main__":
    unittest.main()
