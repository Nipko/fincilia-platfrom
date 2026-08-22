# Architecture Decision Records

Los ADR Accepted no se reescriben sustantivamente; una decisión nueva los supersede. Las aprobaciones humanas pendientes se muestran explícitamente.

| ADR | Tema | Estado |
|---:|---|---|
| [001](ADR-001-modular-monolith-workers.md) | Monolito modular + workers | Accepted shape; stack pending spike |
| [002](ADR-002-postgresql-rls.md) | PostgreSQL, RLS y migraciones | Proposed |
| [003](ADR-003-organization-company-engagement.md) | Organization/company/engagement | Accepted |
| [004](ADR-004-object-storage-evidence-zones.md) | Object storage por zonas | Accepted; retention pending |
| [005](ADR-005-field-lineage.md) | Linaje por campo | Accepted |
| [006](ADR-006-recipes-overlays.md) | Recetas y overlays | Accepted |
| [007](ADR-007-outbox-retry.md) | Outbox, cola y retry ownership | Accepted pattern |
| [008](ADR-008-temporal-execution.md) | Temporal y verdad de ejecución | Accepted pattern |
| [009](ADR-009-ai-gateway.md) | AI Gateway y prohibiciones | Accepted |
| [010](ADR-010-web-mobile-boundary.md) | Responsabilidades web/móvil | Accepted |
| 011 | Metering SRP/OCR/empresa | Planned |
| 012 | IdP, subject y assurance | Planned |
| 013 | RBAC/ABAC/SoD | Planned |
| [014](ADR-014-completeness-balances.md) | Completitud y saldos | Accepted |
| [015](ADR-015-safe-deduplication.md) | Dedupe cross-source seguro | Accepted |
| 016 | Parquet/warehouse por umbral | Planned |
| 017 | No Kafka/Kubernetes inicial | Planned |
| 018 | OCR abstraído/fallback | Planned |
| 019 | OpenTelemetry y audit log | Planned |
| 020 | Región/transmisión/subencargados | Proposed; paquete A-02 en review, decisión humana pendiente |
| 021 | RPO/RTO/delete ledger/Object Lock | Planned |
| 022 | Routing/celdas y transferencia | Planned |
| [023](ADR-023-engine-release.md) | Engine release y reproducibilidad | Accepted |
| 024 | Broker móvil sin side effects | Planned |
| 025 | Propiedad/portabilidad de recetas | Planned |

## Estados

- Proposed: requiere decisión.
- Accepted: dirige implementación.
- Rejected: evaluado y descartado.
- Superseded: sustituido por otro ADR.
- Deprecated: sigue existiendo pero debe retirarse.
