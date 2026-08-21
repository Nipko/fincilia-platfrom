# Registro de decisiones de implementación

Registro append-only. Una corrección crea una nueva decisión que sustituye a la anterior.

| ID | Fecha | Tipo | Estado | Decisión | Owner | Evidencia/revisión |
|---|---|---|---|---|---|---|
| IMP-001 | 2026-08-21 | Governance | Accepted | El plan unificado es la única fuente estratégica vigente | Product/Architecture | Plan §0 |
| IMP-002 | 2026-08-21 | Governance | Accepted | IDs estables FNC-STREAM-NNN; el sprint no forma parte del ID | Integration Steward | Paquete v1 |
| IMP-003 | 2026-08-21 | Governance | Accepted | E0/E1 preceden S1-READY; Sprint 1 inicia después del gate | Product/Architecture | Resolución §51–§52 |
| IMP-004 | 2026-08-21 | Governance | Accepted | En agentes con filesystem compartido solo el coordinador opera Git y archivos centrales | Integration Steward | Riesgo de colisión |
| IMP-005 | 2026-08-21 | Data | Accepted | Hasta DRG-00 solo se permiten datos completamente sintéticos | Security/Privacy/Product | Plan §0.4 |
| IMP-006 | 2026-08-21 | Tooling | Accepted | Git se ejecuta desde Windows en este workspace; Docker y servicios desde WSL | Integration Steward | Evitar EOL/permisos inconsistentes |

## Campos para nuevas decisiones

- ID y fecha.
- Tipo: ADR, PRODUCT, SECURITY, PRIVACY, LEGAL, DATA o GOVERNANCE.
- Estado: Proposed, Accepted, Rejected, Superseded o Expired.
- Owner y aprobadores.
- Fase/gate.
- Contexto, alternativas y decisión.
- Consecuencias, costo operativo y rollback.
- Evidencia y rutas/contratos afectados.
- Trigger de revisión y superseded_by.
