# FNC-P3.6 — Contratos reconciliados, excepción por fila y extracción en corriente

P3.5 dejó cinco divergencias declaradas. Cuatro se cierran aquí y la quinta
—`accounting_date`— se blinda a propósito en vez de resolverse.

> **Actualización R2 (2026-08-24):** la sección 11 contiene la evidencia de
> cierre posterior a la auditoría de R1. Sus medidas y estado sustituyen a los
> números históricos de las secciones 3 y 4 cuando se hable del HEAD actual.

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Base | `5aa8c53` |
| Migraciones añadidas | `V0012`–`V0015` — `V0001`–`V0011` con su checksum intacto |
| Rutas nuevas | 3 (`GET`/`POST` de overrides, `POST` de aprobación) más `GET` de asignables |
| ADR-024 | actualizada y **`Proposed`**; no aceptada |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |

---

## 1. Cada tabla, bajo el contrato que le corresponde

Seis tablas de `V0009` existían en PostgreSQL sin que ningún contrato dijera de
quién eran. La tentación era añadirlas todas a `canonical-model.json` y cerrar el
hallazgo. Eso habría convertido el modelo financiero en un cajón: `dataset_chunk`
cuenta cuánto se publicó, no qué se publicó, y llamarlo hecho económico habría
sido cómodo y falso.

| Tabla | Autoridad | Por qué ahí |
|---|---|---|
| `data_source_account` | `canonical-model.json`, módulo `sources` | Es dominio del plano de control: con qué trabaja una empresa. |
| `source_cycle` | `canonical-model.json`, módulo `sources` | Igual: el calendario es del dominio, no de la infraestructura. |
| `source_expectation` | `canonical-model.json` (ya estaba) | Absorbe `cycle_id`, `due_on`, `late_after`, `state`, `satisfied_by`, `satisfied_at` y `waived_reason`. |
| `lineage_transform_plan` | `lineage-model.json#transform_plan_contract` | Describe **cómo se leyó** una columna, no un hecho económico. |
| `lineage_transform_step` | `lineage-model.json#transform_plan_contract` | Lo mismo, por etapa. |
| `lineage_row_override` | `lineage-model.json#row_override_contract` | La excepción por fila; misma razón. |
| `release_approval` | `lineage-model.json#engine_release_contract.approval_record` | Es la firma de una versión del motor: acto de plataforma, no dato de una empresa. |
| `dataset_chunk` | `events-retries.json#checkpoint_contract` | Es el recibo de un tramo ya publicado: vocabulario de reintentos. |

`REQUIRED_ENTITIES` sigue siendo exacta y crece **sólo** con las dos entidades
cuya autoridad es el modelo financiero. Y la lista que no puede entrar ya no es
una convención: `FOREIGN_AUTHORITY` convierte el camino corto en un fallo con
nombre, `DOM-FOREIGN-AUTHORITY`, con pruebas que lo comprueban entidad por
entidad.

Las dos entidades nuevas se añaden **al final** del array. No es estilo: los
punteros de `mutation-harness.json` son índices, y `/entities/13/fields/1/nullable`
seguiría cuadrando sobre otra entidad sin que nadie se entere —`expected_current`
también coincide— y el veredicto sería falso, no un error.

### Mutabilidad declarada de `source_expectation`

`due_on` y `late_after` quedan **inmutables**. Se calculan del ciclo y se
guardan; recalcularlos más tarde con otro ciclo cambiaría si algo llegó tarde, y
eso ya ocurrió. La entidad pasa de `mutable_master_versioned` a
`controlled_state_machine`: el deber de un periodo tiene transiciones
(`pending → satisfied | late | waived`), no es un maestro que se edita.

### Lo que ahora se cruza

`cross-contract` comprueba que las tablas físicas que los contratos de linaje
nombran existan en las migraciones. Un contrato que nombra
`fincilia.lineage_row_override` y una base que no la tiene son dos documentos que
no hablan del mismo sistema, y ni el validador de linaje ni el de migraciones lo
veían por separado: uno mira la forma del contrato y el otro mira el SQL.

---

