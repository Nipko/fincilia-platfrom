---
task: FNC-GOV-001
title: Owners humanos, suplentes, RACI y aprobadores por gate
status: review_pending
implementer: Integration Steward
base_sha: 94ac094
gate: S1-READY
data_ceiling: synthetic_only
accountable_owner: Founder
independent_reviewers: ["Security distinct human pending", "Privacy or Legal distinct human pending", "Accounting distinct human pending", "Database distinct human pending"]
---

# Resultado esperado

Registrar un owner humano accountable provisional, su RACI y el paquete explícito de
decisiones técnicas y ADR aprobado, sin confundirlo con una revisión independiente.

## Corrección 2026-08-24

La frase «una sola persona hará varios roles» se refería al operador físico que prueba
la aplicación mediante personas sintéticas, no a concentrar todos los owners de
gobierno en Founder. Los commits iniciales quedan corregidos de forma append-only; sus
conclusiones no deben consumirse como estado vigente.

## Adjudicación vigente 2026-08-25

El Founder aprobó expresamente la RACI provisional y el paquete recomendado. Se
registra como `FOUNDER-01`, alias estable cuya correspondencia civil permanece fuera
del repositorio. La decisión IMP-017 sustituye el bloqueo previo, pero no satisface
ningún control que exija una segunda persona.

## Rutas reservadas

- `CURRENT_PHASE.md`
- `docs/implementation/BACKLOG_PHASE_0.md`
- `docs/implementation/OWNERSHIP.md`
- `docs/implementation/DECISION_LOG.md`
- `docs/implementation/work-graph.json`
- `docs/implementation/founder-governance.json`
- `docs/implementation/FOUNDER_GOVERNANCE.md`
- `docs/implementation/tasks/FNC-GOV-001.md`
- `docs/implementation/handoffs/FNC-GOV-001.md`
- `docs/implementation/handoffs/FNC-GOV-001-R1.md`
- `tools/founder_governance/**`

## Criterios de aceptación

1. Founder asigna una persona humana nominal o aprueba explícitamente una RACI
   provisional de gobierno. **Cumplido por `FOUNDER-01` e IMP-017.**
2. Owner y reviewer independientes se resuelven a personas distintas cuando el gate lo
   exige.
3. Cada rol conserva sus responsabilidades y autoridad; no se fusionan controles.
4. S1-READY y los gates de datos permanecen fail-closed hasta cumplir sus condiciones.
5. La decisión no autoriza datos reales, piloto real, producción, conectores externos ni
   aprobación automática de movimientos financieros.

## Fuera de alcance

- Contratar o inventar revisores humanos adicionales.
- Marcar ADR como Accepted o superar S1-READY.
- Resolver decisiones jurídicas, regionales o de proveedor sin evidencia aplicable.
- Cambiar contratos de dominio, migraciones o código de producto.
- Diseñar o implementar el selector local de persona/rol sintético.

## Pendiente de revisión

La asignación accountable ya no está bloqueada. Siguen vacantes personas distintas
para las revisiones independientes de Accounting, Database, Security y Privacy/Legal;
por diseño no se inventan ni se sustituyen con usuarios sintéticos de la aplicación.
