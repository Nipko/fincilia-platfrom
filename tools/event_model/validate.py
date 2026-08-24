from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_PRINCIPLES = {
    "EVT-DOMAIN-FIRST", "EVT-AT-LEAST-ONCE", "EVT-OUTBOX-ATOMIC", "EVT-INBOX-ATOMIC",
    "EVT-NO-GLOBAL-ORDER", "RET-ONE-OWNER", "RET-BOUNDED", "RET-ADAPTER-CLASSIFIES",
    "DLQ-VISIBLE", "EXT-NO-BLIND-RETRY", "EXE-SEPARATE-TRUTHS", "EVT-MINIMIZED",
}
REQUIRED_ENTITIES = {"outbox_event", "inbox_receipt", "job_definition", "delivery_attempt", "dead_letter_item"}
REQUIRED_WORK_CLASSES = {
    "outbox_dispatch", "stateless_job", "durable_workflow", "external_idempotent_effect",
    "external_non_idempotent_effect",
}
REQUIRED_TESTS = {
    "TST-OUT-001", "TST-OUT-002", "TST-OUT-003", "TST-OUT-004", "TST-OUT-005",
    "TST-RET-001", "TST-RET-002", "TST-RET-003", "TST-RET-004", "TST-RET-005",
    "TST-DLQ-001", "TST-DLQ-002", "TST-DLQ-003", "TST-ORD-001", "TST-SCH-001",
    "TST-EXT-001", "TST-EXE-001", "TST-EXE-002", "TST-AUTH-001", "TST-TEN-002",
    "TST-CHK-001", "TST-CHK-002", "TST-CHK-003",
}
REQUIRED_EVENT_FIELDS = {
    "event_id", "event_name", "schema_id", "schema_version", "producer_module",
    "occurred_at", "recorded_at", "aggregate_type", "aggregate_id", "aggregate_version",
    "company_scope", "purpose", "classification", "correlation_id", "causation_id",
    "trace_id", "idempotency_key_hash", "payload_digest", "payload_or_reference",
}
REQUIRED_ATTEMPT_FIELDS = {
    "attempt_id", "work_id", "company_scope", "attempt_number", "owner", "started_at",
    "finished_at", "outcome", "failure_class", "reason_code", "policy_version",
    "fencing_token", "cost_bucket", "trace_id",
}
REQUIRED_RETRY_FIELDS = {
    "policy_id", "version", "work_class", "max_attempts", "max_elapsed_time",
    "attempt_timeout", "deadline", "cost_budget", "backoff_strategy",
    "retryable_reason_codes", "exhaustion_action", "owner", "reviewer",
}
REQUIRED_DLQ_FIELDS = {
    "dead_letter_id", "company_scope", "work_class", "work_id", "event_schema_version",
    "payload_digest_or_reference", "failure_class", "reason_code", "attempt_count",
    "first_failed_at", "last_failed_at", "retry_policy_version", "owner",
    "resolution_state", "audit_event_id",
}
REQUIRED_CHECKPOINT_INVARIANTS = {
    "CHK-SAME-TRANSACTION", "CHK-RESERVED-BEFORE-EFFECT", "CHK-POSTGRESQL-AUTHORITY",
    "CHK-VALKEY-NEVER-AUTHORITY", "CHK-ONE-RETRY-OWNER", "CHK-IDEMPOTENT-RESUME",
    "CHK-NOT-FINANCIAL", "CHK-EXHAUSTION-VISIBLE",
}
REQUIRED_CHECKPOINT_FIELDS = {
    "chunk_id", "chunk_ordinal", "company_id", "completed_at", "dataset_version_id",
    "first_record", "last_record", "movement_count", "rejected_count",
}
REQUIRED_REPLAY = {
    "current_authorization_revalidated", "original_schema_available_or_explicit_migration",
    "same_effect_idempotency_key", "budget_and_policy_selected_explicitly",
    "human_approval_when_external_or_financial", "new_delivery_attempt",
}


