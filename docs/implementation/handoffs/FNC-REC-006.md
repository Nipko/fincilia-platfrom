---
task_id: FNC-REC-006
status: REVIEW_PENDING
base_sha: 9dd1759817cbc91cc61a8ee117df920c3be37984
reservation_sha: dcd2034
implementation_sha: fdd0864
tested_head_sha: fdd0864
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-REC-006 — expediente histórico direccionable

## Resultado

La bandeja multiempresa enlaza ahora cada expediente con su `candidate_id`
estable. La estación valida ese identificador y consulta directamente el ledger
append-only, de modo que el expediente sigue visible si sus datasets dejaron de
ser elegibles o si el candidato quedó fuera de la página actual.

La corrección no cambia el ledger ni el motor: no reactiva datasets, no vuelve a
evaluar reglas históricas, no modifica decisiones y no acredita saldos. Si el
candidato ya está en la página visible, se usa la tarjeta existente y no se
duplica el expediente.

## Seguridad y contrato

- `GET /api/v1/companies/{company_id}/reconciliation/reviews/{candidate_id}`
  exige `movement.read`, contexto de empresa resuelto server-side y el RLS ya
  forzado en `match_candidate`, `match_decision` y movimientos.
- El ID se valida como UUID antes de SQL. Un ID inexistente o de otra empresa se
  responde de forma neutral; un valor mal formado devuelve 422.
- La lectura exacta usa el ledger; no consulta `dataset_version` ni llama al
  explorador de candidatos.
- La vista histórica conserva estado, actor, tiempo y enlaces a los dos
  movimientos, además de `sin efecto financiero` y la advertencia de que no
  prueba saldos.
- No se agregó migración, dependencia, caché, permiso ni fuente de verdad.

## Evidencia

| Verificación | Resultado |
|---|---|
| API unitaria en imagen | 153 pruebas, OK |
| PostgreSQL/HTTP focal | 1 escenario integral, OK |
| Caso de inelegibilidad | candidatos 403; expediente exacto 200; cross-company 403; ID inválido 422 |
| Web unitaria | 213 pruebas en 34 ficheros, OK |
| TypeScript, ESLint y build Next | OK |
| Runtime desechable | 28/28 Chromium + 17/17 Axe, OK; cleanup verificado |
| Demo persistente | el expediente histórico que antes fallaba abre y muestra su decisión exacta |
| Work graph y quality gate por incremento | OK |

Comandos principales:

```text
docker run --rm fincilia-api-rec006-check python -m unittest discover -s /app/tests -t /app/tests -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
.\infra\local\test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

El escenario PostgreSQL cambia temporalmente la completitud del dataset a
`mismatch`, comprueba que la generación de candidatos quede bloqueada y que la
lectura histórica permanezca disponible, y restaura `verified` en `finally`.
La primera versión de la prueba omitió el contexto RLS del migrador y afectó
cero filas; ahora fija `fincilia.company_id` y exige `rowcount == 1` en ambos
sentidos.

## Revisión pendiente y rollback

Security debe revisar neutralidad y RLS; Backend/Architecture, la lectura exacta
sin elegibilidad; Product y Accessibility/QA, lenguaje y navegación histórica.
`FOUNDER-01` y el implementador no cuentan como revisores independientes.

ADR-027 y S1-READY permanecen sin promover. El rollback funcional revierte
`fdd0864`; no hay esquema ni datos que revertir. Quedan liberadas todas las
rutas de FNC-REC-006.
