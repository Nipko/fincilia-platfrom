# FNC-P3.5 — Onboarding, puerta de release y linaje escalable

Tres cosas que P3 dejó abiertas y aquí se cierran: una versión del motor sin
aprobar podía publicar, no había forma de dar de alta una cuenta sin editar la
semilla, y el linaje crecía con el producto de filas por campos.

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Migraciones añadidas | `V0009`, `V0010`, `V0011` — `V0001`–`V0008` con su checksum intacto |
| Permisos nuevos | `financial_account.manage`, `data_source.manage` |
| ADR propuesta | ADR-024, `Proposed` y registrada `blocked` |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |

---

## 1. La puerta de la versión del motor

`_release()` buscaba por clave y no miraba el estado. Publicar afirma que algo se
puede reproducir; si nadie revisó el motor que lo produjo, la afirmación no vale
nada y el sistema no debe hacerla.

Ahora se comprueban **cuatro** cosas, no una:

| Comprobación | Si falla | Dónde vive |
|---|---|---|
| la release existe y se llama por su nombre | `engine-release-missing` | `approved_release()` |
| su estado es `approved` | `engine-release-not-approved` | `approved_release()` |
| hay constancia de quién la aprobó | `engine-release-unattested` | `release_approval` |
| lo aprobado es lo que corre | `engine-release-tampered` | disparador **y** lectura |

`superseded` reproduce lo que ya salió de ella y **no empieza nada nuevo**.
Publicar vuelve a comprobar el estado: entre preparar y publicar pueden pasar
días, y sellar con una release retirada sería firmar lo que ya no vale.

La integridad de «lo aprobado es lo que corre» está en dos sitios a propósito: un
disparador congela `components`, `release_key`, `classification` y
`canonical_schema_version` tras la firma, y la API recalcula el digest al leer.
Una integridad comprobada en un solo sitio se pierde el día que ese sitio falla.

### La herramienta, y quién la usa

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.admin.releases show --release fnc-p3-mapping-0.1.0
```

`show` enseña componentes, digests e historial. Es lo que hay que leer **antes**
de firmar. Después:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.admin.releases approve --release fnc-p3-mapping-0.1.0 --actor "tu.nombre" --ref "ACTA-2026-08-23" --rationale "corpus sintético revisado"
```

La herramienta exige actor, referencia y motivo; rechaza `latest`; se niega a
reaprobar; y `datasets --release` dice qué se produjo con una versión, que es lo
primero que hay que saber antes de retirarla.

**Esta ejecución no ha aprobado ninguna release.** El entorno local siembra la
suya en `draft` y el comando de arriba lo ejecuta una persona, con su nombre. Las
pruebas usan aprobaciones sintéticas marcadas `SYNTHETIC-TEST-FIXTURE` /
`FIXTURE-NOT-A-HUMAN-APPROVAL`, sobre releases propias de cada suite.

---

## 2. Alta de cuentas y fuentes

### El identificador no sobrevive a la petición

Entra en el cuerpo, se convierte en HMAC-SHA256 con una clave dedicada, y lo que
queda es el token, los cuatro últimos dígitos y la versión de clave. **Ni la
fila, ni el log, ni el mensaje de un error lo citan.**

Tres decisiones que valen su tamaño:

- **la clave no es la de firma de tokens.** Un secreto que sirve para dos cosas
  tiene el radio de explosión de las dos, y rotar uno obligaría a rotar el otro.
  `ApiSettings` lo rechaza si coinciden;
- **la empresa entra en el material del HMAC.** El mismo número en dos empresas
  produce dos tokens, así que comparar no revela que comparten una cuenta;
- **la versión de clave va al lado del token, no dentro.** Rotarla cambia el
  token y no cambia la identidad económica de la cuenta, que es la fila.

`FINCILIA_IDENTIFIER_TOKENIZATION_KEY` es obligatoria en la API y **rechazada**
en el worker: el worker extrae filas y no da de alta cuentas. Fuera de `local` y
`test` el validador levanta pidiendo un gestor de claves; hoy `env` sólo admite
esos dos valores, así que es la trampa que salta el día que alguien añada
`staging` sin haber decidido Vault o KMS.

### Vínculos, no una columna

Una fuente se relaciona con **varias** cuentas y con un papel tipado —`primary`,
`settlement`, `ledger`, `supporting`—. Incrustar `financial_account_id` en
`data_source` habría hecho imposible el caso normal en cuanto hay pasarelas: una
liquida a una cuenta bancaria y concilia contra un libro contable.

Un índice parcial garantiza **una sola cuenta principal viva** por fuente: si
hubiera dos, «contra qué cuenta se publica esto» dejaría de tener respuesta. Y
preparar un dataset exige que la cuenta esté vinculada y activa: un extracto
bancario que aterriza en la cuenta de otra pasarela cuadra consigo mismo y
descuadra el cierre.

### Nada se borra

No hay verbo de borrado. Una cuenta con movimientos detrás se cierra con su
motivo; borrarla dejaría hechos económicos apuntando a algo que nadie puede
explicar. `ON DELETE RESTRICT` lo impide en el motor y la API lo dice antes con
un mensaje que se entiende.

