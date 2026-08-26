"""Valida el contrato ejecutable del spike FNC-DB-004."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "docs/database/concurrency-spike.json"
EXPECTED_TESTS = {"TST-IDEM-001", "TST-IDEM-004", "TST-IDEM-005"}
EXPECTED_PROJECT = "fincilia-concurrency-spike"
EXPECTED_IMAGE = (
    "postgres:17.11-alpine3.24@sha256:"
    "18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
)
EXPECTED_FUNCTIONS = {
    "fnc_lab.claim_work(text,integer)",
    "fnc_lab.commit_effect(text,text,bigint,text,boolean)",
    "fnc_lab.claim_outbox(text)",
    "fnc_lab.ack_outbox(bigint,text)",
}


def load_model(path: Path = DEFAULT_MODEL) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_model(model: dict[str, Any], *, root: Path = ROOT) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def fail(code: str, location: str, detail: str) -> None:
        findings.append({"code": code, "location": location, "detail": detail})

    if model.get("schema_version") != 1 or model.get("task_id") != "FNC-DB-004":
        fail("CSP-IDENTITY", "$", "schema_version and task_id must identify FNC-DB-004")
    if model.get("status") not in {"in_progress", "review_pending"}:
        fail("CSP-STATUS", "status", "the spike may only be in progress or pending review")
    if model.get("human_acceptance") != "pending":
        fail("CSP-HUMAN", "human_acceptance", "an agent cannot accept this spike")
    if model.get("data_ceiling") != "synthetic_only":
        fail("CSP-DATA", "data_ceiling", "only synthetic data is allowed")

    runtime = model.get("runtime") if isinstance(model.get("runtime"), dict) else {}
    if runtime.get("project") != EXPECTED_PROJECT:
        fail("CSP-PROJECT", "runtime.project", "cleanup must remain confined to the spike project")
    if runtime.get("service") != "postgres" or runtime.get("image") != EXPECTED_IMAGE:
        fail("CSP-RUNTIME", "runtime", "PostgreSQL service and pinned image changed")
    if runtime.get("published_ports") is not False or runtime.get("internal_network") is not True:
        fail("CSP-NETWORK", "runtime", "the laboratory must not publish ports and must use an internal network")
    if runtime.get("cleanup_with_volumes") is not True:
        fail("CSP-CLEANUP", "runtime.cleanup_with_volumes", "ephemeral state must be removed by the confined runner")

    compose_value = runtime.get("compose")
    compose_path = root / compose_value if isinstance(compose_value, str) else None
    if compose_path is None or not compose_path.is_file():
        fail("CSP-COMPOSE", "runtime.compose", "compose file is missing")
    else:
        compose = compose_path.read_text(encoding="utf-8")
        if "ports:" in compose or f"name: {EXPECTED_PROJECT}" not in compose:
            fail("CSP-COMPOSE-SCOPE", "runtime.compose", "compose publishes ports or changes project")
        if EXPECTED_IMAGE not in compose or "internal: true" not in compose:
            fail("CSP-COMPOSE-PIN", "runtime.compose", "image pin or internal network is absent")

    roles = model.get("roles") if isinstance(model.get("roles"), dict) else {}
    if roles.get("runtime_direct_table_writes") is not False or roles.get("runtime_ddl") is not False:
        fail("CSP-PRIVILEGES", "roles", "runtime must not write tables directly or execute DDL")
    if set(roles.get("runtime_function_allowlist", [])) != EXPECTED_FUNCTIONS:
        fail("CSP-FUNCTIONS", "roles.runtime_function_allowlist", "runtime function surface changed")

    cases = model.get("cases") if isinstance(model.get("cases"), list) else []
    if {case.get("id") for case in cases if isinstance(case, dict)} != EXPECTED_TESTS:
        fail("CSP-CASES", "cases", "exactly the three PostgreSQL idempotency tests are required")
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not case.get("marker") or not case.get("rule"):
            fail("CSP-CASE", f"cases[{index}]", "each case needs marker and rule")

    safety = model.get("safety") if isinstance(model.get("safety"), dict) else {}
    required_true = {
        "argv_allowlisted", "environment_allowlisted", "output_bounded",
        "cleanup_project_confined", "real_data_forbidden",
    }
    for key in required_true:
        if safety.get(key) is not True:
            fail("CSP-SAFETY", f"safety.{key}", "required safety control is disabled")
    if safety.get("shell") is not False or safety.get("product_migrations_modified") is not False:
        fail("CSP-SAFETY", "safety", "shell and product migrations must remain disabled")
    if safety.get("agent_may_accept_architecture") is not False:
        fail("CSP-AUTHORITY", "safety.agent_may_accept_architecture", "agent acceptance is forbidden")

    bootstrap = root / "spikes/FNC-DB-004/db/init/001_bootstrap.sql"
    if not bootstrap.is_file():
        fail("CSP-SQL", "bootstrap", "bootstrap SQL is missing")
    else:
        sql = bootstrap.read_text(encoding="utf-8")
        for token in ("FOR UPDATE SKIP LOCKED", "fencing_counter", "SECURITY DEFINER",
                      "REVOKE ALL ON ALL TABLES", "fnc_lab.outbox_event",
                      "fnc_lab.delivery_receipt"):
            if token not in sql:
                fail("CSP-SQL-GUARD", "bootstrap", f"required SQL guard is absent: {token}")
    return findings


def main() -> int:
    findings = validate_model(load_model())
    print(json.dumps({"ok": not findings, "errors": findings}, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
