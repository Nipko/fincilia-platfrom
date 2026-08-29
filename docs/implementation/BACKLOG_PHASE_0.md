# Backlog ejecutable de Fase −1 y Fase 0

## Convenciones

- ID estable: FNC-STREAM-NNN. El sprint y el estado no forman parte del ID.
- Estados: Proposed, Draftable, Ready, Claimed, In progress, Review, Done y Blocked.
- Draftable permite preparar un borrador; Ready exige Definition of Ready completa.
- Un owner humano acepta el resultado. Un agente no firma gates.

## Épicas

| ID | Épica |
|---|---|
| FNC-EP-001 | Gobierno y control de ejecución |
| FNC-EP-002 | DRG-00 y corpus seguro |
| FNC-EP-003 | Descubrimiento de producto y mercado |
| FNC-EP-004 | Dominio financiero y datos |
| FNC-EP-005 | Arquitectura, seguridad y privacidad |
| FNC-EP-006 | Plataforma local, CI y calidad |
| FNC-EP-007 | Diseño y validación de experiencia |
| FNC-EP-008 | Marca, conectividad y viabilidad económica |

## E0 — semanas 0–2

| ID | Carril | Dependencias | Estado inicial | Resultado verificable |
|---|---|---|---|---|
| FNC-GOV-001 | A0/Founder | — | Review | `FOUNDER-01` accountable provisional y paquete IMP-017 registrado; revisores independientes distintos pendientes |
| FNC-GOV-002 | A0 | — | Done | Gobierno, templates, ownership y protocolo multiagente |
| FNC-GOV-003 | A0 | GOV-002 | Review | Backlog, dependencias, decisiones y trazabilidad validados |
| FNC-PRD-001 | A1 | GOV-001 para aceptar | Draftable | PRD del wedge factura→pago→liquidación→banco→ERP |
| FNC-RES-001 | A1 | GOV-001 | Draftable | Protocolo para 5 firmas/10 cierres sin recibir documentos |
| FNC-DAT-001 | A5 | PRD-001 provisional | Draftable | Taxonomía de fuentes/documentos y política por gate |
| FNC-DOM-001 | A2 | PRD-001 provisional | Draftable | Modelo subject/organization/company/engagement/grant |
| FNC-ARC-001 | A2 | DOM-001 | Review | C4 contexto/contenedores/componentes + modelo ejecutable |
| FNC-ARC-002 | A2/A3 | ARC-001, DAT-001 | Review | DFD con flujos, trust boundaries y clasificación |
| FNC-SEC-001 | A3 | DOM-001, PRD-001 | Review | Matriz RBAC/ABAC/SoD y kernel puro de política |
| FNC-SEC-002 | A3 | ARC-002, SEC-001 | Review | Threat model y pruebas por amenaza alta |
| FNC-PRV-001 | A3 | ARC-002, DAT-001 | Review | Mapa de privacidad, región, finalidad, retención y borrado |
| FNC-PLT-001 | A4/A2 | GOV-002 | Draftable | Spike A-01 y decisión documentada de stack |
| FNC-PLT-002 | A4 | PLT-001 | Review | Compose local fijado, loopback, healthchecks y datos sintéticos |
| FNC-PLT-003 | A4/A5 | PLT-001, DAT-002 | Review | CI: formato, tipos, tests, secretos, dependencias y contenedores |
| FNC-DAT-002 | A5 | DAT-001 provisional | Review | Corpus sintético con locales, duplicados, saldos y casos hostiles |
| FNC-UX-001 | A6 | PRD-001 provisional | Review | Arquitectura de información y prototipo base accesible |

### E0-EXIT

- IDs únicos y dependencias sin ciclos.
- Entorno local reproducible desde cero.
- CI sin secretos ni datos reales.
- PRD, tenancy, C4, DFD, RBAC y threat model revisables.
- Ningún documento de cliente recibido.

## DRG-00 — corpus real de investigación

| ID | Carril | Dependencias | Resultado verificable |
|---|---|---|---|
| FNC-LEG-001 | A7/Legal | GOV-001, PRV-001 | Plantilla de tratamiento aprobada por abogado |
| FNC-PRV-002 | A3/Privacy | PRV-001, LEG-001 | Matriz L-01 por clase, evento, plazo, derivados y borrado |
| FNC-ARC-003 | A2/A7 | ARC-002 | ADR A-02 de región y transmisión |
| FNC-SEC-003 | A3 | SEC-002, PRV-002, ARC-003 | Diseño aislado, acceso mínimo y egress deny-by-default |
| FNC-PLT-004 | A4 | SEC-003 | Ambiente aislado reproducible y auditable |
| FNC-DAT-003 | A5 | PRV-002, PLT-004 | Registro nominal de artefactos y estado de purga |
| FNC-PRV-003 | A3 | DAT-003, PLT-004 | Runbook de saneamiento/borrado con reconciliación |
| FNC-QA-001 | A5 | PLT-004, PRV-003 | Ensayo sintético recepción→inventario→purga |
| FNC-GAT-001 | A0 + humanos | Todos | Checklist y firmas Legal, Security y Product |
| FNC-GAT-005 | A0/A3/A4 + humanos | SEC-003, PLT-004, QA-001 | Readiness fail-closed para el primer piloto privado con datos reales |

