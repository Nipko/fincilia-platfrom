# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| HEAD | `053f4ff` — `feat(worker): FNC-DOC-002 perfilado real de documentos y cola persistente` |
| Remoto | empujado a `origin/claude/principal-dev` |
| Base de esta ejecución | `c2d7349` |
| Gate S1-READY | sigue `not_met`, y ninguna de estas tareas lo mueve |

---

## 1. Levantar el stack

Un solo comando, desde la raíz, con volúmenes vacíos o con datos:

```bash
sh infra/local/up.sh
```

Deja seis servicios **healthy**, la web en <http://127.0.0.1:53000> y la API en
<http://127.0.0.1:58080>. Se entra como `ana@demo.local` con la contraseña
sintética `fincilia-demo-only`.

El orden del script no es cosmético: infraestructura, migrar, sembrar, y sólo
después las aplicaciones. Un `docker compose up -d --wait` a secas sobre una base
vacía **falla a propósito**, porque el worker prefiere salir con `1` a declararse
sano sin poder trabajar y `/health/ready` devuelve 503 nombrando el esquema.

---

## 2. Último comando verde

Ejecutado desde volúmenes vacíos, en este orden, todo en verde:

| Comando | Resultado |
|---|---|
| `sh infra/local/up.sh` | 6/6 healthy, `schema: head V0004` |
| `… run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests` | **14 OK** |
| `… --profile migrate run --rm migrate python -m unittest discover -s /app/db/tests -t /app` | **72 OK** |
| `… run --rm --no-deps api python -m unittest discover -s /app/tests -t /app/tests` | **61 OK** |
| `python -m unittest discover -s packages/contracts/python -t packages/contracts/python` | **93 OK** |
| suite del repositorio (lista enumerada en `ci.yml`) | **787 OK** |
| `docker build --target build -f apps/web/Dockerfile …` + `npm run lint` | typecheck y lint limpios |
| `quality_gate`, `local_stack`, `runtime_config`, `migration_readiness`, `workspace_contract` | exit 0 |
| `tools.supply_chain.cli validate` | exit 1 con **4 hallazgos bloqueantes preexistentes** (DRG-00: SBOM, firma, attestation, procedencia) |

---

## 3. Qué funciona hoy, extremo a extremo

Verificado en un navegador real, no sólo por API:

1. `ana@demo.local` entra; el token nunca llega al navegador (cookie `httpOnly`).
2. Ve una firma y sus dos empresas de demo. Beto sólo ve una: la que le
   concedieron.
3. Abre una empresa y ve sus roles, los permisos que **el servidor** deriva, sus
   documentos y —sólo si el rol incluye `audit.read`— la auditoría.
4. Sube un CSV. Se decide el tipo por los primeros bytes, se corta por tamaño
   mientras se lee, y se calcula la huella.
5. Si trae una tarjeta que pasa Luhn o una credencial, queda en `quarantine` y
   **no** se encola. Si está limpio, va a `raw` y se encola.
6. El worker lo toma, lo perfila y guarda la forma: separador, codificación,
   filas, y el tipo de cada columna, con las ambigüedades marcadas para que las
   resuelva una persona.
7. Todo lo anterior deja rastro en `audit_event`, incluidas las denegaciones.

---

## 4. La siguiente rebanada, exacta

**P3 — mapeo con vista previa y publicación de movimientos canónicos.**

Es lo que sigue en el recorrido del mandato y lo único que separa «evidencia
almacenada y perfilada» de «movimientos sobre los que conciliar».

1. **`V0005`**: `column_mapping` (por empresa y por artefacto: columna origen →
   campo canónico, formato de fecha y de decimal elegidos, versión) y
   `canonical_movement` (fecha, descripción, importe `numeric(38,12)`, moneda
   explícita, dirección, referencia, `artifact_id`, `row_number`). RLS forzada en
   ambas. `canonical_movement` **inmutable** para el rol runtime, igual que
   `source_artifact`: `GRANT SELECT, INSERT` y `REVOKE UPDATE, DELETE`.
2. **`fincilia_contracts/mapping.py`**: aplicar un mapeo a una fila y devolver un
   movimiento o un rechazo con motivo. Dinero con `parse_money` —que rechaza
   `float`, no lo convierte— y moneda siempre explícita. Una fila que no encaja
   **no se publica**; se cuenta y se explica.
3. **Vista previa antes de publicar**: la vista previa sí lleva valores, y por eso
   va por un endpoint aparte, bajo `document.read`, y **no** se guarda en el
   perfil. Las primeras N filas ya transformadas, con el recuento de rechazos.
4. **Publicación**: `dataset.map` para proponer el mapeo, y la publicación como
   una transacción sobre el artefacto entero. Republicar el mismo artefacto con
   el mismo mapeo no duplica movimientos: la unicidad va por
   `(artifact_id, row_number)`.
5. **Web**: pantalla de mapeo con la vista previa, los tipos que sugirió el perfil
   y las columnas ambiguas exigiendo elección explícita.

Después de eso, P4 es la conciliación determinista: candidatos por fecha, importe
y referencia, propuesta con `match.propose`, confirmación con `match.confirm`, y
la segregación de funciones que ya está en la matriz de permisos —Ana propone,
Beto confirma— comprobada sobre el mismo objeto, no sólo sobre el rol.

---

## 5. Lo que sigue pendiente y no lo mueve nada de esto

- **Cuatro huecos de cadena de suministro** (SBOM, firma, attestation,
  procedencia), declarados y bloqueantes de DRG-00. Owner: Security.
- **Seis alcances OCI sin monitor de actualizaciones**, visibles como
  `SUP-UPDATES-UNMONITORED`. Se mantienen así a propósito: Dependabot `docker` no
  reconoce los `compose.yaml` sin Dockerfile, y no se han vuelto a añadir
  entradas ficticias para poner el modelo en verde.
- **`FNC-DB-004`** sigue `proposed`. Sus invariantes de idempotencia están hoy
  cubiertas por código de producto (`UNIQUE (company_id, content_sha256)` y las
  pruebas de subida), pero la tarjeta no se ha cerrado.
- **Decisiones humanas intactas**: ADR-002 sigue `proposed`, no hay herramienta de
  migración seleccionada, `product_migrations_allowed` sigue `false` y
  `product_code_allowed` sigue `false`. Lo que se habilitó es un alcance aparte y
  explícito, `local_build`, que enumera en el propio contrato todo lo que **no**
  implica.
- **`apps/mobile`** sigue siendo un scaffold vacío.
