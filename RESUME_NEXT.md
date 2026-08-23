# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Base de esta ejecución | `47652f1` |
| Migraciones añadidas | `V0005`, `V0006`, `V0007` — `V0001`–`V0004` con su checksum intacto |
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

Deja seis servicios healthy y la web en <http://127.0.0.1:53000>. Se entra como
`ana@demo.local` con la contraseña sintética `fincilia-demo-only`.

---

## 2. Qué se corrigió en esta ejecución (FNC-P2.1)

El detalle, con la matriz de privilegios y las divergencias declaradas, está en
[el handoff](docs/implementation/handoffs/FNC-P2.1.md).

| Rebanada | Qué estaba roto |
|---|---|
| **A1** CI | las pruebas documentales corrían sin almacén de objetos; el `-f` del lint de la web no resolvía desde el `working-directory` del job |
| **A2** despachador | un puntero podía nombrar el trabajo de otra empresa; API y worker compartían rol |
| **A3** arriendos | un worker que moría dejaba el trabajo en `running` sin puntero: invisible para siempre |
| **A4** privilegios | el rol de la API podía reescribir el hash de contraseña de cualquier sujeto |
| **A5** cuarentena | un PDF llegaba a la zona de evidencia sin que nadie leyera su contenido |
| **A6** idempotencia | dos subidas simultáneas creaban dos filas o devolvían 500 |

Tres defectos adicionales aparecieron **ejecutando**, no revisando: los `REVOKE …
FROM PUBLIC` corrían después de ceder la propiedad y sólo avisaban, dejando las
cuatro funciones abiertas a `PUBLIC`; los manejadores `async def` con E/S
bloqueante mataban dieciséis subidas simultáneas en `PoolTimeout`; y la lista de
tipos de trabajo vive en tres sitios que hay que ampliar juntos.

---

## 3. Estado de la Fase B (P3)

**No empezada.** La Fase A consumió la ejecución entera, y el mandato pide no
continuar hasta tenerla verde. No hay código de P3 en la rama: ni `column_mapping`,
ni `canonical_movement`, ni preview, ni pantalla de mapeo.

Lo que ya está preparado para ella:

- `V0008` es la siguiente versión libre.
- El perfilador ya marca las columnas ambiguas (`ambiguous_numeric`,
  `ambiguous_date`) y las expone en `needs_decision`, que es exactamente lo que
  debe bloquear una publicación hasta que una persona elija.
- `packages/contracts/python/fincilia_contracts/money.py` ya rechaza `float` en vez
  de convertirlo, y `format_money` emite punto fijo.
- La cola, los privilegios y la auditoría ya soportan un tipo de trabajo nuevo sin
  tocar el despachador: basta añadirlo a las **tres** listas (restricción del
  trabajo, restricción del puntero, validación de `enqueue_processing_run`), y hay
  una prueba que comprueba que coinciden.

### La siguiente rebanada, exacta

**`V0008` — `column_mapping` y `canonical_movement`.**

1. `column_mapping` versionado y company-scoped, con estados
   `draft → validated → published`, autor y marcas de tiempo. RLS forzada.
2. `canonical_movement` **inmutable** para el runtime, igual que `source_artifact`:
   `GRANT SELECT, INSERT` y `REVOKE UPDATE, DELETE`. Importe `numeric(38,12)`,
   moneda ISO explícita, dirección `credit`/`debit` explícita —nunca inferida del
   signo—, fechas separadas cuando apliquen, referencia original y normalizada
   pero **nunca** como unicidad dura.
3. `source_record_id` y linaje obligatorio hasta fichero, fila, columna y celda.
4. Publicación idempotente por `(dataset, mapping, engine release)`; unicidad por
   `(artifact_id, row_number)`. Reprocesar crea una versión nueva y **no**
   sobrescribe movimientos históricos.
5. Cualquier ambigüedad de fecha, decimal, locale, signo o columna **bloquea** la
   publicación hasta que una persona la resuelva.
6. La vista previa sí lleva valores, y por eso va por un endpoint aparte, con
   permiso más estricto que el perfil estadístico, con límites y paginación, y sin
   persistirse en logs ni métricas.
7. SoD: el preparador propone, quien tiene `close.approve`/`match.confirm` publica.

Nada de auto-match, conciliación, fraude por ML, cierre ni IA autoritativa.

---

## 4. Lo que sigue esperando a una persona

Ninguno de estos gates se ha movido, y ninguna decisión humana se ha marcado como
aceptada.

- **DB-G03**: cuatro funciones `SECURITY DEFINER` declaradas, con dueño acotado y
  `human_review_state: pending`. `production_policy.security_definer` sigue
  diciendo `forbidden_without_review`.
- **DRG-01**: se amplió la excepción de RLS de `dispatch_pointer` con
  `available_at`. Es una marca de tiempo, pero amplía una excepción de Security.
- **S-01 / TM-005**: detección de PAN antes de `raw`. Esta ejecución **no lo
  resuelve**; sólo deja de promover lo que no ha inspeccionado.
- **ADR-002**: sigue `proposed`. Sin herramienta seleccionada y con
  `product_migrations_allowed` en `false`.
- **`retry_policy_contract`** no está satisfecho: declara trece campos, incluidos
  `owner` y `reviewer` independientes. Lo que existe es un `max_attempts` con
  valor por defecto local. No se han inventado los dos nombres.
- Cuatro huecos de cadena de suministro (SBOM, firma, attestation, procedencia) y
  seis alcances OCI sin monitor, como estaban.
