# Spike de invariantes de migración SQL-first

| Campo | Valor |
|---|---|
| Tarea | FNC-DB-002 |
| Estado | Review pending |
| Gate | ADR-002-MIGRATIONS — `not_met` |
| Owner | Database Migration Owner |
| Revisores independientes | Architecture, Security, QA |
| Contrato autoritativo | `docs/database/migration-spike.json` |
| Laboratorio | `spikes/FNC-DB-002/` — descartable |
| CLI | `python -m tools.migration_spike.cli` |
| Datos | Exclusivamente sintéticos |

---

## 1. Qué es y qué no es

Es un laboratorio descartable que prueba **invariantes** sobre PostgreSQL 17 real.

**No selecciona herramienta de migraciones y no acepta ADR-002.** Precisamente por
eso no usa Flyway, dbmate ni node-pg-migrate: aplica SQL con `psql` para demostrar
que los invariantes son alcanzables *sin condicionar la elección*. Que se cumplan
aquí no dice cuál herramienta los cumple mejor.

Tampoco toca `db/migrations`, `infra/local`, roles productivos ni CI.

---

## 2. Tres roles, no uno

| Rol | Puede | No puede |
|---|---|---|
| `fnc_spike_bootstrap` | crear roles y esquema durante la inicialización | existir después como actor ordinario |
| `fnc_spike_migrator` | aplicar migraciones; es propietario del esquema y del historial | ser SUPERUSER, BYPASSRLS, CREATEDB o CREATEROLE |
| `fnc_spike_runtime` | leer y escribir filas de su compañía; leer el historial | crear, alterar o borrar objetos; escribir el historial; ser propietario |

La separación no es decorativa: si el runtime pudiera migrar, un fallo de la
aplicación se convertiría en un cambio de esquema.

---

## 3. Cómo se aplica una migración

Un solo driver, `sql/apply_one.sql`, invocado con `psql --single-transaction` y
`ON_ERROR_STOP=1`. El orden es deliberado:

1. **`pg_advisory_xact_lock`** — serializa migradores concurrentes y se libera al
   terminar la transacción, sin necesidad de limpiar nada a mano.
2. **Guardia de checksum** — si la versión ya está aplicada con *otro* contenido,
   aborta **antes de ejecutar nada**.
3. **Guardia de idempotencia** — si ya está aplicada con el *mismo* contenido, no
   se repite.
4. **Aplicar e insertar historial**, con `applied_at` del servidor.

### Un detalle de psql que costó un fallo real

`psql` **no** interpola `:'variable'` dentro de un bloque entrecomillado con
dólares. El primer driver metía las variables dentro del `DO $$…$$` y fallaba con un
error de sintaxis en las nueve pruebas de PostgreSQL. La corrección es pasar los
valores por `SET LOCAL` —que sí admite interpolación— y leerlos dentro del bloque
con `current_setting`. Queda escrito aquí porque quien escriba el driver productivo
tropezará con lo mismo.

---

## 4. Los doce invariantes

Nueve exigen PostgreSQL real; tres son estáticos y corren siempre, incluso sin
runtime de contenedores.

| Caso | Invariante | Matriz FNC-DB-001 |
|---|---|---|
| `DBS-BLANK` | una base vacía llega a head y registra tres migraciones | DBS-01 |
| `DBS-REPLAY` | la segunda ejecución no aplica nada y no duplica historial | DBS-02 |
| `DBS-TAMPER` | editar una migración aplicada aborta por checksum antes de ejecutar | DBS-04 |
| `DBS-PARTIAL-FAILURE` | un error a mitad no deja objeto parcial ni fila de historial | DBS-07 |
| `DBS-PRIVILEGES` | migrator y runtime sin privilegios; el runtime no es propietario | DBS-06 |
| `DBS-RUNTIME-DENIAL` | el runtime no crea, altera, borra ni escribe historial | DBS-06 |
| `DBS-RLS` | A no lee ni escribe B; sin contexto no se ve ni se escribe nada | DBS-06 |
| `DBS-FORCE-RLS` | la tabla sensible conserva RLS habilitada **y forzada** | DBS-06 |
| `DBS-CONCURRENCY` | dos migradores concurrentes producen una sola aplicación | DBS-05 |
| `DBS-CHECKSUM-ORDER` | barajar el manifiesto no cambia el plan canónico *(estático)* | DBS-04 |
| `DBS-UNKNOWN-MIGRATION` | versión duplicada, hueco o fichero no manifestado se rechazan *(estático)* | DBS-01 |
| `DBS-CLEANUP-SCOPE` | todo argv apunta al proyecto del spike *(estático)* | DBS-05 |

`FORCE ROW LEVEL SECURITY` importa más de lo que parece: sin ella el propietario
queda exento y el aislamiento sería una ilusión que solo se sostiene mientras nadie
se conecte con el rol equivocado.

---

## 5. Resultado real de la ejecución

```
adapter: wsl · Docker 29.7.2 · postgres 17.11
outcomes: {"pass": 12}
failed: (ninguno) · not_executed: (ninguno)
```

