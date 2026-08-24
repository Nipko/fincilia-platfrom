# FNC-P3 — Mapeo y movimiento canonico

De unos bytes aceptados a un importe publicado que se puede auditar hasta la
celda. Esta nota dice que aterrizo, con que restricciones, y que sigue esperando
a una persona.

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Migraciones anadidas | `V0008` — `V0001`–`V0007` con su checksum intacto |
| Permiso nuevo | `dataset.publish`, segregado de `dataset.map` |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |

---

## 1. La cadena, de punta a punta

```
subida  ->  cuarentena  ->  escaneo  ->  raw  ->  extraccion  ->  raw_record
                                                                     |
                                          mapeo (version + decisiones)|
                                                                     v
                          dataset_version  ->  source_record  ->  canonical_movement
                                 |                                      |
                                 |            lineage_node / lineage_edge
                                 v
                        reproducibility_manifest
```

Tres cosas que **no** hace, y que no son un olvido: no empareja, no concilia y
no cierra. Un error de mapeo que se propagara a un cierre contable seria mucho
mas caro de encontrar que el mismo error parado aqui.

---

## 2. Que decide cada eslabon

| Eslabon | Decide | No decide |
|---|---|---|
| escaneo | si unos bytes pueden salir de cuarentena | que ponen |
| perfilado | la **forma**: cuantas columnas, de que tipo, con que confianza | ningun valor |
| extraccion | los **valores**, con su coordenada exacta | que significan |
| mapeo | que columna es cada campo canonico y con que convenio se lee | nada economico por su cuenta |
| preparacion | que filas producen movimiento y cuales se rechazan | si eso se publica |
| publicacion | que lo preparado pasa a ser utilizable | nada del contenido |

La separacion entre perfilar y extraer es la que decide donde vive cada cosa. El
perfil va al resultado de la ejecucion, que lee cualquiera con `document.read`.
Los valores van a `raw_record`, que exige contexto de empresa, y salen por un
endpoint aparte con `dataset.map`.

---

## 3. Permisos

`dataset.publish` es un permiso propio. Reutilizar `close.approve` habria atado
la publicacion de un mapeo a una decision contable posterior, y `match.confirm` a
una que ni siquiera ha ocurrido.

| Rol | `dataset.map` | `dataset.publish` |
|---|---|---|
| `owner` | si | si |
| `firm_admin` | si | no |
| `preparer` | si | no |
| `reviewer` | no | si |
| `auditor` | no | no |
| `read_only` | no | no |

El par `("dataset.map", "dataset.publish")` esta en `SEGREGATED_PAIRS`, asi que un
`owner` acumula ambos permisos y aun asi no puede ejercerlos sobre la misma
version. La comprobacion vive en tres sitios, y las tres capas hacen falta:

1. **el rol**, que decide si el boton existe;
2. **la API**, que da un mensaje util (`segregation-of-duties`, 409);
3. **un CHECK de la base** (`ck_dataset_publisher_is_not_author`), que es el que
   aguanta cuando alguien llega por otro camino.

---

## 4. Estados

**Version de mapeo**: `draft -> validated -> superseded`. Validar exige que no
quede ni un hallazgo sin resolver.

**Dataset**: `draft -> validated -> published`, con `rejected` como salida
lateral. Preparar deja la version en `validated` —el revisor tiene que poder ver
los movimientos antes de decidir— y publicar la sella.

**Version del motor**: `draft -> approved -> superseded`. Nace `draft` y **esta
ejecucion no aprueba ninguna**: el contrato de linaje dice
`agent_can_self_approve: false`.

---

## 5. Lo que bloquea una publicacion

| Bloqueo | Como se levanta |
|---|---|
| columna ambigua (`MAP-AMBIGUOUS-COLUMN`) | una persona registra su decision **y** el motivo |
| falta una columna obligatoria | corrigiendo el mapeo; no hay explicacion que valga |
| moneda ausente o no soportada | igual |
| esquema desalineado (`schema-drift`) | otra version de mapeo para la forma nueva |
| mapeo en borrador | validandolo |
| documento en cuarentena o sin extraer | no depende del mapeo |

