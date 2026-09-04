from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "platform" / "aws-image-publication.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-private-pilot.yml"
INFRA_ROOT = ROOT / "infra" / "aws" / "private-pilot"
INFRA_PATH = INFRA_ROOT / "supply-chain.tf"
COMPUTE_PATH = INFRA_ROOT / "compute.tf"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ATTESTATION_SHA = re.compile(r"^[0-9a-f]{64}$")
RUN_URL = re.compile(
    r"^https://github\.com/Nipko/fincilia-platfrom/actions/runs/[1-9][0-9]*$"
)
IMAGE_NAMES = ("api", "web", "worker")
EXPECTED_SUBJECT = (
    "repo:Nipko@16093741/fincilia-platfrom@1342497632:"
    "environment:private-pilot"
)
EXPECTED_ACTIONS = {
    "actions/attest": "a1948c3f048ba23858d222213b7c278aabede763",
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "aws-actions/configure-aws-credentials": (
        "e6de054238d6b7531b4efff3b6587d9aade6a06c"
    ),
}
EXPECTED_REPOSITORY_ACTIONS = {
    "ecr:BatchCheckLayerAvailability",
    "ecr:BatchGetImage",
    "ecr:CompleteLayerUpload",
    "ecr:DescribeImages",
    "ecr:DescribeImageScanFindings",
    "ecr:GetDownloadUrlForLayer",
    "ecr:InitiateLayerUpload",
    "ecr:PutImage",
    "ecr:UploadLayerPart",
}


