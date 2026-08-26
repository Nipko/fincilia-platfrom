---
task_id: FNC-REC-005
status: REVIEW_PENDING
base_sha: a4403d64c270b900c80a0def87e39a90e6d2bba9
reservation_sha: b05798ed22caf219c6f6da31961b212cfe07199e
persistence_sha: a42645d707859983b5a35c374cc4221c16419847
web_sha: d97c540edbffe86128e470811b7cfe76fd69d551
tested_head_sha: d97c540edbffe86128e470811b7cfe76fd69d551
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-REC-005 — propuestas agrupadas 1:N y N:1

## Resultado

La estación de conciliación permite crear y volver a consultar borradores
manuales 1:N y N:1 con un movimiento ancla y entre 2 y 49 movimientos completos
del dataset opuesto. La interfaz presenta suma y diferencia exactas por moneda,
incluido el signo negativo, como ayuda de revisión.

El alcance termina en `draft`: no existen asignaciones parciales, tolerancias,
FX, decisión, reserva de miembros, efecto financiero, auto-match ni habilitación
de cierre. ADR-028 permanece `Proposed` y bloqueada para revisión humana.

## Persistencia y fronteras

V0035 crea `match_group_candidate` y `match_group_command_receipt` con
`company_id` no nulo, RLS forzada, escrituras append-only y privilegios mínimos.
Su SHA-256 integrado es
`ffd057e1e29089a2d41a13a5d55914cd736405e67bcb8c7cae8363a746bdbdea`.

El trigger de base vuelve a comprobar orden canónico, unicidad y cardinalidad;
empresa, cuenta, moneda y dirección; datasets distintos y elegibles; completitud,
linaje y auditoría permitida. El runtime no puede actualizar ni borrar borradores.

- Crear exige `movement.read` y `match.propose`; la empresa se resuelve en el
  servidor y toda búsqueda se ejecuta bajo contexto RLS.
- La composición es única por empresa, versión de regla, ancla y conjunto.
- Una misma clave y payload reproduce; reutilizarla con otro payload conflictúa.
- Carreras sobre la misma composición convergen en una sola fila.
- Auditoría, recibo y borrador se confirman atómicamente y no copian valores
  financieros, referencias ni descripciones.
- Los movimientos canónicos y el ledger 1:1 quedan sin cambios.

## API y experiencia web

`GET` y `POST /api/v1/companies/{company_id}/reconciliation/group-proposals`
exponen únicamente datos company-scoped. Los valores `numeric(38,12)` salen como
cadenas decimales fijas, nunca `float`.

La web ofrece dos compositores explícitos, 1:N y N:1, exige al menos dos
relacionados, limita a 49, muestra el conteo seleccionado y repite las
restricciones en lenguaje visible. El historial enlaza cada movimiento a su
evidencia y no presenta botones de confirmar o cerrar.

La prueba manual en `127.0.0.1` inició sesión como `ana@demo.local`, seleccionó
dos movimientos sintéticos y conservó un borrador 1:N con comparación exacta
`100 COP - 350 COP = -250 COP`. La pantalla mostró también el borrador N:1
balanceado y mantuvo ambos como `sin confirmar`.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| Migration readiness | 64 pruebas, OK |
| API unitaria completa | 151 pruebas, OK |
| PostgreSQL/HTTP focal | 2 pruebas, OK; RLS, append-only, replay, conflicto, auditoría y concurrencia |
| Web unitaria completa | 210 pruebas en 34 ficheros, OK |
| TypeScript, ESLint y build Next | OK |
| Navegador local real | creación y consulta 1:N/N:1, OK |
| Runtime desechable V0001-V0035 | 28/28 Chromium + 17/17 Axe, OK; cleanup verificado |
| Quality gate por incremento | OK, sin hallazgos |
| Migración persistente local | V0035 aplicada; replay sin mutación |

Comandos principales:

```text
python -m tools.migration_readiness.test_validate
python -m unittest apps.api.tests.test_reconciliation -v
python -m unittest db.tests.test_reconciliation_group_proposals -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npx --prefix apps/web playwright test tests/e2e/reconciliation.spec.ts --project=chromium
npx --prefix apps/web playwright test tests/e2e/reconciliation-review.a11y.spec.ts --project=accessibility
.\infra\local\test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.adr_readiness.validate
python -m tools.quality_gate.cli
```

## Hallazgos y revisión pendiente

1. En la demo persistente, el filtro histórico de FNC-REC-003 puede priorizar
   un expediente antiguo cuyo dataset ya no aparece en la lista elegible. El
   enlace conserva los IDs, pero la estación lo presenta como comparación no
   disponible. El runtime desechable actual pasa; Product y Architecture deben
   decidir una vista histórica dedicada que no reactive datasets inelegibles.
2. El wrapper PowerShell `fincilia-local.ps1 up` trata una línea informativa de
   progreso de Docker en stderr como error bajo `ErrorActionPreference=Stop`.
   El script WSL subyacente levantó el mismo stack correctamente. Platform debe
   endurecer el wrapper sin silenciar errores reales.
3. Accounting debe confirmar que «diferencia» no implica conciliación ni
   reparto. Security/Database deben revisar el trigger, RLS e idempotencia;
   Architecture/Product, el límite deliberado sin N:M ni asignaciones.
4. `FOUNDER-01` y el implementador no cuentan como revisores independientes.

S1-READY y ADR-028 no cambian de estado. Esta entrega no habilita datos reales,
IA, conectores, decisiones agrupadas, cierre ni certificación financiera.

## Rollback y rutas liberadas

El rollback funcional revierte, en orden, `d97c540` y `a42645d`. V0035 es
forward-only: sus borradores append-only se conservan y cualquier ajuste de
esquema se entrega en una migración posterior; no se edita V0035 ni se borran
filas para limpiar la demo.

Quedan liberadas las rutas de ADR-028, readiness ADR, V0035, pruebas DB,
módulo/rutas/pruebas API, cliente/acciones/página/estilos/pruebas web, ficha,
handoff, backlog, fase vigente, trazabilidad y grafo de FNC-REC-005.