Una decision solo levanta el bloqueo si **coincide con lo que el mapeo declara**.
Decir `mdy` sobre un mapeo que lee `dmy` no resuelve la ambiguedad: deja escrito
que la persona quiso una cosa y el sistema hace otra.

---

## 6. Idempotencia y reproceso

La terna `(ejecucion de extraccion, version de mapeo, version del motor)` es la
identidad de un dataset, y `uq_dataset_reproduction` la impone en el motor.
Consecuencias, todas comprobadas contra PostgreSQL real:

- preparar dos veces devuelve el mismo dataset con `reused: true`;
- tres preparaciones simultaneas producen **uno**;
- publicar dos veces no cambia quien publico ni cuando;
- cuatro publicaciones simultaneas sellan la version una vez y nadie recibe un 500;
- reprocesar el mismo fichero crea **otra** version, y la anterior se conserva.

`reproducibility_manifest.reproduction_key` es el sha256 del JSON canonico de
todas las entradas declaradas, sin los digests de salida. Incluir la salida haria
que la clave cambiara con el resultado, que es lo contrario de lo que sirve.

---

## 7. Linaje

Cada campo publicado tiene un camino tipado hasta su celda:

```
lineage_node(raw_locator)  --derived_from(transform)-->  lineage_node(financial_fact_field)
        ^
        |  included_in_snapshot
lineage_node(artifact_version)
```

El nodo de celda lleva la coordenada completa —`artifact_sha256`,
`record_ordinal`, `field_ordinal`, `byte_start`, `byte_end`— y el nodo del hecho
lleva **la huella del valor y jamas el valor**. Un grafo de linaje que copia
importes se convierte en una segunda base de datos que nadie protege.

La arista nombra la transformacion: `normalise_amount:comma`, `parse_date:dmy`,
`resolve_direction:signed_amount`. `derived_from` significa que el valor fluyo, y
un CHECK exige el nombre; sin el, el grafo diria «esto tiene algo que ver con
aquello».

### Divergencia declarada

`lineage-model.json` describe `PATH-FINANCIAL-FACT` como una secuencia de cinco
saltos: `artifact_version -> raw_locator -> extracted_field -> transformed_value
-> source_record_field -> financial_fact_field`. Lo implementado colapsa los tres
intermedios en una sola arista `derived_from` con la transformacion nombrada.

El motivo es de tamano, y se dice en vez de esconderse: la secuencia completa
son seis nodos por campo y por fila, o seis millones de filas de grafo para un
extracto de doscientas mil lineas con cinco campos. Lo implementado conserva las
dos propiedades que el contrato exige de verdad —cobertura del 100% de los campos
publicados y drill-down hasta `artifact_sha256` y localizador exacto— y pierde la
granularidad intermedia. **No esta aprobado por nadie**: es una divergencia
declarada, no una decision cerrada.

Por la misma razon hay un techo explicito de `MAX_DATASET_ROWS = 10_000` por
publicacion. Un dataset que no cabe se rechaza diciendolo, en vez de tragarselo a
medias.

---

## 8. Privilegios de base

| Tabla | `fincilia_app` | `fincilia_worker` |
|---|---|---|
| `engine_release` | `SELECT` | `SELECT` |
| `financial_account`, `data_source` | `SELECT, INSERT, UPDATE` | ninguno |
| `column_mapping`, `mapping_decision` | `SELECT, INSERT` | ninguno |
| `column_mapping_version`, `dataset_version` | `SELECT, INSERT, UPDATE` | ninguno |
| `raw_record` | `SELECT` | `SELECT, INSERT` |
| `source_record`, `canonical_movement` | `SELECT, INSERT` | ninguno |
| `movement_evidence_link`, `lineage_node`, `lineage_edge` | `SELECT, INSERT` | ninguno |
| `reproducibility_manifest` | `SELECT, INSERT` | ninguno |

El movimiento canonico es **inmutable para el runtime**: `REVOKE UPDATE, DELETE`.
Corregir un movimiento publicado es publicar otra version, y el motor lo niega en
vez de confiar en que nadie escriba el UPDATE.

El worker escribe `raw_record` y nada mas. `module-boundaries` lo dice
literalmente: los workers no publican estado financiero canonico.

