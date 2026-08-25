"""Materializacion digest-only del linaje de decisiones financieras.

ADR-024 conserva las seis etapas por columna en un plan compartido. Este modulo
solo materializa los puntos variables y de baja cardinalidad que aparecen al
observar un saldo o tomar una decision. Nunca copia valores al grafo.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import psycopg

from fincilia_contracts.release import digest_of


EXPECTED_STAGES = (
    "artifact_version", "raw_locator", "extracted_field",
    "transformed_value", "source_record_field", "financial_fact_field",
)


@dataclass(frozen=True)
class LineageError(Exception):
    code: str
    detail: str


@dataclass(frozen=True)
class Anchor:
    dataset_version_id: str
    processing_run_id: str
    lineage_plan_id: str
    engine_release_id: str
    canonical_schema_version: str
    dataset_node_id: str


def _node(cursor: psycopg.Cursor, *, company_id: str, node_type: str,
          entity_ref: str, field_name: str, value_digest: str | None,
          release_id: str, schema_version: str) -> str:
    cursor.execute(
        "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
        "entity_ref, field_name, value_digest, engine_release_id, "
        "canonical_schema_version) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
        "%s, %s, %s) ON CONFLICT (company_id, node_type, entity_ref, field_name) "
        "DO NOTHING RETURNING node_id",
        (company_id, node_type, entity_ref, field_name, value_digest,
         release_id, schema_version))
    inserted = cursor.fetchone()
    if inserted is not None:
        return str(inserted[0])
    cursor.execute(
        "SELECT node_id, value_digest, engine_release_id, canonical_schema_version "
        "FROM fincilia.lineage_node WHERE company_id=%s AND node_type=%s "
        "AND entity_ref=%s AND field_name=%s",
        (company_id, node_type, entity_ref, field_name))
    existing = cursor.fetchone()
    if existing is None or existing[1] != value_digest or str(existing[2]) != release_id \
            or existing[3] != schema_version:
        raise LineageError(
            "financial-lineage-node-conflict",
            "an immutable lineage node already carries different evidence")
    return str(existing[0])


def _edge(cursor: psycopg.Cursor, *, company_id: str, from_node_id: str,
          to_node_id: str, operation: str, transform_ref: str | None,
          subject_id: str, processing_run_id: str, release_id: str,
          schema_version: str) -> None:
    cursor.execute(
        "INSERT INTO fincilia.lineage_edge (edge_id, company_id, from_node_id, "
        "to_node_id, operation, transform_ref, actor_kind, actor_id, "
        "workload_identity, processing_run_id, engine_release_id, "
        "canonical_schema_version) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
        "%s, 'human', %s, 'api', %s, %s, %s) "
        "ON CONFLICT (from_node_id, to_node_id, operation) DO NOTHING RETURNING edge_id",
        (company_id, from_node_id, to_node_id, operation, transform_ref,
         subject_id, processing_run_id, release_id, schema_version))
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        "SELECT company_id, processing_run_id, engine_release_id, "
        "canonical_schema_version FROM fincilia.lineage_edge "
        "WHERE from_node_id=%s AND to_node_id=%s AND operation=%s",
        (from_node_id, to_node_id, operation))
    existing = cursor.fetchone()
    if existing is None or str(existing[0]) != company_id \
            or str(existing[1]) != processing_run_id \
            or str(existing[2]) != release_id or existing[3] != schema_version:
        raise LineageError(
            "financial-lineage-edge-conflict",
            "an immutable lineage edge already carries different provenance")


def _anchor(cursor: psycopg.Cursor, *, company_id: str,
            dataset_version_id: str) -> Anchor:
    cursor.execute(
        "SELECT d.dataset_version_id, d.processing_run_id, d.lineage_plan_id, "
        "d.engine_release_id, d.canonical_schema_version, anchor.node_id "
        "FROM fincilia.dataset_version d JOIN fincilia.lineage_node anchor "
        "ON anchor.company_id=d.company_id AND anchor.node_type='source_record_field' "
        "AND anchor.entity_ref=d.dataset_version_id AND anchor.field_name='dataset' "
        "WHERE d.company_id=%s AND d.dataset_version_id=%s "
        "AND d.state='published' AND d.completeness_state='verified' "
        "AND d.lineage_state='complete' AND d.lineage_plan_id IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM fincilia.lineage_edge sealed "
        "JOIN fincilia.lineage_node artifact ON artifact.node_id=sealed.from_node_id "
        "AND artifact.company_id=sealed.company_id "
        "WHERE sealed.company_id=d.company_id AND sealed.to_node_id=anchor.node_id "
        "AND sealed.operation='included_in_snapshot' "
        "AND artifact.node_type='artifact_version' "
        "AND artifact.entity_ref=d.artifact_id)",
        (company_id, dataset_version_id))
    row = cursor.fetchone()
    if row is None:
        raise LineageError(
            "financial-lineage-anchor-missing",
            "the published dataset has no reproducible lineage anchor")
    return Anchor(*(str(value) for value in row))


def _source_context(cursor: psycopg.Cursor, *, company_id: str,
                    source_record_id: str) -> tuple[Anchor, dict[str, Any], Any]:
    cursor.execute(
        "SELECT s.dataset_version_id, m.field_digests, s.source_payload "
        "FROM fincilia.source_record s JOIN fincilia.canonical_movement m "
        "ON m.company_id=s.company_id AND m.source_record_id=s.source_record_id "
        "WHERE s.company_id=%s AND s.source_record_id=%s "
        "AND s.state='published' AND s.lineage_state='complete' "
        "AND m.state<>'voided' AND m.lineage_state='complete'",
        (company_id, source_record_id))
    row = cursor.fetchone()
    if row is None:
        raise LineageError(
            "financial-lineage-source-missing",
            "the source record has no eligible canonical fact")
    return _anchor(cursor, company_id=company_id,
                   dataset_version_id=str(row[0])), row[1] or {}, row[2]


def _plan_field(cursor: psycopg.Cursor, *, anchor: Anchor,
                canonical_field: str, source_column: int) -> None:
    cursor.execute(
        "SELECT stage, step_ordinal, source_column FROM "
        "fincilia.lineage_transform_step WHERE plan_id=%s "
        "AND company_id=current_setting('fincilia.company_id')::uuid "
        "AND canonical_field=%s ORDER BY step_ordinal",
        (anchor.lineage_plan_id, canonical_field))
    rows = cursor.fetchall()
    if tuple(row[0] for row in rows) != EXPECTED_STAGES \
            or tuple(int(row[1]) for row in rows) != tuple(range(1, 7)) \
            or any(row[2] != source_column for row in rows):
        raise LineageError(
            "financial-lineage-plan-incomplete",
            f"the versioned plan does not explain {canonical_field} at that column")


def materialize_balance(cursor: psycopg.Cursor, *, company_id: str,
                        subject_id: str, balance_id: str, source_record_id: str,
                        amount_field_index: int, as_of_field_index: int,
                        field_digests: dict[str, str]) -> None:
    anchor, source_digests, _ = _source_context(
        cursor, company_id=company_id, source_record_id=source_record_id)
    specs = (
        ("amount", "amount", amount_field_index),
        ("as_of", "occurred_on", as_of_field_index),
    )
    for target_field, source_field, source_column in specs:
        _plan_field(cursor, anchor=anchor, canonical_field=source_field,
                    source_column=source_column)
        source_digest = source_digests.get(source_field)
        target_digest = field_digests.get(target_field)
        if not source_digest or not target_digest:
            raise LineageError(
                "financial-lineage-digest-missing",
                "the selected field does not carry its published digest")
        source_node = _node(
            cursor, company_id=company_id, node_type="source_record_field",
            entity_ref=source_record_id, field_name=source_field,
            value_digest=source_digest, release_id=anchor.engine_release_id,
            schema_version=anchor.canonical_schema_version)
        fact_node = _node(
            cursor, company_id=company_id, node_type="financial_fact_field",
            entity_ref=balance_id, field_name=target_field,
            value_digest=target_digest, release_id=anchor.engine_release_id,
            schema_version=anchor.canonical_schema_version)
        _edge(
            cursor, company_id=company_id, from_node_id=source_node,
            to_node_id=fact_node, operation="derived_from",
            transform_ref=f"observe_balance:{source_field}:v1",
            subject_id=subject_id, processing_run_id=anchor.processing_run_id,
            release_id=anchor.engine_release_id,
            schema_version=anchor.canonical_schema_version)


def materialize_assessment(cursor: psycopg.Cursor, *, company_id: str,
                           subject_id: str, assessment_id: str,
                           dataset_version_id: str, assessment_key: str,
                           state: str, rule_version: str) -> str:
    anchor = _anchor(cursor, company_id=company_id,
                     dataset_version_id=dataset_version_id)
    fact = _node(
        cursor, company_id=company_id, node_type="financial_fact_field",
        entity_ref=assessment_id, field_name="dataset", value_digest=assessment_key,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    decision = _node(
        cursor, company_id=company_id, node_type="decision",
        entity_ref=assessment_id, field_name="assessment",
        value_digest=digest_of({"key": assessment_key, "state": state}),
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    _edge(
        cursor, company_id=company_id, from_node_id=anchor.dataset_node_id,
        to_node_id=fact, operation="derived_from",
        transform_ref=f"assess_completeness:{rule_version}", subject_id=subject_id,
        processing_run_id=anchor.processing_run_id,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    _edge(
        cursor, company_id=company_id, from_node_id=fact, to_node_id=decision,
        operation="decided_using", transform_ref=None, subject_id=subject_id,
        processing_run_id=anchor.processing_run_id,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    return decision


def materialize_control(cursor: psycopg.Cursor, *, company_id: str,
                        subject_id: str, control_result_id: str,
                        assessment_id: str, dataset_version_id: str,
                        control_type: str, outcome: str, expected: Any,
                        observed: Any, rule_version: str,
                        assessment_node_id: str) -> None:
    anchor = _anchor(cursor, company_id=company_id,
                     dataset_version_id=dataset_version_id)
    fact = _node(
        cursor, company_id=company_id, node_type="financial_fact_field",
        entity_ref=control_result_id, field_name="dataset",
        value_digest=digest_of({"dataset_version_id": dataset_version_id}),
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    decision = _node(
        cursor, company_id=company_id, node_type="decision",
        entity_ref=control_result_id, field_name="control",
        value_digest=digest_of({"control_type": control_type, "outcome": outcome,
                                "expected": expected, "observed": observed,
                                "rule_version": rule_version}),
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    _edge(
        cursor, company_id=company_id, from_node_id=anchor.dataset_node_id,
        to_node_id=fact, operation="derived_from",
        transform_ref=f"evaluate_control:{rule_version}", subject_id=subject_id,
        processing_run_id=anchor.processing_run_id,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    _edge(
        cursor, company_id=company_id, from_node_id=fact, to_node_id=decision,
        operation="decided_using", transform_ref=None, subject_id=subject_id,
        processing_run_id=anchor.processing_run_id,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)
    _edge(
        cursor, company_id=company_id, from_node_id=decision,
        to_node_id=assessment_node_id, operation="decided_using",
        transform_ref=None, subject_id=subject_id,
        processing_run_id=anchor.processing_run_id,
        release_id=anchor.engine_release_id,
        schema_version=anchor.canonical_schema_version)


def materialize_item(cursor: psycopg.Cursor, *, company_id: str, subject_id: str,
                     item_decision_id: str, evidence_source_record_ids: Iterable[str],
                     decision_payload: dict[str, Any], release_id: str,
                     schema_version: str) -> None:
    decision = _node(
        cursor, company_id=company_id, node_type="decision",
        entity_ref=item_decision_id, field_name="item",
        value_digest=digest_of(decision_payload), release_id=release_id,
        schema_version=schema_version)
    for ordinal, source_record_id in enumerate(evidence_source_record_ids, start=1):
        anchor, _, source_payload = _source_context(
            cursor, company_id=company_id, source_record_id=source_record_id)
        if anchor.engine_release_id != release_id \
                or anchor.canonical_schema_version != schema_version:
            raise LineageError(
                "financial-lineage-version-conflict",
                "item evidence was published by another engine or schema version")
        source = _node(
            cursor, company_id=company_id, node_type="source_record_field",
            entity_ref=source_record_id, field_name="record",
            value_digest=digest_of(source_payload), release_id=release_id,
            schema_version=schema_version)
        fact = _node(
            cursor, company_id=company_id, node_type="financial_fact_field",
            entity_ref=item_decision_id, field_name=f"evidence_{ordinal:03d}",
            value_digest=digest_of({"source_record_id": source_record_id}),
            release_id=release_id, schema_version=schema_version)
        _edge(
            cursor, company_id=company_id, from_node_id=source, to_node_id=fact,
            operation="derived_from", transform_ref="item_evidence:v1",
            subject_id=subject_id, processing_run_id=anchor.processing_run_id,
            release_id=release_id, schema_version=schema_version)
        _edge(
            cursor, company_id=company_id, from_node_id=fact, to_node_id=decision,
            operation="decided_using", transform_ref=None, subject_id=subject_id,
            processing_run_id=anchor.processing_run_id, release_id=release_id,
            schema_version=schema_version)


def materialize_statement(cursor: psycopg.Cursor, *, company_id: str,
                          subject_id: str, statement_id: str) -> None:
    cursor.execute(
        "SELECT statement_id, bank_closing_balance_id, books_closing_balance_id, "
        "completeness_assessment_ids, confirmed_reconciling_item_ids, "
        "confirmed_additions_to_bank, confirmed_deductions_from_bank, "
        "adjusted_bank_balance, unexplained_difference, state, statement_key, "
        "engine_release_id, canonical_schema_version FROM "
        "fincilia.reconciliation_statement WHERE company_id=%s AND statement_id=%s",
        (company_id, statement_id))
    row = cursor.fetchone()
    if row is None:
        raise LineageError("financial-lineage-statement-missing",
                           "the statement is not available")
    release_id, schema_version = str(row[11]), row[12]
    statement_node = _node(
        cursor, company_id=company_id, node_type="decision",
        entity_ref=statement_id, field_name="statement",
        value_digest=digest_of({
            "bank_closing_balance_id": str(row[1]),
            "books_closing_balance_id": str(row[2]),
            "assessment_ids": sorted(str(value) for value in row[3]),
            "item_ids": sorted(str(value) for value in row[4]),
            "confirmed_additions_to_bank": str(row[5]),
            "confirmed_deductions_from_bank": str(row[6]),
            "adjusted_bank_balance": str(row[7]),
            "unexplained_difference": str(row[8]), "state": row[9],
            "statement_key": row[10],
        }), release_id=release_id, schema_version=schema_version)

    inputs: list[tuple[str, str]] = []
    cursor.execute(
        "SELECT fact.node_id, dataset.processing_run_id FROM "
        "fincilia.account_balance balance JOIN fincilia.source_record source "
        "ON source.company_id=balance.company_id "
        "AND source.source_record_id=balance.source_record_id "
        "JOIN fincilia.dataset_version dataset ON "
        "dataset.company_id=source.company_id "
        "AND dataset.dataset_version_id=source.dataset_version_id "
        "JOIN fincilia.lineage_node fact ON fact.company_id=balance.company_id "
        "AND fact.node_type='financial_fact_field' "
        "AND fact.entity_ref=balance.balance_id AND fact.field_name='amount' "
        "WHERE balance.company_id=%s AND balance.balance_id=ANY(%s) "
        "AND balance.lineage_state='complete'",
        (company_id, [str(row[1]), str(row[2])]))
    inputs.extend((str(item[0]), str(item[1])) for item in cursor.fetchall())
    cursor.execute(
        "SELECT decision.node_id, dataset.processing_run_id FROM "
        "fincilia.completeness_assessment assessment "
        "JOIN fincilia.dataset_version dataset ON "
        "dataset.company_id=assessment.company_id "
        "AND dataset.dataset_version_id=assessment.dataset_version_id "
        "JOIN fincilia.lineage_node decision ON "
        "decision.company_id=assessment.company_id "
        "AND decision.node_type='decision' "
        "AND decision.entity_ref=assessment.assessment_id "
        "AND decision.field_name='assessment' "
        "WHERE assessment.company_id=%s AND assessment.assessment_id=ANY(%s) "
        "AND assessment.lineage_state='complete'",
        (company_id, [str(value) for value in row[3]]))
    inputs.extend((str(item[0]), str(item[1])) for item in cursor.fetchall())
    if row[4]:
        cursor.execute(
            "SELECT decision.node_id, min(edge.processing_run_id::text)::uuid "
            "FROM fincilia.reconciling_item item JOIN fincilia.lineage_node decision "
            "ON decision.company_id=item.company_id AND decision.node_type='decision' "
            "AND decision.entity_ref=item.item_decision_id "
            "AND decision.field_name='item' JOIN fincilia.lineage_edge edge "
            "ON edge.company_id=item.company_id AND edge.to_node_id=decision.node_id "
            "AND edge.operation='decided_using' WHERE item.company_id=%s "
            "AND item.item_decision_id=ANY(%s) AND item.lineage_state='complete' "
            "GROUP BY decision.node_id",
            (company_id, [str(value) for value in row[4]]))
        inputs.extend((str(item[0]), str(item[1])) for item in cursor.fetchall())
    expected = 2 + len(row[3]) + len(row[4])
    if len(inputs) != expected:
        raise LineageError(
            "financial-lineage-input-incomplete",
            "one or more statement inputs do not have complete materialized lineage")
    for input_node, processing_run_id in inputs:
        _edge(
            cursor, company_id=company_id, from_node_id=input_node,
            to_node_id=statement_node, operation="decided_using",
            transform_ref=None, subject_id=subject_id,
            processing_run_id=processing_run_id, release_id=release_id,
            schema_version=schema_version)


def explain_statement(connection: psycopg.Connection, *, statement_id: str) -> dict[str, Any]:
    """Resumen acotado del grafo. Solo metadatos y digests, nunca valores."""
    try:
        identifier = str(uuid.UUID(statement_id))
    except (TypeError, ValueError, AttributeError):
        raise LineageError("financial-lineage-statement-missing",
                           "the statement is not available") from None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT statement_id, lineage_state FROM fincilia.reconciliation_statement "
            "WHERE statement_id=%s", (identifier,))
        statement = cursor.fetchone()
        if statement is None:
            raise LineageError("financial-lineage-statement-missing",
                               "the statement is not available")
        cursor.execute(
            "SELECT input.node_type, input.entity_ref, input.field_name, "
            "input.value_digest, edge.operation, edge.processing_run_id, "
            "edge.engine_release_id, edge.canonical_schema_version "
            "FROM fincilia.lineage_node decision JOIN fincilia.lineage_edge edge "
            "ON edge.to_node_id=decision.node_id AND edge.company_id=decision.company_id "
            "JOIN fincilia.lineage_node input ON input.node_id=edge.from_node_id "
            "AND input.company_id=edge.company_id WHERE decision.node_type='decision' "
            "AND decision.entity_ref=%s AND decision.field_name='statement' "
            "ORDER BY input.node_type, input.entity_ref, input.field_name LIMIT 1003",
            (identifier,))
        rows = cursor.fetchall()
    if len(rows) > 1000:
        raise LineageError("financial-lineage-too-large",
                           "the statement lineage exceeds the bounded view")
    return {
        "statement_id": str(statement[0]), "lineage_state": statement[1],
        "complete": statement[1] == "complete",
        "inputs": [{
            "node_type": row[0], "entity_ref": str(row[1]),
            "field_name": row[2], "value_digest": row[3],
            "operation": row[4], "processing_run_id": str(row[5]),
            "engine_release_id": str(row[6]),
            "canonical_schema_version": row[7],
        } for row in rows],
        "notice": "digest_only_lineage; no values or close authority",
    }
