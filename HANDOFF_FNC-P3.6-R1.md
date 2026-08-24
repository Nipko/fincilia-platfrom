# FNC-P3.6-R1 — estado y continuación

> Fichero de traspaso. Escrito porque la sesión que empezó R1 se quedó sin
> contexto. **Bórralo cuando R1 cierre**: no es documentación del producto, es una
> nota entre agentes.

| Campo | Valor |
|---|---|
| Base del mandato | `666745dc6a488fab2b0f8aa108404251790af48f` |
| HEAD al escribir esto | `c1b02d0` (empujado) |
| Rama | `claude/principal-dev` |
| Worktree | limpio |
| CI del último commit | lanzada al empujar `c1b02d0`; **hay que leerla** |
| Última CI verde conocida | `666745d` → https://github.com/Nipko/fincilia-platfrom/actions/runs/32684955542 |

---

## 0. Lo primero que tiene que hacer quien siga

```bash
gh run list --branch claude/principal-dev --limit 1
```

Todo está commiteado y empujado hasta `c1b02d0`. Lo que corre en local está verde
(316 pruebas de contrato, 24 validadores, quality gate), pero **nada de esto se ha
ejercido contra PostgreSQL real todavía**, y ahí es donde vive el riesgo de esta
tanda: los cambios del worker (`_flush`, `_stored_records`) y del carril sólo los
prueba CI. Lee esa corrida antes que nada.

Si sale en rojo, lo más probable es que sea algo del §2.2 que se pasó por alto, o
el `_flush` nuevo contra PostgreSQL de verdad. `gh run view <id> --log-failed`.

Ciclo de verificación: escribir → `git push` → `gh run list --branch
claude/principal-dev` → `gh run view <id> --log-failed`. Unos 7 minutos por
vuelta. **No hay Docker en esta máquina**: `db/tests/**`, las pruebas de la API y
las del worker no se pueden correr en local. Lo que sí corre local está en la
sección 4.

---

## 1. Qué pide el mandato y qué está hecho

| # | Requisito | Estado |
|---|---|---|
| 1 | CP1252 con el primer byte no ASCII tras `SNIFF_WINDOW`; nunca U+FFFD en silencio; la corriente coincide con `extract()` o falla cerrado | **hecho**, con pruebas |
| 2 | Aplicar `MAX_EXTRACT_BYTES`; exactamente `max_rows` → `complete`; `max_rows+1` → `truncated` sin persistir la de más; sólo cabecera → falla; error del lector → `failed` | **hecho**, con pruebas |
| 3 | Verificar los bytes leídos contra `source_artifact.content_sha256`; distinguir digest bruto del lógico | **hecho**, con pruebas puras; **falta ejercerlo contra la base** |
| 4 | Conflicto idéntico se ignora; conflicto divergente aborta la tanda; `stored_records` refleja PostgreSQL | **código hecho**; **faltan las pruebas de base** (ver §2) |
| 5 | Reconciliar `TARGET_ROWS` con el límite productivo; ejecutar `workflow_dispatch` de verdad y enlazar el run | **reconciliado**; **falta lanzar el carril** (ver §3) |
| 6 | SQLSTATE concreto; privilegios comprobados por nombre; `TEMPORARY` sigue pendiente de aprobación humana | **hecho**; falta verlo pasar en CI |

---

## 2. Lo que falta, en orden

### 2.1 Pruebas de base para el requisito 4 — **lo más importante que queda**

El código de `_flush` detecta conflictos divergentes y devuelve el conteo real,
pero **ninguna prueba lo ejerce**. Hay que añadir a
`db/tests/test_extraction_resume.py`:

1. **Conflicto idéntico se ignora.** Ya lo cubre `TST_P36_033` de refilón (la
   reanudación reinserta las dos primeras tandas y no duplica). Basta con
   añadir una aserción explícita de que la reanudación **no** levanta.
2. **Conflicto divergente aborta y falla cerrado.** Escribir a mano, como
   migrador y con contexto de empresa puesto, una fila de `raw_record` de un
   `processing_run_id` existente con **otro** `raw_values`; después reanudar y
   comprobar que:
   - la ejecución acaba en `failed` con `error_code = 'raw_record_conflict'`;
   - la clase de fallo es `fatal` (no se reintenta: volvería a divergir);
   - la tanda no dejó filas a medias.
   La excepción es `fincilia_worker.jobs.RawRecordConflict` y la clasifica
   `classify_extraction`.
