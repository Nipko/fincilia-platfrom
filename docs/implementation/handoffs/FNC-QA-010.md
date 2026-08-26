---
task_id: FNC-QA-010
status: REVIEW_PENDING
base_sha: 6937f6e
reservation_sha: c19393f
database_isolation_sha: 8536c16
dependabot_sha: 55fbeaf
tenancy_fixture_sha: d9da96f
workflow_reservation_sha: 26c37d5
workflow_fix_sha: 4bf10cc
ci_tested_sha: 4bf10cc
ci_run: https://github.com/Nipko/fincilia-platfrom/actions/runs/32952885021
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [QA, Database, Security, Platform]
---

# Handoff FNC-QA-010 — estabilizacion de `main`

## Resultado

El workflow `fincilia-ci` de `main` queda verde sin retirar pruebas ni relajar
RLS, auditoria, inmutabilidad o SoD. Las suites PostgreSQL eliminan solamente sus
propias fixtures, el inventario de funciones sigue los renames de migraciones y
el navegador prepara su estado sintetico despues de la suite de base en vez de
consumir residuos accidentales.

Dependabot conserva monitores ejecutables para npm, pip y GitHub Actions. Se
retiraron cuatro entradas Docker que apuntaban a directorios con Compose pero
sin Dockerfile y que GitHub terminaba como `dependency_file_not_found`. La falta
de un monitor nativo para cinco alcances Compose queda declarada como gap; no se
presenta como cobertura. Trece PR automaticas basadas en revisiones antiguas se
cerraron sin fusionar dependencias y no queda ninguna PR abierta.

## Defectos demostrados y corregidos

1. `ApiAuthorizationTests` dejaba artifacts, capabilities y processing runs que
   impedían operaciones posteriores por FK. Ahora registra y retira solo lo que
   crea, en orden referencial.
2. `IssuedAuthorizationContextTests` borraba contextos de empresas completas,
   incluidos los de otras suites. Ahora posee una lista exacta de fixtures.
3. Dos pruebas de privacidad confundian el nombre legitimo del actor con PII en
   el payload. La comprobacion se limita a `audit_event.detail` y conserva la
   identidad auditable del actor.
4. El extractor ACL ignoraba `ALTER FUNCTION ... RENAME TO`; ahora procesa
   `CREATE`, `CREATE OR REPLACE` y renames en orden.
5. La prueba de transferencia mutaba `firm_id` en un engagement historico ya
   referenciado. Ahora revoca el engagement anterior, crea uno nuevo y conserva
   la historia inmutable.
6. Los E2E de cierre dependian de periodos dejados por otras pruebas. CI ejecuta
   `/checks/e2e_fixture.py` despues de las 358 pruebas PostgreSQL y antes del
   navegador. El contrato `LOCAL-CI-E2E-FIXTURE` falla ante omision o reorden.
7. Los monitores Docker ficticios hacian ruido rojo sin vigilar Compose. El
   modelo los rechaza con `SUP-UPDATE-MONITOR-INVALID` y reporta el gap real.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| `fincilia-ci` sobre `4bf10cc` | 5 jobs obligatorios `success`; performance omitida por diseño |
| Suite PostgreSQL real | 358 pruebas, OK; 260,8 s |
| Fixture de aceptacion | `ok: true`, datos `synthetic_only`, 1 periodo materializado |
| API dentro de imagen | 149 pruebas, OK |
| Worker con PostgreSQL y object storage | 18 pruebas, OK |
| Chromium | 27/27, OK |
| WCAG 2.2 AA automatizado | 16/16 Axe, OK |
| Repositorio local | 1219 pruebas, OK |
| Web local | lint y typecheck OK; 208/208 unitarias |
| Supply chain | 77/77 pruebas, OK; discovery estable |
| Contrato de lifecycle | 39/39 pruebas, OK; validador `ok: true` |
| Grafo y quality gate | validos; indice sin hallazgos |
| PR automaticas | 13 cerradas, 0 fusionadas, 0 abiertas |

`python -m tools.supply_chain.cli validate` conserva exit 1 intencional: cuatro
gaps altos de procedencia/SBOM/firma y cinco gaps medios de monitoreo Compose no
estan resueltos. Ocultarlos para obtener verde seria una regresion del modelo;
CI ejecuta discovery y las pruebas del validador, no declara esos riesgos
cerrados.

## Limites, revision y rollback

No se editaron migraciones V0001-V0034, esquema, RLS, permisos productivos,
auditoria, semantica financiera, dependencias de aplicacion, mobile, IA ni gates.
Toda la ejecucion uso datos sinteticos. El cierre de PR es recuperable y ninguna
actualizacion de terceros entro en `main`.

QA debe revisar el aislamiento y el orden E2E, Database la propiedad de fixtures
y el inventario ACL, Security la distincion actor/payload y Platform el alcance
real de Dependabot. El implementador y `FOUNDER-01` no cuentan como revisores
independientes. S1-READY no cambia por esta tarea.

El rollback revierte, en orden, `4bf10cc`, `26c37d5`, `d9da96f`, `55fbeaf`,
`8536c16` y `c19393f`. No requiere rollback de base ni destruccion de volumenes.

## Rutas liberadas

Las cuatro suites DB, workflow, Dependabot, baseline/modelo/herramientas de
supply chain, contrato de lifecycle, ficha, handoff y registros centrales.