## 2. ADR-024: la fila que no sigue el plan de su columna

ADR-024 decidió que las seis etapas son propiedades de la columna. Lo que dejaba
sin contestar es la fila que se aparta: alguien corrige un importe a mano, alguien
resuelve el signo mirando el documento, una fila se rechaza.

Sin sitio donde decirlo sólo había dos salidas, y las dos malas: que la corrección
desapareciera del camino —y el linaje afirmara algo falso— o cambiar el plan de la
columna para acomodar una fila, que miente sobre las otras noventa y nueve mil
novecientas noventa y nueve.

`V0012` crea `fincilia.lineage_row_override`: company-scoped, con RLS forzada,
claves ajenas compuestas y siete clases de excepción (`manual_correction`,
`overlay_applied`, `exceptional_parse`, `sign_resolution`, `substituted_value`,
`rejected_value`, `row_rule`).

| Regla | Dónde se sostiene |
|---|---|
| El valor nunca se guarda | La tabla no tiene columna para él; sólo dos huellas |
| Autor ≠ aprobador en campo crítico | API, `ck_override_segregation` y disparador |
| Un override sin aprobar bloquea la publicación | `publish_dataset` → `override-not-approved` |
| Una huella de resultado que no cuadra bloquea | `override_digest_problems` contra `field_digests` |
| Se intercala en la posición lógica correcta | `reconstruct(..., overrides=...)` inserta tras la etapa base |
| Sin override, el plan compartido | Las seis etapas salen tal cual; la ausencia no es una etapa que falte |
| No se edita | El disparador admite un único cambio: el sello de aprobación |
| No se borra | `fincilia_app` no recibe `DELETE`, igual que sobre el plan |

El borrado lo cubre el privilegio que no se concede y **no** el disparador. Un
`RAISE` en el `DELETE` no añadiría garantía alguna —el runtime ya no puede— y a
cambio dejaría una tabla que el dueño del esquema no puede limpiar al retirar una
empresa.

Cambiar de opinión escribe otro override con el ordinal siguiente. El vigente es
el último; el anterior se conserva, y las dos opiniones quedan.

**ADR-024 sigue en `Proposed`.** Su disparador de revisión cambia: una regla que
dependa de la fila ya no rompe la premisa, porque ahora tiene dónde vivir. Lo que
la rompería es que dejara de ser la excepción.

---

## 3. Extracción en corriente, medida

### Estrategia

`sniff()` lee una muestra acotada (64 KiB) para decidir codificación, delimitador
y cabecera, y devuelve un lector que **reproduce esa muestra** antes del resto: no
hay una segunda descarga del objeto. `stream_records()` es un generador; el
proceso nunca sostiene más de una tanda.

El troceado en líneas es **por bytes**, no por texto decodificado. Ninguna de las
codificaciones admitidas (`utf-8-sig`, `utf-8`, `cp1252`, `latin-1`) usa `0x0A`
dentro de un carácter, así que partir por `\n` no puede cortar uno por la mitad, y
los desplazamientos de byte del localizador salen exactos por construcción en vez
de por una conversión que hay que acertar.

El digest se calcula incrementalmente sobre los bytes leídos, y el desenlace es
explícito: `complete`, `truncated` o `failed`, con su motivo. Una extracción
truncada nunca alimenta una publicación.

### Números, de la corrida verde

| Medida | P3.5 (fichero entero) | Corriente + `INSERT` | Corriente + `COPY` |
|---|---|---|---|
| Filas | 100.000 | 100.000 | 100.000 |
| Extracción | 33,0 s | 28,5 s | **17,1 s** |
| Preparación | 75,8 s | 74,1 s | 76,9 s |
| Total | — | 102,8 s | **94,2 s** (presupuesto: 180) |
| Pico de RSS | 229,1 MiB | 184,8 MiB | **195,9 MiB** |
| Crecimiento sobre la línea base | no medido | 37,3 MiB | **49,2 MiB** |
| Tramos | 50 | 50 | 50 |
| Nodos de linaje en toda la empresa | 2 | 2 | 2 |
| Rechazadas | 0 | 0 | 0 |

