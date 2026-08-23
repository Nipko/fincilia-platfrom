# Handoff — FNC-P2.1: rebanada correctiva de despacho, privilegios y cuarentena

| Campo | Valor |
|---|---|
| Tarea | FNC-P2.1 |
| Estado | **`REVIEW_PENDING`** |
| Base | `47652f1`, rama `claude/principal-dev` |
| Migraciones añadidas | `V0005`, `V0006`, `V0007` |
| Owner | Platform |
| Revisores independientes requeridos | **Security** (dos puntos, abajo), QA |
| Gates | S1-READY sigue `not_met`; DRG-00, DRG-01, DB-G03 y S-01 siguen sin cumplir |

---

## 1. Lo que se corrigió

Seis defectos encontrados en revisión independiente, cada uno con la prueba que lo
fija. Ninguno se podía arreglar editando `V0001`–`V0004`: están aplicadas y su
checksum es inmutable a propósito. Se comprobó que siguen intactos.

### A1 — CI no ejecutaba lo que decía ejecutar

Llevaba roja desde `14f8d6e` por dos motivos que sólo se manifestaban en el
runner:

- las pruebas documentales corrían con **sólo PostgreSQL** arriba y reventaban
  contra el almacén de objetos;
- `docker build -f apps/web/Dockerfile` no resolvía, porque `-f` se resuelve desde
  el `working-directory` del job y en local yo lo invocaba con rutas absolutas.

`tools/local_stack` gana un contrato sobre el propio workflow:
`LOCAL-CI-DEPENDENCIES` (cada suite declara qué servicios necesita y se comprueba
contra el **orden real** de los pasos), `LOCAL-CI-BUILD-CONTEXT` y
`LOCAL-CI-COVERAGE`. Los dos defectos se reproducen ahora en un segundo con
`python -m tools.local_stack.validate`, en vez de en cuatro minutos de runner.

### A2 — El despachador no estaba aislado

`dispatch_pointer.run_id` referenciaba `processing_run`, pero `company_id` era una
columna suelta: nada impedía un puntero con el trabajo de la empresa A y la
empresa B. Ahora la clave ajena es compuesta contra `UNIQUE (run_id, company_id)`,
y lo rechaza el motor.

La API y el worker compartían un rol. Ahora hay tres además del migrador, y la API
**no tiene ningún privilegio** sobre `dispatch_pointer`.

### A3 — Un trabajo podía quedarse invisible para siempre

El worker marcaba `running` y, si moría, `release_stale` liberaba sólo el puntero.
El siguiente worker no lo encontraba en `queued`, borraba el puntero, y el trabajo
quedaba fuera de toda cola y de toda lista. `drop_pointer` y `release_stale` ya no
existen: eran los dos únicos escritores del puntero sin comprobar nada.

### A4 — El rol de la API podía reescribir cualquier contraseña

`ALTER DEFAULT PRIVILEGES` de `V0001` concedía `SELECT, INSERT, UPDATE` sobre toda
tabla creada después. Eso incluía `fincilia.local_credential`, que **no tiene
RLS**. El `GRANT SELECT` de `V0002` no restringía nada: repetía un bit ya puesto.
Con eso, el rol de la API podía sustituir el hash de cualquier sujeto y entrar
como él. Es la clase de privilegio que nadie revisa porque nadie lo escribió.

### A5 — Un PDF llegaba a la zona de evidencia sin que nadie lo mirara

El DFD declara F02 `upload_to_quarantine` (`evidence_quarantine_only`) y F03
`scan_and_promote_to_raw` (control `C-SCAN`, decisión persistida). El esquema los
tenía colapsados. Había incluso una prueba que fijaba el defecto como correcto.

### A6 — Dos subidas simultáneas creaban dos filas o devolvían 500

La comprobación previa «¿ya existe?» pasa cualquier prueba secuencial y falla
exactamente donde importa.

---

## 2. Roles y matriz de privilegios

Cuatro roles. Ninguno es superusuario ni tiene `BYPASSRLS`; `fincilia_dispatch` ni
siquiera inicia sesión.

| Objeto | `fincilia_app` | `fincilia_worker` | `fincilia_dispatch` | `fincilia_migrator` |
|---|---|---|---|---|
| `subject`, `company`, `engagement`, `membership`, `company_grant`, `authorization_version` | SELECT (+ INSERT/UPDATE en los tres últimos) | — | — | owner |
| `local_credential` | **SELECT** | — | — | owner |
| `identity_binding`, `firm` | **—** | — | — | owner |
| `source_artifact` | SELECT, INSERT | SELECT | SELECT | owner |
| `processing_run` | **SELECT** | SELECT | SELECT, INSERT, UPDATE | owner |
| `dispatch_pointer` | **nada** | **nada** | SELECT, INSERT, UPDATE, DELETE | owner |
| `run_attempt`, `dead_letter_item` | SELECT | SELECT | SELECT, INSERT, UPDATE | owner |
| `promotion_decision` | SELECT | SELECT, INSERT | SELECT | owner |
| `audit_event` | SELECT, INSERT | SELECT, INSERT | — | owner |
| `schema_history` | SELECT | SELECT | — | owner |
| `enqueue_processing_run()` | EXECUTE | EXECUTE | owner | EXECUTE |
| `claim_next_run()`, `finish_run()` | — | EXECUTE | owner | — |
| `send_to_dead_letter()` | — | — | owner | — |

