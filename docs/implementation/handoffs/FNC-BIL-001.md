---
id: FNC-BIL-001
status: REVIEW_PENDING
base_sha: 80b1cbb
integration_sha: pending
data_ceiling: synthetic_only
independent_reviewers: [Product, Finance, Security, Architecture, QA]
---

# Entrega

V0050 introduce un catálogo versionado de tres planes, cuenta de billing por
firma, suscripción, eventos, uso append-only e inbox de webhook provider-neutral.
V0051 restringe el runtime a evaluaciones sin precio: incluso con SQL directo no
puede inventar `active`, `trialing`, proveedor ni cliente de pagos, y no puede
reescribir la identidad de una suscripción.

La cuenta web muestra Inicio, Negocio y Contador, el uso observado y el historial.
Owner o firm_admin puede cambiar la evaluación idempotentemente. La UI dice de
forma explícita que no hay cobro ni precio publicado. Seguridad, privacidad y
exportación básica permanecen incluidas en todas las familias y ningún
entitlement concede autorización.

# Evidencia ejecutada

- V0050/V0051 aplicadas sobre PostgreSQL 17 real con checksum.
- `db.tests.test_billing_plans`: 3 pruebas, OK; catálogo,
  cambio/replay/conflicto, uso idempotente, owner-only, checkout 503 y rechazo
  de estados de pago forjados por el runtime.
- Regresión de carga documental: 28 pruebas, OK con la medición transaccional.
- Web `/cuenta`: TypeScript, 3 pruebas y build Next.js de producción, OK.
- La creación nueva de un documento registra una unidad y bytes en la misma
  transacción de su fila; un duplicado no vuelve a medir.

# Límites y decisiones pendientes

- ADR-038 sigue `Proposed`; no se acepta en nombre de Finance/Security.
- Precio, moneda, impuestos, límites exactos, trial, morosidad y proveedor no
  tienen valor ficticio. `payments_enabled=false` y checkout responde 503.
- La inbox no tiene privilegios runtime ni endpoint hasta definir firma de
  webhook. No existe customer o invoice externo fabricado.
- DRG-00/DRG-01/GA-01 y `synthetic_only` no cambian.

# Rollback

Retirar consumidor web, rutas y medición. V0050/V0051 son expand-only y pueden
permanecer sin productores; no reescribir migraciones aplicadas.
