---
task_id: FNC-ING-003
status: REVIEW_PENDING
base_sha: 454da9db893c6974b246cfa94137896c69488b4e
reservation_sha: e5d99fe5cdf2acd10fd1ed0b698b3c82f3382d5c
implementation_shas: [1dab035, 3cdfe10]
tested_head_sha: 3cdfe10654d80637b74c899a2eb7f030ad8dd13a
ci_run: https://github.com/Nipko/fincilia-platfrom/actions/runs/33036975418
ci_status: success
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Data, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-ING-003 — fuente de recepcion y centro documental

## Resultado

Cada carga nueva queda ligada a una fuente de datos activa que el servidor
resuelve dentro de la empresa autorizada. La misma evidencia recibida otra vez
desde la misma fuente es idempotente; recibida desde otra fuente crea una
recepcion logica distinta sin duplicar los bytes del objeto.

El contador dispone de un centro documental direccionable y paginado. Puede
buscar por nombre y filtrar por fuente, zona efectiva y estado de procesamiento,
ver resumenes operativos y abrir el expediente exacto sin recorrer todas las
cargas de la empresa.

## Implementacion y controles

- V0038 sustituye la unicidad historica por `(company_id, data_source_id,
  content_sha256)` para recepciones atribuidas y conserva una guarda separada
  para filas legacy sin fuente. No existe backfill ni inferencia de procedencia.
- La API exige `data_source_id` antes de leer o almacenar el cuerpo, verifica la
  fuente bajo RLS y rechaza fuentes inexistentes, ajenas o inactivas.
- El BFF transmite la fuente elegida a la API. El identificador del cliente no
  concede autoridad y la asociacion persistida no es actualizable por el rol de
  aplicacion.
- El historico usa cursores opacos sobre `(uploaded_at, artifact_id)`, limites
  cerrados y filtros ejecutados en PostgreSQL. Una fuente ajena falla de forma
  neutral y cursores o filtros invalidos devuelven errores estables.
- La respuesta no expone `object_key`, actor, hallazgos sensibles, celdas,
  descripciones, referencias ni valores financieros. Los conteos son solo
  operativos.
- La web preserva filtros al avanzar y retroceder, distingue vacio, acceso
  restringido y error, y enlaza cada fila con su artefacto exacto.
- La tabla desplazable es operable con teclado. La inspeccion real en navegador
  llevo a traducir los estados tecnicos y conservar las mayusculas originales
  de los nombres de archivo.
- No se incorporo IA, dato real, OCR, auto-mapeo, auto-match, cierre ni cambio de
  gate.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Migracion V0038 sobre el stack persistente | Aplicada; replay `head: V0038`, `applied: []`, `mutated: false` |
| PostgreSQL + API + MinIO documental | 28 pruebas, OK |
| PostgreSQL + API, regresion afectada | 98 pruebas; los modulos funcionales pasan |
| Concurrencia con worker detenido | 11 pruebas, OK; 16 cargas simultaneas convergen en una recepcion |
| Web unitaria completa | 35 archivos / 221 pruebas, OK |
| TypeScript, ESLint y build Next | OK |
| Chromium focal | 1/1, OK |
| WCAG automatizado focal | 1/1 Axe, OK |
| Navegador local real | Contenido y navegacion correctos; 0 errores de consola |
| Quality gate por incremento | OK |
| CI integral sobre `3cdfe10` | Todos los jobs aplicables, Chromium y Axe, OK; performance omitida por contrato |

Comandos principales:

```text
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_api_documents
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_upload_concurrency -v
npm --prefix apps/web run test:unit
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e -- tests/e2e/document-history.spec.ts
npm --prefix apps/web run test:a11y -- tests/e2e/document-history.a11y.spec.ts
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La prueba concurrente se ejecuto con el worker persistente detenido para evitar
que consumiera la cola del fixture y se lo restauro inmediatamente despues. El
stack local quedo sano y accesible en `http://127.0.0.1:53000`.

## Revision, limites y despliegue

Data debe revisar la identidad de recepcion y el tratamiento legacy; Security y
Database, RLS, privilegios, indices y concurrencia; Backend/Architecture, el
contrato keyset e idempotencia; Product y Accessibility/QA, lenguaje, filtros y
operacion con teclado. El implementador y `FOUNDER-01` no cuentan como revisores
independientes. Las consultas deben someterse a una prueba de volumen antes de
produccion; este alcance solo demostro correccion funcional con datos sinteticos.

El rollout aplica V0038 antes de API y web. El rollback funcional oculta el
centro y deja de ofrecer nuevas cargas, pero no desasocia recepciones ya creadas
ni borra evidencia. Cualquier correccion de esquema es una nueva migracion hacia
delante; V0038 no se reescribe. S1-READY no cambia. Con este handoff quedan
liberadas todas las rutas reservadas por FNC-ING-003.
