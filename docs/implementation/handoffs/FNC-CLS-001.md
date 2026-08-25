---
task_id: FNC-CLS-001
status: REVIEW_PENDING
base_sha: d81dadd
reservation_sha: dfebaf6
backend_sha: 50606f0
web_sha: bae2af7
journey_sha: d1a2365
refinement_sha: 29cee87
tested_head_sha: 29cee87
integration_sha: pending
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLS-001 — preparacion diagnostica de cierre

## Resultado entregado

La plataforma tiene un centro web multiempresa que explica, por periodo, que
evidencia existe y que bloquea un eventual cierre. La API decide el alcance
company-scoped bajo RLS; la web consulta una empresa a la vez y conserva como
vista parcial toda revocacion, restriccion o indisponibilidad.

El resultado siempre lleva `mode: diagnostic_only`, `close_ready: false` y
`can_execute_close: false`. No existe endpoint de mutacion, boton de cierre,
calculo de saldo, suma de importes, mezcla de monedas, porcentaje de match ni
afirmacion de conciliacion certificada.

## Implementacion y regla de evidencia

- `source_expectation` define los periodos y fuentes esperadas. La API acepta
  solo `limit` entre 1 y 24; empresa, estados y conteos se resuelven server-side.
- Para una expectativa satisfecha, el dataset se elige con regla visible y
  determinista: publicado, luego validado, luego otro estado; dentro del estado,
  `prepared_at` e identificador descendentes. Elegirlo no afirma completitud.
- La ventana completa falla con `close-readiness-scope-too-large` si contiene
  mas de 1.200 expectativas. No devuelve una fraccion que pueda parecer completa.
- Catorce controles separan recepcion, dataset, publicacion, completitud, linaje,
  filas rechazadas, fecha contable, revisiones, calidad, correcciones, saldos,
  estado de conciliacion y capacidad productiva de cierre.
- Alertas y revisiones se deduplican por identificador. Solo se leen metadatos;
  no se consultan importes, referencias, descripciones ni valores corregidos.
- La interfaz filtra empresa y periodo usando exclusivamente opciones obtenidas
  de empresas ya autorizadas. El resumen multiempresa suma solo conteos de trabajo.

## Seguridad y limites fail-closed

- Permiso `report.read`, `company_context` y transaccion con contexto RLS en cada
  lectura. La prueba real demuestra que Espiga no ve una expectativa de Andinos.
- Datos reales bloqueados con 503; todo el recorrido usa datos sinteticos.
- Una dispensa, `accepted_exception`, dataset no publicado o evidencia ausente
  bloquea. La aplicacion no inventa el contrato de excepcion contable que falta.
- `account_balance` y `reconciliation_statement` no existen como entidades
  productivas. Ambos controles son `unavailable`, no ceros ni estados exitosos.
- No se agrego migracion, cache, IA, workflow, ledger, cierre o efecto financiero.

## Evidencia ejecutada

| Verificacion | Resultado |
|---|---|
| API unitaria completa en imagen | 123 pruebas, OK |
| PostgreSQL/API/RLS focal | 2 pruebas, OK |
| Web unitaria completa | 182 pruebas en 29 ficheros, OK |
| TypeScript, ESLint y build Next productivo | OK; ruta `/preparacion-cierre` incluida |
| E2E focal | autenticacion, navegacion, filtro empresa/periodo, detalle y ausencia de accion; OK |
| Accesibilidad focal Axe | 0 violaciones, OK |
| Accesibilidad web completa | 13 pruebas, OK |
| Migraciones inmutables | V0001–V0025; `applied: []`, `mutated: false` |
| Quality gate, work graph y contrato S1 | validos |
| Stack local | API, web, worker, PostgreSQL, Valkey y MinIO saludables |
| Navegador integrado | 5 periodos sinteticos visibles; 5 bloqueados; filtro Espiga deja 2 |

La regresion funcional completa sobre la base local persistente termino 23/24.
El unico caso ajeno, FNC-REC-002, intenta confirmar un expediente que una
ejecucion anterior ya dejo terminal; no hay expediente abierto disponible en
ese fixture. No se borro ni reabrio el ledger append-only para forzar verde. El
recorrido focal FNC-CLS-001 pasa y el carril CI usa un worker y base nueva.

S1-READY permanece en 39/40 (97,5 %): el unico blocker es
`ADR-RDY-INDEPENDENT-REVIEWS`. Esta tarea no modifica el gate.

## Hallazgos de ejecucion

1. Limitar periodos no limita por si solo el numero de fuentes. El primer diseno
   podia crecer sin cota dentro de un periodo; ahora rechaza mas de 1.200.
2. Una lectura que no encuentra alertas o revisiones no prueba conciliacion. La
   interfaz dice `0 observaciones`, pero conserva el periodo bloqueado y el aviso.
3. Ejecutar los E2E locales con 11 workers sobre una base compartida produjo
   interferencia entre fixtures antiguos de roles, calidad, carga y recordatorios.
   Con el worker unico de CI, 23 pasaron y solo quedo el ledger ya consumido.
4. Las entidades requeridas para saldo y reconciliation statement aun no estan
   en el esquema canonico productivo. Implementarlas exige contrato/ADR y otra
   rebanada; ocultar esa ausencia habria creado un falso listo para cierre.

## Revision humana requerida

- Accounting: semantica de cada control, tratamiento de dispensa/excepcion y
  evidencia minima futura de saldo y reconciliation statement.
- Security + Backend/Architecture: consultas RLS, regla de seleccion, cota de
  1.200 y auditoria de metadatos.
- Product + Accessibility/QA: jerarquia visual, lenguaje fail-closed, filtros,
  tabla de evidencia y ausencia inequívoca de una accion de cierre.

`FOUNDER-01`, el implementador y los usuarios sinteticos no cuentan como
revisores independientes.

## Rollback

Es una proyeccion read-only. Puede retirarse la ruta web, navegacion y endpoint
sin tocar datos. No hay migracion ni filas propias que revertir. Auditorias de
lectura ya registradas se conservan.

## Rutas liberadas

API y pruebas de close-readiness, ruta y helpers web, navegacion, estilos,
pruebas Playwright/Axe, ficha, handoff y registros centrales de FNC-CLS-001.
