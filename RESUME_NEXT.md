# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Base de esta ejecución | `cda931a` |
| Migraciones añadidas | `V0008` — `V0001`–`V0007` con su checksum intacto |
| Permiso nuevo | `dataset.publish`, segregado de `dataset.map` |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |

---

## 1. Levantar el stack

```bash
sh infra/local/up.sh
```

> **Si tu volumen local es anterior a `V0005`**, recréalo primero con
> `docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes`.
> Los roles nuevos los crea el bootstrap, que sólo corre sobre un volumen vacío, y
> la migración se detiene diciéndolo en vez de conceder privilegios a medias.

Deja seis servicios healthy y la web en <http://127.0.0.1:53000>.

---

## 2. Qué hay ahora: la vertical de P3, entera

El detalle —permisos, estados, linaje, privilegios y divergencias declaradas—
está en [el handoff](docs/implementation/handoffs/FNC-P3.md).

De unos bytes a un importe publicado que se puede auditar hasta la celda:

```
subida -> cuarentena -> escaneo -> raw -> extracción -> raw_record
                                                           |
                                    mapeo (versión + decisiones)
                                                           v
                    dataset_version -> source_record -> canonical_movement
                            |                                  |
                            |          lineage_node / lineage_edge
                            v
                  reproducibility_manifest
```

| Rebanada | Qué aterrizó |
|---|---|
| **P3.1** | `V0008`: trece tablas company-scoped con RLS forzada, claves ajenas compuestas, `engine_release` global y versionado, importe `numeric(38,12)` siempre positivo, dirección explícita, tres fechas separadas y referencia con índice y **no** con UNIQUE |
| **P3.2** | extracción fiel de CSV con tramo de bytes por registro y ordinal de campo por celda; vista previa paginada por endpoint propio con `dataset.map` |
| **P3.3** | `draft → validated → published`, bloqueo por ambigüedad, drift y mapeo en borrador; preparación transaccional; publicación segregada e idempotente |
| **P3.4** | cuatro vistas —Original, Extracción, Mapping, Canónico— con selector visual de columnas, formularios de decisión con motivo obligatorio, y navegación de un importe hasta su celda |

### Lo probado, y contra qué

**55 pruebas nuevas de P3** (`TST_P3_001`–`TST_P3_055`), todas contra PostgreSQL
y MinIO reales, más 27 unitarias de extracción y 4 de permisos:

- que quien preparó no puede publicar, comprobado desde el `CHECK` de la base y
  desde la API;
- que cuatro publicaciones simultáneas sellan la versión una vez y no duplican un
  movimiento;
- que tres preparaciones simultáneas producen un solo dataset;
- que los bytes que dice el localizador **son** la fila;
- que el rastro de auditoría de una vista previa cuenta filas y no cita ninguna;
- que un dataset de otra empresa es indistinguible de uno que no existe.

---

## 3. Tres cosas que costaron una vuelta

Ninguna se vio revisando; las tres aparecieron **ejecutando**.

**El ordinal no puede contar líneas.** Un campo entrecomillado con un salto de
línea dentro desplaza cada referencia posterior. Se cuentan registros, y el tramo
de bytes sale de las líneas que el lector CSV consumió para cada uno.

**`utf-8-sig` decodifica igual de bien un fichero sin marca de orden**, así que el
nombre del códec no dice si había marca. Lo dice el fichero, y hay que mirarlo: si
no, los tres bytes se cuentan de más y todos los tramos quedan desplazados.

**La comprobación de drift no se podía alcanzar.** Una versión de mapeo estaba
atada a un artefacto, así que el perfil comparado era siempre el suyo y el digest
nunca cambiaba. Pero una plantilla que no sirve para el extracto del mes
siguiente no es una plantilla. Ahora lo que decide es la huella del esquema.

---

## 4. La siguiente rebanada, exacta

**No hay alta de cuentas ni de fuentes en el producto.** `financial_account` y
`data_source` existen, tienen RLS y se leen por API, pero las únicas filas que hay
las siembra el entorno local. La pantalla de mapeo elige de esa lista; crear una
cuenta nueva hoy exige tocar la semilla. Es la carencia que más se nota al usarlo.

Después, y por este orden:

1. **Exportación del dataset publicado.** El mandato de P3 no la pedía, pero un
   conjunto canónico que no se puede sacar obliga a mirarlo por pantalla.
2. **El camino de linaje completo**, si alguien aprueba el coste. Hoy hay dos
   nodos y una arista tipada por campo; el contrato describe cinco saltos. La
   divergencia está declarada en el handoff, sección 7.
3. **`accounting_date`**, que hoy queda nula: asignar periodo contable es una
   decisión de cierre, y P3 no cierra.
4. **Formatos que no son CSV.** Un libro de cálculo sigue quedándose en
   cuarentena con `no_scanner_for_format`, y eso es correcto: prometer que está
   soportado sería peor que decir que no lo está.

Nada de auto-match, conciliación, fraude por ML, cierre ni IA autoritativa.

---

## 5. Lo que sigue esperando a una persona

Ninguno de estos gates se ha movido, y ninguna decisión humana se ha marcado como
aceptada.

- **`engine_release` sin aprobar.** La versión con la que publica el entorno local
  nace `draft`. Aprobarla es de `human_platform_owner` y exige `approval_ref`,
  `result_diff_report` y revisión independiente. Para datos sintéticos no
  bloquea; para producción sí.
- **La divergencia del camino de linaje** (handoff, sección 7) no está aprobada.
- **DB-G03**: cuatro funciones `SECURITY DEFINER` declaradas, con dueño acotado y
  `human_review_state: pending`.
- **DRG-01**: la excepción de RLS de `dispatch_pointer` sigue ampliada con
  `available_at`.
- **S-01 / TM-005**: detección de PAN antes de `raw`. Sin resolver; lo que hay es
  que no se promueve lo que no se ha inspeccionado.
- **ADR-002**: sigue `proposed`, sin herramienta seleccionada.
- **`retry_policy_contract`**: declara trece campos, incluidos `owner` y
  `reviewer` independientes. Existe un `max_attempts` con valor por defecto local,
  y los dos nombres no se han inventado.
- Cuatro huecos de cadena de suministro (SBOM, firma, attestation, procedencia) y
  seis alcances OCI sin monitor, como estaban.
