---
task_id: FNC-LIN-001
status: REVIEW_PENDING
base_sha: 891a1a0bc23640fa023e1105fb25da02a6caa6f9
reservation_sha: a45177c
database_api_sha: e97c193
web_sha: ff1b313
replay_fix_sha: afa2a72
tested_head_sha: 830336dc8c1211816250cdb4f80f12e0232cc555
integration_sha: 830336dc8c1211816250cdb4f80f12e0232cc555
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Data/Architecture, Security, Database, Accessibility/QA]
---

# Handoff FNC-LIN-001 — linaje financiero previo al cierre

## Resultado

Los saldos y las decisiones que alimentan la preparación de cierre ya no pueden
declarar linaje completo sin materializar la prueba física correspondiente.
V0031-V0033 añaden nodos y aristas digest-only para observaciones de saldo,
evaluaciones de completitud, controles, partidas conciliatorias y statements.
PostgreSQL comprueba de forma diferida tanto la presencia del grafo como la
correspondencia exacta con empresa, entidad, ejecución, release, esquema y
evidencia fijada.

La API construye el grafo dentro de la misma unidad transaccional que la decisión
y sólo sella un statement después de verificar todas sus entradas. El endpoint de
trazabilidad aplica la autorización server-side y RLS y devuelve exclusivamente
identidades opacas, coordenadas, reglas, versiones y huellas SHA-256. No devuelve
importes, valores de celda, payloads ni documentos.

La preparación de cierre incorpora un drill-down visual de esa evidencia. Sigue
sin existir una acción de cerrar, certificar, aceptar materialidad o reabrir.

## Semántica e invariantes

- `account_balance.amount` y `account_balance.as_of` descienden a la fila publicada,
  el plan de seis etapas, el artefacto y sus digests exactos.
- Assessments y controles fijan dataset, ejecución, release, versión de esquema,
  regla y resultado; `unknown`, `mismatch` o linaje incompleto no se promueven.
- Cada partida confirmada conserva sus evidencias, versión de decisión, SoD y
  compatibilidad de moneda/release/esquema con el statement.
- El statement fija exactamente saldos, assessments y partidas vigentes. La
  selección de partidas ya no acepta una decisión compatible sólo por nombre o
  estado: exige moneda, release y esquema idénticos.
- Un replay exacto puede añadir únicamente el grafo faltante de una fila antigua
  que ya decía `complete`. Si cambia el observation key, el contenido, la versión
  o la procedencia, falla cerrado y no reescribe cifras ni estados financieros.
- Una violación de integridad en el INSERT del statement se traduce a un conflicto
  de dominio estable; nunca vuelve como error 500 ni deja una decisión parcial.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| Base temporal vacía V0001-V0033 | 33 aplicadas, head V0033, OK |
| Replay del plan sobre la misma base | 33 already applied, 0 aplicadas, `mutated=false` |
| PostgreSQL/RLS/SoD focal | 8 pruebas, OK |
| API unitaria completa | 141 pruebas, OK |
| Herramientas de repositorio | 1196 pruebas, OK |
| Contratos Python compartidos | 329 pruebas, OK |
| Web unitaria | 198 pruebas en 32 ficheros, OK |
| ESLint, TypeScript y build Next | OK; 23 rutas de producto |
| Chromium completo | 26/26, OK |
| Axe completo | 15/15, 0 violaciones automatizadas |
| Canonical, completitud, linaje y vocabulario cruzado | OK |
| Golden registry | 14 casos, verify OK |
| Mutation registry | 68/68 killed, 0 survivors, árbol intacto |
| Catálogo ejecutable | modelo válido, sin findings bloqueantes |
| Quality gate por commit | OK, 0 hallazgos |
| S1-READY después de refrescar evidencia | 39 machine pass, 1 pendiente humano |

Comandos principales:

```text
python -m tools.lineage_model.validate
python -m tools.canonical_model.validate
python -m tools.completeness_model.validate
python -m tools.cross_contract_model.validate
python -m tools.golden_harness.cli verify
python -m tools.mutation_harness.cli run
python -m tools.test_catalog.cli validate
python -m tools.s1_readiness.cli evaluate
python -m tools.quality_gate.cli
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
npm --prefix apps/web run test:a11y
```

Las 141 pruebas API y las 8 pruebas PostgreSQL se ejecutaron dentro de las
imágenes `api` y `migrate`. La prueba blank/replay utilizó exclusivamente la base
temporal `fincilia_lineage_blank_v0033`, creada con ese nombre y eliminada al
terminar.

## Hallazgos durante la ejecución

1. El statement incorporaba partidas confirmadas de moneda, release o esquema
   distintos. El guard de base lo rechazaba como 500; ahora el productor filtra
   exactamente y el error de carrera se expresa como conflicto estable.
2. Un replay histórico podía conservar `lineage_state=complete` sin nodos físicos.
   Se añadió reparación aditiva sólo para replay exacto y se probaron los dos
   lados: materializa si coincide y rechaza si el digest diverge.
3. Los selectores E2E encontraban resúmenes ocultos de otras tarjetas. Se limitaron
   a `summary:visible`; Chromium y Axe completos pasan.
4. El volumen local persistente acumula empresas, periodos y filas creados por
   suites PostgreSQL/E2E, incluso fixtures con años futuros. Eso puede desplazar
   la empresa demo fuera de la primera ventana y hace que filas antiguas sigan
   visibles pero bloqueadas. No se borró ni reinterpretó evidencia append-only.
   El aislamiento/limpieza de suites contra el volumen de demostración debe
   tratarse como una tarea QA separada.
5. La inspección visual con el perfil fundador confirmó grants multirol reales,
   creación de ciclo y periodos, ausencia de acciones de cierre y bloqueo honesto
   de evidencia incompleta. La ruta positiva completa se probó contra PostgreSQL
   y el endpoint de linaje, no mediante manipulación manual de fixtures viejos.

## Revisiones y gate

Accounting debe revisar la semántica de inputs y estados; Data/Architecture, la
cobertura y cardinalidad del grafo; Security y Database, RLS, funciones y guards
diferidos; Accessibility/QA, el drill-down con tecnología asistiva real.
El implementador y `FOUNDER-01` no cuentan como revisores independientes.

S1-READY permanece `not_met`. La evidencia mecánica vuelve a 39/40; el único
blocker es `ADR-RDY-INDEPENDENT-REVIEWS`. Esta entrega no acepta ese pendiente,
DRG-00, DRG-01 ni ningún riesgo residual.

## Rollback y rutas liberadas

Rollback de aplicación: revertir primero `ff1b313`, después `afa2a72` y
`e97c193`. Las migraciones V0031-V0033 son expand/forward-only y permanecen para
preservar las garantías; no existe migración descendente ni borrado de nodos.
Volver al código anterior presenta el linaje faltante como bloqueo y no altera
movimientos, saldos, assessments, partidas, statements ni auditoría.

Todas las rutas de FNC-LIN-001 quedan liberadas. La tarea pasa a revisión
independiente, no a Done ni a aprobación de gate.
