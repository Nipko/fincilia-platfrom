---
task: FNC-ARC-005
title: Contrato de conectores con fallback permanente por archivos
status: review_pending
implementer: Integration Steward
base_sha: 209a663
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Definir un contrato ejecutable read-only para conectores que pruebe capacidades,
identidad, completitud, seguridad, modo degradado, legal/costo y fallback permanente sin
recibir credenciales bancarias ni prometer cobertura no certificada.

## Rutas

- `docs/contracts/connectors/**`
- `tools/connector_model/**`
- `docs/implementation/handoffs/FNC-ARC-005.md`
- CI/estado/trazabilidad solo por Integration Steward.

## Dependencias

FNC-ARC-002/004, FNC-DOM-003/004, FNC-PRV-001. Proveedores, región, DPA, SLA y costos
siguen pendientes de owners humanos.

## Criterios

1. Read-only, pagos deshabilitados y cero credenciales bancarias recibidas.
2. Capability unknown nunca se vende como supported.
3. Cursor/paginación/correcciones/pending-posted son versionados.
4. Completitud débil produce unknown y bloquea publicación.
5. Adapter no reintenta; ARC-004 conserva ownership.
6. Webhook firma/replay/digest antes del inbox.
7. Archivo es fallback permanente con los mismos gates y linaje.
8. Schema drift/feed parcial nunca se interpreta cero/completo.
9. SSRF, egress, secretos, company scope y logs son fail-closed.
10. Gates Legal/Security/Cost permanecen pending_human.
