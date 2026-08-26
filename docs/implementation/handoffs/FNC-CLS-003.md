---
task_id: FNC-CLS-003
status: REVIEW_PENDING
base_sha: 1c58b91
reservation_sha: 21465e2
contract_sha: dd1bf26
domain_sha: 2d47395
database_sha: cf9daa1
api_sha: 715f3a7
api_volume_sha: 28f40e7
web_sha: bda61ec
tested_head_sha: bda61ec
integration_sha: ddf6f19
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Database/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLS-003 — estados reproducibles de conciliacion de saldos

## Resultado entregado

La plataforma ya puede evaluar la completitud de cada fuente y periodo, calcular
un estado reproducible entre saldos de banco y libros, proponer partidas
conciliatorias y someterlas a una decision humana separada. Cada resultado fija
empresa, cuenta, moneda, periodo, versiones de assessments y partidas, release
del motor, version de esquema, reglas y entradas exactas.

La estacion es deliberadamente diagnostica. No acepta excepciones contables ni
materialidad, no genera asientos, no certifica ni ejecuta un cierre y no usa IA.
Los saldos del producto permanecen con linaje `required_pending`; por eso una
operacion real no puede presentarse como conciliada hasta completar ese camino.

## Contrato y semantica financiera

- `completeness_assessment`, `completeness_control_result`,
  `reconciliation_statement` y `reconciling_item` son entidades canonicas con
  ownership, relaciones, versionado y linaje explicitos.
- La evaluacion de completitud materializa todos los controles requeridos. Un
  control ausente o evidencia no verificada produce `unknown`, nunca `verified`.
- La ecuacion usa `Decimal` y dinero `numeric(38,12)` con moneda explicita. Un
  `float` no entra en el contrato.
- Una partida tiene monto positivo y lado explicito. Solo la ultima version
  `confirmed`, con evidencia verificada, linaje completo y aprobador distinto al
  preparador, participa en la ecuacion.
- El statement conserva ambas entradas, diferencia exacta y razon explicable.
  `balanced` exige diferencia exactamente cero y todas las precondiciones; de lo
  contrario queda `review_required`.
- La repeticion exacta es idempotente. Una evaluacion divergente crea nueva
  version; una decision divergente tambien se anexa y nunca edita el pasado.

## Persistencia, RLS y concurrencia

- `V0028__balance_reconciliation_statements.sql` crea las cuatro tablas
  company-scoped con RLS forzada, claves compuestas y privilegios minimos.
- `V0029__balance_reconciliation_audit_guards.sql` agrega validaciones de
  evidencia, SoD y auditoria sin importes, referencias ni contenido sensible.
- `V0030__portable_reconciliation_audit_payload_guard.sql` corrige hacia adelante
  una dependencia no portable de `jsonb_object_length`; V0028/V0029 no se
  reescribieron despues de aplicarse.
- La identidad de statement se serializa con advisory lock transaccional. Esto
  evita que dos evaluaciones concurrentes creen versiones incompatibles sin
  requerir `UPDATE` sobre una tabla append-only.
- Todas las relaciones financieras llevan `company_id` no nulo y fallan cerradas
  ante mezcla de empresa, cuenta, moneda, periodo, fuente o evidencia.
- La instalacion V0001→V0030 se verifico en una base vacia aislada y el replay
  inmediato devolvio todas las migraciones como ya aplicadas, sin mutaciones.
  Los recursos Docker temporales se eliminaron y el entorno persistente quedo
  saludable.

## API, autorizacion y auditoria

La API expone un workspace acotado y cuatro comandos:

- `GET /companies/{company_id}/balance-reconciliation`;
- `POST .../assessments`;
- `POST .../statements`;
- `POST .../statements/{statement_id}/items`;
- `POST .../items/{item_root_id}/decisions`.

La empresa y el alcance se resuelven en servidor. Assessment y statement exigen
`close.prepare`; la decision exige `close.approve`, revalida SoD y no confia en
cuenta, moneda, versiones ni resultados calculados por el cliente. El workspace
publica totales de historico y una marca de truncamiento, manteniendo cada lista
acotada. Los eventos de auditoria contienen identificadores y estados, pero no
montos ni evidencia financiera.

