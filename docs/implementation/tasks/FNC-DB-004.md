---
task: FNC-DB-004
title: Spike PostgreSQL de reclamo concurrente, outbox y lease expirado
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 1daf11d
integration_sha: pending
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, QA]
---

# Resultado esperado

Probar contra PostgreSQL real las tres invariantes de idempotencia que no son
demostrables con lógica pura y que `FNC-DOM-007` dejó explícitamente fuera:

- `TST-IDEM-001` — dos reclamos concurrentes del mismo trabajo producen una sola
  ejecución, mediante inserción atómica o compare-and-set.
- `TST-IDEM-004` — una caída después del commit de dominio y antes de la entrega no
  pierde el efecto: el outbox lo vuelve a entregar.
- `TST-IDEM-005` — un worker que despierta tras expirar su lease no puede escribir,
  porque su token de fencing es viejo.

El patrón de laboratorio ya está validado en `spikes/FNC-DB-002`: Compose con proyecto
propio, imagen fijada por digest, sin puerto publicado, red interna y limpieza confinada.

# Rutas reservadas

- `spikes/FNC-DB-004/**`
- `tools/concurrency_spike/**`
- `docs/database/concurrency-spike.json`
- `docs/database/CONCURRENCY_SPIKE.md`
- `docs/implementation/tasks/FNC-DB-004.md`
- `docs/implementation/handoffs/FNC-DB-004.md`

# Criterios de aceptacion

- **AC-01.** El contrato ejecutable liga exactamente `TST-IDEM-001/004/005` a
  casos PostgreSQL reales y rechaza evidencia declarada sin ejecucion.
- **AC-02.** Dos sesiones que compiten por un unico trabajo producen exactamente
  un claim y una ejecucion; la perdedora no crea efecto ni espera indefinidamente.
- **AC-03.** Efecto de dominio y outbox se confirman o revierten juntos. Simular
  una caida despues del commit deja un evento pendiente que otro dispatcher puede
  reclamar y entregar una sola vez.
- **AC-04.** Cada lease incrementa un fencing token monotono. Tras expirar y ser
  reclamado por otro worker, el token anterior no puede escribir efecto, outbox ni
  finalizar el trabajo.
- **AC-05.** Runtime opera solo mediante funciones allowlisted; no tiene DDL ni
  escritura directa sobre tablas. El laboratorio no publica puertos.
- **AC-06.** Runner usa argv cerrado, entorno acotado, salida limitada y limpieza
  confinada al proyecto `fincilia-concurrency-spike`.
- **AC-07.** Pruebas unitarias mutan contrato, rutas, proyecto, roles, SQL y
  adjudicacion; las tres invariantes se ejecutan dos veces contra PostgreSQL 17.
- **AC-08.** Handoff registra versiones, comandos, evidencia, hallazgos, rollback
  y revisores pendientes sin aceptar ADR, gate ni arquitectura productiva.

# Rutas prohibidas y limites

No modifica `db/migrations`, aplicaciones, Compose local, CI, ADR aceptados ni
contratos financieros. No elige broker o workflow productivo. El laboratorio es
descartable, solo sintetico y sus resultados prueban invariantes, no autorizan una
implementacion de produccion.