Las tres columnas son corridas verdes distintas de CI, no estimaciones. La
tercera es la que corre hoy.

El crecimiento es el número que de verdad dice si el fichero se sostiene en
memoria: un pico alto puede venir del intérprete, uno alto de crecimiento sólo
puede venir de lo que se acumula. La diferencia entre 37,3 y 49,2 MiB cae dentro
del ruido de dos corridas en máquinas que no se reservan. Los techos del test se
ponen sobre estos números —400 MiB de pico, 150 de crecimiento, 180 s— y no sobre
el deseo.

Se mide con `getrusage` y **no** con `tracemalloc`: trazar cada reserva multiplica
el tiempo por varias veces, y entonces el número de tiempo diría más del medidor
que del código.

### Reanudación

Se hace fallar `_flush` en el hueco exacto entre dos tandas. La prueba comprueba
que dos tandas ya son durables, que la ejecución no figura como terminada, y que
al reanudar el recuento, el digest y el estado son los mismos que los de una
lectura entera, con tantas filas como ordinales distintos.

Lo hace cierto `uq_raw_record_ordinal` sobre `(processing_run_id, record_ordinal)`
con `ON CONFLICT DO NOTHING`, y que el reintento conserve el mismo `run_id`.

---

## 4. `INSERT` multifila contra `COPY` a tabla temporal

`COPY FROM` no funciona sobre una tabla con RLS —PostgreSQL lo rechaza, y eso ya
se supo en P3.5—, así que la única variante que merece medirse es `COPY` a una
tabla `TEMPORARY ... ON COMMIT DROP` seguido de `INSERT ... SELECT`.

`db/spikes/staging_benchmark.py` comprueba las diez propiedades contra PostgreSQL
real y mide tres rutas: `INSERT` con tandas de 500, `COPY` con tandas de 500 y
`COPY` con tandas de 5.000.

Dos cosas que la medida hace explícitas:

- **`TEMPORARY` sobre la base es un privilegio que PostgreSQL concede a `PUBLIC`
  por defecto.** La ruta B no pide un `GRANT` nuevo, pero apoyarse en un
  privilegio de `PUBLIC` no es lo mismo que no necesitar ninguno.
- **`ON COMMIT DROP` con una transacción por tanda obliga a un
  `CREATE TEMPORARY TABLE` por tanda.** Es el precio de la propiedad, no un
  detalle de implementación, y por eso se mide también con tandas grandes.

### Veredicto: se adopta

Los ocho criterios se cumplen, incluido el octavo. La medida, con cinco mil filas
y el rol que escribe de verdad:

| Ruta | Tanda | Filas/s | Frente a A |
|---|---:|---:|---:|
| `INSERT` multifila | 500 | 4.100 | — |
| `COPY` a temporal | 500 | 7.871 | **1,91×** |
| `COPY` a temporal | 5.000 | 8.206 | **2,00×** |

Y las diez comprobaciones de seguridad salieron: `rls_still_enabled`,
`rls_still_forced`, `company_context_before_load`, `temp_privilege_already_held`,
`invisible_to_another_session`, `dropped_on_commit`,
`no_persistent_shared_staging`, `rollback_leaves_nothing`,
`rollback_drops_the_temp_table` y `cross_company_refused` —esta última con
`InsufficientPrivilege`, que es la política del destino haciendo su trabajo—.

El worker escribe por esta ruta desde `ea02807`, y el efecto extremo a extremo se
midió: la extracción de cien mil filas pasó de 28,5 s a **17,1 s**.

Un riesgo que este veredicto obliga a cubrir: `COPY` tiene formato de texto
propio, y una tabulación, una barra invertida o un salto de línea dentro de un
campo entrecomillado son justo lo que ese formato escapa. Una diferencia de
escapado corrompería la evidencia **sin que nada lo dijera**, porque el digest se
calcula antes de escribir. `TST-P36-043` comprueba que los tres sobreviven el
viaje.

La versión anterior de este handoff decía lo contrario, y lo decía sin la medida.

---

## 5. Responsables entre miembros autorizados