---

## 3. Ciclos esperados

`source_cycle` lleva el calendario —periodicidad, plazo, gracia, responsable— y
`source_expectation` el deber de un periodo concreto, con la forma que declara
`canonical-model`. Van separados porque meter la periodicidad en la expectativa
haría que cada instancia repitiera la regla, y cambiar la regla obligaría a
reescribir la historia.

**Ninguna función del cálculo mira el reloj.** La fecha «de hoy» entra como
argumento: una que la mirara daría un resultado distinto en cada ejecución y
haría imposible probar que el atraso se calcula bien. El estado tardío se calcula
**al leer**; guardarlo exigiría un proceso nocturno, y el día que no corriera,
nada estaría atrasado.

No hay envío de recordatorios. El vencimiento se calcula; avisar por un canal
externo es otra decisión, con su propio consentimiento y su propio gate.

---

## 4. Linaje: lógico completo, físico constante

**La divergencia de P3 queda resuelta.** El drill-down devuelve las seis etapas
de `PATH-FINANCIAL-FACT`, en orden, cada una con su operación tipada, sus tipos
semánticos de entrada y salida, su transformación nombrada y sus versiones.

Lo que cambia es dónde vive cada cosa:

| Qué | Dónde | Cardinalidad |
|---|---|---|
| las seis etapas, tipadas y versionadas | `lineage_transform_plan` + `_step` | 6 por campo y **plan** |
| qué celda produjo el campo | `raw_record.origin_locator` + `step.source_column` | ya existía |
| qué registro de origen | `source_record.raw_record_id` | ya existía |
| la huella del valor publicado | `canonical_movement.field_digests` | ya existía la fila |
| la evidencia sellada | `lineage_node` + arista `included_in_snapshot` | 1 por dataset |

El dato que lo hace viable: **las seis etapas son propiedades de la columna, no
de la fila**. Leer la columna 3 como decimal con coma es la misma decisión en la
fila 7 que en la 90.000.

Medido en CI sobre 100.000 filas y cuatro campos: **2 nodos de linaje en toda la
empresa**. Con la representación de P3 serían ochocientos mil sólo para ese
dataset.

Un plan se ata a `(mapping_version_id, engine_release_id)` con `UNIQUE`. Cambiar
la transformación cambia el par, luego es otro plan, y el anterior sigue
explicando lo que produjo. Reconstruir con el código de hoy sería el `latest` que
el manifiesto prohíbe, con otro nombre.

Si una etapa no se reconstruye, `lineage_complete` sale en falso y lo dice.
Publicar sin plan lo impide un CHECK.

**ADR-024** propone esta representación. Está `Proposed` y registrada `blocked`:
una propuesta no cuenta como decisión tomada.

---

## 5. Escala

El techo de 10.000 no era una política: era el síntoma de cargar el fichero
entero en memoria y escribir veintitrés sentencias por fila.

Preparar **ya no es una transacción**. El dataset nace en `staging` —invisible
como publicado—, cada lote entra en la suya junto a su punto de control, y el
paso final lo pasa a `validated` de una vez.

| Antes | Ahora |
|---|---|
| `fetchall()` de 100k filas y **después** el techo | `count(*)` antes de traer una fila |
| 23 sentencias por fila | 3 sentencias multifila por lote de 2.000 |
| una transacción para todo | una por lote, con su `dataset_chunk` |
| digest desde una lista en memoria | cursor de servidor sobre lo que quedó escrito |
| sin reanudación | reanuda desde el último lote; lo que no figura, no ocurrió |

`COPY` habría sido más rápido y **no se puede**: PostgreSQL no lo admite sobre
una tabla con seguridad por filas, que es justo lo que protege estas tres. Entre
perder el aislamiento y perder velocidad, se pierde velocidad.

### Medición en CI, 100.000 filas

Corrida verde `32623363931`:

```
bytes                     5 755 595
extracted_records           100 001   (sin truncar)
extract_seconds                33,0
prepare_seconds                75,8
rounds                            3
chunks                           50
movements                   100 000
rejected                          0
process_peak_rss_mib          229,1
rss_growth_mib                 90,0
lineage_nodes_company_wide        2
```

Se mide con `getrusage` y no con `tracemalloc`: trazar cada reserva multiplica
el tiempo por varias veces, y con el puesto la preparación marcaba 238 s, un
número que dice más del medidor que del código.

La extracción completa —subir, escanear, perfilar y escribir 100.001
`raw_record`— tardó 33,0 s. **Es el tramo lento y no está resuelto**: la
extracción sigue materializando el fichero entero en memoria antes de escribirlo
(`extraction.py` construye la lista completa de filas). Lo que se rediseñó es la
publicación, que es donde estaba el techo. El siguiente cuello es la extracción,
y está a 27 s del límite declarado de 60 s, y con la mitad más de filas lo
cruzaría.

