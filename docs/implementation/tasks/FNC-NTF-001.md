---
id: FNC-NTF-001
title: Notificaciones externas, preferencias y entrega verificable
status: proposed
implementer: Codex principal dev + Integration Steward
base_sha: pending_after_ing_006
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Privacy, Security, Platform, Product, QA]
---

# Resultado esperado

Convertir recordatorios internos elegibles en intenciones de notificación
company-scoped, con preferencias, quiet hours, outbox, entrega idempotente,
historial y supresión. El adaptador real queda apagado hasta el final.

# Criterios de aceptación

Allowlist estricta de plantilla, sin datos financieros sensibles; consentimiento
y baja; idempotencia/retry/DLQ; estados honestos; API/web; auditoría minimizada y
pruebas de aislamiento y concurrencia.

