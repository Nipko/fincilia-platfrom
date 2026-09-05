---
id: FNC-BIL-002
title: Stripe Checkout, portal y suscripciones verificables
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 88781f7
gate: DRG-00/DRG-01/GA-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Finance, Security, Privacy, Architecture, Database, QA]
---

# Resultado esperado

Dejar Stripe listo como proveedor de pago, apagado por defecto y sin precios ni
credenciales reales: Checkout alojado, Customer Portal, webhook firmado,
aplicacion idempotente y monotona del estado de suscripcion, referencias de
proveedor no expuestas, configuracion fail-closed y experiencia web completa.

# Rutas reservadas

- `apps/api/**` y `apps/web/**` en la superficie de billing
- `.env.example`
- `packages/platform/python/fincilia_platform/settings.py`
- `db/migrations/V0064__stripe_billing_runtime.sql` y
  `db/migrations/V0065__stripe_plan_readiness.sql` y
  `db/migrations/V0066__stripe_webhook_serialization.sql`
- `db/tests/test_stripe_billing.py`
- `db/bootstrap/roles.py` y `db/bootstrap/test_roles.py`
- `docs/adr/ADR-038-plans-entitlements-billing.md`
- `docs/database/migration-tooling.json`
- `docs/platform/runtime-config.json`
- `infra/aws/private-pilot/variables.tf`, `compute.tf`,
  `pilot.auto.tfvars.example` y `README.md`
- `tools/aws_private_pilot/model.py` y `test_validate.py`
- `docs/product/web-functional-status.json`
- `docs/product/STRIPE_READINESS.md`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Criterios de aceptacion

1. El servidor resuelve plan, version y `price_id`; el navegador nunca envia
   monto, moneda ni privilegios.
2. Checkout y Portal solo aceptan managers activos de la firma y usan claves de
   idempotencia estables.
3. El webhook verifica el cuerpo crudo con `Stripe-Signature`, limita tamano,
   acepta un vocabulario cerrado y nunca persiste su payload.
4. Eventos duplicados o fuera de orden no degradan ni reactivan una suscripcion;
   la unica autoridad comercial es un evento Stripe verificado.
5. La base conserva referencias tecnicas provider-only y expone al producto solo
   digests, estados normalizados y trazabilidad append-only.
6. `payments_enabled=false` es el default. Activar exige pilot, Secrets Manager,
   identidad administrada, datos reales atestiguados y configuracion Stripe
   completa; los tres planes y sus precios se cargan despues.
7. Pruebas unitarias, HTTP, PostgreSQL, web, build, quality gate y handoff son
   reproducibles; no se usa dinero real ni se mueve ningun gate.

# Limites y rollback

No se crean productos, precios, clientes, cobros ni endpoints live en Stripe.
No se almacenan PAN/CVV ni payloads de webhook. La migracion es expand-only y la
capacidad queda inerte sin configuracion comercial. El rollback apaga el flag y
retira las rutas/UI consumidoras; las tablas append-only se conservan para
auditoria. Aprobacion independiente y activacion siguen fuera de esta tarea.
