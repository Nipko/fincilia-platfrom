---
task_id: FNC-QA-008
status: REVIEW_PENDING
base_sha: a6de61b
reservation_sha: 05418cf
regression_sha: 5f43778
accessibility_sha: 8b95642
tested_head_sha: 8b95642
integration_sha: 6377017
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [QA, Security, Web/UX, Accessibility/Product]
---

# Handoff FNC-QA-008 — regresion web persistente y repetible

## Resultado

La regresion completa de la plataforma web pasa de forma repetible sobre el mismo
runtime local persistente usado para pruebas manuales. No se borraron volumenes,
no se reabrieron decisiones append-only y no se relajo la invalidacion de sesiones
por cambios de autorizacion.

La configuracion Playwright usa un worker para los proyectos que comparten el
tenant sintetico. Esto no es una limitacion del producto: la suite prueba
deliberadamente la revocacion real y `authorization_version`; ejecutar a la vez
otro recorrido con la misma identidad hace que su sesion deba caducar. Paralelizar
de nuevo requiere empresas e identidades aisladas por worker, no desactivar ese
control.

## Hallazgos demostrados

1. La primera corrida paralela obtuvo 17/26. Ocho fallos eran sesiones o permisos
   modificados por otra prueba concurrente; la corrida serial dejo 23/26 y aislo
   los tres defectos restantes.
2. Dos recorridos buscaban el enlace historico `Conciliacion`; la navegacion actual
   distingue `Conciliar saldos` de `Cruzar movimientos`. Ambos selectores,
   Chromium y Axe, ahora usan el nombre accesible vigente.
3. El helper encontraba un expediente abierto pero asumía que su candidato seguia
   en la primera pagina. Ahora busca lotes acotados hasta localizar los movimientos
   exactos y calcula la pagina de 25 elementos que la UI debe abrir.
4. REC-002 asumía que la base siempre era virgen. El helper ahora prefiere una
   revision abierta; si el ledger ya es terminal, verifica el historico y que no
   exista segunda decision. Un conflicto de exclusividad abierto se rechaza en vez
   de intentar una confirmacion prohibida.

## Evidencia

| Verificacion | Resultado |
|---|---|
| Focal conciliacion, primera corrida | 4/4, OK |
| Focal conciliacion, repeticion sobre el mismo ledger | 4/4, OK |
| Chromium completo, corrida 1 | 26/26, OK en 36,0 s |
| Chromium completo, corrida 2 | 26/26, OK en 36,1 s |
| Axe completo | 15/15, 0 violaciones, OK |
| TypeScript y ESLint | OK |
| Web unitaria | 195/195 en 31 ficheros, OK |
| Build Next productivo | OK, 23 rutas de producto y shell |
| Quality gate por commit | OK, 0 hallazgos |
| Stack probado | API, web, PostgreSQL, Valkey y MinIO saludables |

Comandos principales:

```text
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run build
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53000 npm --prefix apps/web run test:e2e
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53000 npm --prefix apps/web run test:a11y
python -m tools.work_graph.validate
python -m tools.test_catalog.cli validate
python -m tools.quality_gate.cli
```

## Limites, revision y rollback

No se modificaron API, DB, migraciones, seeds, contratos, permisos, RLS, producto,
mobile ni gates. Todos los datos son sinteticos locales. Las altas E2E conservan
su historial y por eso el portafolio local puede mostrar empresas sinteticas de
corridas anteriores; no se eliminaron para obtener verde.

QA y Security deben revisar que la serializacion representa correctamente la
frontera compartida de autorizacion. Web/UX y Accessibility/Product deben revisar
los nombres accesibles y las ramas abierta, conflictiva y terminal del expediente.
`FOUNDER-01` y el implementador no cuentan como revisores independientes.

Revertir `8b95642` y `5f43778` devuelve los selectores, helper y configuracion
anteriores sin tocar datos. No usar `down --volumes` ni borrar ledgers como
rollback. S1-READY conserva 39/40 y sigue bloqueado solo por revision humana
independiente.

## Rutas liberadas

`apps/web/playwright.config.ts`, helpers y specs E2E, ficha, handoff y registros
centrales de FNC-QA-008.
