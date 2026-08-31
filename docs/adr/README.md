# Architecture Decision Records

Los ADR Accepted no se reescriben sustantivamente; una decisión nueva los supersede. Las aprobaciones humanas pendientes se muestran explícitamente.

El estado operativo y los blockers de aprobación se verifican en
[`ADR_READINESS.md`](../architecture/ADR_READINESS.md); una etiqueta Accepted no sustituye
owners nominales, revisión independiente ni el gate S1-READY.

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
| [012](ADR-012-idp-subject-assurance.md) | IdP, subject, assurance y registro por adaptador | Proposed; adaptador sintetico autorizado, IdP real pendiente |
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
| [026](ADR-026-staged-field-overlay.md) | Overlay tipado por etapas | Proposed; revisión Accounting/Security/Database pendiente |
| [027](ADR-027-reconciliation-review-ledger.md) | Ledger de propuesta y decision humana de conciliacion | Proposed; revisión Accounting/Security/Database/Architecture pendiente |
| [028](ADR-028-reconciliation-group-proposals.md) | Propuestas manuales agrupadas sin asignaciones | Proposed; revisión Accounting/Security/Database/Architecture/Product pendiente |
| [029](ADR-029-opentofu-aws-t0.md) | Control plane AWS T0 con OpenTofu | Proposed; laboratorio sintetico aplicado, revision pendiente |
| [030](ADR-030-aws-t1-remote-lab.md) | Host unico SSM para laboratorio AWS T1 | Proposed; laboratorio sintetico aplicado, revision pendiente |
| [031](ADR-031-closed-synthetic-beta.md) | Beta cerrada sintetica antes de DRG-01 | Proposed; BETA-01 condicionado a evidencia y revision independiente |
| [032](ADR-032-aws-private-real-data-pilot.md) | Entorno AWS separado para piloto privado real | Proposed; bloqueado por DRG-00/01 y revisión independiente |
| [033](ADR-033-uat-production-platform-administration.md) | UAT separado, promoción limpia y administración de plataforma | Proposed; dirección del Founder registrada, revisión independiente pendiente |
| [034](ADR-034-github-oidc-ecr-publication.md) | Publicación OIDC de imágenes a ECR | Proposed; implementación y evidencia integradas, revisión independiente pendiente |
| [035](ADR-035-accounting-period-close.md) | Cierre y reapertura de periodos | Proposed; implementación sintética autorizada, revisión Accounting/Security/Database pendiente |
| [036](ADR-036-safe-pdf-ocr.md) | PDF seguro y OCR desacoplado | Proposed; parser local primero, proveedor externo pendiente |
| [037](ADR-037-notification-delivery.md) | Entrega externa de notificaciones | Proposed; adaptadores reales desactivados |
| [038](ADR-038-plans-entitlements-billing.md) | Planes, entitlements y facturación | Proposed; cobros reales desactivados |

## Estados

- Proposed: requiere decisión.
- Accepted: dirige implementación.
- Rejected: evaluado y descartado.
- Superseded: sustituido por otro ADR.
- Deprecated: sigue existiendo pero debe retirarse.