@dataclass(frozen=True, order=True)
class EventModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {item["id"]: item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _owner(architecture: dict[str, Any], entity_id: str) -> str | None:
    for module in architecture.get("modules", []):
        if entity_id in module.get("owns", []):
            return module.get("id")
    return None


def _exact_ids(
    errors: list[EventModelError], items: Any, expected: set[str], location: str, code: str
) -> None:
    actual = _ids(items)
    if set(actual) != expected or len(actual) != len(expected):
        errors.append(EventModelError(code, location, f"ids must be exact; got {actual}"))


def validate_model(
    model: dict[str, Any],
    architecture: dict[str, Any],
    idempotency: dict[str, Any],
    dfd: dict[str, Any],
    threat_model: dict[str, Any],
) -> list[EventModelError]:
    errors: list[EventModelError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(EventModelError(code, location, message))

    if model.get("schema_version") != 1 or model.get("task_id") != "FNC-ARC-004":
        fail("EVT-METADATA", "$", "schema version 1 and task FNC-ARC-004 are required")
    if model.get("status") != "review_pending" or model.get("human_acceptance") != "pending":
        fail("EVT-ACCEPTANCE", "$", "human acceptance must remain pending")
    if model.get("data_ceiling") != "synthetic_only":
        fail("EVT-DATA-CEILING", "data_ceiling", "only synthetic data is allowed")
    if model.get("provider_selection") != "pending_human":
        fail("EVT-PROVIDER", "provider_selection", "queue/workflow provider cannot be selected by this task")

    _exact_ids(errors, model.get("principles"), REQUIRED_PRINCIPLES, "principles", "EVT-PRINCIPLES")
    _exact_ids(errors, model.get("owned_entities"), REQUIRED_ENTITIES, "owned_entities", "EVT-ENTITIES")
    _exact_ids(errors, model.get("work_classes"), REQUIRED_WORK_CLASSES, "work_classes", "EVT-WORK-CLASSES")
    _exact_ids(errors, model.get("required_tests"), REQUIRED_TESTS, "required_tests", "EVT-TEST-COVERAGE")

    for entity in model.get("owned_entities", []):
        entity_id = entity.get("id")
        if entity.get("owner_module") != "platform" or _owner(architecture, entity_id) != "platform":
            fail("EVT-OWNER", f"owned_entities.{entity_id}", "Platform must be the unique conceptual owner")

    envelope = model.get("event_envelope", {})
    if set(envelope.get("required_fields", [])) != REQUIRED_EVENT_FIELDS:
        fail("EVT-ENVELOPE-FIELDS", "event_envelope.required_fields", "event envelope fields are incomplete")
    if envelope.get("immutable") is not True or envelope.get("company_scope_source") != "server_verified_authorization_context_or_explicit_platform_scope":
        fail("EVT-ENVELOPE-SCOPE", "event_envelope", "event must be immutable and server scoped")
    if set(envelope.get("forbidden_classes", [])) != {"secret", "prohibited"}:
        fail("EVT-ENVELOPE-CLASS", "event_envelope.forbidden_classes", "secret and prohibited must remain forbidden")
    if not {"raw_payload", "credential", "token", "account_number", "tax_id", "financial_reference", "amount"} <= set(envelope.get("forbidden_metadata", [])):
        fail("EVT-ENVELOPE-MINIMIZATION", "event_envelope.forbidden_metadata", "sensitive metadata denylist is incomplete")
    if envelope.get("unknown_schema_action") != "dead_letter_without_domain_effect":
        fail("EVT-UNKNOWN-SCHEMA", "event_envelope.unknown_schema_action", "unknown schema must have no effect")

    outbox = model.get("outbox_contract", {})
    if set(outbox.get("states", [])) != {"pending", "claimed", "published", "retry_scheduled", "terminal_failed"}:
        fail("EVT-OUTBOX-STATES", "outbox_contract.states", "outbox states changed")
    if outbox.get("domain_and_outbox_transaction") != "same_postgresql_transaction":
        fail("EVT-OUTBOX-ATOMIC", "outbox_contract", "domain and outbox must commit together")
    if outbox.get("producer_access") != "platform_port_inside_originating_transaction_no_direct_repository":
        fail("EVT-OUTBOX-PORT", "outbox_contract.producer_access", "producer must use Platform port")
    if outbox.get("delivery") != "at_least_once" or outbox.get("broker_ack_before_published") is not True:
        fail("EVT-OUTBOX-DELIVERY", "outbox_contract", "delivery and broker ack semantics are unsafe")
    if outbox.get("delete_after_publish") is not False or outbox.get("reconciliation_required") is not True:
        fail("EVT-OUTBOX-EVIDENCE", "outbox_contract", "published evidence and reconciliation are required")
    if outbox.get("ordering") != "aggregate_version_only_no_global_order":
        fail("EVT-ORDERING", "outbox_contract.ordering", "global order cannot be assumed")

    inbox = model.get("inbox_contract", {})
    if set(inbox.get("states", [])) != {"received", "processing", "succeeded", "retryable_failed", "terminal_failed", "conflict"}:
        fail("EVT-INBOX-STATES", "inbox_contract.states", "inbox states changed")
    if set(inbox.get("identity_fields", [])) != {"consumer_id", "event_id"}:
        fail("EVT-INBOX-IDENTITY", "inbox_contract.identity_fields", "consumer/event identity is required")
    if inbox.get("payload_digest_required") is not True or inbox.get("claim") != "database_unique_constraint_then_digest_compare":
        fail("EVT-INBOX-CLAIM", "inbox_contract", "inbox claim must be atomic and digest-bound")
    if inbox.get("receipt_and_effect_transaction") != "same_consumer_database_transaction" or inbox.get("receipt_before_effect_commit") is not False:
        fail("EVT-INBOX-ATOMIC", "inbox_contract", "receipt and effect must commit atomically")
    if inbox.get("same_id_different_digest") != "conflict_and_security_signal" or inbox.get("cross_company_effect") != "forbidden":
        fail("EVT-INBOX-CONFLICT", "inbox_contract", "digest conflict and company isolation are required")

    attempt = model.get("delivery_attempt_contract", {})
    if attempt.get("append_only") is not True or set(attempt.get("required_fields", [])) != REQUIRED_ATTEMPT_FIELDS:
        fail("EVT-ATTEMPT", "delivery_attempt_contract", "attempt must be append-only and complete")
    if set(attempt.get("failure_classes", [])) != {"retryable", "rate_limited", "fatal", "requires_human", "unknown"}:
        fail("EVT-FAILURE-CLASSES", "delivery_attempt_contract.failure_classes", "failure classes changed")
    if attempt.get("raw_error_or_payload_forbidden") is not True or attempt.get("unknown_failure_action") != "fail_closed_requires_triage":
        fail("EVT-ATTEMPT-SAFETY", "delivery_attempt_contract", "attempt telemetry must be minimized and fail closed")

    work = _by_id(model.get("work_classes"))
    expected_owners = {
        "outbox_dispatch": "outbox_dispatcher",
        "stateless_job": "managed_queue",
        "durable_workflow": "durable_workflow_engine",
        "external_idempotent_effect": "parent_queue_or_workflow_never_adapter",
        "external_non_idempotent_effect": "none_automatic",
    }
    for work_id, expected_owner in expected_owners.items():
        item = work.get(work_id, {})
        if item.get("schedule_owner") != expected_owner:
            fail("EVT-RETRY-OWNER", f"work_classes.{work_id}", f"expected {expected_owner}")
        if item.get("adapter_retries") is not False:
            fail("EVT-ADAPTER-RETRY", f"work_classes.{work_id}", "adapter must never own retry loop")
        if not item.get("exhaustion"):
            fail("EVT-EXHAUSTION", f"work_classes.{work_id}", "exhaustion action is required")

    retry = model.get("retry_policy_contract", {})
    if set(retry.get("required_fields", [])) != REQUIRED_RETRY_FIELDS:
        fail("EVT-RETRY-FIELDS", "retry_policy_contract.required_fields", "retry policy fields are incomplete")
    if retry.get("owner_and_reviewer_independent") is not True:
        fail("EVT-RETRY-SOD", "retry_policy_contract", "retry policy needs independent review")
    for field in ("retry_after_is_capped_by_budget", "deadline_precedes_new_attempt", "policy_change_effect"):
        if not retry.get(field):
            fail("EVT-RETRY-BOUND", f"retry_policy_contract.{field}", "bounded retry control is missing")
    if retry.get("circuit_breaker_schedules_retry") is not False or retry.get("adapter_schedules_retry") is not False:
        fail("EVT-RETRY-LAYERS", "retry_policy_contract", "adapter/circuit breaker cannot schedule retries")
    if retry.get("broker_redelivery_is_not_extra_owner") is not True:
        fail("EVT-RETRY-BROKER", "retry_policy_contract", "broker redelivery cannot become a second owner")

    dead = model.get("dead_letter_contract", {})
    if dead.get("entity") != "dead_letter_item" or set(dead.get("required_fields", [])) != REQUIRED_DLQ_FIELDS:
        fail("EVT-DLQ-FIELDS", "dead_letter_contract", "dead-letter entity/fields are incomplete")
    if set(dead.get("states", [])) != {"open", "triaged", "replay_approved", "replayed", "discarded_with_reason", "requires_human"}:
        fail("EVT-DLQ-STATES", "dead_letter_contract.states", "dead-letter states changed")
    if set(dead.get("replay_requires", [])) != REQUIRED_REPLAY:
        fail("EVT-DLQ-REPLAY", "dead_letter_contract.replay_requires", "safe replay requirements are incomplete")
    if dead.get("raw_payload_forbidden") is not True or dead.get("replay_mutates_original") is not False:
        fail("EVT-DLQ-IMMUTABLE", "dead_letter_contract", "dead letter must be minimized and immutable")
    if dead.get("discard_requires_reason_and_author") is not True or dead.get("financial_state_authority") is not False:
        fail("EVT-DLQ-AUTHORITY", "dead_letter_contract", "discard audit and non-authority are required")

    schema = model.get("schema_compatibility_contract", {})
    if schema.get("registry_required") is not True or schema.get("consumer_contracts_versioned") is not True:
        fail("EVT-SCHEMA-REGISTRY", "schema_compatibility_contract", "versioned schema registry is required")
    if schema.get("breaking_change") != "new_major_schema_and_explicit_consumer_migration":
        fail("EVT-SCHEMA-BREAKING", "schema_compatibility_contract.breaking_change", "breaking changes need a major migration")
    if schema.get("unknown_schema_behavior") != "dead_letter_without_effect" or schema.get("latest_reference_forbidden") is not True:
        fail("EVT-SCHEMA-UNKNOWN", "schema_compatibility_contract", "unknown/latest schema behavior is unsafe")
    if schema.get("payload_migration") != "new_event_or_replay_attempt_linked_to_original_never_mutate_original":
        fail("EVT-SCHEMA-MIGRATION", "schema_compatibility_contract.payload_migration", "migration must preserve original")

    ordering = model.get("ordering_contract", {})
    if ordering.get("global_order_guaranteed") is not False or ordering.get("aggregate_version_required") is not True:
        fail("EVT-ORDER-GLOBAL", "ordering_contract", "only aggregate version ordering is supported")
    if ordering.get("future_gap") != "pause_aggregate_and_reconcile_or_redeliver":
        fail("EVT-ORDER-GAP", "ordering_contract.future_gap", "gap must pause and reconcile")
    if ordering.get("concurrent_aggregate_change") != "optimistic_conflict_no_last_write_wins":
        fail("EVT-ORDER-CONFLICT", "ordering_contract.concurrent_aggregate_change", "last-write-wins is forbidden")

    truth = model.get("execution_truth_contract", {})
    expected_truth = {
        "postgresql": "domain_state_job_definition_outbox_inbox_and_visible_status",
        "durable_workflow": "workflow_history_timers_compensations_and_human_waits",
        "managed_queue": "stateless_work_delivery_and_backoff",
        "valkey": "ephemeral_progress_heartbeat_and_cache_only",
        "analytics": "rebuildable_projection_only",
    }
    for field, value in expected_truth.items():
        if truth.get(field) != value:
            fail("EVT-EXECUTION-TRUTH", f"execution_truth_contract.{field}", f"must equal {value}")
    if truth.get("valkey_loss_effect") != "progress_degraded_no_domain_or_retry_state_loss":
        fail("EVT-VALKEY", "execution_truth_contract.valkey_loss_effect", "Valkey loss cannot lose durable state")
    if truth.get("workflow_history_financial_authority") is not False or truth.get("queue_message_financial_authority") is not False:
        fail("EVT-FINANCIAL-AUTHORITY", "execution_truth_contract", "execution stores cannot own financial truth")

    external = model.get("external_effect_contract", {})
    if external.get("provider_idempotency_verified_before_auto_retry") is not True or external.get("local_effect_ledger_required") is not True or external.get("provider_reconciliation_required") is not True:
        fail("EVT-EXTERNAL-IDEMPOTENCY", "external_effect_contract", "external retry controls are incomplete")
    if external.get("unknown_outcome") != "reconcile_before_retry" or external.get("non_idempotent_unknown_outcome") != "requires_human":
        fail("EVT-EXTERNAL-UNKNOWN", "external_effect_contract", "unknown external outcome cannot be retried blindly")
    if external.get("payments_enabled") is not False or external.get("credential_or_funds_handling") is not False:
        fail("EVT-EXTERNAL-SCOPE", "external_effect_contract", "payments/funds/credentials remain disabled")

    auth = model.get("authorization_contract", {})
    for field in ("company_scope_server_resolved", "authorization_version_on_work", "revalidate_before_read", "revalidate_before_publish_or_external_effect", "service_principal_capability_short_lived", "dead_letter_replay_reauthorizes"):
        if auth.get(field) is not True:
            fail("EVT-AUTHORIZATION", f"authorization_contract.{field}", "authorization control cannot be disabled")
    if auth.get("revocation_action") != "cancel_or_block_pending_work_and_invalidate_capabilities":
        fail("EVT-REVOCATION", "authorization_contract.revocation_action", "revocation must block pending work")

    observability = model.get("observability_contract", {})
    if not {"payload", "raw_error", "amount", "account_number", "tax_id", "financial_reference", "token", "credential", "secret"} <= set(observability.get("forbidden", [])):
        fail("EVT-OBSERVABILITY", "observability_contract.forbidden", "telemetry denylist is incomplete")
    if not {"stuck_outbox", "stuck_inbox", "dead_letter_growth", "retry_storm", "authorization_revoked_work", "reconciliation_drift"} <= set(observability.get("alerts", [])):
        fail("EVT-ALERTS", "observability_contract.alerts", "operational alerts are incomplete")

    idem_concurrency = idempotency.get("concurrency_contract", {})
    if idem_concurrency.get("outbox_same_transaction_as_domain_change") is not True or idem_concurrency.get("consumer_receipt_before_effect_forbidden") is not True:
        fail("EVT-IDEMPOTENCY-ALIGNMENT", "idempotency.concurrency_contract", "DOM-004 atomicity alignment failed")
    if idem_concurrency.get("worker_delivery") != "at_least_once":
        fail("EVT-DELIVERY-ALIGNMENT", "idempotency.concurrency_contract.worker_delivery", "at-least-once alignment failed")

    # -- punto de control de un lote --------------------------------------
    # Un tramo publicado es un recibo, y su contrato es de reintentos, no de
    # finanzas: por eso vive aqui y no en el modelo canonico.
    checkpoint = model.get("checkpoint_contract")
    if not isinstance(checkpoint, dict):
        fail("EVT-CHECKPOINT", "checkpoint_contract", "chunked work needs a declared checkpoint contract")
    else:
        if checkpoint.get("checkpoint_authority") != "postgresql":
            fail("EVT-CHECKPOINT-AUTHORITY", "checkpoint_contract.checkpoint_authority", "the checkpoint lives in PostgreSQL")
        if checkpoint.get("valkey_is_checkpoint_authority") is not False:
            fail("EVT-CHECKPOINT-VALKEY", "checkpoint_contract.valkey_is_checkpoint_authority", "Valkey is never the checkpoint authority")
        if checkpoint.get("valkey_loss_effect") != "progress_bar_resets_no_chunk_is_repeated_or_lost":
            fail("EVT-CHECKPOINT-VALKEY", "checkpoint_contract.valkey_loss_effect", "losing the cache cannot repeat or lose a chunk")
        if checkpoint.get("checkpoint_and_effect_transaction") != "same_transaction":
            fail("EVT-CHECKPOINT-ATOMIC", "checkpoint_contract.checkpoint_and_effect_transaction", "receipt and effect commit together")
        if checkpoint.get("checkpoint_reserved_before_effect") is not True:
            fail("EVT-CHECKPOINT-ATOMIC", "checkpoint_contract.checkpoint_reserved_before_effect", "the chunk row is claimed before the batch is written")
        if checkpoint.get("partial_chunk") != "rolled_back_whole_never_half_written":
            fail("EVT-CHECKPOINT-ATOMIC", "checkpoint_contract.partial_chunk", "half a chunk is not a state")
        if checkpoint.get("retry_owner") != "worker_job_runner" or checkpoint.get("broker_redelivery_is_not_extra_owner") is not True:
            fail("EVT-CHECKPOINT-OWNER", "checkpoint_contract.retry_owner", "exactly one retry owner, and redelivery is not a second one")
        if checkpoint.get("resume_semantics") != "skip_recorded_ordinals_and_continue":
            fail("EVT-CHECKPOINT-RESUME", "checkpoint_contract.resume_semantics", "resuming skips what is already recorded")
        if checkpoint.get("dead_letter_on_exhaustion") is not True:
            fail("EVT-CHECKPOINT-DLQ", "checkpoint_contract.dead_letter_on_exhaustion", "an exhausted publication is visible, not silently complete")
        if checkpoint.get("financial_state_authority") is not False or checkpoint.get("lineage_authority") is not False:
            fail("EVT-CHECKPOINT-SCOPE", "checkpoint_contract", "a chunk counts how much was published, never what")
        declared = {item.get("id") for item in checkpoint.get("invariants", []) if isinstance(item, dict)}
        for missing in sorted(REQUIRED_CHECKPOINT_INVARIANTS - declared):
            fail("EVT-CHECKPOINT-INVARIANT", f"checkpoint_contract.{missing}", "required checkpoint invariant is missing")
        for missing in sorted(REQUIRED_CHECKPOINT_FIELDS - set(checkpoint.get("required_fields") or [])):
            fail("EVT-CHECKPOINT-FIELD", f"checkpoint_contract.{missing}", "a checkpoint without this field cannot be resumed")

    dfd_threats = set(_ids(dfd.get("threat_catalog")))
    dfd_controls = set(_ids(dfd.get("control_catalog")))
    if "T12" not in dfd_threats or "C-IDEMP" not in dfd_controls:
        fail("EVT-DFD-COVERAGE", "dfd", "duplicate effect threat/control must remain present")
    threat_ids = set(_ids(threat_model.get("risks")))
    if "TM-009" not in threat_ids:
        fail("EVT-THREAT-COVERAGE", "threat_model", "TM-009 replay/retry risk is required")

    return sorted(errors)


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FNC-ARC-004 event/retry contract")
    parser.add_argument("--model", type=Path, default=Path("docs/architecture/events-retries.json"))
    parser.add_argument("--architecture", type=Path, default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--idempotency", type=Path, default=Path("docs/domain/idempotency-dedupe.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    parser.add_argument("--threat-model", type=Path, default=Path("docs/security/threat-model.json"))
    args = parser.parse_args()
    errors = validate_model(
        _load(args.model), _load(args.architecture), _load(args.idempotency),
        _load(args.dfd), _load(args.threat_model),
    )
    print(json.dumps({"errors": [item.as_dict() for item in errors], "ok": not errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