class PublicationError(ValueError):
    """El contrato o la evidencia no representa una publicación segura."""


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicationError(f"{path.name} debe contener un objeto JSON")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_contract(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_top = {
        "schema_version", "task_id", "status", "data_ceiling",
        "deployment_authorized", "execution_authorized",
        "real_data_authorized", "aws", "github", "actions", "iam",
        "publication", "gate_claims",
    }
    if set(model) != expected_top:
        errors.append("campos superiores del contrato no son exactos")
    if model.get("schema_version") != "1.0.0" or \
            model.get("task_id") != "FNC-SUP-003":
        errors.append("identidad del contrato invalida")
    if model.get("data_ceiling") != "synthetic_only":
        errors.append("la publicacion solo admite datos sinteticos")
    for field in (
        "deployment_authorized", "execution_authorized", "real_data_authorized"
    ):
        if model.get(field) is not False:
            errors.append(f"{field} debe permanecer false")

    aws = model.get("aws", {})
    expected_aws = {
        "account_id": "632144225293",
        "region": "sa-east-1",
        "credential_mode": "github_oidc_temporary_session",
        "maximum_session_seconds": 3600,
        "static_access_keys_allowed": False,
    }
    if aws != expected_aws:
        errors.append("frontera AWS o credenciales temporales derivaron")

    github = model.get("github", {})
    expected_github = {
        "owner": "Nipko",
        "owner_id": "16093741",
        "repository": "fincilia-platfrom",
        "repository_id": "1342497632",
        "environment": "private-pilot",
        "issuer": "https://token.actions.githubusercontent.com",
        "audience": "sts.amazonaws.com",
        "immutable_subject": EXPECTED_SUBJECT,
        "workflow": ".github/workflows/publish-private-pilot.yml",
        "trigger": "workflow_dispatch",
        "trusted_branch": "refs/heads/main",
        "runner": "ubuntu-24.04",
        "permissions": {
            "attestations": "write", "contents": "read", "id-token": "write"
        },
    }
    if github != expected_github:
        errors.append("identidad GitHub OIDC no es exacta e inmutable")
    if model.get("actions") != EXPECTED_ACTIONS:
        errors.append("las Actions no corresponden a los SHA adjudicados")

    iam = model.get("iam", {})
    if iam.get("role_name") != "fincilia-private-pilot-ecr-publisher":
        errors.append("rol publicador inesperado")
    if iam.get("global_actions") != ["ecr:GetAuthorizationToken"]:
        errors.append("acciones ECR globales no son minimas")
    if set(iam.get("repository_actions", [])) != EXPECTED_REPOSITORY_ACTIONS or \
            len(iam.get("repository_actions", [])) != len(EXPECTED_REPOSITORY_ACTIONS):
        errors.append("acciones ECR por repositorio no son exactas")
    expected_arns = [
        f"arn:aws:ecr:sa-east-1:632144225293:repository/"
        f"fincilia/private-pilot/{name}"
        for name in IMAGE_NAMES
    ]
    if iam.get("repository_arns") != expected_arns:
        errors.append("recursos ECR no son los tres repositorios exactos")
    for field in (
        "wildcard_subject_allowed", "repository_delete_allowed",
        "image_delete_allowed", "infrastructure_mutation_allowed",
    ):
        if iam.get(field) is not False:
            errors.append(f"iam.{field} debe permanecer false")

    publication = model.get("publication", {})
    expected_repositories = {
        name: f"fincilia/private-pilot/{name}" for name in IMAGE_NAMES
    }
    if publication.get("repositories") != expected_repositories:
        errors.append("repositorios de publicacion derivaron")
    expected_publication = {
        "tag": "full_release_sha",
        "deployment_reference": "ecr_digest_only",
        "build_test_push_same_run": True,
        "all_three_required": True,
        "scan_status_required": "COMPLETE",
        "maximum_critical_findings": 0,
        "image_attestation_required": True,
        "aggregate_sbom_attestation_required": True,
        "partial_release_deployable": False,
        "deploys_runtime": False,
        "accepts_gates": False,
    }
    for field, expected in expected_publication.items():
        if publication.get(field) != expected:
            errors.append(f"publication.{field} debe ser {expected!r}")
    if model.get("gate_claims") != {
        "DRG-00": "not_met", "DRG-01": "not_met", "GA-01": "not_met"
    }:
        errors.append("los gates deben permanecer not_met")
    return errors


def _source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def validate_sources(
    workflow: str | None = None,
    infra: str | None = None,
    compute: str | None = None,
) -> list[str]:
    workflow = _source(WORKFLOW_PATH) if workflow is None else workflow
    infra = _source(INFRA_PATH) if infra is None else infra
    compute = _source(COMPUTE_PATH) if compute is None else compute
    errors: list[str] = []
    required_workflow = (
        "workflow_dispatch:",
        "environment: private-pilot",
        "runs-on: ubuntu-24.04",
        "contents: read",
        "id-token: write",
        "attestations: write",
        "fetch-depth: 0",
        "git merge-base --is-ancestor",
        'test "$GITHUB_REF" = "refs/heads/main"',
        'test "$RELEASE_SHA" = "$WORKFLOW_SHA"',
        "AWS_PRIVATE_PILOT_PUBLISH_ROLE_ARN",
        "allowed-account-ids: 632144225293",
        "role-duration-seconds: 3600",
        "aws ecr wait image-scan-complete",
        '--image-ids "imageTag=${RELEASE_SHA}"',
        'test "$resolved_digest" = "$digest"',
        '--image-id "imageTag=${RELEASE_SHA}"',
        "tools.aws_image_publication.cli manifest",
        'FINCILIA_REAL_DATA_ENABLED: "false"',
    )
    for token in required_workflow:
        if token not in workflow:
            errors.append(f"workflow no contiene control: {token}")
    for action, pin in EXPECTED_ACTIONS.items():
        reference = f"{action}@{pin}"
        if reference not in workflow:
            errors.append(f"workflow no fija {action} al SHA adjudicado")
    if workflow.count(f"actions/attest@{EXPECTED_ACTIONS['actions/attest']}") != 5:
        errors.append("workflow debe atestar bundle, SBOM y tres imagenes")
    forbidden_workflow = (
        "pull_request:", "pull_request_target:", "schedule:",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "secrets.AWS_",
        "packages: write", "artifact-metadata: write", "tofu apply",
        "aws ecs update-service", "FINCILIA_REAL_DATA_ENABLED=true",
    )
    for token in forbidden_workflow:
        if token in workflow:
            errors.append(f"workflow contiene patron prohibido: {token}")

    required_infra = (
        'resource "aws_iam_openid_connect_provider" "github"',
        'url            = "https://token.actions.githubusercontent.com"',
        'client_id_list = ["sts.amazonaws.com"]',
        'test     = "StringEquals"',
        'variable = "token.actions.githubusercontent.com:aud"',
        'values   = ["sts.amazonaws.com"]',
        'variable = "token.actions.githubusercontent.com:sub"',
        f'github_oidc_subject = "{EXPECTED_SUBJECT}"',
        "values   = [local.github_oidc_subject]",
        'name                 = "fincilia-private-pilot-ecr-publisher"',
        "max_session_duration = 3600",
        'actions   = ["ecr:GetAuthorizationToken"]',
        "resources = [for repository in values(aws_ecr_repository.runtime) : repository.arn]",
        'resource "aws_iam_role_policy" "github_ecr_publisher"',
    )
    for token in required_infra:
        if token not in infra:
            errors.append(f"IaC no contiene control: {token}")
    for action in sorted(EXPECTED_REPOSITORY_ACTIONS):
        if f'"{action}"' not in infra:
            errors.append(f"IaC no declara accion minima: {action}")
    observed_ecr_actions = re.findall(r'"(ecr:[A-Za-z*]+)"', infra)
    expected_ecr_actions = EXPECTED_REPOSITORY_ACTIONS | {
        "ecr:GetAuthorizationToken"
    }
    if set(observed_ecr_actions) != expected_ecr_actions or \
            len(observed_ecr_actions) != len(expected_ecr_actions):
        errors.append("IaC contiene acciones ECR adicionales o duplicadas")
    if 'repositories = toset(["api", "web", "worker"])' not in compute:
        errors.append("compute.tf no fija los tres repositorios exactos")
    forbidden_infra = (
        "StringLike", "ecr:DeleteRepository", "ecr:BatchDeleteImage",
        'Action = "ecr:*"', 'actions = ["ecr:*"]', "sts:AssumeRole\"",
    )
    for token in forbidden_infra:
        if token in infra:
            errors.append(f"IaC contiene patron prohibido: {token}")
    return errors


def _policy_document(value: Any, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None, f"{label} no contiene JSON valido"
    if not isinstance(value, dict):
        return None, f"{label} no es un documento IAM conocido"
    return value, None


def _statements(document: dict[str, Any]) -> list[dict[str, Any]]:
    statements = document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or any(
        not isinstance(statement, dict) for statement in statements
    ):
        return []
    return statements


def _as_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return set()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    changes = {
        str(item.get("address")): item
        for item in plan.get("resource_changes", [])
        if item.get("mode", "managed") == "managed"
    }
    expected_addresses = {
        "aws_iam_openid_connect_provider.github",
        "aws_iam_role.github_ecr_publisher",
        "aws_iam_role_policy.github_ecr_publisher",
    }
    for address in sorted(expected_addresses - set(changes)):
        errors.append(f"plan no contiene {address}")
    if errors:
        return errors

    for address in sorted(expected_addresses):
        actions = changes[address].get("change", {}).get("actions", [])
        if "delete" in actions and "create" not in actions:
            errors.append(f"{address} no puede borrarse")

    provider = changes[
        "aws_iam_openid_connect_provider.github"
    ].get("change", {}).get("after") or {}
    # Creation plans retain the configured HTTPS URL. After AWS refreshes the
    # resource, the provider normalizes that same issuer by omitting the scheme.
    # These are the only two equivalent forms accepted for resumable applies.
    if provider.get("url") not in {
        "https://token.actions.githubusercontent.com",
        "token.actions.githubusercontent.com",
    } or \
            provider.get("client_id_list") != ["sts.amazonaws.com"]:
        errors.append("plan OIDC no fija issuer y audience exactos")

    role = changes["aws_iam_role.github_ecr_publisher"].get(
        "change", {}
    ).get("after") or {}
    if role.get("name") != "fincilia-private-pilot-ecr-publisher" or \
            role.get("max_session_duration") != 3600:
        errors.append("plan del rol publicador deriva en nombre o duracion")
    role_unknown = changes["aws_iam_role.github_ecr_publisher"].get(
        "change", {}
    ).get("after_unknown") or {}
    trust = None
    if role.get("assume_role_policy") is None and \
            role_unknown.get("assume_role_policy") is True:
        pass
    else:
        trust, trust_error = _policy_document(
            role.get("assume_role_policy"), "trust policy"
        )
        if trust_error:
            errors.append(trust_error)
    if trust is not None:
        statements = _statements(trust)
        expected_condition = {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": EXPECTED_SUBJECT,
        }
        valid = len(statements) == 1
        if valid:
            statement = statements[0]
            principal = statement.get("Principal", {})
            federated = principal.get("Federated") if isinstance(principal, dict) else None
            valid = (
                statement.get("Effect") == "Allow"
                and _as_set(statement.get("Action")) == {
                    "sts:AssumeRoleWithWebIdentity"
                }
                and isinstance(federated, str)
                and federated.endswith(
                    ":oidc-provider/token.actions.githubusercontent.com"
                )
                and statement.get("Condition") == {
                    "StringEquals": expected_condition
                }
            )
        if not valid:
            errors.append("trust policy planificada no es exacta")

    policy_value = changes["aws_iam_role_policy.github_ecr_publisher"].get(
        "change", {}
    ).get("after") or {}
    policy_unknown = changes[
        "aws_iam_role_policy.github_ecr_publisher"
    ].get("change", {}).get("after_unknown") or {}
    policy = None
    if policy_value.get("policy") is None and policy_unknown.get("policy") is True:
        pass
    else:
        policy, policy_error = _policy_document(
            policy_value.get("policy"), "policy ECR"
        )
        if policy_error:
            errors.append(policy_error)
    if policy is not None:
        statements = _statements(policy)
        global_statements = [
            item for item in statements
            if _as_set(item.get("Action")) == {"ecr:GetAuthorizationToken"}
        ]
        repository_statements = [
            item for item in statements
            if _as_set(item.get("Action")) == EXPECTED_REPOSITORY_ACTIONS
        ]
        expected_arns = {
            f"arn:aws:ecr:sa-east-1:632144225293:repository/"
            f"fincilia/private-pilot/{name}"
            for name in IMAGE_NAMES
        }
        if len(statements) != 2 or len(global_statements) != 1 or \
                global_statements[0].get("Effect") != "Allow" or \
                _as_set(global_statements[0].get("Resource")) != {"*"} or \
                len(repository_statements) != 1 or \
                repository_statements[0].get("Effect") != "Allow" or \
                _as_set(repository_statements[0].get("Resource")) != expected_arns:
            errors.append("policy ECR planificada no es minima y exacta")
    return errors


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PublicationError(f"{label} debe ser entero no negativo")
    return value


def build_manifest(
    release_sha: str,
    run_url: str,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not SHA40.fullmatch(release_sha):
        raise PublicationError("release_sha debe ser un SHA Git completo")
    if not RUN_URL.fullmatch(run_url):
        raise PublicationError("run_url no corresponde al repositorio Fincilia")
    if len(observations) != len(IMAGE_NAMES):
        raise PublicationError("se requieren exactamente tres observaciones")

    by_name: dict[str, dict[str, Any]] = {}
    for item in observations:
        if not isinstance(item, dict) or item.get("name") not in IMAGE_NAMES:
            raise PublicationError("nombre de imagen desconocido")
        name = str(item["name"])
        if name in by_name:
            raise PublicationError(f"imagen duplicada: {name}")
        expected_repository = f"fincilia/private-pilot/{name}"
        if item.get("repository") != expected_repository:
            raise PublicationError(f"repositorio inesperado para {name}")
        if item.get("tag") != release_sha:
            raise PublicationError(f"tag no corresponde al release para {name}")
        digest = item.get("digest")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise PublicationError(f"digest invalido para {name}")
        if item.get("scan_status") != "COMPLETE":
            raise PublicationError(f"escaneo incompleto para {name}")
        counts = item.get("severity_counts")
        if not isinstance(counts, dict):
            raise PublicationError(f"severidades invalidas para {name}")
        normalized_counts = {
            severity: _nonnegative_int(counts.get(severity, 0), f"{name}.{severity}")
            for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL", "UNDEFINED")
        }
        if normalized_counts["CRITICAL"] != 0:
            raise PublicationError(f"{name} contiene vulnerabilidades CRITICAL")
        attestation = item.get("attestation_bundle_sha256")
        if not isinstance(attestation, str) or not ATTESTATION_SHA.fullmatch(attestation):
            raise PublicationError(f"attestation invalida para {name}")
        by_name[name] = {
            "attestation_bundle_sha256": attestation,
            "digest": digest,
            "image": (
                "632144225293.dkr.ecr.sa-east-1.amazonaws.com/"
                f"{expected_repository}@{digest}"
            ),
            "name": name,
            "repository": expected_repository,
            "scan_status": "COMPLETE",
            "severity_counts": normalized_counts,
            "tag": release_sha,
        }
    if set(by_name) != set(IMAGE_NAMES):
        raise PublicationError("faltan imagenes api, web o worker")
    return {
        "schema_version": "1.0.0",
        "task_id": "FNC-SUP-003",
        "release_sha": release_sha,
        "run_url": run_url,
        "account_id": "632144225293",
        "region": "sa-east-1",
        "complete": True,
        "deployable": False,
        "real_data_authorized": False,
        "images": [by_name[name] for name in IMAGE_NAMES],
    }


def validate_manifest(value: dict[str, Any]) -> list[str]:
    try:
        expected = build_manifest(
            str(value.get("release_sha", "")),
            str(value.get("run_url", "")),
            value.get("images", []),
        )
    except PublicationError as exc:
        return [str(exc)]
    return [] if value == expected else ["manifiesto contiene campos o valores no canonicos"]


def validate(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    model = load_json(CONTRACT_PATH)
    contract_errors = validate_contract(model)
    source_errors = validate_sources()
    plan_errors = validate_plan(plan) if plan is not None else []
    errors = contract_errors + source_errors + plan_errors
    return {
        "ok": not errors,
        "errors": errors,
        "report": {
            "contract_valid": not contract_errors,
            "sources_valid": not source_errors,
            "plan_valid": plan is None or not plan_errors,
            "execution_authorized": False,
            "deployment_authorized": False,
            "real_data_authorized": False,
        },
    }
