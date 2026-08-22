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
| FNC-GOV-001 | A0/Founder | — | Blocked: human | Owners nominales, suplentes, RACI y aprobador por gate |
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
| FNC-ARC-004 | A2 | ARC-001, DOM-002 | Eventos, outbox, retries, DLQ e idempotencia |
| FNC-ARC-005 | A2 | ARC-004 | Contrato de conector con archivos como fallback |
| FNC-ARC-006 | A2 | DOM-001..005, ARC-001..005 | ADR bloqueantes aceptados |
| FNC-PLT-005 | A2/A4 | DOM-001, SEC-001, ARC-004 | Spike auth-context, RLS, outbox y parser sintético |
| FNC-QA-002 | A5 | DOM-002..005 | Estrategia integral de pruebas |
| FNC-QA-003 | A5 | DAT-002, DOM-002..005 | Golden harness determinista en CI |
| FNC-UX-002 | A6 | UX-001, RES-002 | Pruebas con contadores y PYMEs |
| FNC-BRD-001 | A7 | — | Clearance jurídico de Fincilia |
| FNC-INT-001 | A7 | PRD-001 | Tres cotizaciones comparables de agregadores |
| FNC-FIN-001 | A7/Founder | INT-001, PLT-005 | Presupuesto F0–F2 +30% |
| FNC-GAT-002 | A0 + humanos | Todo F0 | Gate Fase 0 y backlog Fase 1 |

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
