---
task_id: FNC-REC-001
status: REVIEW_PENDING
base_sha: 03c1524ed0f18765b687767fec4ca8059cba081e
reservation_sha: 67b3886
tested_head_sha: d571607055d39851a19cfbd14616774076a08f49
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-REC-001 — explorador de candidatos de conciliación

## Resultado

Fincilia puede cotejar dos datasets autorizados de una empresa y presentar una
página estable de hipótesis deterministas. El motor exige importe decimal y
moneda exactos, direcciones opuestas, cuentas distintas, linaje completo y una
ventana explícita de 0 a 31 días. La referencia normalizada sólo explica y
ordena; nunca incluye, excluye o confirma por sí sola.

La superficie es read-only: no existe tabla de candidato, decisión, score,
tolerancia, auto-match, merge ni cierre. La respuesta declara
`candidate_only` y `proves_balance_reconciliation: false`. La web repite el
límite, muestra los dos movimientos lado a lado y enlaza cada uno a su linaje.

Todo dato ejecutado fue sintético local. No se tocaron migraciones, seed,
permisos, RLS, worker, móvil, contratos compartidos, IA, dependencias ni gates.

## Cambios

- `apps/api/src/fincilia_api/reconciliation.py`: consulta acotada en PostgreSQL,
  elegibilidad neutral, orden determinista y serialización decimal fija.
- `apps/api/src/fincilia_api/routes.py`: endpoint company-scoped con
  `movement.read` y guarda explícita de techo sintético.
- `apps/web/src/app/empresas/[companyId]/conciliacion`: estación visual,
  selectores, estados de error/vacío, paginación y drill-down de ambos lados.
- `apps/web/src/lib`: contrato tipado de la respuesta y contexto URL validado.
- `apps/api/tests`, `db/tests` y `apps/web/tests`: reglas puras, RLS/PostgreSQL,
  pantalla, E2E y Axe.

## Matriz de aceptación

| Criterio | Evidencia |
|---|---|
| AC-01, AC-09, AC-13 | PostgreSQL: cross-company 403 neutral; misma versión/ventana inválida 422; módulo: dataset ausente o inelegible usa un único código |
| AC-02..AC-04 | PostgreSQL: exactitud, dirección, ventana, moneda distinta y referencia distinta; dinero sale como string de 12 decimales |
| AC-05 | PostgreSQL y unitaria conservan dos pares con el mismo movimiento izquierdo |
| AC-06..AC-07 | SQL ordena por referencia, distancia, ordinales e IDs; solicita `limit + 1`, máximo 200 y offset máximo 10.000 |
| AC-08 | API y pantalla prueban `candidate_only`, reglas, truncamiento y no conciliación de saldos |
| AC-10..AC-12 | 93 unitarias web y verificación visible: contexto en URL, 3 tarjetas, 6 links de evidencia y 0 botones de decisión |
| AC-14 | PostgreSQL real muerde importe, moneda, dirección, fecha, completitud, cross-company y referencia; unitarias muerden linaje/estado y límites |
| AC-15 | build, tipos, lint, API, PostgreSQL, E2E, Axe y validadores listados abajo |

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| API dentro de imagen fijada | **76**, OK |
| PostgreSQL + MinIO + RLS, caso FNC-REC-001 | **1 recorrido / 20+ aserciones**, OK |
| Web TypeScript + Next production build | OK, ruta `/conciliacion` incluida |
| Web unitarias | **93** en 16 archivos, OK |
| Web ESLint | OK |
| Playwright Chromium | **11**, OK |
| Playwright/Axe | **5**, 0 hallazgos serios o críticos |
| Navegador de la app | 3 tarjetas, 6 enlaces de evidencia, 0 controles prohibidos, 0 errores de consola |
| `npm audit` ejecutado al restaurar lockfile | 0 vulnerabilidades |
| work graph | `ok: true`, 69 tareas, 0 reservas tras el cierre |
| test catalog | `model_valid: true`, 0 blockers; 13 planned y 41 contractuales no implementados |
| golden harness | **14** casos, `ok: true` |
| mutation harness | **68** mutaciones / 9 validadores, `ok: true` |
| quality gate sobre índice Git | `ok: true`, 0 findings |

