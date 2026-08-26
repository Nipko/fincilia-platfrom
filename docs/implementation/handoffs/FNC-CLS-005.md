---
task_id: FNC-CLS-005
status: REVIEW_PENDING
base_sha: 90997d4
reservation_sha: b77738b
persistence_sha: 7348c44
web_sha: d2dada9
tested_head_sha: 05abf8f
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLS-005 — expediente de revision previa al cierre

## Resultado

La preparacion de cierre puede fijarse ahora como un expediente inmutable por
empresa y periodo. El preparador asigna un revisor elegible y persiste una
manifestacion canonica digest-only del diagnostico observado. La persona
asignada puede registrar una unica decision append-only: `evidence_reviewed` o
`changes_requested`.

El expediente es evidencia de revision humana, no una operacion contable. Todas
las respuestas y la interfaz declaran `financial_effect=none`,
`certifies_close=false` y `can_execute_close=false`. No se creo snapshot, firma,
certificacion, excepcion de materialidad, cambio de ciclo ni accion de cierre.

## Persistencia, autorizacion y consistencia

V0034 crea `close_review_packet`, `close_review_decision` y
`close_review_command_receipt` con `company_id` no nulo, RLS forzada y triggers
append-only. El runtime de aplicacion solo recibe `SELECT`/`INSERT`; worker y
`PUBLIC` no reciben privilegios y no existe `UPDATE`/`DELETE` productivo. Su
SHA-256 integrado es
`de11a4f2d920062c0f6b1e8dcb9530efb3e5608d741fa377e2782acf44a3be6a`.

- Preparar requiere `close.prepare`; revisar requiere `close.approve`.
- El revisor se resuelve online entre miembros activos y elegibles de la empresa.
- Preparador y revisor deben ser sujetos diferentes aunque una persona posea
  ambos permisos. PostgreSQL repite esta comprobacion y niega la auto-revision.
- Solo el revisor asignado puede decidir y una segunda decision se rechaza.
- Antes de decidir, la API reconstruye la manifestacion company-scoped y compara
  su SHA-256. Un cambio de evidencia exige un expediente nuevo.
- `evidence_reviewed` solo se admite si la evidencia fijada continua
  `ready_for_review`; un expediente bloqueado solo admite cambios solicitados.
- Claves idempotentes conservan replay estable, detectan cambio de payload y
  tienen un unico ganador bajo concurrencia.
- La auditoria registra accion, sujeto, recurso y resultado, pero nunca copia la
  manifestacion ni contenido financiero.

La manifestacion contiene estados, conteos, IDs, versiones y digests. No incluye
importes, monedas, nombres provenientes de documentos ni valores de celdas.

## API y experiencia web

Se incorporaron superficies company-scoped para listar revisores, listar y
crear expedientes y registrar la decision asignada. La sala
`/preparacion-cierre` muestra, por periodo, la version y huella de la evidencia,
su preparador/revisor, estado de revision y controles permitidos segun el actor.

La UI excluye al actor actual de la asignacion, impide que otra persona decida y
no presenta ningun boton o endpoint de cierre. Cada region de periodo tiene un
nombre accesible unico; esta correccion surgio de Axe al detectar landmarks
duplicados en una pagina con doce periodos.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| PostgreSQL/RLS focal | 6 pruebas, OK |
| API focal | 8 pruebas, OK |
| API unitaria completa | 149 pruebas, OK |
| Web unitaria completa | 208 pruebas en 34 ficheros, OK |
| TypeScript, ESLint y build Next | OK |
| Chromium focal | 1/1, OK |
| Axe focal | 1/1, 0 violaciones, OK |
| Runtime aislado V0001-V0034 | 27/27 Chromium + 16/16 Axe, OK; cleanup verificado |
| Work graph y quality gate por incremento | OK, sin hallazgos |
| Migracion persistente local | V0034 aplicada; checksum verificado e inmutable |

Comandos principales:

```text
python -m unittest apps.api.tests.test_close_review -v
python -m unittest db.tests.test_close_review_packets -v
python -m unittest discover -s apps/api/tests
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npx --prefix apps/web playwright test tests/e2e/close-review.spec.ts --project=chromium
npx --prefix apps/web playwright test tests/e2e/close-review.a11y.spec.ts --project=chromium
.\infra\local\test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La suite DB completa se ejecuto adicionalmente sobre la demo persistente ya
mutada por corridas anteriores: 358 pruebas, 350 pass, 1 skip, 4 failures y 3
errors. Es un diagnostico no autoritativo: los siete casos son contaminacion o
drift previo fuera de FNC-CLS-005 (FK de fixtures persistentes, aserciones que
encuentran el nombre sintetico del actor, ACL contractual de una funcion V0033
y perfil reutilizado por la prueba de fecha ambigua). Ninguno referencia V0034,
las tablas del expediente o `close_review.py`. La suite focal en PostgreSQL real
y el runtime desechable construido desde V0001 hasta V0034 si quedaron verdes.

## Riesgos y revision pendiente

1. PostgreSQL valida forma y scope de la manifestacion, pero no recalcula por si
   mismo el SHA-256 al insertar. La aplicacion lo calcula al crear y al decidir;
   antes de produccion debe evaluarse digest en base o atestacion firmada contra
   un runtime comprometido.
2. El expediente conserva IDs y digests, pero algunas entidades fuente podrian
   borrarse por retencion. Legal/Privacy debe definir la ventana que preserve la
   verificabilidad antes de usar datos reales.
3. La elegibilidad SQL enumera los roles actuales con `close.approve`; Security
   debe mantenerla sincronizada con el contrato de permisos si este cambia.
4. La lista de expedientes tiene limite inicial de cien versiones; una historia
   mayor requerira paginacion estable.
5. Accounting, Security, Database, Backend/Architecture, Product y
   Accessibility/QA deben revisar de forma independiente. `FOUNDER-01` y el
   implementador no cuentan como revisores independientes.

S1-READY permanece 39/40. Este handoff no acepta gates ni habilita cierre o
datos reales.

## Rollback y rutas liberadas

El rollback funcional revierte, en orden, `05abf8f`, `d2dada9` y `7348c44`.
V0034 es forward-only: sus ledgers append-only se conservan y cualquier cambio
de esquema posterior debe ser V0035 o superior. No se deben editar ni borrar
filas historicas para presentar una demo limpia.

Quedan liberadas las rutas de V0034, pruebas DB, modulo/rutas/pruebas API,
cliente/agregador/acciones/pagina/estilos/pruebas web, ficha, handoff, backlog,
fase vigente y grafo de FNC-CLS-005.
