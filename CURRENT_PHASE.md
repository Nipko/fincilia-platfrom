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
integration_owner: FOUNDER-01
product_owner: FOUNDER-01
accounting_owner: FOUNDER-01
architecture_owner: FOUNDER-01
security_owner: FOUNDER-01
privacy_owner: FOUNDER-01
legal_owner: FOUNDER-01
review_date: 2026-09-30
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
| FNC-GOV-001 | Owner provisional, RACI y paquete de decisiones del Founder | Review pending | Integration Steward | `FOUNDER-01` accountable provisional; revisores humanos distintos continúan pendientes; decisión IMP-017 |
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
| FNC-ARC-004 | Eventos, outbox, retries y dead letters | Review pending | Integration Steward | docs/architecture/EVENTS_RETRIES.md, events-retries.json, tools/event_model, CI, handoff |
| FNC-ARC-005 | Conectores read-only y fallback por archivos | Review pending | Integration Steward | docs/contracts/connectors, tools/connector_model, CI, handoff |
| FNC-DOM-005 | Linaje por campo, overlays y engine release | Review pending | Claude + Integration Steward | docs/domain/LINEAGE_SPEC.md, lineage-model.json, tools/lineage_model, CI, handoff |
| FNC-PLT-005 | Auth-context, RLS, outbox/inbox y parser sintético | Review pending | Integration Steward | spikes/FNC-PLT-005, CI, evidencia, handoff |
| FNC-ARC-006A | Stores, clasificación y engine release cross-contract | Review pending | Integration Steward | docs/architecture/CROSS_CONTRACT_VOCABULARY.md, tools/cross_contract_model, ADR-023, CI, handoff |
| FNC-GOV-003 | Grafo ejecutable de trabajo y reservas | Review pending | Integration Steward | docs/implementation/WORK_GRAPH.md, work-graph.json, tools/work_graph, CI, handoff |
| FNC-PLT-002 | Entorno local mínimo y lifecycle reproducible | Review pending | Integration Steward | infra/local, tools/local_stack, CI, evidencia, handoff |
| FNC-UX-001 | Arquitectura de información y prototipo accesible | Review pending | Integration Steward | docs/ux, tools/ux_contract, CI, handoff |
| FNC-ARC-003 | Paquete A-02 de región, transmisión y subencargados | Review pending | Integration Steward | AWS `sa-east-1` priorizada solo para evaluación; Free Tier viable únicamente para spike sintético; gasto, despliegue, A-02 y datos reales siguen bloqueados |
| FNC-ARC-006 | Readiness ejecutable de ADR bloqueantes | Review pending | Integration Steward | docs/architecture/ADR_READINESS.md, adr-readiness.json, tools/adr_readiness, handoff |
| FNC-INT-001 | Due diligence y RFQ de conectividad read-only | Review pending | Integration Steward | docs/integrations, tools/provider_evaluation, handoff |
| FNC-FIN-001 | Presupuesto ejecutable F0–F2 y runway | Review pending | Integration Steward | docs/business/BUDGET_F0_F2.md, budget-f0-f2.json, tools/budget_model, handoff |
| FNC-RES-001 | Protocolo seguro de investigación de cierres | Review pending | Integration Steward | docs/product/RESEARCH_PROTOCOL.md, research-protocol.json, tools/research_protocol, handoff |
| FNC-BRD-001 | Clearance preliminar y paquete legal de Fincilia | Review pending | Integration Steward | docs/business/BRAND_CLEARANCE_FINCILIA.md, brand-clearance.json, tools/brand_clearance, handoff |
| FNC-PLT-006 | Scaffold pre-S1 del monorepo | Review pending | Integration Steward | apps, workers/document, packages, db/migrations, tools/workspace_contract, handoff |
| FNC-CFG-001 | Contrato de configuración y secretos | Review pending | Integration Steward | .env.example, docs/platform/runtime-config.json, tools/runtime_config, handoff |
| FNC-DB-001 | Evaluación de tooling de migraciones | Review pending | Integration Steward | docs/database/migration-tooling.json, tools/migration_readiness, handoff |
| FNC-QA-002 | Estrategia ejecutable de pruebas y huecos declarados | Review pending | Claude + Integration Steward | docs/testing/TEST_STRATEGY.md, test-strategy.json, tools/quality_strategy, handoff |
| FNC-QA-003 | Golden harness adjudicado y fail-closed | Review pending | Claude + Integration Steward | docs/testing/GOLDEN_HARNESS.md, golden-harness.json, tools/golden_harness, tests/golden/harness, handoff |
| FNC-QA-004 | Catálogo ejecutable y reconciliación dinámica | Review pending | Claude + Integration Steward | docs/testing/TEST_CATALOG_MODEL.md, test-catalog-model.json, tools/test_catalog, catálogo, CI, handoff |
| FNC-QA-005 | Arnés determinista de mutaciones | Review pending | Claude + Integration Steward | docs/testing/MUTATION_HARNESS.md, mutation-harness.json, tools/mutation_harness, tests/golden/mutations, CI, handoff |
| FNC-SUP-001 | Baseline ejecutable de cadena de suministro | Review pending | Claude + Integration Steward | SBOM, firma y procedencia del candidato verificados; queda un bloqueo alto de origen independiente y seis monitores OCI medios |
| FNC-SUP-002 | Attestation verificable del candidato | Review pending | Codex + Integration Steward | Run `33349841370` sobre `f05fdbd`: bundle V0045, SLSA y SPDX firmados por OIDC y revalidados fuera del runner; Security/QA pendientes |
| FNC-SUP-003 | Publicación OIDC de imágenes inmutables al piloto privado | Review pending | Codex + Integration Steward | Run `33358386719` verde: OIDC exacto, rol ECR mínimo, escaneo, attestations y manifiesto por digest; plan 142 create/11 read sin apply y revisión independiente pendiente |
| FNC-DB-002 | Spike PostgreSQL de migraciones SQL-first | Review pending | Claude + Integration Steward | docs/database/MIGRATION_SPIKE.md, migration-spike.json, spikes/FNC-DB-002, tools/migration_spike, handoff |
| FNC-DB-004 | Spike PostgreSQL de claim, outbox y fencing | Review pending | Codex + Integration Steward | TST-IDEM-001/004/005 demostrados dos veces contra PostgreSQL 17; laboratorio aislado y revisión Architecture/Security/QA pendiente |
| FNC-PLT-007 | CLI segura de desarrollo local | Review pending | Claude + Integration Steward | docs/platform/DEVELOPER_CLI.md, developer-cli.json, tools/dev_cli, handoff |
| FNC-GAT-003 | Agregador ejecutable de readiness S1 | Review pending | Claude + Integration Steward | docs/implementation/S1_READINESS_REPORT.md, s1-readiness.json, tools/s1_readiness, handoff |
| FNC-WEB-001 | Endurecimiento verificable del recorrido web P3 | Review pending | Codex + Integration Steward | apps/web, pruebas web, CI, ficha y handoff |
| FNC-API-001 | Creacion atomica y segura de mapeos | Review pending | Codex + Integration Steward | rutas/dominio API de mapeos, prueba PostgreSQL y handoff |
| FNC-MAP-001 | Integridad de fuente entre evidencia y mapeo | In progress | Codex + Integration Steward | V0053, negativa neutral API, fixture fiel y pruebas PostgreSQL; CI y handoff pendientes |
| FNC-WEB-002 | Puesto web de revision y excepciones de dataset | Review pending | Codex + Integration Steward | readiness API, overrides/rechazo web, pruebas PostgreSQL y web |
| FNC-WEB-003 | Portafolio multiempresa e historico operativo web | Review pending | Codex + Integration Steward | portafolio, vencimientos, volumenes e historico de datasets web |
| FNC-WEB-004 | Sistema visual y navegacion contextual web | Review pending | Codex + Integration Steward | shell visual, menus jerarquicos, vistas clave y responsive; 34 Chromium + 21 Axe aislados verdes |
| FNC-CLN-001 | Propuestas tipadas de correccion por fila | Review pending | Codex + Integration Steward | overlay tipado, revision SoD, blockers, PostgreSQL y web |
| FNC-CLN-002 | Aplicacion reproducible de correcciones aprobadas | Review pending | Codex + Integration Steward | V0023/V0024, version derivada, manifest, linaje digest-only, API/web, PostgreSQL y recorrido visual sintetico |
| FNC-CLN-003 | Aplicabilidad de correcciones ligada al plan de linaje | Review pending | Codex + Integration Steward | targets dinámicos, rechazo fail-closed, 117 API, 10 PostgreSQL y recorrido visual sintético |
| FNC-CLN-004 | Rango, preview canonico y plantillas de limpieza reutilizables | Review pending | Codex + Integration Steward | rango inclusivo, preview canonico read-only, versiones de plantilla, PostgreSQL y web accesible verificados; revision independiente pendiente |
| FNC-QA-006 | Aceptacion web integral y arranque local coherente | Review pending | Codex + Integration Steward | bootstrap local, contrato ejecutable y E2E de roles/tenancy |
| FNC-QA-007 | Administracion final de usuarios y roles por empresa | Review pending | Codex + Integration Steward | API member.manage, revocacion/versionado, web equipo y pruebas PostgreSQL/E2E |
| FNC-QA-008 | Regresion web repetible sobre runtime persistente | Review pending | Codex + Integration Steward | 26 Chromium dos veces y 15 Axe verdes; fixtures compartidos seriales y expedientes append-only localizados por pagina exacta |
| FNC-QA-009 | Regresion web aislada de la demo persistente | Review pending | Codex + Integration Steward | 26 Chromium + 15 Axe verdes dos veces sobre proyecto desechable; cleanup y no interferencia con la demo verificados |
| FNC-QA-010 | Estabilizacion de CI y monitoreo de dependencias | Review pending | Codex + Integration Steward | `main` verde: 358 PostgreSQL, 149 API, 18 worker, 27 Chromium y 16 Axe; 13 PR automaticas obsoletas cerradas sin fusionar |
| FNC-REC-001 | Explorador read-only de candidatos de conciliacion | Review pending | Codex + Integration Steward | motor/endpoint sintetico, estacion web y pruebas |
| FNC-REC-002 | Propuesta y decision humana de conciliacion sin efecto financiero | Review pending | Codex + Integration Steward | ledger append-only, SoD, idempotencia, API/web y pruebas; revisiones independientes pendientes |
| FNC-REC-003 | Bandeja multiempresa de revision de conciliaciones | Review pending | Codex + Integration Steward | R2: filtro por empresa, paginacion real, carga visible y retorno cerrado al expediente; sin efecto financiero |
| FNC-REC-004 | Exclusividad uno-a-uno de confirmaciones | Review pending | Codex + Integration Steward | V0025 aplicada, conflicto concurrente, API/web y recorrido visual; revision independiente pendiente |
| FNC-REC-005 | Propuestas manuales agrupadas 1:N/N:1 | Review pending | Codex + Integration Steward | V0035, API y web permiten borradores 1:N/N:1 de movimientos completos; PostgreSQL, E2E y Axe verdes; ADR-028 y revisión independiente pendientes |
| FNC-REC-006 | Expediente histórico direccionable de conciliación | Review pending | Codex + Integration Steward | Lectura exacta company-scoped y fallback web histórico verificados; no reactiva datasets ni recalcula candidatos; revisión independiente pendiente |
| FNC-ING-001 | Ingesta segura de XLSX sintetico de una hoja | Review pending | Codex + Integration Steward | V0036, parser OPC cerrado, perfil/extraccion deterministas, preview web y E2E/Axe verdes; revision independiente pendiente |
| FNC-ING-002 | Seleccion explicita de hoja XLSX y limpieza visual web | Review pending | Codex + Integration Steward | V0037, seleccion inmutable, procesamiento de hoja exacta y limpieza visual; PostgreSQL, E2E y Axe verdes; revision independiente pendiente |
| FNC-ING-003 | Ingesta ligada a fuente y centro historico de documentos | Review pending | Codex + Integration Steward | V0038, fuente inmutable, API keyset y centro documental web verificados; revision independiente pendiente |
| FNC-ING-004 | Bandeja web de carga multiple por fuente | Review pending | Codex + Integration Steward | Hasta 10 archivos, concurrencia maxima 2, resultado/reintento individual y regresion Chromium/Axe verdes; revision independiente pendiente |
| FNC-ING-005 | Ingesta segura de ODS y contrato honesto de formatos | Review pending | Codex + Integration Steward | ODS tabular seguro recorre escaneo, perfil, extraccion y linaje; PDF/ZIP siguen en cuarentena explicita; revision independiente pendiente |
| FNC-CLS-001 | Centro diagnostico de preparacion de cierre | Review pending | Codex + Integration Steward | API/web company-scoped por empresa y periodo, limites cerrados y pruebas reales; revision independiente pendiente |
| FNC-CLS-002 | Observaciones canonicas de saldo por cuenta | Review pending | Codex + Integration Steward | V0026/V0027, API/web company-scoped, decimal exacto, evidencia visible y pruebas reales; revision independiente pendiente |
| FNC-CLS-003 | Estados reproducibles de conciliacion de saldos | Review pending | Codex + Integration Steward | V0028-V0030, API/web company-scoped, ecuacion Decimal, SoD, PostgreSQL real y E2E/Axe verdes; revision independiente pendiente |
| FNC-CLS-004 | Preparacion de cierre integrada | Review pending | Codex + Integration Steward | Statements vigentes por cuenta/periodo, evidencia lista para revision separada de cierre y regresion completa verde; revision independiente pendiente |
| FNC-CLS-005 | Expediente de revision previa al cierre | Review pending | Codex + Integration Steward | V0034, expediente digest-only, asignacion y decision append-only con SoD; PostgreSQL y E2E/Axe verdes; revision independiente pendiente |
| FNC-LIN-001 | Linaje materializado previo al cierre | Review pending | Codex + Integration Steward | V0031-V0033, decisiones financieras digest-only, guards PostgreSQL exactos y drill-down web verdes; revisión independiente pendiente |
| FNC-EXP-001 | Exportacion canonica segura de dataset publicado | Review pending | Codex + Integration Steward | permiso explicito, CSV determinista, BFF streaming y pruebas; solo sintetico y no certificado |
| FNC-OPS-001 | Centro operativo de ciclos y recordatorios web | Review pending | Codex + Integration Steward | API y web company-by-company verificadas; revision humana Product/Accounting, Security/Privacy, Backend/Architecture y Accessibility/QA pendiente |
| FNC-DQ-001 | Centro de alertas de calidad y anomalias deterministas | Review pending | Codex + Integration Steward | backend, V0018, web multiempresa, PostgreSQL, E2E y a11y verdes; revision humana independiente pendiente |
| FNC-RPT-001 | Centro web de informes operativos e historicos | Review pending | Codex + Integration Steward | API, PostgreSQL, web, CSV, E2E y a11y verdes en a18afcf; revision humana independiente pendiente |
| FNC-ONB-001 | Alta transaccional de empresa y espacio operativo | Review pending | Codex + Integration Steward | Company, engagement, owner y maestros iniciales sin depender de la semilla; V0020 aplicada y recorridos PostgreSQL/E2E/a11y verdes |
| FNC-ONB-002 | Registro autoservicio y primer espacio desde la web | Review pending | Codex + Integration Steward | Recorrido local sintetico y continuidad a FNC-ONB-001 completos; el alta Google publica definitiva se consolida en FNC-IAM-004 sin autorizar datos reales |
| FNC-BET-001 | Despliegue UAT público inicial (ID histórico) | Review pending | Codex + Integration Steward | Release `90110e7` activo en `fincilia.com`; backup/restore y recorrido sintético verificados; ADR-033 sustituye el nombre y prohíbe convertir sus datos en producción |
| FNC-GAT-005 | Readiness del piloto privado con datos reales | In progress | Codex + Integration Steward | 14 blockers: cross-tenant, ingreso, canales y derechos/incidente adjudicados; entorno protegido, supply, restore target y revisiones humanas siguen pendientes |
| FNC-GAT-006 | Evidencia adjudicada de aislamiento, ingreso y canales DRG-01 | Review pending | Codex + Integration Steward | R2 ligada al contrato AWS ampliado tras suite PostgreSQL del run `33357761851`; 90 casos adjudicados y D01-XTENANT/INGRESS/CHANNELS sin cambios; revisión independiente pendiente |
| FNC-PRV-004 | Ensayo ejecutable de derechos e incidente previo a DRG-01 | Review pending | Codex + Integration Steward | 12 pasos sintéticos reproducibles Windows/Linux: escritura binaria, purga read-only, revocación, tombstone, restore cerrado y post-revisión; Legal pendiente |
| FNC-PLT-004 | Ambiente aislado reproducible para corpus DRG-00 | Review pending | Codex + Integration Steward | Dos sondas UID 65532, root read-only y sin egress pasaron; runtime real continúa deshabilitado |
| FNC-DAT-003 | Inventario nominal de artefactos y purga | Review pending | Codex + Integration Steward | Ledger append-only con hash chain, idempotencia, minimización y reconciliación verificados |
| FNC-PRV-003 | Saneamiento, borrado y restore con tombstones | Review pending | Codex + Integration Steward | Tombstone previo a unlink, purga idempotente y restore cerrado verificados; L-01 humana pendiente |
| FNC-QA-001 | Ensayo recepción→inventario→purga | Review pending | Codex + Integration Steward | LAB-T01..T12 pasaron con evidencia digest-only completamente sintética; revisión independiente pendiente |
| FNC-PLT-012 | Entorno AWS separado del piloto real | In progress | Codex + Integration Steward | Contrato `04bf2bc` y foundation `5b88ea2` verdes; plan/apply AWS, evidencia runtime, DRG-00/01 y revisión independiente pendientes |
| FNC-PLT-013 | Ciclo frío y activación temporal del piloto AWS | Review pending | Codex + Integration Steward | `cold` por defecto; OpenTofu 1.12.6 verificado y resoluble en WSL; plan frío de 139 altas validado sin apply y cuenta AWS sin recursos `private-pilot`; DRG-00/01 y revisión independiente pendientes |
| FNC-PLT-014 | Laboratorio efímero de actividades AWS Credits | Review pending | Codex + Integration Steward | Cinco actividades adjudicadas: USD 200 disponibles; Lambda, rol y RDS eliminados; Bedrock sin recursos persistentes; revisión independiente pendiente |
| FNC-IAM-001 | Inicio de sesión Google mediante Cognito | Review pending | Codex + Integration Steward | Backend/web más Google y cliente público AWS aplicados (`987778d`), callbacks exactos y drift cero; DRG-00, atestación KMS y revisión independiente bloquean activación |
| FNC-IAM-002 | Centro de cuenta y recorrido de identidad coherente | Review pending | Codex + Integration Steward | `/me`, cuenta, sesión, empresas y roles integrados sin exponer identidad externa; Security/Privacy/UX/QA pendientes y DRG-00 no cambia |
| FNC-IAM-003 | Cierre operativo de identidad administrada | Review pending | Codex + Integration Steward | Logout Cognito, SignUp nativo cerrado y sonda live de 16 controles; AWS, assurance y revisión independiente pendientes |
| FNC-IAM-004 | Alta pública definitiva con Google y aceptación legal versionada | Review pending | Codex + Integration Steward | Control plane Google/Cognito 16/16 live y protegido contra borrado; runtime protegido, revisiones independientes y DRG-00 continúan pendientes |
| FNC-ADM-001 | Plano de control y superadmin inicial | Review pending | Codex + Integration Steward | Bootstrap Google/HMAC único, roles de plataforma, API, consola, diagnósticos y auditoría verificados sin acceso financiero implícito; revisiones independientes pendientes |
| FNC-UAT-001 | Ciclo UAT y promoción limpia a producción | In progress | Codex + Integration Steward | Release `b099c64` con CI `33473978646` y candidato firmado `33474841341` verdes; despliegue exige backup/restore fresco y conserva rollback, mientras ensayo destructivo y revisiones independientes siguen pendientes |
| FNC-UAT-002 | Aceptación integral desechable desde esquema vacío | Review pending | Codex + Integration Steward | Dos corridas limpias: alta vacía, 47 backend, 9 PostgreSQL, 42 Chromium y 26 Axe por corrida; cleanup exacto verificado |
| FNC-ACC-001 | Recorrido contable guiado de punta a punta | Review pending | Codex + Integration Steward | Siete etapas desde configuración hasta expediente previo al cierre, sin ejecutar ni certificar cierre; Accounting/Architecture/UX/QA pendientes |
| FNC-CLS-006 | Cierre y reapertura real de periodo | Review pending | Codex + Integration Steward | V0046, snapshot append-only, bloqueo DB y reapertura SoD verificados en PostgreSQL; ADR-035 y revisión independiente pendientes |
| FNC-ING-006 | PDF seguro y OCR desacoplado | Review pending | Codex + Integration Steward | Texto embebido seguro y localizador PDF implementados; OCR externo y datos reales permanecen desactivados |
| FNC-NTF-001 | Notificaciones externas verificables | Review pending | Codex + Integration Steward | V0048/V0049, preferencias, intención idempotente, RLS por sujeto, historial y supresión honesta; proveedor/remitente al final |
| FNC-BIL-001 | Planes, entitlements y facturación | Review pending | Codex + Integration Steward | V0050/V0051, tres planes versionados, evaluación por firma, uso append-only y checkout cerrado; proveedor/precios al final |
| FNC-UX-003 | Shell SaaS premium y sistema visual web v2 | Review pending | Codex + Integration Steward | Shell SaaS, navegación jerárquica, tokens, motion reducido, 390 px y Axe integrados; Product/UX y Accessibility/QA pendientes |
| FNC-LEG-002 | Centro legal público Fincilia/Parallext.com | In progress | Codex + Integration Steward | Borradores públicos de privacidad, términos, cookies, seguridad, DPA, subencargados y eliminación; revisión Legal pendiente |
| FNC-SEC-004 | Contexto durable de autorizacion | Review pending | Codex + Integration Steward | V0021, kernel de emision/revalidacion/revocacion, PostgreSQL real y auditoria; revision Security + Database/Architecture pendiente |
| FNC-SEC-005 | Trabajos durables vinculados a autorizacion emitida | Review pending | Codex + Integration Steward | V0022, productor API, despacho y vallado por lote; compatibilidad expand-only y revision independiente pendientes |
| FNC-SEC-006 | Endurecimiento HTTP verificable para UAT | Review pending | Codex + Integration Steward | Baseline exacta API/web, CSP y pruebas Chromium; HSTS permanece bajo autoridad del edge HTTPS |
| FNC-REC-007 | Productividad segura del explorador de conciliación | Review pending | Codex + Integration Steward | Filtro server-side all/matching/different conservado en URL y paginación, sin efecto financiero |
| FNC-ADM-002 | Diagnóstico operativo agregado del plano de control | Review pending | Codex + Integration Steward | V0052, ACL, API y consola agregada probadas contra PostgreSQL; sin datos financieros transversales |
| FNC-AUD-001 | Centro web company-scoped de accesos y auditoria | Review pending | Codex + Integration Steward | API keyset, actor, filtros cerrados, portafolio company-by-company y estados parciales; revision independiente pendiente |
| FNC-PLT-009 | Runtime local persistente de Docker Engine en Windows/WSL | Review pending | Codex + Integration Steward | wrapper oculto y reversible, lifecycle completo, contrato ejecutable y persistencia de datos verificada; revision independiente pendiente |
| FNC-PLT-010 | Control plane AWS T0 exclusivamente sintetico | Review pending | Codex + Integration Steward | 8 recursos bootstrap + 45 control plane aplicados sin drift; CloudTrail/Cognito/ECR/S3/presupuesto verificados; cero runtime y datos reales; revisión independiente pendiente |
| FNC-PLT-011 | Laboratorio remoto AWS T1 con runtime sintetico | Review pending | Codex + Integration Steward | Release por digest desplegado sin drift; stack completo, tenancy, promocion, backup/restore, SSM-only y autostop verificados con datos sinteticos; revision independiente pendiente |
| FNC-REL-001 | Candidato de release reproducible y baseline operativo | Review pending | Codex + Integration Steward | bundle SPDX cross-platform, manifiesto fail-closed, observabilidad segura, workflow manual y CI 33189792888 verdes; revisión Security/QA/Architecture pendiente |
| FNC-LEG-001 | Plantilla ejecutable de tratamiento para corpus real | Review pending | Codex + Integration Steward | 11 actividades dinámicas, 16 secciones y 26 pruebas; paquete listo para abogado independiente, sin autorizar datos reales ni mover DRG-00 |
| FNC-PRV-002 | Matriz ejecutable L-01 de retención y borrado | Review pending | Codex + Integration Steward | 19 políticas frescas por digest, dos estados fail-closed y 29 pruebas; plazos y cuatro revisores humanos permanecen pendientes |
| FNC-SEC-003 | Diseño ejecutable del laboratorio aislado para corpus real | Review pending | Codex + Integration Steward | 37 controles, 6 zonas, 12 casos y 34 pruebas; IdP/proveedor/región/despliegue/evidencia siguen pendientes y datos reales prohibidos |

