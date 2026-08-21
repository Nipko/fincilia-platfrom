# Modelo canónico v0 — índice

- Estado: Seed
- Tareas: FNC-DOM-002 a FNC-DOM-005

## Schemas propietarios propuestos

iam, control, sources, ingestion, clean, finance, reconciliation, close, risk, reporting, billing, platform y audit.

## Invariantes de persistencia

- Todo registro financiero tiene company_id no nulo.
- FK financiera usa par compuesto company_id + id.
- UUIDv7 de aplicación no codifica tenant.
- Dinero es numeric/decimal, monto positivo, dirección explícita y moneda ISO 4217.
- occurred_at, posted_at, value_date y accounting_date son distintos.
- UTC y zona/locale originales se conservan.
- Objetos inmutables y decisiones append-only no se actualizan destructivamente.
- No hay ON DELETE CASCADE desde company hacia evidencia o finanzas.
- JSONB solo contiene metadatos acotados y validados.
- Payload/binario grande permanece en object storage.
- Dedupe fingerprint nunca es UNIQUE.

## Entidades por etapa

Evidencia/proceso:

- data_source, connection, source_expectation.
- source_artifact, artifact_version, document.
- processing_run, engine_release.
- raw_record, source_record.
- schema_profile, mapping_template_version, transform_recipe_version, manual_overlay.
- dataset_version, origin_locator, lineage_edge.

Finanzas:

- obligation, money_movement, movement_evidence_link, settlement.
- ledger_entry, ledger_line, counterparty, financial_account.
- account_balance, external_reference, reference_dataset_version.

Conciliación/cierre:

- completeness_assessment.
- match_run, match_candidate, match_group, match_decision.
- dedupe_candidate, merge_decision, exception.
- reconciliation_statement, reconciling_item.
- close_cycle, close_task, close_approval, closed_snapshot.

