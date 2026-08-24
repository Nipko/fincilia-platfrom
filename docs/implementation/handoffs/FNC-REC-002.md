---
task_id: FNC-REC-002
status: REVIEW_PENDING
base_sha: 1c9cbf5336b5c04a3672d7eb9e2200f48143c3db
reservation_sha: dce6965
tested_head_sha: 01f0266
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Accounting, Security, Database, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-REC-002 — revisión humana sin efecto financiero

## Resultado

Un preparador puede materializar un par exacto del explorador como propuesta y
un revisor diferente puede confirmarlo o rechazarlo. Propuesta, decisión,
evidencia, auditoría y recibo idempotente quedan en un ledger company-scoped y
append-only. La API vuelve a comprobar la elegibilidad y la base vuelve a
comprobar tenancy y segregación de funciones.

Confirmar es sólo un juicio humano registrado: la respuesta declara
`financial_effect: none` y `proves_balance_reconciliation: false`; ningún estado,
importe, saldo, cierre o reporte certificado cambia.

## Cambios

- ADR-027 permanece `Proposed` y describe límites, rollout sintético y rollback.
- V0017 agrega `match_candidate`, `match_decision` y `match_command_receipt` con
  RLS forzada, privilegios mínimos, referencias company-scoped, triggers
  append-only/SoD y evidencia ligada a `audit_event`.
- La API agrega listar, proponer y decidir, con revalidación server-side,
  advisory locks transaccionales, vocabulario cerrado, replay y conflictos
  estables. Una denegación se audita en una transacción que sí confirma antes de
  devolver el problema HTTP.
- La web usa exclusivamente permisos devueltos por la API para ofrecer acciones;
  no reconstruye autorización ni SoD. El token permanece server-side y cada
  formulario porta una clave idempotente distinta.
- La estación muestra estados abierto/confirmado/rechazado, actor, instante UTC,
  motivo y advertencias permanentes de no efecto financiero.

## Evidencia por aceptación

| Criterios | Evidencia |
|---|---|
| AC-01..AC-04 | PostgreSQL: revalidación, permisos, replay, conflicto de payload, dos propuestas concurrentes convergentes y SoD de preparador/owner/revisor |
| AC-05..AC-07 | V0017 + pruebas directas: RLS forzada, runtime sin UPDATE/DELETE, triggers append-only/SoD, auditoría permitida en la misma transacción y denegación durable |
| AC-08..AC-10 | API/web: historial por par, tres estados, motivos cerrados, scope neutral, degradación fail-closed y mensajes que no afirman conciliación |
| AC-11 | 2 recorridos contra PostgreSQL 17 + MinIO: cross-company, concurrencia, idempotencia, auditoría y estados de seis movimientos idénticos antes/después |
| AC-12 | 79 API unitarias; 100 web unitarias; tipos, lint y build; 3 E2E Chromium; 1 Axe; quality gate; inspección visual y consola limpia |

## Verificaciones ejecutadas

| Comando/carril | Resultado |
|---|---|
| migración limpia V0001→V0017 | `ok: true`, 17 aplicadas, checksum V0017 `38dee48…` |
| replay de migración | `mutated: false`, head V0017 |
| `db.tests.test_reconciliation_decisions` | 2, OK, PostgreSQL/MinIO reales |
| `unittest discover -s tests` dentro de imagen API | 79, OK |
| Vitest web completo | 100 en 16 archivos, OK |
| TypeScript, ESLint y Next production build | OK; ruta dinámica `/conciliacion` incluida |
| Playwright Chromium focal | 3, OK; propuesta abierta confirmada por Beto |
| Axe focal | 1, 0 violaciones |
| navegador integrado | estados confirmado/rechazado visibles; 0 warnings/errores de consola tras corregir hidratación |
| quality gate sobre cada índice Git | `ok: true`, 0 findings |

El laboratorio `fincilia-rec002` usa volúmenes y puertos alternos
(`53100/58180/59100/59101`). Se borró y regeneró exclusivamente su almacenamiento
sintético al detectar que dos nombres Compose habían montado el mismo volumen;
`fincilia_local_pgdata` nunca se borró ni se modificó por esa limpieza.

## Hallazgos de ejecución

1. Dos proyectos Compose con guion/guion bajo compartieron el volumen temporal y
   dañaron su checkpoint. Se comprobó la etiqueta, se borraron sólo los dos
   volúmenes `fincilia_rec002_*` regenerables y se reconstruyó con un único nombre.
2. Una aserción comparaba seis movimientos iniciales con sólo cuatro finales;
   falló correctamente y se corrigió la prueba para contrastar el mismo conjunto.
3. El navegador detectó React #418: `toLocaleString()` generaba texto distinto en
   SSR y cliente. El instante ahora usa formato UTC determinista y una pestaña
   limpia confirmó cero errores de consola.
4. El `npm` global de Windows apunta a un módulo inexistente. Las verificaciones
   usaron los binarios fijados en `apps/web/node_modules/.bin`; no se instalaron ni
   cambiaron dependencias.

## Riesgos y pendientes humanos

- Accounting debe revisar que confirmar siga siendo sólo evidencia de revisión y
  aceptar el vocabulario de motivos; no existe asignación N:M, reversal ni efecto.
- Security/Database deben revisar RLS, triggers, funciones/privilegios y el ledger
  idempotente. Backend/Architecture debe revisar locks y códigos de problema.
- Accessibility/QA debe revisar la jerarquía y lenguaje además del Axe automatizado.
- ADR-027 sigue `Proposed`; S1-READY sigue `not_met`. DRG-00/DRG-01, ADR-002,
  ADR-024, DB-G03, S-01/TM-005 y demás decisiones humanas no se movieron.
- El entorno principal de usuario sigue en V0016 porque conserva un checksum
  histórico local divergente. No se borró; la demostración V0017 vive en el
  laboratorio alterno hasta que el usuario autorice recrear el volumen principal.

## Commits y rollback

1. `dce6965` — ficha y reserva.
2. `c78c578` — ADR-027 y V0017.
3. `560d44e` — API y pruebas PostgreSQL.
4. `62a8c23` — experiencia web y unitarias.
5. `01f0266` — E2E, Axe y corrección de hidratación.

Revertir 5 retira sólo aceptación/corrección visual; 4 retira los controles web;
3 retira endpoints; 2 retira la migración del código. La migración aplicada es
forward-only: sus filas de auditoría se conservan y nunca se purgan selectivamente.
