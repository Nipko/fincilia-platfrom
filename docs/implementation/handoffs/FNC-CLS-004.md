---
task_id: FNC-CLS-004
status: REVIEW_PENDING
base_sha: 020a7be
reservation_sha: 3236c34
backend_sha: fff522d
web_sha: eeb803b
tested_head_sha: eeb803b
integration_sha: pending_handoff_commit
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLS-004 — preparacion de cierre integrada

## Resultado

La sala de preparación de cierre ya consume los estados reproducibles de
FNC-CLS-003. Por cada empresa, periodo y cuenta descubre la evaluación de
completitud ligada al dataset seleccionado y la última versión determinista del
root de conciliación. Distingue falta de assessment, falta de statement,
evidencia anterior, estado que requiere revisión y cobertura balanceada.

Un periodo puede quedar `ready_for_review` únicamente cuando todos los controles
diagnósticos pasan. Esa etiqueta nunca cambia `close_ready=false` ni
`can_execute_close=false`: no existe botón, comando ni endpoint de cierre,
certificación o aceptación de materialidad.

## Semántica y seguridad

- Assessment se selecciona por `(source_expectation_id, dataset_version_id)`;
  una evaluación del extracto anterior no sirve para el periodo actual.
- Statement se selecciona por `(financial_account_id, period_start, period_end)`
  y versión descendente con desempate estable. Nunca hay un `latest` global.
- La cobertura compara exactamente el conjunto de assessments elegibles de las
  fuentes actuales con los IDs fijados por el statement.
- Estado balanceado, cobertura de entradas y linaje del propio statement son
  controles separados. Así, el sistema puede reconocer un cálculo existente sin
  ocultar que su camino de linaje aún está pendiente.
- La proyección conserva `close.prepare`/`report.read`, contexto server-side y
  RLS. Sólo expone IDs, nombres de cuenta, conteos, estados y razones; no lee ni
  agrega importes, monedas o diferencias.
- `product_close` continúa `unavailable` como guardia visible, pero no se mezcla
  con los blockers de evidencia previa.

## Experiencia web

`/preparacion-cierre` ahora muestra:

- periodos bloqueados y periodos con evidencia lista para revisión humana;
- controles separados de assessments, statement vigente y linaje del estado;
- tabla expandible por cuenta con fuentes, evaluaciones, versión, estado,
  cobertura y linaje;
- lenguaje explícito que no confunde revisión con cierre;
- enlaces a ciclos, calidad y conciliaciones, sin acción financiera.

La inspección visual sobre el contenedor final verificó jerarquía, tarjetas,
tablas y responsive de la estación. El resumen se ajustó a una cuadrícula 4+3
para evitar una métrica aislada en escritorio. No hubo errores de consola.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| API unitaria completa | 139 pruebas, OK |
| API focal de readiness | 10 pruebas, OK |
| PostgreSQL/RLS/readiness existente | 2 pruebas, OK |
| PostgreSQL statement → readiness → nueva versión | 3 pruebas, OK |
| Web unitaria completa | 196 pruebas en 31 ficheros, OK |
| TypeScript y ESLint | OK |
| Build Next local y build Docker productivo | OK; 23 rutas y shell |
| Chromium completo | 26/26, OK |
| Axe completo | 15/15, 0 violaciones, OK |
| Canonical, completitud, linaje y cross-contract | OK |
| Work graph y catálogo ejecutable | OK |
| Quality gate por commit | OK, 0 hallazgos |
| Stack final | API, web, worker, PostgreSQL, Valkey y MinIO saludables |

Comandos principales:

```text
python -m unittest discover -s tests
python -m unittest db.tests.test_close_readiness -v
python -m unittest db.tests.test_balance_reconciliation_statements -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web run typecheck
npm --prefix apps/web run test:e2e
npm --prefix apps/web run test:a11y
python -m tools.canonical_model.validate
python -m tools.completeness_model.validate
python -m tools.lineage_model.validate
python -m tools.cross_contract_model.validate
python -m tools.quality_gate.cli
```

Los comandos de Python de aplicación se ejecutaron dentro de las imágenes
`api`/`migrate`; los de PostgreSQL usaron el servicio real del proyecto
`fincilia-local`.

## Hallazgos y límites

1. La proyección anterior seguía declarando `reconciliation_statements` como
   inexistente, aunque FNC-CLS-003 ya los persistía. La lectura queda sincronizada
   sin migración ni mutación financiera.
2. El statement productivo fija versiones e inputs, pero su `lineage_state`
   continúa `required_pending` por diseño de V0029. La sala lo reconoce y muestra
   ese hueco como bloqueo; esta tarea no inventa aristas ni lo promueve a complete.
3. Ejecutar `next build` y `tsc` en paralelo puede competir por `.next/types` y
   producir un error transitorio. La cadena final se ejecutó en orden y ambos
   comandos pasaron; CI ya usa orden secuencial.
4. El volumen local conserva empresas y periodos sintéticos de regresiones
   anteriores. No se borró evidencia append-only para presentar una demo limpia.

Accounting debe revisar cobertura por cuenta y significado de revisión;
Security y Backend/Architecture, consultas, RLS y selección determinista;
Product y Accessibility/QA, lenguaje y uso con tecnología asistiva real.
`FOUNDER-01` y el implementador no cuentan como revisores independientes.

## Rollback y rutas liberadas

Revertir `eeb803b` retira la presentación integrada. Revertir después `fff522d`
restaura el diagnóstico anterior sin tocar statements, balances, assessments,
ciclos ni auditoría. No hay migración descendente ni datos que borrar.

Rutas liberadas: módulo/tests API de readiness, aserciones focales DB, tipos,
agregador, página/estilos/pruebas web, ficha, backlog, fase y handoff de
FNC-CLS-004. S1-READY permanece 39/40 y no cambia por esta entrega.