## Experiencia web

La ruta `/empresas/{companyId}/conciliacion-saldos` presenta:

- volumenes de expectativas, evaluaciones, estados y partidas;
- completitud por fuente y periodo con controles faltantes visibles;
- formulario de calculo que selecciona saldos, assessments y partidas por sus
  versiones autorizadas;
- ecuacion y diferencia exactas, fuentes, estados y razones explicables;
- propuesta de partida y decision separada por rol;
- historial de ultimas versiones y aviso cuando la vista esta truncada.

No existe boton de cerrar, certificar, publicar asiento ni aceptar materialidad.
La inspeccion en el navegador integrado comprobo jerarquia, contraste, controles,
estados, ecuaciones y ausencia de desbordes; Playwright y Axe probaron el mismo
recorrido sobre los contenedores finales reconstruidos.

## Evidencia ejecutada

| Verificacion | Resultado |
|---|---|
| Validadores canonico, completitud, linaje, idempotencia y cross-contract | OK |
| API unitaria completa | 137 pruebas, OK |
| Web unitaria completa | 195 pruebas en 31 ficheros, OK |
| TypeScript y ESLint | OK |
| Build Next productivo y build Docker | OK; ruta `/conciliacion-saldos` incluida |
| PostgreSQL/RLS/API/concurrencia focal | 3 pruebas, OK |
| Migracion desde cero y replay | V0001-V0030, OK; checksums previos intactos |
| E2E focal Chromium | 1 prueba, OK |
| Accesibilidad focal Axe | 1 prueba, 0 violaciones |
| Quality gate sobre cada indice Git | OK |
| Stack local final | API, web, PostgreSQL, Valkey y MinIO saludables |

Los comandos reproducibles principales son:

```text
python -m tools.canonical_model.validate
python -m tools.completeness_model.validate
python -m tools.lineage_model.validate
python -m tools.idempotency_model.validate
python -m tools.cross_contract_model.validate
python -m unittest discover -s apps/api/tests
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run build
docker compose -f infra/local/compose.yaml run --rm migrate python -m unittest db.tests.test_balance_reconciliation_statements
npx --prefix apps/web playwright test apps/web/tests/e2e/balance-reconciliation.spec.ts --config apps/web/playwright.config.ts --project=chromium
npx --prefix apps/web playwright test apps/web/tests/e2e/balance-reconciliation.a11y.spec.ts --config apps/web/playwright.config.ts --project=accessibility
```

## Revision humana y limites abiertos

- Accounting debe revisar signos, ecuacion, reglas de elegibilidad y semantica de
  partida confirmada.
- Security y Database/Architecture deben revisar RLS, grants, triggers, advisory
  lock, auditoria y el modelo append-only.
- Product y Accessibility/QA deben revisar lenguaje, jerarquia, seleccion de
  versiones y operacion accesible.

`FOUNDER-01`, el implementador y los usuarios sinteticos no cuentan como
revisores independientes. FNC-CLS-003 no supera S1-READY ni DRG-00/DRG-01.
Continuan fuera de alcance: excepciones aceptadas, materialidad, snapshots,
firma, cierre/reapertura, reporte certificado, IA, movil y datos reales.

## Rollback y recuperacion

La API y la ruta web pueden retirarse sin modificar el ledger. No se ejecutan
down migrations sobre tablas financieras append-only. Una correccion de esquema
se entrega mediante nueva migracion forward-only; un estado ya calculado se
conserva y se reemplaza por una version posterior. La recuperacion ante desastre
restaura PostgreSQL y vuelve a aplicar el ledger de migraciones hasta V0030.

## Rutas liberadas

Contratos y validadores canonicos de conciliacion, V0028-V0030 y pruebas de base,
modulo/rutas/pruebas API, cliente/acciones/ruta/estilos/pruebas web, ficha,
handoff y registros centrales de FNC-CLS-003.