Una lectura truncada ya **no** se puede publicar: `truncated` es un estado y no
un fallo, y la preparación no lo miraba. Un fichero cortado por el límite de
tiempo podía publicarse como completo, con un total que cuadraba consigo mismo y
le faltaban filas.

---

## 6. Endpoints nuevos

| Método y ruta | Permiso |
|---|---|
| `POST /companies/{c}/accounts` | `financial_account.manage` |
| `GET /companies/{c}/accounts` | `movement.read` |
| `GET /companies/{c}/accounts/{a}` | `movement.read` |
| `PATCH /companies/{c}/accounts/{a}` | `financial_account.manage` |
| `POST /companies/{c}/sources` | `data_source.manage` |
| `GET /companies/{c}/sources` | `document.read` |
| `GET /companies/{c}/sources/{s}` | `document.read` |
| `PATCH /companies/{c}/sources/{s}` | `data_source.manage` |
| `POST /companies/{c}/sources/{s}/accounts` | `data_source.manage` |
| `GET /companies/{c}/links` | `document.read` |
| `PATCH /companies/{c}/links/{l}` | `data_source.manage` |
| `PUT /companies/{c}/sources/{s}/cycle` | `data_source.manage` |
| `POST /companies/{c}/sources/{s}/expectations` | `data_source.manage` |
| `GET /companies/{c}/expectations` | `document.read` |
| `POST /companies/{c}/datasets/{d}/continue` | `dataset.map` |

`POST /datasets` devuelve **201** si el conjunto entero cabe en el presupuesto de
tiempo y **202** si queda en `staging`. Ninguna ruta nombra `release`: aprobar es
un acto de plataforma y no hay superficie pública que lo toque.

---

## 7. Pantallas

`/empresas/{c}/fuentes` reúne el onboarding: cuentas, fuentes, vínculos y ciclos,
con el orden explícito y un estado por cada cosa que puede faltar. Desde una
fuente con cuenta principal hay un enlace a subir documento.

`/empresas/{c}/movimientos/{m}` enseña las seis etapas por campo, con el tipo que
entra, el que sale y la transformación en castellano.

Estados con texto propio: sin cuentas, sin fuentes, fuente sin cuenta, vínculos
sin principal, cuenta suspendida o cerrada con su motivo, periodo atrasado con
sus días, conjunto a medias con su botón de continuar, cuarentena, sin extraer,
lectura truncada, bloqueado, validado, publicado, rechazado, sin acceso.

---

## 8. Lo que sigue esperando a una persona

Ninguno se ha movido y ninguno se ha marcado como aceptado.

- **Aprobación real de `engine_release`.** Requiere `approval_ref`,
  `result_diff_report` y revisión independiente, y es de `human_platform_owner`.
- **ADR-024**, `Proposed` y `blocked`: falta ratificación de Data y Architecture
  y la enmienda del contrato de linaje.
- **DB-G03**: cuatro funciones `SECURITY DEFINER` con `human_review_state: pending`.
- **DRG-01**: la excepción de RLS de `dispatch_pointer` sigue ampliada.
- **S-01 / TM-005**: detección de PAN antes de `raw`, sin resolver.
- **ADR-002**: sigue `proposed`.
- **`retry_policy_contract`**: trece campos declarados, `owner` y `reviewer`
  independientes sin nombrar.
- **Vault o KMS** para la clave de tokenización fuera de local.

---

## 9. Divergencias declaradas

1. **`data_source_account`, `source_cycle`, `lineage_transform_plan`,
   `lineage_transform_step`, `dataset_chunk` y `release_approval` no están en
   `canonical-model.json`.** Añadirlas exige editar `REQUIRED_ENTITIES` en el
   validador, que es la guarda contra la deriva accidental del modelo; hacerlo en
   silencio la volvería inútil. ADR-024 propone la extensión.
2. **`source_expectation` tiene columnas que el modelo no declara**
   (`due_on`, `late_after`, `state`, `cycle_id`, `satisfied_by`,
   `waived_reason`). El modelo describe la entidad; la tabla la implementa con lo
   operativo.
3. **La extracción sigue sin ser streaming.** La publicación se rediseñó; la
   lectura del fichero no. Está medido arriba.
4. **El desplegable de responsables del ciclo lista sólo a quien tiene sesión.**
   No existe una lectura de miembros de la empresa, e inventar nombres ofrecería
   un responsable que la base no conoce.
5. **`accounting_date` sigue nula.** Asignar periodo contable es una decisión de
   cierre, y esto no cierra.

---

## 10. Cómo ejercerlo

```bash
sh infra/local/up.sh
```

Entra como `sofia@demo.local` (owner) con `fincilia-demo-only`, abre **Fuentes y
cuentas**, crea una cuenta y una fuente, vincúlalas y declara el ciclo. Aprueba
la versión del motor con el comando de la sección 1 —con tu nombre—. Luego entra
como `ana@demo.local`, sube un CSV, mapea y prepara; y como `beto@demo.local`,
publica. Abre un movimiento y recorre sus seis etapas.

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_scale_publication -v
```