3. **`stored_records` dice la verdad.** Tras la reanudación, comprobar que
   `result['stored_records']` es igual a
   `SELECT count(*) FROM fincilia.raw_record WHERE processing_run_id = ...`, y
   que `result['inserted_records']` es **menor** (este intento sólo puso las que
   faltaban). Antes las dos habrían dicho lo mismo y las dos habrían mentido.

### 2.2 Pruebas que este cambio rompe y hay que actualizar

**Las cuatro ya están hechas en `c1b02d0`.** Se dejan listadas porque si CI sale
en rojo son el primer sitio donde mirar, y porque puede haber una quinta que no
se vio:

| Fichero | Qué asumía | Hecho |
|---|---|---|
| `db/tests/test_extraction_resume.py:127` | `outcome.content_digest` | → `record_digest` |
| `db/tests/test_extraction_resume.py:211` | `settled['result'].get('content_digest')` | → `record_digest`, y se añadió que `object_digest` es el sha256 del fichero subido y que no coincide con el de registros |
| `db/tests/test_extraction_resume.py` (`TST_P36_041`) | lista cerrada `{records, state, reason, digest, run}` | → `{records, stored, state, reason, object_digest, record_digest, run}`, cerrada igual |
| `workers/document/tests/test_jobs.py` | `try/except` sin `else` ni `self.fail` | arreglada, y añadida la clasificación de `RawRecordConflict` |

Ojo: `db/tests/test_scale_publication.py` afirma que a 100.000 filas la lectura
**no** sale truncada. Con el arreglo del límite eso sigue siendo cierto (100.000
< 200.000), pero si alguien baja `MAX_EXTRACT_ROWS` habrá que mirarlo.

### 2.3 Requisito 5 — lanzar el carril

`ci.yml` está en `main` con `workflow_dispatch`, así que el despacho **sí**
alcanza al job `performance-lane`, que sólo existe en esta rama:

```bash
gh workflow run fincilia-ci --ref claude/principal-dev
```

El job corre el fichero del `--ref`, no el de `main`. Dos avisos:

- **El grupo de concurrencia lo puede cancelar.** `ci.yml:11` usa
  `${{ github.workflow }}-${{ github.ref }}` con `cancel-in-progress: true`, así
  que un `push` a la misma rama mata el despacho y al revés. O se espera a que no
  haya nada corriendo, o se mete `github.event_name` en la clave del grupo. Lo
  segundo es lo correcto y son dos líneas.
- El carril tarda; el `timeout-minutes` es 45.

Después hay que **enlazar el run** en el handoff y pegar la línea `[carril]` del
log, igual que se hizo con `[escala]` y `[staging]`.

### 2.4 Documentación

- `docs/implementation/handoffs/FNC-P3.6.md:121` **ya afirmaba** que «el digest se
  calcula incrementalmente sobre los bytes leídos». Era falso cuando se escribió:
  el digest era sobre los valores decodificados. Ahora es cierto, pero hay que
  decir que se corrigió, no dejar que parezca que siempre lo fue.
- El mismo handoff necesita la sección de R1: qué se corrigió, medidas nuevas, y
  el veredicto del carril.
- `RESUME_NEXT.md` y `docs/platform/LOCAL_DEVELOPMENT.md` citan 200.000 filas en
  prosa; ahora concuerdan con `TARGET_ROWS`. Verificar que siguen concordando.

---

## 3. Decisiones tomadas, para no volver a discutirlas

**Promoción de codec en vez de fallar siempre.** Un extracto colombiano en cp1252
con tildes más allá de 64 KiB es un fichero legítimo que `extract()` lee bien.
Rechazarlo habría quitado una capacidad que el producto ya tiene. Se promociona
**sólo** mientras cuanto se ha leído sea ASCII, que es cuando cambiar de codec no
toca ninguna fila anterior; en cuanto se ha decodificado algo que no es ASCII, se
levanta. Los candidatos se prueban en el mismo orden que usa `decode()`, o los dos
lectores podrían elegir codecs distintos.

**`TARGET_ROWS` se reconcilió hacia abajo.** Subir `MAX_EXTRACT_ROWS` a 250.000
habría sido subir el techo del producto para que cuadrara una prueba. El carril
mide ahora el fichero más grande que el producto acepta, y prueba que una fila más
trunca.

**El borrado de `lineage_row_override` lo cubre el privilegio, no un disparador.**
Decidido en P3.6 y sigue igual.

---

## 4. Qué se puede comprobar sin Docker

```bash
python -m unittest discover -s packages/contracts/python -t packages/contracts/python
python -m tools.dev_cli.cli validate
python -m tools.quality_gate.cli
```