La fixture visible retenida en el stack local usa exclusivamente valores
sintéticos y approvals marcadas `SYNTHETIC-TEST-FIXTURE`. Los datasets visibles
son `71139610-4b4b-4ccd-9251-35817f0ccfd4` y
`0117b377-427b-4a15-b6a5-62fcc1a1d5d9`; producen tres candidatos y permanecen
abiertos en la pestaña entregada al usuario.

## Hallazgos de ejecución

1. El orden correcto coloca primero las dos coincidencias de referencia antes
   del par con referencia distinta. Una expectativa inicial asumía orden por
   importe y falló; se corrigió la prueba, no el contrato.
2. Una prueba preexistente buscaba `dataset.map` en toda la página de Beto y
   confundía eventos visibles de auditoría con permisos. Se acotó la aserción al
   panel server-authoritative de roles/permisos.
3. El stack no está vacío: conserva datasets sintéticos de aceptación y
   rendimiento. Los E2E ya no asumen una base vacía y distinguen selección
   pendiente, scope inelegible y cero candidatos.
4. `pnpm` no era el gestor del árbol local y movió paquetes generados. Se retiró
   su store y `npm ci --ignore-scripts` restauró exactamente el lockfile; ningún
   manifiesto ni lock cambió.

## Riesgos y límites

- La consulta usa índices existentes por dataset, pero aún no existe evidencia
  `EXPLAIN ANALYZE` sobre dos datasets grandes de cuentas distintas. Antes de
  afirmar capacidad sostenida debe abrirse un spike de performance; cualquier
  índice nuevo requeriría tarea de migración y revisión DB.
- La estación ofrece las últimas 50 versiones porque ése es el límite del API
  de datasets. Buscar historia más antigua requiere paginar ese contrato en una
  tarea aparte.
- Se permiten excepciones de completitud ya aceptadas porque el contrato de
  dominio lo autoriza; esta tarea no crea ni acepta esas excepciones.
- No existe decisión persistente. Confirmar/rechazar candidatos es una rebanada
  posterior con revisión Accounting/Security, SoD, auditoría e idempotencia.
- CI remota sobre el commit final y las revisiones independientes siguen
  pendientes; el implementador no se autoaprueba.

## Gates y decisiones no movidos

S1-READY continúa `not_met`; DRG-00/DRG-01, ADR-002, ADR-024, DB-G03,
S-01/TM-005, owners humanos y decisiones abiertas mantienen su estado. Esta
entrega no autoriza datos reales, piloto, auto-match, cierre ni IA.

## Commits y rollback

1. `67b3886` — ficha, backlog y reserva.
2. `bb1771e` — motor y endpoint read-only.
3. `da92f37` — recorrido PostgreSQL/RLS inicial.
4. `6386886` — estación web y pruebas de pantalla.
5. `0762fab` — E2E, Axe y corrección de aserción de permisos.
6. `d571607` — negativos PostgreSQL de moneda e incompletitud.

Revertir 6 y 3 retira sólo pruebas. Revertir 5 retira sólo aceptación web.
Revertir 4 y 2 elimina la pantalla y el endpoint sin tocar datos o esquema. La
fixture sintética retenida puede permanecer como evidencia inerte; retirarla
requiere ejecutar el purge acotado del harness, nunca borrar volúmenes.

## Revisión independiente pendiente

- Accounting: reglas candidatas, muchos-a-muchos y lenguaje de no conciliación.
- Security: neutralidad cross-company, permiso y ausencia de valores en logs.
- Backend/Architecture/DB: plan SQL, límites y spike de performance requerido.
- Accessibility/QA/Product: jerarquía visual, estados, paginación y enlaces de
  evidencia.
