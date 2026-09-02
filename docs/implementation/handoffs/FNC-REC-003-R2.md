---
task_id: FNC-REC-003
round: R2
status: REVIEW_PENDING
base_sha: 796b62d46c34676b32df47b072cd08628915ff2c
implementation_sha: 7e6f00f9f27d9964fb8556cab459571ddbaedb0d
tested_head_sha: 1e70ae0fa0d0ecccc2e402cb66bfd01fa127aab7
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-REC-003 R2 — productividad de bandeja

## Resultado

La bandeja multiempresa ya permite trabajar por empresa, paginar de forma real
y volver desde el expediente al mismo estado operativo. La vista general sigue
consultando empresa por empresa; no existe un endpoint transversal ni una
identidad de empresa confiada al cliente.

El filtro manipulado falla cerrado. Una empresa seleccionada usa paginas de 50
expedientes con offset maximo 10000; el portafolio completo muestra truncamiento
y exige elegir empresa en vez de fingir una pagina global. El trabajo visible se
resume sin dinero ni saldos y se ofrece el expediente pendiente mas antiguo.

## Contrato de continuidad

El enlace al expediente lleva tres valores cerrados: filtro, empresa actual o
`todas`, y pagina acotada. La estacion reconstruye por codigo el enlace de
retorno. No recibe `returnTo`, no admite un host/ruta arbitrarios y rechaza una
empresa distinta de la que se esta consultando. Las decisiones humanas siguen
en FNC-REC-002 y el retorno permanece tras cada server action.

## Evidencia

| Alcance | Resultado |
|---|---|
| Vitest web completo | 283 pruebas en 49 archivos, OK |
| Vitest focal REC-003/estacion | 42 pruebas en 4 archivos, OK |
| TypeScript + ESLint focal | OK |
| Next production build | OK dentro de la imagen E2E |
| instalación vacia + onboarding | 1/1 Chromium, OK |
| primera regresion integral | 41/42 Chromium; unico fallo en selector ambiguo del test, corregido |
| REC-003 focal sobre stack efimero | 1/1 Chromium, OK |
| REC-003 accesibilidad | 1/1 Axe, cero violaciones |
| aislamiento | contenedores, redes y volumenes `fincilia-e2e` eliminados y ausencia verificada |

## Hallazgos de ejecucion

1. `getByLabel('Empresa')` tambien encontraba la region titulada “Carga visible
   por empresa”. El selector E2E se hizo exacto; no se cambio el etiquetado
   accesible del producto.
2. Al repetir toda la regresion, antes de llegar al navegador, el test existente
   `test_exact_candidates_are_explained_paginated_and_many_to_many` genero una
   forma sintetica diferente a la plantilla y recibio correctamente
   `MAP-SCHEMA-DRIFT`. Habia pasado en la corrida inmediatamente anterior. Es
   una no determinacion del fixture PostgreSQL fuera del diff de esta ronda; el
   producto REC-003 se volvio a ejercer de forma aislada y paso.
3. El limite de pagina web coincide con el offset maximo ya contratado por la
   API: pagina 200 por 50 = 10000. No se modifico backend ni base de datos.

## Limites y revisiones

- Solo datos sinteticos; DRG-00/DRG-01 y S1-READY no cambian.
- No hay auto-match, confirmacion masiva, score, tolerancia, cierre ni efecto
  financiero.
- Product/Accounting debe revisar prioridad y lenguaje; Security/Architecture,
  el fallo cerrado y retorno; Accessibility/QA, densidad y foco en movil.
- ADR-027 permanece `Proposed`. Ninguna revision humana fue aceptada.

## Commits y rollback

1. `7e6f00f` — filtros, paginacion, resumen, siguiente pendiente y retorno seguro.
2. `1e70ae0` — recorridos Chromium/Axe de filtro, expediente y retorno.

Revertir 2 retira solo cobertura E2E. Revertir 1 vuelve a la bandeja R1 sin
tocar ledger, API, migraciones, propuestas, decisiones ni datos.
