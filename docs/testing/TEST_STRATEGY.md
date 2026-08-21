# Estrategia de pruebas v0

- Estado: Seed
- Tareas: FNC-QA-002 y FNC-QA-003

## Capas

1. Unit: invariantes y transformaciones puras.
2. Property: dinero, fechas, locales, idempotencia y combinaciones.
3. Contract: OpenAPI, eventos, jobs y conectores.
4. Integration: PostgreSQL/RLS, objetos, outbox y workers.
5. Golden: parser/template/engine_release.
6. Security: cross-tenant, archivos, replay, egress y restore.
7. E2E: walking skeleton sintético.
8. Usability/accessibility.

## Gate de CI inicial

- Formato, lint y tipos.
- Unit/property.
- JSON Schema y documentación.
- Secret scan y dependency/container scan.
- Detección de fixtures sin manifiesto.
- Migraciones desde cero.
- RLS positivo/negativo cuando exista DB.

El catálogo de IDs vive en TEST_CATALOG.md. Un test solo cuenta como evidencia si registra comando, versión y resultado.

