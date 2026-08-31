---
id: FNC-BIL-001
title: Tres planes, suscripciones, entitlements y facturación
status: proposed
implementer: Codex principal dev + Integration Steward
base_sha: pending_after_ntf_001
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