Solo el Integration Steward modifica esta tabla.

## Siguientes tareas paralelizables

| Ola | Tarea | Dependencia | Estado |
|---:|---|---|---|
| 0 | FNC-GOV-001 Owners humanos y RACI | Ninguna | Review pending; `FOUNDER-01` asignado, revisores independientes distintos pendientes |
| 0 | FNC-GOV-003 Grafo ejecutable de trabajo | FNC-GOV-002 | Review pending |
| 0 | FNC-PRD-001 PRD general y wedge | FNC-GOV-001 para aprobación | Review pending |
| 0 | FNC-DOM-001 Modelo tenancy | PRD provisional | Review pending |
| 0 | FNC-ARC-001 C4 contexto/contenedores | FNC-DOM-001 | Review pending |
| 0 | FNC-ARC-002 DFD y clasificación por flujo | FNC-ARC-001, FNC-DAT-001 | Review pending |
| 0 | FNC-SEC-001 RBAC/ABAC/SoD | FNC-DOM-001 | Review pending |
| 0 | FNC-SEC-002 Threat model y pruebas de riesgo | FNC-ARC-002, FNC-SEC-001 | Review pending |
| 0 | FNC-DAT-001 Taxonomía y política de datos | PRD provisional | Review pending |
| 0 | FNC-PLT-001 Spike y decisión de stack | Gobierno | Review pending |
| 0 | FNC-PLT-002 Entorno local reproducible | FNC-PLT-001 | Review pending |
| 0 | FNC-UX-001 Arquitectura de información | PRD provisional | Review pending |
| 0 | FNC-DAT-002 Corpus y golden harness sintético | FNC-DAT-001 provisional | Review pending |
| 0 | FNC-PLT-003 CI sintético y policy gate | FNC-PLT-001, FNC-DAT-002 | Review pending |
| 1 | FNC-DOM-002 Modelo canónico financiero | FNC-DOM-001, FNC-DAT-001 | Review pending |
| 1 | FNC-DOM-003 Completitud y saldos | FNC-DOM-002 | Review pending |
| 1 | FNC-DOM-004 Evidencia, dedupe e idempotencia | FNC-DOM-002, FNC-ARC-002 | Review pending |
| 1 | FNC-PRV-001 Privacidad, retención y borrado | FNC-ARC-002, FNC-DAT-001 | Review pending |
| 1 | FNC-ARC-004 Eventos, outbox, retries y DLQ | FNC-ARC-001, FNC-DOM-004 | Review pending |
| 1 | FNC-ARC-005 Contrato de conectores y fallback | FNC-ARC-004, FNC-DOM-003/004 | Review pending |
| 1 | FNC-DOM-005 Linaje, overlays y engine release | FNC-DOM-002/004, FNC-PRV-001 | Review pending |
| 1 | FNC-PLT-005 Spike auth-context, RLS, eventos y parser | FNC-DOM-001, FNC-SEC-001, FNC-ARC-004 | Review pending |
| 1 | FNC-ARC-006A Reconciliación cross-contract | FNC-ARC-002, FNC-DOM-005, FNC-PRV-001 | Review pending |
| 1 | FNC-ARC-003 Decisión de región y transmisión | FNC-ARC-002 | Review pending; decisión humana A-02 pendiente |
| 1 | FNC-ARC-006 Paquete de ADR bloqueantes | FNC-DOM-001..005, FNC-ARC-001..005 | Review pending; S1-READY continúa not_met |
| 1 | FNC-INT-001 Cotizaciones comparables de agregadores | FNC-PRD-001 | Review pending; outreach humano y 3 respuestas pendientes |
| 1 | FNC-FIN-001 Presupuesto F0–F2 +30% | FNC-INT-001, FNC-PLT-005 | Review pending; costos/capital requieren Founder/Finance |
| 1 | FNC-RES-001 Protocolo 5 firmas/10 cierres | FNC-GOV-001 para ejecutar | Review pending; sesiones reales no autorizadas |
| 1 | FNC-BRD-001 Clearance jurídico Fincilia | Ninguna para borrador | Review pending; SIC/WIPO y filing pendientes de Legal/Founder |
| 1 | FNC-PLT-006 Scaffold pre-S1 | FNC-PLT-002, FNC-ARC-001 | Review pending; lógica/frameworks bloqueados |
| 1 | FNC-CFG-001 Configuración y secretos | FNC-PLT-002, FNC-ARC-003 | Review pending; cloud/producción bloqueados |
| 1 | FNC-DB-001 Tooling de migraciones | FNC-PLT-001 | Review pending; spike Flyway no ejecutado |
| 1 | FNC-QA-002 Estrategia integral de pruebas | FNC-DOM-002..005 | Review pending |
| 1 | FNC-QA-003 Golden harness determinista | FNC-DAT-002, FNC-DOM-002..005 | Review pending |
| 1 | FNC-QA-004 Catálogo ejecutable de pruebas | FNC-QA-002/003 | Review pending; sin drift bloqueante |
| 1 | FNC-QA-005 Mutation harness de validadores | FNC-QA-002/003 | Review pending; 63/63 mutaciones muertas |
| 1 | FNC-SUP-001 Baseline de supply chain | FNC-PLT-003, FNC-QA-005 | Review pending; cinco alcances Compose sin monitor y procedencia/SBOM/firma siguen abiertos |
| 1 | FNC-DB-002 Spike de invariantes de migración | FNC-DB-001, FNC-PLT-002 | Review pending; 12/12 invariantes verificadas y ADR-002 ratificada por IMP-017; revisión independiente pendiente |
| 1 | FNC-PLT-007 CLI de desarrollo | FNC-PLT-002/003, FNC-QA-004/005 | Review pending; gap esperado de supply chain visible |
| 1 | FNC-GAT-003 Readiness S1 ejecutable | FNC-ARC-006, FNC-QA-004/005, FNC-SUP-001, FNC-DB-002 | Review pending; un único blocker: revisión independiente por personas distintas |

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
- [x] ADR-001 a ADR-010 y ADR de engine release ratificados por IMP-017; la revisión independiente se controla por separado.
- [ ] Corpus sintético y golden suite inicial.
- [ ] Design system y prototipo navegable.
- [ ] Cero datos reales en repo, local, CI o artefactos.
- [ ] Cero riesgo crítico sin tratamiento, owner y fecha.
