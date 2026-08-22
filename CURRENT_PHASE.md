---
program: FINCILIA
implementation_package_version: 1.0
plan_version: 1.0-unificada
phase_id: F-1_F0
phase_name: Descubrimiento y arquitectura ejecutable
iteration: E0
execution_stage: PRE_SPRINT_1
status: active
current_gate: S1-READY
next_data_gate: DRG-00
started_at: 2026-08-21
data_ceiling: synthetic_only
real_financial_data_allowed: false
real_research_corpus_allowed: false
real_pilot_allowed: false
public_pricing_allowed: false
external_ai_with_customer_data_allowed: false
integration_owner: UNASSIGNED
product_owner: UNASSIGNED
accounting_owner: UNASSIGNED
architecture_owner: UNASSIGNED
security_owner: UNASSIGNED
privacy_owner: UNASSIGNED
legal_owner: UNASSIGNED
review_date: UNASSIGNED
---

# Fase vigente

## Objetivo

Cerrar los artefactos previos a Sprint 1 definidos en el plan y dejar ejecutables los fundamentos de Fase 0 sin utilizar datos reales.

## Calendario operativo

- E0, semanas 0–2: gobierno, modelos v0, repo, entorno local, investigación y datos sintéticos.
- E1, semanas 3–4: DRG-00, stack spike, ADR bloqueantes, golden suite y revisión integral.
- S1-READY, fin de semana 4: gate interno que habilita Sprint 1 de producto.
- Sprint 1, desde semana 5: código de producto sobre contratos aprobados; no autoriza piloto real.

Hasta S1-READY solo se admite scaffolding, automatización, pruebas, documentación, prototipos y spikes explícitamente descartables.

## Permitido

- Gobierno del repositorio y Git.
- Entorno Docker local y CI con datos sintéticos.
- ADR, C4, DFD, threat model y contratos.
- Modelos de tenancy y dominio.
- Corpus completamente sintético y golden tests.
- Prototipos sin datos reales.
- Pruebas de RLS, outbox, parser e idempotencia con fixtures sintéticos.
- Investigación de proceso sin recibir documentos de clientes.

## Prohibido

- Recibir, copiar o versionar documentos financieros reales.
- Conectar bancos, DIAN, ERP, correo, SFTP o pasarelas reales.
- Ejecutar IA externa sobre información de clientes.
- Construir auto-match o cierre como función autorizada.
- Publicar precios definitivos.
- Declarar superado un gate sin aprobadores humanos requeridos.
- Tratar un spike como arquitectura productiva sin ADR.

## Trabajo activo

| ID | Resultado | Estado | Implementador | Rutas |
|---|---|---|---|---|
| FNC-GOV-002 | Paquete de implementación multiagente | Done | Integration Steward | raíz, docs/implementation, docs/adr |
| FNC-PRD-001 | PRD y wedge de firma contable | Review pending | Hume | docs/product/PRD_WEDGE.md, handoff |
| FNC-DOM-001 | Tenancy company/engagement | Review pending | Einstein | docs/domain/TENANCY_MODEL.md, handoff |
| FNC-DAT-001 | Glosario y política sintética | Review pending | Bohr | docs/domain/GLOSSARY.md, docs/testing/SYNTHETIC_DATA_POLICY.md, handoff |
| FNC-PLT-001 | Walking spike del stack | Review pending | Integration Steward | spikes/FNC-PLT-001, ADR-001/002, evidencia |
| FNC-SEC-001 | Matriz y kernel de autorización | Review pending | Claude + Integration Steward | docs/security/RBAC_ABAC_SOD.md, spikes/FNC-SEC-001, handoff |
| FNC-DAT-002 | Corpus y linter sintéticos | Review pending | Integration Steward | tools/synthetic_corpus, tests/golden/synthetic, docs/testing, handoff |
| FNC-PLT-003 | CI y quality gate inicial | Review pending | Integration Steward | .github/workflows, tools/quality_gate, docs/testing, handoff |
| FNC-ARC-001 | C4 y modelo ejecutable de módulos | Review pending | Integration Steward | docs/architecture, tools/architecture_model, CI, handoff |
| FNC-ARC-002 | DFD ejecutable y clasificación por flujo | Review pending | Integration Steward | docs/architecture/DFD.md, dfd-flows.json, tools/dfd_model, CI, handoff |
| FNC-SEC-002 | Threat model ejecutable | Review pending | Integration Steward | docs/security/THREAT_MODEL.md, threat-model.json, tools/threat_model, CI, handoff |
| FNC-DOM-002 | Modelo canónico financiero ejecutable | Review pending | Integration Steward | docs/domain/CANONICAL_MODEL.md, canonical-model.json, tools/canonical_model, CI, handoff |
| FNC-DOM-003 | Completitud y conciliación de saldos | Review pending | Integration Steward | docs/domain/COMPLETENESS_BALANCES.md, completeness-balances.json, tools/completeness_model, CI, handoff |
| FNC-DOM-004 | Evidencia, dedupe e idempotencia segura | Review pending | Integration Steward | docs/domain/EVIDENCE_DEDUPE_IDEMPOTENCY.md, idempotency-dedupe.json, tools/idempotency_model, CI, handoff |
| FNC-PRV-001 | Mapa ejecutable de privacidad, retención y borrado | Review pending | Claude + Integration Steward | docs/privacy, tools/privacy_model, CI, handoff |

