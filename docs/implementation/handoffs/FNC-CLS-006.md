---
task_id: FNC-CLS-006
status: REVIEW_PENDING
base_sha: b2a7603
contract_sha: c633d64
tested_head_sha: pending_integration_commit
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Database, Security, Architecture, QA]
---

# Handoff FNC-CLS-006 — cierre y reapertura contable

## Resultado

Fincilia puede cerrar un periodo desde el último expediente
`evidence_reviewed`, conservar una instantánea digest-only de la evidencia y
bloquear en PostgreSQL nuevas escrituras financieras que intersecten el
intervalo. Una reapertura requiere solicitud motivada y decisión de otra
persona; no modifica ni elimina el cierre original.

El cierre cambia únicamente el estado operativo del periodo. No crea asientos,
no calcula dinero y declara `certifies_financial_statements=false`.

## Persistencia y controles

V0046 crea cuatro ledgers company-scoped con RLS forzada y escritura
append-only: cierre, solicitud de reapertura, decisión de reapertura y recibos
idempotentes. `PUBLIC` y el worker no reciben privilegios. La aplicación solo
puede insertar y leer; no puede actualizar ni borrar historia.

- El cierre exige el expediente más reciente, decisión positiva, misma huella
  vigente y el revisor asignado como actor.
- Los 16 controles, fuentes y statements del snapshot se validan otra vez en
  PostgreSQL; una fuente no publicada, incompleta o sin linaje falla cerrada.
- Un lock por empresa serializa cierre, reapertura y escrituras protegidas.
- Se bloquean movimientos, saldos, statements, cambios de expectativa y
  decisiones de conciliación que intersecten un cierre activo.
- Reabrir requiere motivo y fundamento acotados. El solicitante no puede
  decidir su propia solicitud, incluso si posee ambos permisos.
- Repetir la misma clave idempotente devuelve el resultado existente; cambiar
  el comando con esa clave produce conflicto.
- Auditoría y snapshot contienen identificadores, estados, versiones y digests,
  nunca importes ni valores de las fuentes.

## API y web

Se añadieron endpoints para listar periodos, cerrar, solicitar reapertura y
decidirla, junto con `close.reopen.request` y `close.reopen.approve`. La sala de
preparación muestra estado, versión, huellas y acciones según actor. El mismo
revisor que registró `evidence_reviewed` materializa el cierre; una persona
distinta decide la reapertura.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| Migración sobre PostgreSQL 17 persistente | V0046 aplicada; stack healthy |
| Recorrido PostgreSQL y MinIO | preparar → revisar → cerrar → bloquear → reabrir, OK |
| Aislamiento/ACL focal | 19 pruebas, OK |
| Contrato de cierre | 4 pruebas, OK |
| Contratos de permisos | 34 pruebas, OK |
| API unitaria completa | 186 pruebas, OK |
| Web unitaria completa | 269 pruebas en 48 ficheros, OK |
| ESLint y TypeScript | OK |
| Build Next de producción | OK durante reconstrucción del stack |

Comandos principales:

```text
sh infra/local/up.sh --empty
docker compose ... run --use-aliases --rm migrate python -m unittest db.tests.test_balance_reconciliation_statements.BalanceReconciliationDatabaseTests.test_api_materializes_assessment_statement_item_and_sod -v
docker compose ... run --rm migrate python -m unittest discover -s /app/tests -t /app/tests -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
```

## Riesgos y decisiones pendientes

1. ADR-035 permanece `proposed`; Accounting y Database deben revisar que el
   periodo contractual se base en `accounting_date` confirmada y el conjunto de
   tablas bloqueadas sea suficiente.
2. La asignación de `accounting_date` sigue siendo humana mediante overlays: no
   se infiere desde `occurred_on`, `posted_on` ni otra fecha.
3. El digest del expediente continúa calculándose en aplicación. El trigger
   compara forma y referencias pero no recalcula SHA-256 por sí mismo; Security
   debe adjudicar si la atestación de runtime requerida cubre este riesgo.
4. Solo se usaron datos sintéticos. S1-READY, DRG-00 y DRG-01 no cambian.

## Rollback

V0046 es forward-only. Un rollback funcional oculta las acciones web/API y
detiene nuevos cierres, pero conserva los ledgers. Revertir la capacidad de
bloqueo requiere una migración posterior explícita; nunca editar V0046 ni
borrar historia ya materializada.