Se mantienen a propósito `INSERT`/`UPDATE` de la API sobre `engagement`,
`company_grant` y `authorization_version`: el DFD declara F13
(`engagement_revocation`) como una acción **del producto**, con efecto autoritativo
sobre el estado de autorización. Retirarlos convertiría revocar un acceso en una
intervención manual de operador, que es debilitar `C-REVOKE`, no reforzarlo.

---

## 3. Estados y transiciones de un trabajo

```
                 claim (arriendo + testigo)
  queued  ──────────────────────────────────────►  running
     ▲                                              │
     │  requeue: fallo reintentable y quedan         │  finish con testigo vigente
     │  intentos; attempt += 1; espera creciente     │
     └──────────────────────────────────────────────┤
                                                    ├──► succeeded   (puntero borrado)
                                                    ├──► failed      (fatal / requires_human)
                                                    └──► failed + dead_letter_item
                                                         (intentos agotados)
  arriendo vencido ─► el reclamo cierra el intento como `abandoned`,
                      devuelve el trabajo a `queued` y sube `attempt`;
                      si ya no quedan intentos, carta muerta.
```

Cuatro invariantes lo sostienen, y cada uno existe por un fallo reproducible:

1. **`running` y arriendo son un solo hecho** (`ck_run_lease`). No hay un tercer
   estado en el que un trabajo esté en curso sin dueño.
2. **Terminal y sin puntero ocurren en la misma transacción**, dentro de
   `finish_run`. Borrar el puntero desde fuera era lo que perdía trabajos.
3. **Cerrar exige el testigo vigente.** Un worker que revive después de que otro
   recuperó el trabajo recibe `stale_lease` y no escribe nada.
4. **El worker no libera nada por su cuenta.** La recuperación la hace
   `claim_next_run`, que ve las dos filas a la vez.

No se añadió un estado `dead_letter`: `failed` con `error_code` más una fila en
`dead_letter_item` dice lo mismo, satisface las restricciones de `V0003` tal como
están escritas, y se mantiene más cerca del enum `job_state` ya declarado en
`docs/domain/canonical-model.json`.

---

## 4. Flujo cuarentena → escaneo → evidencia

```
subida ──► SIEMPRE quarantine ──► trabajo `scan` ──► decisión persistida
                                                     │
                        promoted ────────────────────┼──► copia a raw ──► trabajo `profile`
                        quarantined / rejected ──────┘    (se queda donde está)
```

- Sólo se promueve lo que se inspecciona **de principio a fin**. Hoy eso es
  `text/csv` y nada más.
- PDF, ZIP genérico, XLSX y ODS: `no_scanner_for_format`. Se quedan en cuarentena
  con el motivo visible en la web.
- Un ZIP se identifica por **manifiesto**, no por extensión. Un libro con
  `xl/vbaProject.bin` se rechaza: una macro es código.
- La decisión lleva la versión del escáner en su clave, así que reintentar un
  escaneo es inocuo y revisar la decisión con un escáner nuevo no obliga a borrar
  la anterior.
- El original **se conserva** en cuarentena: promover copia, no mueve.

---

## 5. Idempotencia y reconciliación

- `INSERT ... ON CONFLICT (company_id, content_sha256) DO NOTHING RETURNING`, con
  lectura de respaldo. El perdedor responde lo mismo que el ganador.
- READ COMMITTED **explícito** en cada conexión del pool: bajo REPEATABLE READ la
  lectura de respaldo no vería la fila recién confirmada.
- La clave del objeto sale del contenido, así que una escritura concurrente
  duplicada escribe los mismos bytes en el mismo sitio.
- `db/reconcile/objects.py` detecta filas sin objeto, objetos sin fila y
  artefactos sin el trabajo que les toca. **No borra nada** — un objeto
  direccionado por contenido puede estar referenciado por una transacción que aún
  no confirmó. Y si no hay alcance que revisar **lo dice**, en vez de devolver un
  informe vacío en verde.

---

## 6. Lo que sigue necesitando una persona

Nada de lo siguiente se ha decidido en código, y ninguno de estos gates se ha
movido.