Solo el Integration Steward modifica esta tabla.

## Siguientes tareas paralelizables

| Ola | Tarea | Dependencia | Estado |
|---:|---|---|---|
| 0 | FNC-GOV-001 Owners humanos y RACI | Ninguna | Blocked: founder |
| 0 | FNC-PRD-001 PRD general y wedge | FNC-GOV-001 para aprobación | Review pending |
| 0 | FNC-DOM-001 Modelo tenancy | PRD provisional | Review pending |
| 0 | FNC-ARC-001 C4 contexto/contenedores | FNC-DOM-001 | Review pending |
| 0 | FNC-ARC-002 DFD y clasificación por flujo | FNC-ARC-001, FNC-DAT-001 | Review pending |
| 0 | FNC-SEC-001 RBAC/ABAC/SoD | FNC-DOM-001 | Review pending |
| 0 | FNC-SEC-002 Threat model y pruebas de riesgo | FNC-ARC-002, FNC-SEC-001 | Review pending |
| 0 | FNC-DAT-001 Taxonomía y política de datos | PRD provisional | Review pending |
| 0 | FNC-PLT-001 Spike y decisión de stack | Gobierno | Review pending |
| 0 | FNC-UX-001 Arquitectura de información | PRD provisional | Draftable |
| 0 | FNC-DAT-002 Corpus y golden harness sintético | FNC-DAT-001 provisional | Review pending |
| 0 | FNC-PLT-003 CI sintético y policy gate | FNC-PLT-001, FNC-DAT-002 | Review pending |
| 1 | FNC-DOM-002 Modelo canónico financiero | FNC-DOM-001, FNC-DAT-001 | Review pending |
| 1 | FNC-DOM-003 Completitud y saldos | FNC-DOM-002 | Review pending |
| 1 | FNC-DOM-004 Evidencia, dedupe e idempotencia | FNC-DOM-002, FNC-ARC-002 | Review pending |
| 1 | FNC-PRV-001 Privacidad, retención y borrado | FNC-ARC-002, FNC-DAT-001 | Review pending |

Draftable significa que un agente puede preparar un borrador, pero no marcarlo Accepted hasta resolver la dependencia.

## Salida S1-READY

- [ ] Owners humanos y revisores independientes asignados.
- [ ] PRD general y wedge.
- [ ] Modelo organization/company/engagement.
- [ ] Modelo canónico con saldos, completitud y dedupe.
- [ ] C4 y DFD.
- [ ] Threat model.
- [ ] Matriz RBAC/ABAC/SoD.
- [ ] Mapa de privacidad y retención revisado y firmado por Privacy y Legal.
- [ ] Especificación de linaje.
- [ ] Contrato de conectores.
- [ ] Estados, eventos y retry ownership.
- [ ] ADR-001 a ADR-010 y ADR de engine release.
- [ ] Corpus sintético y golden suite inicial.
- [ ] Design system y prototipo navegable.
- [ ] Cero datos reales en repo, local, CI o artefactos.
- [ ] Cero riesgo crítico sin tratamiento, owner y fecha.
