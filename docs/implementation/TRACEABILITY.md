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
| REQ-FNC-018-LINEAGE | §18 | DOM-005, ARC-006A, P3.5, P3.6 | ADR-005/006/023/024, `lineage-model.json` (`transform_plan_contract`, `row_override_contract`), `cross-contract-vocabulary.json`, `V0009`, `V0012` | TST-LIN-001..006, TST-OVR-001..006, TST-PAR-001..007, TST-XCON-001..006, `db/tests/test_row_overrides.py` | S1-READY | Review |
| REQ-FNC-024-RETRY | §24 | ARC-004, PLT-005, P3.6 | ADR-007, ADR-008, `events-retries.json` (`checkpoint_contract`) | TST-OUT-001, TST-RET-001, TST-DLQ-001, TST-CHK-001..003, `db/tests/test_extraction_resume.py` | S1-READY | Review |
| REQ-FNC-025-CONNECTOR | §25 | ARC-005 | `connector-contract.json`, manifest schema | TST-CON-001..015 | S1-READY | Review |
| REQ-FNC-029-XTENANT | §29 | SEC-001, SEC-002, PLT-005 | ADR-002, matriz auth, `spikes/FNC-PLT-005` | TST-RLS-001/002, TST-AUTH-001/002 | DRG-01 | Review |
| REQ-FNC-037-AI | §37–§41 | ARC-006 | ADR-009 | TST-AI-001 | Fase 4 | Planned |
| REQ-FNC-054-QUALITY | §54 | QA-002..005 | `test-strategy.json`, `golden-harness.json`, `test-catalog-model.json`, `mutation-harness.json` | TST-MUT-001, GH-REG-*, GH-RUN-*, GH-ORACLE-*, MUT-* | S1-READY | Review pending |
| REQ-FNC-055-GOVERNANCE | §51–§52 | GOV-003 | `work-graph.json`, reservas y política de gates | TST-META-001 | S1-READY | Review |
| REQ-FNC-056-LOCAL | §20, §52 | PLT-002 | `infra/local/compose.yaml`, bootstrap y lifecycle | TST-LOCAL-001 | S1-READY | Review |
| REQ-FNC-057-UX | §5–§13, §54.5 | UX-001, FNC-WEB-001 | IA, ADR-010 y recorrido web local P3.7 | TST-A11Y-001, suites de `apps/web` | S1-READY | Review; implementación local sintética no mueve el gate |
| REQ-FNC-058-REGION | §20, §29, §31 | ARC-003 | ADR-020 y `region-transmission-decision.json` | TST-A02-001 | A-02 | Review; human decision pending |
| REQ-FNC-059-ADR-READINESS | §51–§52 | ARC-006 | `adr-readiness.json`, inventario ADR y blockers | `tools.adr_readiness.test_validate` | S1-READY | Review; gate not met |
| REQ-FNC-060-CONNECTIVITY-VENDOR | §25, §44 | INT-001 | `provider-evaluation.json`, due diligence y RFQ | `tools.provider_evaluation.test_validate` | INT-G02..G07 | Review; quotes pending |
| REQ-FNC-061-CAPITAL | §49–§50 | FIN-001 | `budget-f0-f2.json`, escenarios COP/USD +30% | `tools.budget_model.test_validate` | F0-CAPITAL | Review; founder approval pending |
| REQ-FNC-062-RESEARCH | §48 F0 | RES-001 | `research-protocol.json`, guion y límites de captura | `tools.research_protocol.test_validate` | RES-G01..G04 | Review; real sessions blocked |
| REQ-FNC-063-BRAND | §48 F0 | BRD-001 | `brand-clearance.json`, búsqueda y arquitectura de marca | `tools.brand_clearance.test_validate` | BRD-G01..G06 | Review; counsel pending |
| REQ-FNC-064-WORKSPACE | §20–§21 | PLT-006 | `workspace-scaffold.json`, siete componentes | `tools.workspace_contract.test_validate` | S1-READY | Review; product code blocked |
| REQ-FNC-065-CONFIG | §20, §29 | CFG-001 | `runtime-config.json`, `.env.example` | `tools.runtime_config.test_validate` | CFG-G01..G03 | Review; production disabled |
| REQ-FNC-066-MIGRATIONS | §23.2 | DB-001 | `migration-tooling.json`, ADR-002 evaluation | `tools.migration_readiness.test_validate` | DB-G01..G04 | Review; tool not selected |
| REQ-FNC-067-SUPPLY-CHAIN | §29, §54 | SUP-001 | `supply-chain.json`, inventario de pins y gaps de procedencia | `tools.supply_chain.test_validate` | DRG-00 / TM-005 | Review pending; SBOM, firma y procedencia abiertos |
| REQ-FNC-068-MIGRATION-SPIKE | §23.2 | DB-002 | `migration-spike.json`, PostgreSQL 17 descartable | `tools.migration_spike.test_validate`, carril CI PostgreSQL | ADR-002-MIGRATIONS | Review pending; 12/12 invariantes, ADR no aceptado |
| REQ-FNC-069-DEVELOPER-CLI | §20, §52 | PLT-007 | `developer-cli.json`, CLI allowlisted | `tools.dev_cli.test_cli` | S1-READY | Review pending |
| REQ-FNC-070-S1-READINESS | §51–§52 | GAT-003 | `s1-readiness.json`, reporte fail-closed | `tools.s1_readiness.test_validate` | S1-READY | Review pending; 10 blockers, aceptación humana pendiente |
| REQ-FNC-071-OPERATIONS | PRD §5.2, §7, §9 y §13 | OPS-001 | `source_cycle`, `source_expectation`, proyeccion operativa API/web | 134 web, 95 API, 292 PostgreSQL, 16 Chromium y 9 Axe | S1-READY | Review pending; recordatorios solo dentro de plataforma y datos sinteticos; CI 32796949542 verde |
| REQ-FNC-072-ISSUED-CONTEXT | §29; tenancy §7 | SEC-004, PLT-005 | IMP-017/`UD-ISSUED-CONTEXT`, V0021, `issued_contexts.py` | 8 pruebas PostgreSQL reales; migration readiness | S1-READY | Review pending; capacidad durable implementada, consumidores y revision independiente pendientes |
| REQ-FNC-073-JOB-CONTEXT | §29; tenancy §7; events/retries | SEC-005, SEC-004 | V0022, `enqueue_processing_run(..., issued_context_id)`, `processing_context_is_valid` | 5 pruebas PostgreSQL nuevas; 44 contexto/despacho; 26 HTTP; API/worker unit | S1-READY | Review pending; consumidor de procesamiento implementado, fase contract y revision independiente pendientes |
| REQ-FNC-074-AUDIT-CENTER | PRD §7 y §9; privacy PA-12/PA-13 | AUD-001, SEC-001 | `/audit/events`, `list_audit_page`, `/auditoria` | 111 API, 28 PostgreSQL/HTTP, 170 web y recorrido visual real de filtros/paginacion; build/lint/typecheck | S1-READY | Review pending; solo metadatos sinteticos, consulta company-by-company y revision independiente pendiente |
| REQ-FNC-075-WSL-RUNTIME | §20; developer CLI UD-PLT-CLI-WSL | PLT-009, PLT-007 | `fincilia-local.ps1`, `wsl-local-runtime.json`, validador | 11 pruebas de contrato; 126 suites Platform/CLI; up/status/down/up y persistencia real | S1-READY | Review pending; stack local estable y sintetico, revision independiente pendiente |
| REQ-FNC-076-CORRECTION-APPLICATION | §18; ADR-026 | CLN-002, CLN-001, DOM-005 | V0023/V0024, `correction_application.py`, manifiesto y `lineage_row_override`, accion/pantalla web | 115 API, 4 PostgreSQL, 174 web, migracion repetible y recorrido visual Sofia→Beto→Sofia | S1-READY | Review pending; base inmutable y version derivada validadas con datos sinteticos; ADR-026 y revision independiente pendientes |
| REQ-FNC-077-CORRECTION-APPLICABILITY | §18; ADR-026 | CLN-003, CLN-002 | `complete_lineage_fields`, targets derivados de `dataset.lineage_plan_id`, rechazo `correction-field-not-applicable` y aviso web | 117 API, 10 PostgreSQL, 174 web y recorrido visual con selector reducido por plan | S1-READY | Review pending; evita propuestas imposibles y no inventa linaje; revisión independiente pendiente |
| REQ-FNC-078-EXCLUSIVE-CONFIRMATION | §17; ADR-027 | REC-004, REC-002 | V0025, `match_confirmation_member`, trigger y savepoint de decision, indicador web de conflicto | 117 API, 2 PostgreSQL/MinIO, 176 web, replay de migracion y recorrido visual real | S1-READY | Review pending; un movimiento tiene una sola confirmacion, sin efecto financiero ni cierre; revision independiente pendiente |
| REQ-FNC-079-GROUPED-PROPOSALS | PRD §5.1/§17; ADR-028 Proposed | REC-005, REC-004, DOM-003, DOM-005 | V0035, `match_group_candidate`, recibo idempotente, API company-scoped y compositor web 1:N/N:1 | 151 API, 2 PostgreSQL/HTTP focales, 210 web, 28 Chromium, 17 Axe, replay V0035 y recorrido visual sintético | S1-READY | Review pending; solo movimientos completos y borradores sin asignaciones, decisión, efecto financiero ni cierre; ADR y revisión independiente pendientes |

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