| Punto | Quién | Estado |
|---|---|---|
| **Cuatro funciones `SECURITY DEFINER`** declaradas en `migration-tooling.json` con dueño, motivo y gate. `production_policy.security_definer` sigue diciendo `forbidden_without_review` y las cuatro están en `human_review_state: pending`. Declarar no es revisar. | Security / Database | **DB-G03, sin cumplir** |
| **Se amplió la excepción de RLS de `dispatch_pointer`** con la columna `available_at`. Es una marca de tiempo, no un dato de negocio, pero amplía una excepción cuyo dueño es Security. | Security | **DRG-01, sin cumplir** |
| **S-01 / TM-005**: detección de PAN antes de `raw`. Esta rebanada **no lo resuelve**. Un fichero con PAN sigue aterrizando en cuarentena antes de que nadie lo mire, que es la cuestión de alcance PCI abierta (BL-11). Lo único que cambia es que ya nada sale de cuarentena sin inspección. | Security / Legal | **sin cumplir** |
| **ADR-002** sigue `proposed`; no hay herramienta de migración seleccionada y `product_migrations_allowed` sigue `false`. | Architecture | **sin cambios** |

### Divergencias declaradas, no resueltas

- **`dead_letter_item.work_class`**: ninguna de las cinco clases declaradas en
  `events-retries.json` describe una cola en PostgreSQL. Se guarda la más cercana
  (`stateless_job`) en vez de añadir una sexta por la puerta de atrás. El contrato
  pone el dueño de la planificación en una cola gestionada; el nuestro está en
  PostgreSQL.
- **`work_schema_version`**: no hay outbox ni registro de esquemas — el contrato
  lo exige y lo tiene diferido. La columna existe y guarda la versión canónica del
  trabajo, como marcador.
- **`retry_policy_contract`** declara trece campos, incluidos `owner` y
  `reviewer` independientes. **No está satisfecho.** Lo que existe es un
  `max_attempts` por trabajo con valor por defecto local. Una política de
  producción necesita esos dos nombres humanos, y no se han inventado.
- **`processing_run`** sigue sin `engine_release_id`, `canonical_schema_version`
  ni `idempotency_key`, que `canonical-model.json` declara obligatorios: dependen
  de entidades (`artifact_version`, `engine_release`) que todavía no existen. Se
  añadió sólo `authorization_version`, que sí tiene sus dependencias.

### Catálogo de pruebas

Las 124 pruebas nuevas contra PostgreSQL real **no reducen** el contador de
`TCM-CONTRACT-NOT-IMPLEMENTED`, que sigue en 38. El catálogo sólo detecta
implementación por nombre de método en `tools/**/*.py`, y estas pruebas viven en
`db/tests/` y `workers/document/tests/`, que no están en su alcance de escaneo.
Se deja constancia en vez de ampliar el alcance: hacerlo tocaría
`docs/testing/TEST_CATALOG.md`, que es entrada adjudicada del arnés golden y
objetivo de mutación, y arrastraría una readjudicación manual de dos registros más.
No hay deriva nueva; tampoco hay crédito.

---

## 7. Verificación ejecutada

Desde volúmenes vacíos, con `sh infra/local/up.sh`:

| Comando | Resultado |
|---|---|
| `… --profile migrate run --rm migrate` | `head V0007`, y `mutated: false` al repetir |
| `… run --rm migrate python -m unittest discover -s /app/db/tests -t /app` | **124 OK** |
| `… run --rm --no-deps api python -m unittest discover -s /app/tests -t /app/tests` | **61 OK** |
| `… run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests` | **8 OK** |
| `python -m unittest discover -s packages/contracts/python -t packages/contracts/python` | **106 OK** |
| suite enumerada del repositorio | **1146 OK** |
| `quality_gate`, `local_stack`, `runtime_config`, `migration_readiness`, `workspace_contract` | exit 0 |
| `golden_harness verify` + `run`, `mutation_harness verify` + `run`, `test_catalog validate` | exit 0 |
| `docker build --target build …` + `npm run lint` | typecheck y lint limpios |
| Recorrido en navegador | CSV limpio promovido; CSV con tarjeta y PDF en cuarentena con su motivo |

Checksums de `V0001`–`V0004` sin cambios: el migrador los verifica en cada réplica
y `mutated: false` lo demuestra.

---

## 8. Efecto sobre un volumen local existente

`001_bootstrap.sql` sólo corre sobre un volumen vacío, y `V0005` exige los roles
nuevos. Sobre una base creada antes de este cambio, la migración **se detiene
diciendo qué hacer** en vez de conceder a medias:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes
sh infra/local/up.sh
```

CI no ve este caso porque siempre arranca desde volúmenes vacíos. Está anotado
aquí precisamente por eso.