`GET /companies/{id}/assignees` lista **sólo** a quien cumple las tres condiciones
que usa el autorizador: delegación viva de una firma sobre la empresa, membresía
activa **en esa firma**, y al menos una concesión sin revocar. Se resuelven con la
misma consulta que `repository.authorize`, para que las dos definiciones no puedan
separarse con el tiempo.

Devuelve `subject_id` opaco, `display_name` y roles funcionales. **Nada más**: ni
correo, ni binding externo, ni credenciales, ni membresías de otras firmas.

En la web: selector de personas elegibles con su rol al lado, estado explícito
cuando no hay candidatos —con el motivo, que es mejor que un desplegable vacío que
parece un fallo—, y aviso de **pendiente de reemplazo** cuando quien respondía ya
no tiene acceso. El aviso está atado al campo con `aria-describedby` y el campo
marcado `aria-invalid`: un aviso que sólo está al lado no lo lee un lector de
pantalla al llegar al control. Todo son controles nativos, así que el recorrido
por teclado es el del navegador.

---

## 6. `accounting_date` sigue nula, y ahora blindada

No se inventa. Se declara lo que **no** hace:

- no alimenta reportes certificados;
- no alimenta cierre;
- no se infiere automáticamente;
- se resolverá en P4, por periodo contable, reglas y revisión humana.

Nueve pruebas lo sostienen: siete puras —el campo no está en `CANONICAL_FIELDS`,
`Movement` no tiene el atributo, el módulo de mapeo no lo menciona, no hay etapa
para él— y dos contra la base, una de las cuales barre con expresión regular las
listas de columnas de **todo** `INSERT` y `UPDATE` de los módulos de la API.
Tratar `occurrence_date` o `posting_date` como `accounting_date` por defecto no es
una omisión que se pueda colar: es una prueba que falla.

---

## 7. Release y privilegios

Sin cambios de política, y con la comprobación generalizada. El validador ya no
lleva lista fija: descubre cada `CREATE FUNCTION` de las migraciones y exige su
`REVOKE ALL PRIVILEGES ... FROM PUBLIC`, mirando **todas** las migraciones juntas
—lo que importa es cómo acaba el esquema, no en qué fichero se dijo—. Contra la
base viva, la prueba consulta `pg_proc` y compara lo descubierto con lo que
existe, en vez de enumerar cinco nombres que envejecen.

Una función nace con `proacl` nulo, y un ACL nulo significa **ejecutable por
PUBLIC**. Es la trampa que hizo falta `V0011` para cerrar, y por eso la
comprobación es dinámica.

---

## 8. Lo que sigue esperando a una persona

Ninguno se ha movido y ninguno se ha marcado como aceptado.

- **Aprobación real de `engine_release`**: `approval_ref`, `result_diff_report` y
  revisión independiente, de `human_platform_owner`.
- **ADR-024**, `Proposed` y `blocked`: falta ratificación de Data y Architecture.
- **Re-adjudicación del registro dorado y del de mutaciones.** Los digests de
  entrada se re-anotaron porque los ficheros cambiaron de verdad —paso 2 del
  procedimiento de `GOLDEN_HARNESS.md`—. El **paso 3**, revisión independiente
  por quien no tocó el contrato, sigue pendiente. Ninguna expectativa se movió.
- **Revisión de la adopción de la ruta `COPY`/temporal.** El spike midió, las
  diez comprobaciones salieron y el worker ya escribe por ahí. Lo que falta es
  que alguien de Security lea la propiedad en la que se apoya —`TEMPORARY`
  sobre la base es un privilegio que PostgreSQL concede a `PUBLIC` por
  defecto— y diga si le vale.
- **DB-G03**: cinco funciones `SECURITY DEFINER` con `human_review_state: pending`.
- **DRG-01**: la excepción de RLS de `dispatch_pointer` sigue ampliada.
- **S-01 / TM-005**: detección de PAN antes de `raw`, sin resolver.
- **ADR-002**: sigue `proposed`.
- **`retry_policy_contract`**: `owner` y `reviewer` independientes sin nombrar.
- **Vault o KMS** para la clave de tokenización fuera de local.
- **SBOM, firma y procedencia**: `security-supply-chain` falla por diseño.

