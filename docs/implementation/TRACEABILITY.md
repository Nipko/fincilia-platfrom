# Matriz de trazabilidad

Cadena obligatoria:

Requisito → tarea → decisión/ADR → artefacto → prueba → evidencia → gate.

Una celda de implementación vacía significa no implementado. No se rellena con N/A para aparentar cobertura.

| Requisito | Plan | Tareas iniciales | ADR/artefacto | Pruebas | Gate | Estado |
|---|---|---|---|---|---|---|
| REQ-FNC-000-DRG00 | §0.4 | LEG-001, PRV-002, SEC-003, PLT-004, DAT-003, QA-001 | Paquete DRG | TST-DRG-001 | DRG-00 | Planned |
| REQ-FNC-014-ENGAGEMENT | §14 | DOM-001 | ADR-003, tenancy model | TST-TEN-001, TST-RLS-001 | S1-READY | Draft |
| REQ-FNC-015-MONEY | §15.4 | DOM-002 | Modelo canónico | TST-MON-001 | S1-READY | Planned |
| REQ-FNC-016-COMPLETENESS | §16.1 | DOM-003 | ADR-014 | TST-CMP-001 | S1-READY | Planned |
| REQ-FNC-017-DEDUPE | §17 | DOM-004 | ADR-015 | TST-IDEM-001, TST-DED-001 | S1-READY | Planned |
| REQ-FNC-018-LINEAGE | §18 | DOM-005 | ADR-005, ADR-023 | TST-LIN-001 | S1-READY | Planned |
| REQ-FNC-024-RETRY | §24 | ARC-004, PLT-005 | ADR-007, ADR-008, `events-retries.json` | TST-OUT-001, TST-RET-001, TST-DLQ-001 | S1-READY | Review |
| REQ-FNC-025-CONNECTOR | §25 | ARC-005 | Contrato conector | TST-CON-001 | S1-READY | Planned |
| REQ-FNC-029-XTENANT | §29 | SEC-001, SEC-002, PLT-005 | ADR-002, matriz auth | TST-RLS-001/002 | DRG-01 | Planned |
| REQ-FNC-037-AI | §37–§41 | ARC-006 | ADR-009 | TST-AI-001 | Fase 4 | Planned |
| REQ-FNC-054-QUALITY | §54 | QA-002/003 | Estrategia de pruebas | Catálogo completo | S1-READY | Draft |

## Campos al implementar

- Requirement ID y versión.
- Tarea.
- ADR/decisión.
- Ruta o símbolo implementado.
- PR y commit.
- Test IDs y comando.
- Evidencia.
- Gate.
- Owner.
- Estado.

Un cambio material crea nueva versión del requisito o decisión; no reutiliza silenciosamente el ID.
