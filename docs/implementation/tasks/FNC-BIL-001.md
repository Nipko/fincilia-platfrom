---
id: FNC-BIL-001
title: Tres planes, suscripciones, entitlements y facturación
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 80b1cbb
gate: DRG-00/DRG-01/GA-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Finance, Security, Architecture, QA]
---

# Resultado esperado

Ofrecer catálogo de tres planes, trial, suscripción por firma, entitlements,
medición idempotente, historial y consola administrativa. Checkout y webhooks
reales permanecen desactivados hasta seleccionar y configurar proveedor.

# Criterios de aceptación

Catálogo versionado; entitlements no autorizan datos; mínimos de seguridad y
portabilidad nunca se bloquean; uso append-only; cambios idempotentes; RLS y
alcance de firma; API/web; webhook fail-closed; pruebas y handoff.

# Resultado implementado

- Catálogo versionado de Inicio, Negocio y Contador con capacidades explícitas;
  seguridad, privacidad y exportación básica son invariantes en los tres.
- Evaluación por firma, cambio idempotente, historial append-oriented y consola
  para owner/firm_admin. No se denomina trial ni suscripción pagada.
- Medición idempotente de documentos y bytes al crear evidencia; replays no
  duplican uso. Los entitlements no participan en RBAC/RLS.
- Inbox de webhook sin privilegios runtime, checkout fail-closed y RLS por
  membresía. El rol app no puede inventar proveedor, pago, trial ni plan activo.
- Precio, moneda, impuestos, límites, trial y proveedor quedan sin configurar
  hasta la decisión comercial consolidada.