---

## 9. Divergencias que quedan

1. **`accounting_date` sigue nula.** Es deliberado y está blindado; se resuelve en
   P4.
2. **El modelo canónico dice `uuid_v7` y las migraciones usan `gen_random_uuid()`**
   en las veintidós entidades. Es anterior a P3.6 y ningún validador lo cruza.
3. **Los índices únicos parciales de `data_source_account`** (`WHERE status =
   'active'`) no se representan en `unique_constraints`: el contrato no tiene
   vocabulario para un predicado parcial, y escribirlos como totales afirmaría
   algo falso.
4. **`lifecycle_state` declara cuatro valores y los `CHECK` admiten tres.** Es el
   patrón que ya seguía `data_source`; no lo introduce P3.6, pero sigue ahí.
5. **La mutabilidad declarada en el modelo canónico es una declaración, no una
   garantía del motor**: `fincilia_app` tiene `UPDATE` sobre estas tablas.

---

## 10. Cómo ejercerlo

```bash
sh infra/local/up.sh
```

Entra como `sofia@demo.local` con `fincilia-demo-only`, abre **Fuentes y
cuentas** y verás el desplegable de responsables con las personas de la empresa,
no sólo contigo.

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_row_overrides db.tests.test_extraction_resume db.tests.test_staging_benchmark -v
```

Y el carril de rendimiento, que no corre en cada empuje:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm -e FINCILIA_PERF_LANE=true migrate python -m unittest db.tests.test_perf_lane -v
```

---

## 11. Cierre R2 — integridad de corriente, fencing y escala real

R2 parte de `eb33133` y cierra los pendientes que dejó el traspaso temporal
`HANDOFF_FNC-P3.6-R1.md`. No mueve ningún gate humano ni cambia el techo del
producto para hacer pasar una prueba.

### 11.1 Correcciones que quedaron autoritativas

- El reloj de extracción mide trabajo activo del lector. El tiempo durante el
  que el generador está suspendido porque PostgreSQL consume una tanda no gasta
  el presupuesto de lectura.
- `max_rows` significa filas de datos tanto en el lector materializado como en
  corriente. Exactamente `N` queda `complete`; `N + 1` queda `truncated` sin
  emitir la fila adicional. Membrete, cabecera y filas blancas no inflan el
  recuento.
- Un registro sin span de bytes válido falla cerrado con
  `locator_unavailable`; ya no existe el localizador inventado `(0, 0)`.
- `record_count` cuenta registros realmente emitidos y no el ordinal máximo.
- `V0013` añade `hold_processing_lease()`: la primera sentencia de cada `_flush`
  valida empresa, token, estado y expiración, y sostiene un bloqueo de fila hasta
  el commit de la tanda. Un worker con lease obsoleto no escribe ni clasifica el
  caso como fallo documental.
- La inserción ocurre antes de buscar divergencias. Sólo cuando
  `ON CONFLICT DO NOTHING` omitió alguna fila se compara la tanda exacta; una
  divergencia en empresa, artefacto, localizador, valores o digest revierte toda
  la transacción.
- Conteo durable, `finish_run` y auditoría de éxito comparten una transacción. Si
  el conteo o la auditoría fallan, el run queda recuperable y no aparece un éxito
  sin rastro.
- El spike usa el mismo `digest_of()` canónico que el worker.

`hold_processing_lease()` es la quinta función `SECURITY DEFINER` declarada. Su
`human_review_state` continúa `pending` y el gate **DB-G03 no se acepta aquí**.

### 11.2 Defecto de escala encontrado por la limpieza

La primera corrida completa importó correctamente 200.000 filas, pero limpiar
600.000 registros del spike tardó más de quince minutos. No era el recorrido del
producto: PostgreSQL comprobaba claves foráneas sin índices que comenzaran por la
columna hija y repetía barridos grandes por cada padre.

Se corrigió sólo hacia adelante:

| Migración | Índices |
|---|---|
| `V0014` | artefacto → `raw_record`; `source_record` y override → `raw_record` |
| `V0015` | movimiento, vínculo y override → `source_record` |

