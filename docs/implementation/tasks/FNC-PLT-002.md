---
task: FNC-PLT-002
title: Entorno local reproducible y mínimo
status: review_pending
implementer: Integration Steward
base_sha: 380ad9e
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Platform, Security, Architecture]
---

# Resultado esperado

Proveer un entorno Docker Compose local, fijado e inspeccionable que arranque desde cero,
se limite a loopback, tenga healthcheck, conserve datos sintéticos entre reinicios y se
detenga o purgue de manera explícita.

## Contenedores mínimos aceptados para E0

- PostgreSQL 17: persistencia autoritativa del control y dominio sintético.
- Un runner efímero del mismo artefacto PostgreSQL, habilitado solo con perfil `test`.

Valkey, Temporal, analytics y object storage no se activan hasta que su necesidad, motor,
región y contrato estén decididos. Su ausencia no permite reemplazarlos por PostgreSQL.

## Rutas

- `infra/local/**`
- `tools/local_stack/**`
- `docs/implementation/tasks/FNC-PLT-002.md`
- `docs/implementation/handoffs/FNC-PLT-002.md`
- `docs/implementation/evidence/FNC-PLT-002/**`
- Integración central por Integration Steward.

## Criterios de aceptación

1. Imagen fijada por tag y digest; proyecto y puerto deterministas.
2. Único puerto publicado ligado a `127.0.0.1`.
3. Red interna, volumen nombrado, init read-only y healthcheck.
4. Rol de aplicación `NOSUPERUSER`, `NOBYPASSRLS`, sin creación en `public`.
5. Arranque limpio, healthcheck, reinicio, stop/start, persistencia y purga probados.
6. Datos bootstrap y probes marcados como sintéticos.
7. Validador estático falla ante imagen flotante, exposición, privilegios o drift.
8. CI reproduce el lifecycle sin depender de secretos ni servicios externos.

## Fuera de alcance

- Migración productiva, cloud, backups productivos, datos reales o conectores.
- Convertir el bootstrap local en esquema de producto.
- Declarar aceptados ADR, proveedor, región o S1-READY.

