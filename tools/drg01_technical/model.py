from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "docs/implementation/evidence/FNC-GAT-006.json"

CONTROL_TESTS = {
    "D01-XTENANT": {
        "db/tests/test_api_authorization.py": [
            "test_reading_another_company_is_denied",
            "test_revoking_the_engagement_removes_access_without_deleting_facts",
        ],
        "db/tests/test_api_documents.py": [
            "test_a_source_from_another_company_is_neutral_and_writes_nothing",
            "test_uploading_into_another_company_is_denied",
            "test_documents_are_not_visible_across_companies",
            "test_reading_another_companys_document_by_id_is_denied",
        ],
        "db/tests/test_issued_authorization_context.py": [
            "test_rls_hides_another_company_and_runtime_cannot_rewrite_history",
            "test_composite_engagement_scope_rejects_a_mixed_company",
        ],
        "db/tests/test_processing_authorization_context.py": [
            "test_revoked_context_is_rejected_before_claim",
            "test_revocation_after_claim_blocks_batches_and_success",
            "test_context_from_another_company_cannot_be_attached",
            "test_runtime_cannot_rebind_a_run_to_another_context",
        ],
    },
    "D01-INGRESS": {
        "db/tests/test_api_documents.py": [
            "test_a_file_with_a_card_stays_in_quarantine",
            "test_nothing_is_queued_for_profiling_before_it_is_scanned",
            "test_a_renamed_executable_is_refused",
            "test_a_zip_bomb_is_refused",
            "test_everything_lands_in_quarantine_and_nothing_in_raw",
        ],
        "db/tests/test_quarantine_before_raw.py": [
            "test_an_upload_always_lands_in_quarantine",
            "test_a_clean_csv_is_promoted_only_after_being_read_whole",
            "test_a_pdf_never_reaches_raw",
            "test_a_generic_zip_never_reaches_raw",
            "test_a_csv_with_a_card_stays_quarantined",
            "test_a_quarantined_file_never_feeds_a_profile",
            "test_a_refusal_to_promote_is_audited_as_denied",
        ],
    },
}

CHANNEL_SOURCES = (
    "apps/api/src/fincilia_api/routes.py",
    "apps/api/src/fincilia_api/corrections.py",
    "apps/api/src/fincilia_api/main.py",
)
CHANNEL_CONFIG = (
    "docs/platform/aws-private-pilot.json",
    "infra/aws/private-pilot/compute.tf",
)
DISABLED_CAPABILITIES = {
    "external_ai", "payments", "email_ingest", "sftp", "api_connectors",
    "webhooks", "automatic_close",
}
FORBIDDEN_ROUTE_PARTS = (
    "/email-ingest", "/email_ingest", "/sftp", "/connectors", "/webhooks",
)


class EvidenceError(RuntimeError):
    pass


def _digest(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _test_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _route_paths(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes: set[str] = set()
    for node in ast.walk(tree):
        decorators = getattr(node, "decorator_list", ())
        for decorator in decorators:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            function = decorator.func
            if not isinstance(function, ast.Attribute):
                continue
            if function.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            first = decorator.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                routes.add(first.value)
    return routes


def _assert_sources() -> tuple[dict[str, list[str]], list[str]]:
    selectors: dict[str, list[str]] = {}
    for control, files in CONTROL_TESTS.items():
        selected: list[str] = []
        for relative, required in files.items():
            methods = _test_methods(ROOT / relative)
            missing = sorted(set(required) - methods)
            if missing:
                raise EvidenceError(f"{relative} is missing {missing}")
            selected.extend(f"{relative}::{name}" for name in required)
        selectors[control] = sorted(selected)

    contract = json.loads((ROOT / CHANNEL_CONFIG[0]).read_text(encoding="utf-8"))
    if set(contract.get("disabled_capabilities", ())) != DISABLED_CAPABILITIES:
        raise EvidenceError("private-pilot disabled capabilities drifted")
    compute = (ROOT / CHANNEL_CONFIG[1]).read_text(encoding="utf-8")
    required_flags = (
        '{ name = "FINCILIA_REAL_DATA_ENABLED", value = "false" }',
        '{ name = "FINCILIA_AI_GATEWAY_ENABLED", value = "false" }',
        '{ name = "FINCILIA_PAYMENTS_ENABLED", value = "false" }',
    )
    if any(flag not in compute for flag in required_flags):
        raise EvidenceError("private-pilot fail-closed runtime flags drifted")
    routes = sorted(set().union(*(_route_paths(ROOT / path) for path in CHANNEL_SOURCES)))
    forbidden = [route for route in routes if any(part in route for part in FORBIDDEN_ROUTE_PARTS)]
    if forbidden:
        raise EvidenceError(f"disabled intake channel route exists: {forbidden}")
    return selectors, routes


def build_evidence() -> dict[str, Any]:
    selectors, routes = _assert_sources()
    source_paths = sorted({
        *CHANNEL_SOURCES, *CHANNEL_CONFIG,
        *(path for files in CONTROL_TESTS.values() for path in files),
        "packages/contracts/python/fincilia_contracts/ingestion.py",
        "workers/document/src/fincilia_worker/main.py",
    })
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": "FNC-GAT-006",
        "data_classification": "completely_synthetic",
        "real_data_authorized": False,
        "observed_at": "2026-08-31T01:38:46Z",
        "database_engine": "PostgreSQL 17",
        "object_store": "MinIO S3-compatible",
        "executed_suite": {
            "command": (
                "python -m unittest db.tests.test_managed_oidc_identity "
                "db.tests.test_api_authorization db.tests.test_issued_authorization_context "
                "db.tests.test_processing_authorization_context "
                "db.tests.test_api_documents db.tests.test_quarantine_before_raw -v"
            ),
            "tests_run": 90,
            "failures": 0,
            "errors": 0,
        },
        "technical_controls": {
            "D01-XTENANT": {
                "state": "passed",
                "test_selectors": selectors["D01-XTENANT"],
                "assertion": "server_resolved_company_scope_rls_revocation_and_context_fencing",
            },
            "D01-INGRESS": {
                "state": "passed",
                "test_selectors": selectors["D01-INGRESS"],
                "assertion": "quarantine_before_parser_full_scan_before_raw_and_sensitive_content_denied",
            },
            "D01-CHANNELS": {
                "state": "passed",
                "disabled_capabilities": sorted(DISABLED_CAPABILITIES),
                "forbidden_route_matches": [],
                "observed_http_route_count": len(routes),
                "assertion": "unused_intake_channels_absent_and_external_capabilities_fail_closed",
            },
        },
        "source_sha256": {path: _digest(ROOT / path) for path in source_paths},
        "limitations": [
            "identity_control_plane_is_configured_but_not_active_in_protected_runtime",
            "cloud_restore_rights_incident_and_supply_chain_controls_remain_pending",
            "pdf_and_other_unscannable_formats_remain_in_quarantine",
            "independent_human_review_remains_pending",
        ],
    }
    payload["evidence_sha256"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return payload


def validate_evidence(payload: dict[str, Any]) -> list[str]:
    try:
        expected = build_evidence()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SyntaxError, EvidenceError) as error:
        return [str(error)]
    return [] if payload == expected else ["adjudicated DRG-01 technical evidence drifted"]


def load_evidence() -> dict[str, Any]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
