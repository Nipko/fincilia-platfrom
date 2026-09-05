---
id: FNC-NTF-002
title: Despacho durable de correo y adaptador AWS SES
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 2906a00
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Privacy, Security, Platform, Product, QA]
---

# Resultado esperado

Completar el camino tecnico de correo transaccional desde una intencion
company-scoped hasta un adaptador AWS SES, con destino cifrado, arriendo durable,
reintentos acotados, resultado incierto fail-closed, feedback idempotente y
diagnostico. El proveedor permanece apagado por defecto y no se envia correo.

# Rutas reservadas

- `apps/api/src/fincilia_api/notifications.py`
- `apps/api/src/fincilia_api/oidc.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/api/tests/test_notifications.py`
- `apps/api/tests/test_oidc.py`
- `packages/platform/python/fincilia_platform/settings.py`
- `packages/platform/python/fincilia_platform/email_delivery.py`
- `packages/platform/python/fincilia_platform/__init__.py`
- `workers/notification/**`
- `db/migrations/V0059__notification_dispatch_and_encrypted_destination.sql`
- `db/migrations/V0060__notification_delivery_at_most_once.sql`
- `db/migrations/V0061__unique_notification_provider_reference.sql`
- `db/tests/test_notification_dispatch.py`
- `docs/database/migration-tooling.json`
- `infra/local/compose.yaml`
- `infra/local/db/init/001_bootstrap.sql`
- `db/bootstrap/roles.py`
- `db/bootstrap/test_roles.py`
- `tools/database_bootstrap/control.py`
- `tools/database_bootstrap/test_control.py`
- `infra/aws/private-pilot/compute.tf`
- `apps/api/Dockerfile`
- `.github/workflows/ci.yml`
- `.env.example`
- `docs/platform/runtime-config.json`
- `apps/web/src/app/recordatorios/**`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/web-capabilities.ts`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Criterios de aceptacion

1. Ningun correo se guarda en claro: solo referencia HMAC y ciphertext KMS.
2. El dispatcher usa un rol separado, funciones acotadas, lease con fencing y
   cero privilegios directos sobre identidad o finanzas.
3. SES recibe plantillas cerradas sin importes, cuentas, documentos ni adjuntos.
4. Fallos transitorios reintentan con limite; timeout incierto nunca reenvia a
   ciegas; rechazo, rebote y queja suprimen el destino.
5. Feedback se deduplica por digest y no conserva payload del proveedor.
6. La web distingue queued, sent, delivered, failed, uncertain y suppressed.
7. Configuracion y proveedor fallan cerrados; local no hace egress ni envia.
8. Migracion, unitarias, PostgreSQL, web, E2E y accesibilidad quedan verdes.

# Limites

Solo datos sinteticos. No activa SES, no crea identidad de dominio, no usa una
direccion real, no acepta ADR-037, DRG-00, DRG-01 o GA-01.