FNC-GAT-001 es la única tarea que puede autorizar el primer artefacto real de investigación.

## Fase 0 restante

| ID | Carril | Dependencias | Resultado verificable |
|---|---|---|---|
| FNC-RES-002 | A1 | RES-001 | Diez cierres observados en cinco firmas |
| FNC-COR-001 | A5 | GAT-001 | 150–250 documentos inventariados |
| FNC-COR-002 | A5 | COR-001 | Ranking reproducible de formatos y costo de limpieza |
| FNC-PRD-002 | A1 | RES-002, COR-002 | Buyer/ICP/wedge confirmado, ajustado o rechazado |
| FNC-PRD-003 | A1/Finance | RES-002 | Pricing discovery; precios siguen como hipótesis |
| FNC-CAL-001 | Accounting | RES-002 | Calendario fiscal/operativo versionado |
| FNC-DOM-002 | A2 | DOM-001, DAT-001 | Modelo canónico y diccionario v0.1 |
| FNC-DOM-003 | A2 | DOM-002 | Balances, statements y completitud |
| FNC-DOM-004 | A2 | DOM-002 | Evidencia/movimiento/dedupe e idempotencia segura |
| FNC-DOM-005 | A2/A5 | DOM-002 | Linaje, overlays y engine release |
| FNC-DOM-006 | A2/A5 | DOM-003 | Especificación ejecutable de completitud y saldos |
| FNC-DOM-007 | A2/A5 | DOM-004 | Especificación ejecutable de identidad, idempotencia y dedupe |
| FNC-DB-004 | A2/A4 | DOM-007, DB-002 | Spike PostgreSQL de reclamo concurrente, outbox y lease |
| FNC-ARC-004 | A2 | ARC-001, DOM-002 | Eventos, outbox, retries, DLQ e idempotencia |
| FNC-ARC-005 | A2 | ARC-004 | Contrato de conector con archivos como fallback |
| FNC-ARC-006 | A2 | DOM-001..005, ARC-001..005 | ADR bloqueantes aceptados |
| FNC-PLT-005 | A2/A4 | DOM-001, SEC-001, ARC-004 | Spike auth-context, RLS, outbox y parser sintético |
| FNC-PLT-006 | A4 | PLT-002, ARC-001 | Scaffold pre-S1 de apps, worker, paquetes y migraciones |
| FNC-CFG-001 | A4/A3 | PLT-002, ARC-003 | Contrato de configuración, ambientes y secretos |
| FNC-DB-001 | A2/A4 | PLT-001 | Evaluación y spike plan de migraciones SQL-first |
| FNC-QA-002 | A5 | DOM-002..005 | Estrategia integral de pruebas |
| FNC-QA-003 | A5 | DAT-002, DOM-002..005 | Golden harness determinista en CI |
| FNC-QA-004 | A5 | QA-002, QA-003 | Catálogo ejecutable y reconciliación dinámica de cobertura |
| FNC-QA-005 | A5 | QA-002, QA-003 | Arnés determinista de mutaciones de validadores |
| FNC-SUP-001 | A3/A5 | PLT-003, QA-005 | Baseline ejecutable de cadena de suministro y gaps TM-005 |
| FNC-SUP-002 | A3/A4/A5 | SUP-001, REL-001 | Procedencia y SBOM del candidato firmados y verificables por OIDC/Sigstore |
| FNC-DB-002 | A2/A4 | DB-001, PLT-002 | Spike PostgreSQL de invariantes de migración SQL-first |
| FNC-PLT-007 | A4/A5 | PLT-002/003, QA-004/005 | CLI segura de desarrollo y diagnóstico local |
| FNC-PLT-008 | A4 | PLT-002, CFG-001 | Stack local de producto ejecutable con API, worker y almacenamiento |
| FNC-GAT-003 | A0/A5 | ARC-006, QA-004/005, SUP-001, DB-002 | Agregador ejecutable fail-closed de readiness S1 |
| FNC-GAT-004 | A0/A5 | GAT-003 | Relevancia explícita de contradicciones y enrutado con owner |
| FNC-UX-002 | A6 | UX-001, RES-002 | Pruebas con contadores y PYMEs |
| FNC-BRD-001 | A7 | — | Clearance jurídico de Fincilia |
| FNC-INT-001 | A7 | PRD-001 | Tres cotizaciones comparables de agregadores |
| FNC-FIN-001 | A7/Founder | INT-001, PLT-005 | Presupuesto F0–F2 +30% |
| FNC-GAT-002 | A0 + humanos | Todo F0 | Gate Fase 0 y backlog Fase 1 |

