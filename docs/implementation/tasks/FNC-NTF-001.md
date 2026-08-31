---
id: FNC-NTF-001
title: Notificaciones externas, preferencias y entrega verificable
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: cebbbd7
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

# Resultado implementado

- Preferencia por persona y empresa con consentimiento explícito, locale,
  zona horaria y quiet hours validados.
- Intención lógica idempotente y entrega honesta: mientras no exista proveedor,
  toda entrega queda `suppressed`, nunca `sent` ni `delivered`.
- Plantillas cerradas y contexto limitado por base de datos a periodo, fecha y
  ruta interna; no admite importes, cuentas, documentos ni campos adicionales.
- RLS por empresa y sujeto, API/BFF y controles web con historial propio.
- Retry, reconciliación de timeout y DLQ quedan como parte del puerto de entrega
  real: no se simulan ni se activan antes de configurar proveedor y credenciales.
