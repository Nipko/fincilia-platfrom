---
task: FNC-GOV-001
title: Owners humanos, gobierno unipersonal provisional y paquete de decisiones
status: in_progress
implementer: Integration Steward
base_sha: 94ac094
gate: S1-READY
data_ceiling: synthetic_only
accountable_owner: Founder
independent_reviewers: []
---

# Resultado esperado

Registrar que, durante la etapa fundacional, una sola persona humana —`Founder`—
asume provisionalmente todos los roles accountable. La entrega debe permitir avanzar
las decisiones de producto y arquitectura sin representar esa acumulación como una
revisión independiente de seguridad, privacidad, legal, migraciones o semántica
financiera.

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
- `tools/founder_governance/**`

## Criterios de aceptación

1. Los siete slots humanos de `CURRENT_PHASE.md` quedan asignados a `Founder`.
2. El modelo declara una sola identidad humana y detecta que owner y reviewer no son
   independientes cuando ambos resuelven a esa identidad.
3. Cada rol conserva sus responsabilidades y autoridad; no se fusionan controles.
4. Las decisiones técnicas abiertas tienen recomendación, owner, revisores, gate,
   consecuencias y estado humano explícito.
5. Founder puede ratificar dirección y riesgo provisional, pero no satisfacer controles
   que exigen revisión independiente.
6. S1-READY y los gates de datos permanecen fail-closed hasta cumplir sus condiciones.
7. La decisión no autoriza datos reales, piloto real, producción, conectores externos ni
   aprobación automática de movimientos financieros.
8. Existen validador y pruebas negativas para evitar independencia ficticia.

## Fuera de alcance

- Contratar o inventar revisores humanos adicionales.
- Marcar ADR como Accepted o superar S1-READY.
- Resolver decisiones jurídicas, regionales o de proveedor sin evidencia aplicable.
- Cambiar contratos de dominio, migraciones o código de producto.
