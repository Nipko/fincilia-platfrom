---
id: FNC-NTF-001
status: REVIEW_PENDING
base_sha: cebbbd7
integration_sha: pending
data_ceiling: synthetic_only
independent_reviewers: [Privacy, Security, Platform, Product, QA]
---

# Entrega

Los recordatorios operativos elegibles ya producen intenciones idempotentes y
un historial de entrega por persona. Cada usuario controla consentimiento,
idioma, zona y horario silencioso. V0048 separa preferencia, intención y entrega;
V0049 restringe RLS también por sujeto y convierte el contexto de plantilla en
una allowlist exacta de tres campos minimizados.

El proveedor continúa deliberadamente apagado. Una preferencia habilitada crea
una entrega `suppressed: adapter_unconfigured`; una deshabilitada crea
`suppressed: user_opt_out`. La interfaz no llama enviado ni entregado a ninguno
de esos estados.

# Evidencia ejecutada

- V0048 y V0049 aplicadas sobre PostgreSQL 17 real, checksums registrados.
- `db.tests.test_operational_reminders`: 3 pruebas, OK; incluye autorización,
  aislamiento, preferencia, replay idempotente, estado honesto y validación TZ.
- Web: TypeScript, 2 pruebas de recordatorios y build Next.js de producción, OK.
- La bandeja no expone destinos, contenido financiero ni referencias del
  proveedor; el audit conserva solo metadatos allowlisted.

# Límites y revisión pendiente

- ADR-037 sigue `Proposed`; esta entrega no lo acepta.
- Retry, reconciliación de timeout y DLQ se materializan al conectar un adaptador
  real; no se fabrica evidencia de entrega mientras está desactivado.
- Proveedor, From/Reply-To, DKIM, textos de baja y política definitiva de quiet
  hours quedan en la lista consolidada para el Founder.
- DRG-00/DRG-01 y el techo `synthetic_only` no cambian.

# Rollback

Retirar rutas y controles web y dejar de crear intenciones. V0048/V0049 son
expand-only y pueden permanecer sin productores; no reescribir migraciones ya
aplicadas.