Estado al escribir esto: 316 pruebas OK; 24 validadores pasan y sólo falla
`security-supply-chain`, que **falla por diseño** (SBOM, firma y procedencia no
demostradas: es un hueco declarado, no una regresión).

Las pruebas adversariales nuevas están en
`packages/contracts/python/tests/test_stream_integrity.py` (24). Se escribieron
**antes** de la corrección: 12 de las 18 primeras fallaban contra `666745d`. Hay
un script que lo comprueba en el scratchpad de la sesión
(`do_they_bite.py`): copia el paquete, le devuelve el `extraction.py` de HEAD y
corre las pruebas nuevas contra él. Merece la pena volver a pasarlo con las 24 y
dejar el resultado en el handoff, porque una prueba que pasa con el fallo dentro
no prueba nada.

---

## 5. Hallazgos de la auditoría que **no** se han tocado

Salieron de un barrido de seis auditores sobre el código real. Están confirmados
leyendo fuente, y quedan fuera del mandato de R1. No los pierdas:

1. **`_flush` no está vallado por el `lease_token`.** Sólo `finish_run` comprueba
   el arriendo, así que un worker cuyo arriendo venció puede seguir escribiendo
   evidencia mientras otro ya recuperó el trabajo.
2. **El spike y el worker calculan `values_digest` distinto.** El spike usa
   `json.dumps` con separadores por defecto; el worker usa
   `fincilia_contracts.release.digest_of`, que usa `(",", ":")`. Para los mismos
   valores dan huellas distintas.
3. **`_audit_extraction` vive en el `else:` de un `try`.** Un fallo escribiendo la
   auditoría no lo captura ese `try`, así que sube sin clasificar. Lo mismo vale
   ahora para `_stored_records`, que se llama justo al lado. Moverlos dentro del
   `try` los haría fallar cerrado.
4. **`max_rows` significa dos cosas.** En `extract()` cuenta registros con
   cabecera incluida; en `stream_records()` cuenta filas de datos. Mismo nombre,
   dos semánticas, y ninguna prueba fija la diferencia.
5. **Una lectura corta es indistinguible de un fichero terminado.**
   `_byte_lines` trata un `read()` vacío como fin de fichero; una descarga que se
   corta sin excepción produce una extracción parcial marcada `complete`. La
   comprobación del `object_digest` la caza **si** el artefacto trae huella
   declarada, que es el caso hoy; sin ella, no.
6. **`MAX_PROFILE_ROWS` es un literal independiente** de `MAX_EXTRACT_ROWS`, y
   `MAX_UPLOAD_BYTES` (25 MiB) es el techo que de verdad ata a un fichero grande.
7. **El tramo `(0, 0)`** al que cae `stream_records` cuando `take_span()` devuelve
   `None` produciría un localizador con `byte_start == byte_end == 0`.

---

## 6. Bloqueos humanos vigentes (ninguno se ha movido)

- Aprobación real de `engine_release`.
- ADR-024, `Proposed` y `blocked`.
- **Paso 3 de la re-adjudicación** de los registros dorado y de mutaciones:
  los digests de entrada se re-anotaron porque los ficheros cambiaron de verdad;
  falta la revisión independiente por quien no tocó el contrato.
- Revisión de seguridad de la ruta `COPY`/temporal: se apoya en que `TEMPORARY`
  sobre la base es un privilegio que PostgreSQL concede a `PUBLIC` por defecto.
- DB-G03, DRG-01, S-01/TM-005, ADR-002, Vault/KMS, cadena de suministro.

---

## 7. Rollback

Todo R1 es un commit: `0e729b1`. `git revert 0e729b1` devuelve el
comportamiento de `666745d` sin tocar migraciones —**R1 no añade ninguna**— ni
esquema ni datos. Los ficheros afectados son cinco de código y dos de prueba:

```
packages/contracts/python/fincilia_contracts/extraction.py
packages/contracts/python/tests/test_stream_integrity.py   (nuevo)
packages/contracts/python/tests/test_streaming.py
workers/document/src/fincilia_worker/main.py
workers/document/src/fincilia_worker/jobs.py
db/spikes/staging_benchmark.py
db/tests/test_perf_lane.py
```

Revertir devuelve también los defectos, incluido el que sustituye bytes por
U+FFFD en silencio. Si hace falta revertir por una regresión concreta, es mejor
revertir sólo el trozo culpable: las seis correcciones son independientes entre
sí salvo el renombrado de `content_digest`, del que dependen las pruebas.