`engine_release` no lleva `company_id` ni RLS, y es deliberado: una version del
software no es dato de una empresa. No hay nada que aislar y el runtime solo lee.

---

## 9. Endpoints

| Metodo y ruta | Permiso |
|---|---|
| `GET /companies/{c}/documents/{a}/preview` | `dataset.map` |
| `GET /companies/{c}/accounts` | `movement.read` |
| `GET /companies/{c}/sources` | `document.read` |
| `POST /companies/{c}/mappings` | `dataset.map` |
| `GET /companies/{c}/mappings` | `dataset.map` |
| `GET /companies/{c}/mappings/{v}` | `dataset.map` |
| `POST /companies/{c}/mappings/{v}/decisions` | `dataset.map` |
| `POST /companies/{c}/mappings/{v}/validate` | `dataset.map` |
| `POST /companies/{c}/datasets` | `dataset.map` |
| `GET /companies/{c}/datasets` | `movement.read` |
| `GET /companies/{c}/datasets/{d}` | `movement.read` |
| `POST /companies/{c}/datasets/{d}/publish` | `dataset.publish` |
| `POST /companies/{c}/datasets/{d}/reject` | `dataset.publish` |
| `GET /companies/{c}/datasets/{d}/movements` | `movement.read` |
| `GET /companies/{c}/movements/{m}` | `movement.read` |

Todo error es RFC 7807. **Ninguno distingue «no existe» de «no puedes»**: un
codigo que separa las dos cosas convierte la API en un buscador de documentos
ajenos. El unico 409 que existe es `segregation-of-duties`, y ese no filtra nada
porque quien lo recibe ya podia ver el dataset.

---

## 10. Pantallas

`/empresas/{c}/documentos/{a}/mapeo` reune cuatro vistas sobre el mismo
documento, porque son cuatro preguntas distintas:

- **Original**: que subiste, su huella y su zona;
- **Extraccion**: la tabla paginada con el numero de fila del fichero, la
  cabecera, el tipo inferido y su confianza;
- **Mapping**: el selector visual de columnas, los bloqueos con su formulario de
  decision, y las decisiones ya tomadas con su motivo;
- **Canonico**: el conjunto, su manifiesto, el boton de publicar y la tabla de
  movimientos.

`/empresas/{c}/movimientos/{m}` ensena de que celda sale cada campo, con la
transformacion en castellano y el tramo de bytes.

Estados que tienen su propio texto en vez de una tabla vacia: cuarentena, sin
extraer, lectura truncada, bloqueado, validado, publicado, rechazado y sin
acceso. El boton de publicar aparece solo si este sujeto tiene el permiso, el
conjunto esta validado y no es quien lo preparo; si falta alguna de las tres, hay
una frase que dice cual.

---

## 11. Lo que sigue esperando a una persona

Ninguno de estos gates se ha movido, y ninguna decision humana se ha marcado como
aceptada.

- **`engine_release` sin aprobar.** La version que publica el entorno local nace
  `draft`. Aprobarla es de `human_platform_owner` y exige `approval_ref`,
  `result_diff_report` y revision independiente. Para datos sinteticos no
  bloquea; para produccion si.
- **La divergencia del camino de linaje** de la seccion 7 no esta aprobada.
- **DB-G03**: cuatro funciones `SECURITY DEFINER` con `human_review_state:
  pending`.
- **DRG-01**: la excepcion de RLS de `dispatch_pointer` sigue ampliada.
- **S-01 / TM-005**: deteccion de PAN antes de `raw`, sin resolver.
- **ADR-002**: sigue `proposed`.
- **`retry_policy_contract`**: trece campos declarados, incluidos `owner` y
  `reviewer` independientes, que no se han inventado.

---

## 12. Como ejercerlo

```bash
sh infra/local/up.sh
```

Entra como `ana@demo.local` (preparadora) con `fincilia-demo-only`, sube un CSV
de extracto a Panaderia La Espiga, espera a que el escaneo lo promueva, abre
**Mapear y publicar**, asigna columnas y prepara. Despues entra como
`beto@demo.local` (revisor) y publica: Ana no puede, y la interfaz lo dice antes
de que lo intente.

Las pruebas del recorrido entero, contra PostgreSQL y MinIO reales:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_p3_vertical -v
```