Una prueba contra `pg_indexes` exige los seis caminos exactos. RLS, ACL,
mutabilidad y semántica financiera no cambian. `V0014` no se reescribió después
de aplicada: el segundo nivel descubierto se materializó en `V0015`.

### 11.3 Evidencia local contra PostgreSQL 17 y MinIO

| Suite | Resultado |
|---|---:|
| Contratos compartidos | 321, OK |
| Worker puro | 8, OK |
| Base completa | 274, OK; 1 omitida por ser carril manual |
| Reanudación/fencing/asentamiento | 8, OK |
| Despacho y lease real | 31, OK |
| Staging e índices de FK | 5, OK |

La corrida bloqueante de 100.000 filas produjo 100.001 registros crudos contando
la cabecera, con 100.000 movimientos: 7,0 s de extracción, 35,4 s de preparación
y 42,5 s totales.

El carril manual local del límite productivo terminó verde:

| Medida | Resultado |
|---|---:|
| Filas de datos | 200.000 |
| Bytes | 11.622.262 |
| Extracción | 15,0 s |
| Total hasta dataset validado | 85,5 s |
| Tramos | 100 |
| Movimientos / rechazadas | 200.000 / 0 |
| Pico RSS / crecimiento | 230,3 MiB / 3,5 MiB |
| Una fila por encima | 200.000 emitidas; `truncated`, `row_limit` |

El spike del mismo carril, siempre bajo RLS, midió:

| Ruta | Tanda | Tiempo | Filas/s | Frente a INSERT |
|---|---:|---:|---:|---:|
| `INSERT` multifila | 500 | 19,04 s | 10.506 | — |
| `COPY` a temporal | 500 | 13,31 s | 15.024 | 1,43× |
| `COPY` a temporal | 5.000 | 10,97 s | 18.230 | 1,74× |

Las comprobaciones de seguridad del spike quedaron todas verdaderas. La revisión
humana de la dependencia en el privilegio `TEMPORARY` sigue pendiente; una prueba
de rendimiento no puede aprobarla.

### 11.4 Infraestructura local durante la prueba

La repetición llenó C: por cachés de desarrollo y provocó un cierre de WSL/Docker.
Se recuperaron 26,7 GiB retirando únicamente artefactos regenerables
(`apps/web/node_modules`, caché de Jest y caché de descargas de pip). PostgreSQL
reinició sano, el migrador confirmó `head: V0015`, `mutated: false`, y el carril
anterior se repitió completo después de la recuperación. No se borraron volúmenes
ni datos del repositorio.

### 11.5 Estado de integración

R2 quedó integrado y empujado en
`b4814119681bb9eccaba30e56f28a88646973858`. La corrida por `push` terminó
completamente verde:

- workflow: https://github.com/Nipko/fincilia-platfrom/actions/runs/32695531220
- repositorio y política sintética: verde;
- migraciones PostgreSQL 17: verde;
- RLS, worker y parser: verde;
- lifecycle local con migraciones, API, worker y web: verde.

El carril `workflow_dispatch`, separado del push mediante `github.event_name` en
el grupo de concurrencia, también terminó verde:

- workflow: https://github.com/Nipko/fincilia-platfrom/actions/runs/32695925730
- job de rendimiento: `97337854715`;
- 3 pruebas en 307,976 s, OK;
- 200.000 movimientos, 0 rechazados, 100 tramos;
- extracción: 28,4 s; recorrido total: 136,6 s;
- pico RSS: 231,0 MiB; crecimiento: 4,3 MiB;
- 200.001 filas de datos: 200.000 emitidas y `truncated / row_limit`;
- staging: 5.023 filas/s con INSERT, 7.932 con COPY/500 y 8.898 con
  COPY/5.000; las comprobaciones de seguridad quedaron verdaderas.

La diferencia frente a la medida local es esperable porque GitHub usa un runner
compartido. Ambas corridas permanecen dentro de los presupuestos declarados. La
revisión humana de DB-G03 y del privilegio `TEMPORARY` continúa pendiente.
