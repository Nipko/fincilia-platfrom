---
task_id: FNC-CLN-003
status: REVIEW_PENDING
base_sha: 4654c3b
reservation_sha: ded2997
implementation_sha: c9d6b9d
integration_sha: pending
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Product, QA]
---

# Handoff FNC-CLN-003 — aplicabilidad ligada al linaje

## Resultado entregado

La plataforma ya no confunde “tipo normalizable” con “corrección aplicable”. El
endpoint de targets deriva el conjunto corregible desde `lineage_plan_id` del
dataset y solo devuelve campos con las seis etapas de linaje exactas, únicas y
ordenadas. Una petición que intente saltarse la interfaz recibe
`correction-field-not-applicable` y no crea overlay.

Un movimiento visible cuyo plan no tenga ningún campo aplicable devuelve una
lista vacía, no un falso 403. Un movimiento inexistente o de otra empresa sigue
recibiendo respuesta neutral.

## Regla implementada

Las etapas obligatorias son, en orden:

1. `artifact_version`
2. `raw_locator`
3. `extracted_field`
4. `transformed_value`
5. `source_record_field`
6. `financial_fact_field`

La consulta parte de `dataset_version` bajo RLS y une sus pasos por plan y
empresa. El cliente no envía plan, etapa, locator ni declaración de cobertura.
Duplicados, huecos, orden incorrecto, campo desconocido o plan ausente excluyen
el campo completo.

`SUPPORTED_FIELDS` continúa siendo el allowlist de tipos; no se redujo la
capacidad futura. La intersección entre allowlist y plan completo es la capacidad
real de cada versión.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| Pruebas puras de aplicación/plan | 6, OK |
| PostgreSQL + API + MinIO | 10, OK (`field_overlays` + `correction_application`) |
| API completa en imagen | 117, OK |
| Web lint + TypeScript | OK |
| Web unitarias | 174 en 28 ficheros, OK |
| Web build de producción | OK |
| Work graph y quality gate | OK sobre el índice funcional |
| Navegador integrado | selector real limitado a Importe y Fecha de ocurrencia |

La prueba PostgreSQL comprueba además que `posted_on` no aparece y que un POST
manual para ese campo devuelve 409 sin insertar `field_overlay`. Los flujos
existentes de importe y fecha de ocurrencia, SoD, concurrencia, append-only,
aplicación y publicación independiente continúan verdes.

## Hallazgos

1. El endpoint anterior ejecutaba hasta siete lecturas y devolvía todo el
   allowlist, aunque el plan real solo publicara dos campos. Ahora hace una
   lectura de plan, filtra y reutiliza el probe de importe.
2. `[]` significaba a la vez “movimiento invisible” y “sin campos aplicables”.
   Separar `None` de lista vacía evita convertir una limitación legítima en una
   denegación de acceso engañosa.
3. Tres pruebas antiguas usaban moneda/dirección para demostrar SoD o
   append-only. Se trasladaron a importe/fecha aplicables; no se relajó ninguna
   invariante.

## Revisión y límites

Accounting debe confirmar que restringir por plan es la política correcta;
Security, que la derivación server-side y RLS no abren un oracle; Product/QA,
el lenguaje y el estado sin campos. El implementador y `FOUNDER-01` no cuentan
como revisión independiente.

No hubo migración, dependencia, dato real, IA, móvil, auto-match, cierre ni
publicación automática. ADR-026 sigue `Proposed`; S1-READY conserva 39/40
requisitos en verde y permanece bloqueado exclusivamente por revisión humana
independiente.

## Rollback

Revertir el aviso web y el filtro/guard server-side devuelve el comportamiento
anterior sin transformar datos. No se requiere rollback de base. Los overlays ya
creados antes de esta regla siguen preservados; CLN-002 continuará fallando
cerrado si uno carece de paso terminal.

## Rutas liberadas

Dominio/rutas de correcciones API, pruebas puras y PostgreSQL de correcciones,
detalle web del movimiento y registros de FNC-CLN-003.