## Rebanadas locales sintéticas fuera de gate

Estas tareas endurecen prototipos locales sin ampliar el conjunto dinámico de
dependencias de `FNC-GAT-002` ni afirmar que Sprint 1 está habilitado.

| ID | Carril | Dependencias | Estado inicial | Resultado verificable |
|---|---|---|---|---|
| FNC-WEB-001 | A6 | PLT-008, UX-001 | Review pending | Recorrido web P3 verificable: ciclos conservados, fuente explícita, carga BFF de 25 MiB, estados accesibles y pruebas web |
| FNC-API-001 | A5 | P3.6, WEB-001 | Review pending | Creacion de plantilla y primera version de mapeo atomica, con conflictos estables y aislamiento cross-tenant |
| FNC-WEB-002 | A5/A6 | WEB-001, API-001, P3.6 | Review pending | Readiness server-side, cola de overrides, aprobacion SoD y rechazo motivado en web |
| FNC-WEB-003 | A6 | WEB-002, API-001, PLT-008 | Review pending | Portafolio multiempresa, vencimientos y navegacion historica sin agregar importes |
| FNC-WEB-004 | A6 | WEB-003, QA-010, UX-001 | Review pending | Sistema visual, menus contextuales y responsive web; revision Product y Accessibility/QA pendiente |
| FNC-CLN-001 | A5/A6 | DOM-005, WEB-002, P3.6 | Review pending | Propuesta tipada y revisión SoD de correcciones por fila, sin mutar el dataset base |
| FNC-CLN-002 | A5/A6 | CLN-001, DOM-005, P3.6 | Review pending | Aplicacion reproducible de overlays aprobados a una version nueva, con manifest y linaje digest-only |
| FNC-CLN-003 | A5/A6 | CLN-002, DOM-005 | Review pending | Solo propone campos materializables por el plan real de linaje; petición manipulada falla cerrada |
| FNC-CLN-004 | A5/A6 | ING-002, API-001, CLN-003 | Review pending | Rango final, preview canonico read-only y reutilizacion versionada de plantillas de limpieza; revision independiente pendiente |
| FNC-QA-006 | A6 | PLT-008, WEB-001, WEB-003, CLN-001 | Review pending | Arranque local coherente y aceptación web automatizada de roles y frontera multiempresa |
| FNC-QA-007 | A5/A6 | QA-006, SEC-001 | Review pending | Administracion final de miembros y multiples roles company-scoped, sin autenticacion propia ni debilitamiento de SoD |
| FNC-QA-008 | A6 | QA-006, QA-007, REC-004, CLS-003 | Review pending | Regresion Chromium/Axe repetible sobre el runtime local persistente sin revertir ledgers ni debilitar revocacion |
| FNC-QA-009 | A6 | QA-008, PLT-009 | Review pending | Regresion Chromium/Axe sobre proyecto Compose desechable sin contaminar ni borrar la demo persistente |
| FNC-QA-010 | A5/A6 | QA-009, SUP-001, SEC-004, SEC-005, LIN-001 | Review pending | CI de main verde y reproducible: suites PostgreSQL aisladas, fixture E2E explicita, inventario ACL completo y monitoreo de dependencias sin entradas ficticias |
| FNC-REC-001 | A5/A6 | DOM-003, DOM-004, WEB-003, QA-006 | Review pending | Exploración sintética read-only de candidatos explicados; sin decisión, auto-match ni cierre |
| FNC-REC-002 | A5/A6 | REC-001, DOM-004, SEC-001 | Review pending | Propuesta y decisión humana append-only, con SoD e idempotencia; sin efecto financiero ni cierre |
| FNC-REC-003 | A5/A6 | REC-002, WEB-003 | Review pending | Bandeja multiempresa company-by-company para priorizar revisiones sin agregar importes ni decidir fuera del expediente |
| FNC-REC-004 | A5/A6 | REC-002, REC-003 | Review pending | Exclusividad uno-a-uno de confirmaciones bajo concurrencia, sin efecto financiero ni cierre |
| FNC-REC-005 | A5/A6 | REC-004, DOM-003, DOM-005 | Review pending | Borradores manuales 1:N/N:1 de movimientos completos, append-only, idempotentes y sin asignaciones ni efecto financiero; revisión independiente pendiente |
| FNC-REC-006 | A5/A6 | REC-002, REC-003 | Review pending | Expediente append-only consultable por ID estable aunque su dataset ya no sea elegible o el candidato no esté en la página visible; revisión independiente pendiente |
| FNC-ING-001 | A4/A5/A6 | DOM-005, PLT-008, WEB-001 | Review pending | Ingesta segura y determinista de XLSX sintetico de una hoja con localizador exacto; libros activos o ambiguos permanecen en cuarentena |
| FNC-ING-002 | A4/A5/A6 | ING-001, QA-010 | Review pending | Seleccion company-scoped de una hoja XLSX segura, seguida de perfil, extraccion y limpieza visual en el estudio de mapeo; revision independiente pendiente |
| FNC-ING-003 | A4/A5/A6 | ING-002, CLN-004, WEB-003 | Review pending | Fuente autoritativa e inmutable en cada recepcion nueva y centro web keyset de documentos; legacy permanece sin atribucion inferida |
| FNC-ING-004 | A4/A6 | ING-003, QA-010 | Review pending | Bandeja web de hasta 10 cargas por fuente, concurrencia maxima 2, progreso, cancelacion y reintento por archivo; revision independiente pendiente |
| FNC-ING-005 | A4/A5/A6 | ING-001, ING-002, ING-004 | Review pending | ODS tabular seguro con seleccion, perfil, extraccion y coordenadas; la web distingue procesamiento de simple cuarentena |
| FNC-CLS-001 | A5/A6 | OPS-001, DQ-001, RPT-001, REC-004 | Review pending | Diagnostico company-scoped por periodo de evidencia y bloqueos; nunca ejecuta ni certifica cierre |
| FNC-CLS-002 | A5/A6 | CLS-001, DOM-002, DOM-003, DOM-005 | Review pending | Observaciones canonicas e inmutables de saldo por cuenta con evidencia visible; linaje completo y revision independiente pendientes |
| FNC-CLS-003 | A5/A6 | CLS-002, DOM-003, DOM-005, REC-004 | Review pending | Assessments, partidas conciliatorias y statements reproducibles verificados; sin excepcion aceptada, snapshot ni cierre productivo |
| FNC-CLS-004 | A5/A6 | CLS-001, CLS-002, CLS-003 | Review pending | Preparacion de cierre integra cobertura de statements por cuenta/periodo y distingue evidencia lista para revision, sin ejecutar ni certificar cierre |
| FNC-CLS-005 | A5/A6 | CLS-004, LIN-001, SEC-001 | Review pending | Expediente digest-only, versionado y append-only para revision previa con asignacion, SoD y drift; PostgreSQL y web verificados, sin snapshot, certificacion ni cierre |
| FNC-LIN-001 | A5/A6 | DOM-005, CLS-002, CLS-003, CLS-004 | Review pending | Linaje digest-only materializado de saldos, assessments, controles, partidas y statements; guards exactos, PostgreSQL y web verdes, sin ejecutar cierre |
| FNC-EXP-001 | A5/A6 | WEB-002, DOM-005, SEC-001 | Review pending | Exportacion CSV canonica determinista de dataset publicado, con permiso explicito, RLS y BFF streaming; solo sintetica y no certificada |
| FNC-OPS-001 | A5/A6 | WEB-003, QA-006 | Review pending | Centro web company-by-company de ciclos, vencimientos, recordatorios internos e historico operativo sin importes ni mensajeria externa; CI verde, revision humana pendiente |
| FNC-DQ-001 | A5/A6 | DOM-003, DOM-004, WEB-003, QA-006 | Review pending | Alertas deterministas company-scoped, triaje auditado y resumen visual sin IA, auto-match, cierre ni afirmacion de fraude; revision independiente pendiente |
| FNC-RPT-001 | A5/A6 | WEB-003, REC-003, DQ-001, EXP-001 | Review pending | Informes operativos e historicos company-scoped, importes exactos por moneda, CSV determinista y web verificada; revision humana pendiente |
| FNC-ONB-001 | A5/A6 | PLT-008, QA-007, P3.5 | Review pending | Alta atomica de empresa, engagement y configuracion inicial desde la web; solo sintetico mientras DRG-00 siga cerrado |
| FNC-ONB-002 | A3/A5/A6 | ONB-001, SEC-001, PLT-011 | In progress | Registro web sintetico crea sujeto, firma y owner sin semillas; proveedor local prohibido con datos reales e IdP administrado pendiente |
| FNC-BET-001 | A2/A3/A6 | ONB-002, PLT-011, REL-001 | In progress | Beta cerrada con dominio HTTPS y datos exclusivamente sintéticos; no mueve DRG-00/01 |
| FNC-PLT-012 | A2/A3/A4 | GAT-005, ARC-003, SEC-003, REL-001 | In progress | Foundation separada integrada; plan/apply y activación continúan bloqueados por DRG-00/01 |
| FNC-PLT-013 | A2/A3/A4 | PLT-012, GAT-005 | Review pending | Plano de costo frío/encendido y controlador seguro integrados; aplicación y datos reales continúan bloqueados |
| FNC-PLT-014 | A2 | PLT-012 | Review pending | Actividades AWS Credits completadas con USD 200 disponibles; laboratorio sintético retirado por completo |
| FNC-IAM-001 | A3/A6 | ONB-002, SEC-001, LEG-002 | In progress | Google OIDC/Cognito con PKCE preparado; activación real bloqueada por DRG-00 |
| FNC-IAM-002 | A3/A6 | IAM-001, ONB-002, QA-007 | Review pending | Centro de cuenta y recorrido coherente de identidad, sesión, empresas y roles |
| FNC-IAM-003 | A2/A3/A6 | IAM-001, IAM-002, PLT-012 | Review pending | Logout federado, SignUp nativo cerrado y contrato de assurance Google sin sobreafirmar MFA |
| FNC-ACC-001 | A4/A5/A6 | ING-005, REC-006, CLS-005, RPT-001 | Review pending | Recorrido contable web guiado sin cambiar semántica ni ejecutar cierre |
| FNC-UX-003 | A6 | WEB-004, UX-001, IAM-002, ACC-001 | Review pending | Shell SaaS premium, navegación jerárquica, motion accesible y responsive |
| FNC-LEG-002 | A3/A6 | PRV-001, LEG-001 | In progress | Centro legal público Fincilia desarrollado por Parallext.com; textos sujetos a revisión jurídica |
| FNC-SEC-004 | A3/A5 | SEC-001, PLT-005, DB-002 | Review pending | Contexto durable company-scoped con emision idempotente, revalidacion online, revocacion append-only, HMAC y V0021; sin consumidor artificial ni datos reales |
| FNC-SEC-005 | A3/A5 | SEC-004, DB-002, P3.6 | Review pending | Trabajos nuevos ligados a issued context y revalidados al reclamar, escribir y cerrar; fase expand compatible con filas legacy |
| FNC-PLT-009 | A2/A6 | PLT-002, PLT-007, QA-006 | Review pending | Runtime local persistente de Windows/WSL con keepalive oculto, PID verificado, salida minima y lifecycle que conserva volumenes |
| FNC-PLT-010 | A2/A6 | ARC-003, SEC-003, FIN-001 | Review pending | OpenTofu aplico 8 recursos bootstrap y 45 de control plane sin drift; runtime/datos reales excluidos; revisión Security/Architecture/Platform/QA pendiente |
| FNC-PLT-011 | A2/A6 | PLT-010, REL-001, CFG-001 | Review pending | Laboratorio t3.small SSM-only desplegado por digest; runtime, tenancy, promocion, backup/restore y autostop verificados solo con datos sinteticos |
| FNC-REL-001 | A2/A5/A6 | CFG-001, SUP-001, QA-010, PLT-009 | Review pending | Candidato reproducible Linux/Windows, SBOM SPDX, observabilidad redactada, workflow manual y CI verdes; sin publicar ni habilitar producción |
| FNC-AUD-001 | A5/A6 | SEC-001, QA-007, WEB-003 | Review pending | Centro de auditoria company-scoped con actor, filtros exactos, cursor estable y vista multiempresa sin exponer payload ni convertir fallos en cero |

## No codificar todavía

- Ingesta de documentos reales o conectores reales.
- Operación de cierres, auto-match o informes certificados.
- Parser universal, PDF/OCR general o contraseñas PDF.
- Alertas que declaren fraude.
- IA externa, entrenamiento o Needle.
- Aplicación móvil productiva.
- Billing y precios definitivos.
- Warehouse, Kafka, Kubernetes, OpenSearch, pgvector o múltiples celdas.
- Producción cloud antes de A-02/L-02.
- Autenticación propia; se evaluará IdP B2B administrado.
- Constraints únicos por fecha/monto/referencia.
- Company subordinada estructuralmente a una firma.
