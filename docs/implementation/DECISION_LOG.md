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
| IMP-007 | 2026-08-21 | ADR | Proposed | Aclarar stores de capacidad vs persistencia activa y extracción dinámica de políticas del DFD | Architecture | `decision_requests/FNC-PRV-001-FINDINGS.md` DR-ARC-001 |
| IMP-008 | 2026-08-21 | PRIVACY | Proposed | Separar sensibilidad operativa/financiera de la condición y categoría de dato personal | Privacy + Architecture | `decision_requests/FNC-PRV-001-FINDINGS.md` DR-PRV-001 |
| IMP-009 | 2026-08-21 | LEGAL | Proposed | Fijar orden delete-ledger > backup y reloj legal de retención financiera | Legal + Privacy + Platform | `decision_requests/FNC-PRV-001-FINDINGS.md` DR-LEG-001 |
| IMP-010 | 2026-08-21 | ADR | Proposed | Evaluar Brasil y Chile por flujo/servicio; no seleccionar región antes de A02-G01..G10 | Architecture + Legal | ADR-020 y `decision_requests/FNC-ARC-003-A02.md` |
| IMP-011 | 2026-08-21 | GOVERNANCE | Proposed | Modelar por separado IDs contractuales ausentes del catálogo e IDs runtime planeados todavía sin contrato; la reconciliación debe ser dinámica y ejecutable | QA + Integration Steward | `FNC-QA-002`, hallazgo `UD-QA-CATALOG-DRIFT` |
| IMP-012 | 2026-08-21 | TOOLING | Proposed | Automatizar mutaciones aisladas de validadores sin rebajar la adjudicación humana de cambios en contratos y digests golden | QA + Security | `FNC-QA-003`, hallazgo de fragilidad de adjudicación |
| IMP-013 | 2026-08-24 | GOVERNANCE | Accepted | Durante la etapa fundacional `FOUNDER-01` asume provisionalmente todos los roles humanos; la acumulación asigna responsabilidad pero no cuenta como revisión independiente ni supera gates | Founder | Instrucción humana del Founder; `FOUNDER_GOVERNANCE.md`; FNC-GOV-001 |
| IMP-014 | 2026-08-24 | GOVERNANCE | Proposed | Adjudicar como un paquete las diez recomendaciones técnicas que bloquean S1-READY, conservando revisión por una persona distinta donde el control la exige | Founder + owners afectados | `founder-governance.json`; confirmación específica del Founder pendiente |
| IMP-015 | 2026-08-24 | GOVERNANCE | Accepted | La persona única se refiere al operador físico de pruebas que controla personas sintéticas multirrol dentro de la aplicación; no asigna owners humanos de gobierno | Product/Integration Steward | Aclaración humana; `handoffs/FNC-GOV-001-R1.md`; sustituye la interpretación de gobierno unipersonal |
| IMP-016 | 2026-08-24 | GOVERNANCE | Rejected | No se adjudica el paquete técnico bajo una identidad Founder única; las diez decisiones conservan su estado en los contratos fuente | Founder + owners afectados | Corrección FNC-GOV-001-R1; retira la propuesta de adjudicación conjunta |
| IMP-017 | 2026-08-25 | GOVERNANCE/ADR | Accepted | `FOUNDER-01` asume provisionalmente los siete roles accountable y aprueba el paquete recomendado de diez decisiones y ADR-001..010/023/024; no cuenta como revisor independiente y ADR-026/027 quedan fuera | FOUNDER-01 | Instrucción humana vigente; `founder-governance.json`; sustituye las interpretaciones previas solo respecto del gobierno y paquete ahora aprobados |
| IMP-018 | 2026-08-26 | PRODUCT/ADR | Proposed | Modelar primero propuestas manuales 1:N/N:1 de movimientos completos, sin N:M, asignaciones, confirmación ni efecto financiero | Accounting + Architecture + Product | ADR-028; FNC-REC-005; revisión independiente pendiente |
| IMP-019 | 2026-08-29 | SECURITY/IDENTITY | Proposed | Para la beta Google, no afirmar MFA no demostrable; usar invitacion nominal, sesion corta y assurance federado hasta decidir step-up o identidad empresarial | Security + Product | `decision_requests/FNC-IAM-003-FEDERATED-MFA.md`; revision independiente pendiente |

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
