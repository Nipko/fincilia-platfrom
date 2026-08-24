from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tools.event_model.validate import validate_model


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class EventModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = _load("docs/architecture/events-retries.json")
        cls.architecture = _load("docs/architecture/module-boundaries.json")
        cls.idempotency = _load("docs/domain/idempotency-dedupe.json")
        cls.dfd = _load("docs/architecture/dfd-flows.json")
        cls.threat_model = _load("docs/security/threat-model.json")

    def _codes(
        self,
        model: dict[str, Any] | None = None,
        architecture: dict[str, Any] | None = None,
        idempotency: dict[str, Any] | None = None,
        dfd: dict[str, Any] | None = None,
        threat_model: dict[str, Any] | None = None,
    ) -> set[str]:
        return {
            error.code
            for error in validate_model(
                model if model is not None else self.model,
                architecture if architecture is not None else self.architecture,
                idempotency if idempotency is not None else self.idempotency,
                dfd if dfd is not None else self.dfd,
                threat_model if threat_model is not None else self.threat_model,
            )
        }

    @staticmethod
    def _item(model: dict[str, Any], catalog: str, identifier: str) -> dict[str, Any]:
        return next(item for item in model[catalog] if item["id"] == identifier)

    def test_repository_model_is_valid(self) -> None:
        self.assertEqual([], validate_model(self.model, self.architecture, self.idempotency, self.dfd, self.threat_model))

    def test_provider_cannot_be_selected_by_agent(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["provider_selection"] = "provider_x"
        self.assertIn("EVT-PROVIDER", self._codes(model=mutated))

    def test_required_principle_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["principles"].pop()
        self.assertIn("EVT-PRINCIPLES", self._codes(model=mutated))

    def test_platform_must_own_dead_letter(self) -> None:
        architecture = copy.deepcopy(self.architecture)
        platform = next(item for item in architecture["modules"] if item["id"] == "platform")
        platform["owns"].remove("dead_letter_item")
        self.assertIn("EVT-OWNER", self._codes(architecture=architecture))

    def test_event_envelope_requires_company_scope(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["event_envelope"]["required_fields"].remove("company_scope")
        self.assertIn("EVT-ENVELOPE-FIELDS", self._codes(model=mutated))

    def test_event_company_scope_cannot_come_from_client(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["event_envelope"]["company_scope_source"] = "request_body"
        self.assertIn("EVT-ENVELOPE-SCOPE", self._codes(model=mutated))

    def test_secret_cannot_enter_event(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["event_envelope"]["forbidden_classes"].remove("secret")
        self.assertIn("EVT-ENVELOPE-CLASS", self._codes(model=mutated))

    def test_amount_cannot_enter_event_metadata(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["event_envelope"]["forbidden_metadata"].remove("amount")
        self.assertIn("EVT-ENVELOPE-MINIMIZATION", self._codes(model=mutated))

    def test_unknown_schema_cannot_have_effect(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["event_envelope"]["unknown_schema_action"] = "best_effort_parse"
        self.assertIn("EVT-UNKNOWN-SCHEMA", self._codes(model=mutated))

    def test_outbox_must_commit_with_domain(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["outbox_contract"]["domain_and_outbox_transaction"] = "eventual_insert"
        self.assertIn("EVT-OUTBOX-ATOMIC", self._codes(model=mutated))

    def test_producer_cannot_write_outbox_repository_directly(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["outbox_contract"]["producer_access"] = "direct_repository"
        self.assertIn("EVT-OUTBOX-PORT", self._codes(model=mutated))

    def test_outbox_cannot_mark_published_before_ack(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["outbox_contract"]["broker_ack_before_published"] = False
        self.assertIn("EVT-OUTBOX-DELIVERY", self._codes(model=mutated))

    def test_published_outbox_cannot_be_deleted_immediately(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["outbox_contract"]["delete_after_publish"] = True
        self.assertIn("EVT-OUTBOX-EVIDENCE", self._codes(model=mutated))

    def test_global_order_cannot_be_assumed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["outbox_contract"]["ordering"] = "global_broker_order"
        self.assertIn("EVT-ORDERING", self._codes(model=mutated))

    def test_inbox_claim_requires_payload_digest(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["inbox_contract"]["payload_digest_required"] = False
        self.assertIn("EVT-INBOX-CLAIM", self._codes(model=mutated))

    def test_receipt_cannot_commit_before_effect(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["inbox_contract"]["receipt_before_effect_commit"] = True
        self.assertIn("EVT-INBOX-ATOMIC", self._codes(model=mutated))

    def test_same_event_id_different_digest_must_conflict(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["inbox_contract"]["same_id_different_digest"] = "return_prior_success"
        self.assertIn("EVT-INBOX-CONFLICT", self._codes(model=mutated))

    def test_delivery_attempt_must_be_append_only(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["delivery_attempt_contract"]["append_only"] = False
        self.assertIn("EVT-ATTEMPT", self._codes(model=mutated))

    def test_unknown_failure_must_fail_closed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["delivery_attempt_contract"]["unknown_failure_action"] = "retry_forever"
        self.assertIn("EVT-ATTEMPT-SAFETY", self._codes(model=mutated))

    def test_each_work_class_has_one_expected_retry_owner(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "work_classes", "stateless_job")["schedule_owner"] = "queue_and_workflow"
        self.assertIn("EVT-RETRY-OWNER", self._codes(model=mutated))

    def test_adapter_cannot_retry(self) -> None:
        mutated = copy.deepcopy(self.model)
        self._item(mutated, "work_classes", "external_idempotent_effect")["adapter_retries"] = True
        self.assertIn("EVT-ADAPTER-RETRY", self._codes(model=mutated))

    def test_retry_policy_requires_cost_budget(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retry_policy_contract"]["required_fields"].remove("cost_budget")
        self.assertIn("EVT-RETRY-FIELDS", self._codes(model=mutated))

    def test_retry_owner_needs_independent_reviewer(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retry_policy_contract"]["owner_and_reviewer_independent"] = False
        self.assertIn("EVT-RETRY-SOD", self._codes(model=mutated))

    def test_circuit_breaker_cannot_schedule_retry(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retry_policy_contract"]["circuit_breaker_schedules_retry"] = True
        self.assertIn("EVT-RETRY-LAYERS", self._codes(model=mutated))

    def test_broker_redelivery_cannot_be_second_owner(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retry_policy_contract"]["broker_redelivery_is_not_extra_owner"] = False
        self.assertIn("EVT-RETRY-BROKER", self._codes(model=mutated))

    def test_dead_letter_requires_company_scope(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dead_letter_contract"]["required_fields"].remove("company_scope")
        self.assertIn("EVT-DLQ-FIELDS", self._codes(model=mutated))

    def test_dead_letter_cannot_store_raw_payload(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dead_letter_contract"]["raw_payload_forbidden"] = False
        self.assertIn("EVT-DLQ-IMMUTABLE", self._codes(model=mutated))

    def test_replay_must_reauthorize(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dead_letter_contract"]["replay_requires"].remove("current_authorization_revalidated")
        self.assertIn("EVT-DLQ-REPLAY", self._codes(model=mutated))

    def test_discard_requires_reason_and_author(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["dead_letter_contract"]["discard_requires_reason_and_author"] = False
        self.assertIn("EVT-DLQ-AUTHORITY", self._codes(model=mutated))

    def test_breaking_schema_requires_major_migration(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["schema_compatibility_contract"]["breaking_change"] = "silent_in_place"
        self.assertIn("EVT-SCHEMA-BREAKING", self._codes(model=mutated))

    def test_latest_schema_reference_is_forbidden(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["schema_compatibility_contract"]["latest_reference_forbidden"] = False
        self.assertIn("EVT-SCHEMA-UNKNOWN", self._codes(model=mutated))

    def test_gap_must_pause_aggregate(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["ordering_contract"]["future_gap"] = "apply_anyway"
        self.assertIn("EVT-ORDER-GAP", self._codes(model=mutated))

    def test_last_write_wins_is_forbidden(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["ordering_contract"]["concurrent_aggregate_change"] = "last_write_wins"
        self.assertIn("EVT-ORDER-CONFLICT", self._codes(model=mutated))

    def test_valkey_cannot_own_retry_state(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["execution_truth_contract"]["valkey"] = "retry_schedule"
        self.assertIn("EVT-EXECUTION-TRUTH", self._codes(model=mutated))

    def test_valkey_loss_cannot_lose_domain_state(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["execution_truth_contract"]["valkey_loss_effect"] = "job_lost"
        self.assertIn("EVT-VALKEY", self._codes(model=mutated))

    def test_workflow_history_cannot_be_financial_authority(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["execution_truth_contract"]["workflow_history_financial_authority"] = True
        self.assertIn("EVT-FINANCIAL-AUTHORITY", self._codes(model=mutated))

    def test_external_effect_requires_provider_idempotency(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["external_effect_contract"]["provider_idempotency_verified_before_auto_retry"] = False
        self.assertIn("EVT-EXTERNAL-IDEMPOTENCY", self._codes(model=mutated))

    def test_unknown_external_outcome_must_reconcile(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["external_effect_contract"]["unknown_outcome"] = "retry_immediately"
        self.assertIn("EVT-EXTERNAL-UNKNOWN", self._codes(model=mutated))

    def test_payments_cannot_be_enabled(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["external_effect_contract"]["payments_enabled"] = True
        self.assertIn("EVT-EXTERNAL-SCOPE", self._codes(model=mutated))

    def test_publish_must_revalidate_authorization(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["authorization_contract"]["revalidate_before_publish_or_external_effect"] = False
        self.assertIn("EVT-AUTHORIZATION", self._codes(model=mutated))

    def test_revocation_must_block_pending_work(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["authorization_contract"]["revocation_action"] = "allow_until_job_finishes"
        self.assertIn("EVT-REVOCATION", self._codes(model=mutated))

    def test_observability_cannot_log_payload(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["observability_contract"]["forbidden"].remove("payload")
        self.assertIn("EVT-OBSERVABILITY", self._codes(model=mutated))

    def test_retry_storm_alert_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["observability_contract"]["alerts"].remove("retry_storm")
        self.assertIn("EVT-ALERTS", self._codes(model=mutated))

    def test_dom004_atomicity_alignment_is_required(self) -> None:
        idempotency = copy.deepcopy(self.idempotency)
        idempotency["concurrency_contract"]["outbox_same_transaction_as_domain_change"] = False
        self.assertIn("EVT-IDEMPOTENCY-ALIGNMENT", self._codes(idempotency=idempotency))

    def test_dfd_idempotency_control_is_required(self) -> None:
        dfd = copy.deepcopy(self.dfd)
        dfd["control_catalog"] = [item for item in dfd["control_catalog"] if item["id"] != "C-IDEMP"]
        self.assertIn("EVT-DFD-COVERAGE", self._codes(dfd=dfd))

    def test_tm009_replay_risk_is_required(self) -> None:
        threat = copy.deepcopy(self.threat_model)
        threat["risks"] = [item for item in threat["risks"] if item["id"] != "TM-009"]
        self.assertIn("EVT-THREAT-COVERAGE", self._codes(threat_model=threat))

    def test_required_outbox_test_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["required_tests"] = [item for item in mutated["required_tests"] if item["id"] != "TST-OUT-001"]
        self.assertIn("EVT-TEST-COVERAGE", self._codes(model=mutated))


    def test_the_checkpoint_contract_bites_when_weakened(self) -> None:
        # Cada una de estas mutaciones es una forma real de perder un tramo o de
        # publicarlo dos veces; ninguna se ve mal en una revision por encima.
        for label, mutate, expected in (
            ("la cache decide que ya se hizo",
             lambda m: m["checkpoint_contract"].__setitem__("valkey_is_checkpoint_authority", True),
             "EVT-CHECKPOINT-VALKEY"),
            ("perder la cache repite un tramo",
             lambda m: m["checkpoint_contract"].__setitem__("valkey_loss_effect", "chunks_are_replayed"),
             "EVT-CHECKPOINT-VALKEY"),
            ("el punto de control vive fuera de PostgreSQL",
             lambda m: m["checkpoint_contract"].__setitem__("checkpoint_authority", "valkey"),
             "EVT-CHECKPOINT-AUTHORITY"),
            ("el recibo se escribe aparte del efecto",
             lambda m: m["checkpoint_contract"].__setitem__("checkpoint_and_effect_transaction", "separate_transaction"),
             "EVT-CHECKPOINT-ATOMIC"),
            ("el recibo se toma despues de escribir el lote",
             lambda m: m["checkpoint_contract"].__setitem__("checkpoint_reserved_before_effect", False),
             "EVT-CHECKPOINT-ATOMIC"),
            ("medio tramo es un estado",
             lambda m: m["checkpoint_contract"].__setitem__("partial_chunk", "keep_what_was_written"),
             "EVT-CHECKPOINT-ATOMIC"),
            ("la reentrega del broker tambien reintenta",
             lambda m: m["checkpoint_contract"].__setitem__("broker_redelivery_is_not_extra_owner", False),
             "EVT-CHECKPOINT-OWNER"),
            ("reanudar vuelve a empezar",
             lambda m: m["checkpoint_contract"].__setitem__("resume_semantics", "restart_from_zero"),
             "EVT-CHECKPOINT-RESUME"),
            ("agotar intentos se marca completo",
             lambda m: m["checkpoint_contract"].__setitem__("dead_letter_on_exhaustion", False),
             "EVT-CHECKPOINT-DLQ"),
            ("el tramo pasa a ser autoridad financiera",
             lambda m: m["checkpoint_contract"].__setitem__("financial_state_authority", True),
             "EVT-CHECKPOINT-SCOPE"),
            ("el tramo pasa a ser autoridad de linaje",
             lambda m: m["checkpoint_contract"].__setitem__("lineage_authority", True),
             "EVT-CHECKPOINT-SCOPE"),
        ):
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.model)
                mutate(mutated)
                self.assertIn(expected, self._codes(model=mutated))

    def test_every_declared_checkpoint_invariant_is_required(self) -> None:
        for invariant in [item["id"] for item in self.model["checkpoint_contract"]["invariants"]]:
            with self.subTest(invariant=invariant):
                mutated = copy.deepcopy(self.model)
                mutated["checkpoint_contract"]["invariants"] = [
                    item for item in mutated["checkpoint_contract"]["invariants"]
                    if item["id"] != invariant]
                self.assertIn("EVT-CHECKPOINT-INVARIANT", self._codes(model=mutated))

    def test_a_checkpoint_without_its_window_cannot_resume(self) -> None:
        for field in ("chunk_ordinal", "first_record", "last_record", "dataset_version_id"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.model)
                mutated["checkpoint_contract"]["required_fields"] = [
                    item for item in mutated["checkpoint_contract"]["required_fields"]
                    if item != field]
                self.assertIn("EVT-CHECKPOINT-FIELD", self._codes(model=mutated))

    def test_the_checkpoint_contract_cannot_simply_disappear(self) -> None:
        mutated = copy.deepcopy(self.model)
        del mutated["checkpoint_contract"]
        self.assertIn("EVT-CHECKPOINT", self._codes(model=mutated))

    def test_required_checkpoint_test_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["required_tests"] = [item for item in mutated["required_tests"]
                                     if item["id"] != "TST-CHK-002"]
        self.assertIn("EVT-TEST-COVERAGE", self._codes(model=mutated))


if __name__ == "__main__":
    unittest.main()