**12 de 12 en verde contra PostgreSQL real.** Ninguna evidencia está simulada. Al
terminar, el runner ejecutó su propia limpieza y no quedó ni un contenedor, ni un
volumen, ni una red.

### La carrera de concurrencia, corregida

La primera versión lanzaba las tres versiones a la vez y V0002 fallaba
legítimamente porque V0001 aún no había commiteado. Eso no era una carrera: era
desordenar el plan. El caso correcto lanza **dos migradores por versión** antes de
pasar a la siguiente, y además exige que el segundo encuentre el trabajo ya hecho.
Sin esa segunda condición, un caso podría pasar sin que hubiese existido contienda
alguna. Resultado observado: 3 versiones, 3 aplicaciones, 3 contendientes que
encontraron el trabajo hecho.

---

## 6. Aislamiento del laboratorio

- Proyecto de Compose fijo: **`fincilia-db-spike`**. El runner comprueba el nombre en
  su constructor y se niega a construir ningún argv para otro proyecto.
- Fichero de Compose confinado al directorio del spike.
- **Ningún puerto publicado**: se entra por `compose exec`, así que un puerto abierto
  sería superficie sin uso.
- Red `internal: true`.
- Imagen: exactamente la misma referencia por digest ya adjudicada en
  `infra/local/compose.yaml`. No se introduce ningún artefacto nuevo.
- `down --volumes` solo se aplica al proyecto del spike, cuyo volumen es suyo.

### Adaptadores de runtime

En Linux y en CI, `docker` está en el PATH. En un Windows con Docker dentro de WSL
hay que atravesar `wsl -e`, y las rutas se traducen a `/mnt/<unidad>` de forma
determinista. Se prueban en orden con un argv de sondeo fijo y se usa el primero que
responde. Todo es lista `argv` con `shell=False`.

---

## 7. Qué NO prueba este spike

| Riesgo declarado | Por qué no es demostrable aquí |
|---|---|
| `GAP-DB-UPGRADE` (DBS-03) | no existe release anterior contra la que probar un upgrade |
| `GAP-DB-EXPAND-CONTRACT` (DBS-08) | exige dos versiones de la aplicación corriendo a la vez |
| `GAP-DB-TOOLING-LICENSE` | la revisión de licencia y cadena de suministro no la hace un spike |
| `GAP-DB-VOLUME` | nada aquí dice nada sobre tiempo de bloqueo ni volumen real |

V0003 ejecuta un paso **expand** —una columna nullable, sin default volátil—. El paso
**contract** pertenece a una release posterior y no se ejecuta: comprimir ambos en
una sola release es exactamente lo que rompe la compatibilidad N/N+1. La política
está declarada; la compatibilidad **no** está demostrada.

---

## 8. Manifiesto y checksums

`spikes/FNC-DB-002/MANIFEST.json` lista los 22 ficheros del laboratorio con su
SHA-256. Un `.sql` que no figure en el manifiesto es un fallo de validación, no un
extra inofensivo: podría ejecutarse sin que nadie hubiera revisado su contenido.

El validador también rechaza sentencias destructivas (`DROP`, `TRUNCATE`,
`DELETE FROM`) y sentencias que no pueden vivir en una transacción
(`CREATE INDEX CONCURRENTLY`, `VACUUM`, `CREATE DATABASE`), porque romperían la
atomicidad que este spike existe para demostrar.

---

## 9. CLI

```bash
python -m tools.migration_spike.cli validate
python -m tools.migration_spike.cli plan
python -m tools.migration_spike.cli run --suite all
python -m tools.migration_spike.cli report
```

| Comando | Qué hace | Exit |
|---|---|---|
| `validate` | estructura del contrato y del manifiesto | 0 / 1 |
| `plan` | plan canónico ordenado por versión; **jamás muta** | 0 / 1 |
| `run` | opera el laboratorio exacto | 0 ok · 1 fallo · 3 sin runtime |
| `report` | casos, gates y límites declarados; no inventa evidencia | 0 / 1 |

Si no hay runtime de contenedores, los nueve casos de PostgreSQL quedan
`not_executed` y el comando sale con 3. **Nada se simula**: un resultado inventado
sería peor que ninguno.

---

## 10. Límites honestos

1. Un spike verde prueba invariantes sobre un laboratorio minúsculo, no que el sistema real migre bien.
2. No selecciona herramienta y no acepta ADR-002.
3. No prueba volumen, rendimiento, tiempo de bloqueo, backup, restore ni replicación.
4. No demuestra compatibilidad N/N+1.
5. Que el runtime no pueda migrar aquí no dice nada sobre sus privilegios en producción.
6. El laboratorio es descartable: nada de lo que hay en él es infraestructura.

## 11. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-DB-TOOL` | Qué herramienta se adopta, con qué versión y digest fijados | Architecture |
| `UD-DB-NONTRANSACTIONAL` | Qué política rige las sentencias que no pueden vivir en una transacción | Database Migration Owner |
| `UD-DB-LOCK-KEY` | Qué espacio de claves de advisory lock se reserva para migraciones | Platform |
| `UD-DB-CONTRACT-CADENCE` | Cuántas releases deben pasar entre expand y contract | Architecture |
