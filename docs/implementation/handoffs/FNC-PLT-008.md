# Handoff — FNC-PLT-008: stack local de producto ejecutable

| Campo | Valor |
|---|---|
| Tarea | FNC-PLT-008 |
| Estado | **`REVIEW_PENDING`** |
| Base | `9edfd02`, rama `claude/principal-dev` |
| Owner | Platform |
| Revisores independientes | Security, QA |
| Gate | S1-READY — sigue `not_met` |

---

## 1. Lo que ya funciona

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local up -d --wait
```

Exit `0` con volúmenes limpios. Los cinco servicios quedan **healthy**:

```
api           Up (healthy)   127.0.0.1:58080->8000/tcp
objectstore   Up (healthy)   127.0.0.1:59000->9000/tcp, 127.0.0.1:59001->9001/tcp
postgres      Up (healthy)
valkey        Up (healthy)
worker        Up (healthy)
```

Verificado desde el host, tanto WSL como Windows:

```json
GET /health/ready → 200
{"status":"ready","dependencies":[
  {"name":"postgresql","status":"up","detail":"fincilia_app@17.11","latency_ms":14},
  {"name":"valkey","status":"up","detail":"pong","latency_ms":1},
  {"name":"object_storage","status":"up","detail":"4 buckets","latency_ms":209}]}
```

El worker registra `dependencies ready: postgresql=up, valkey=up, object_storage=up`
y solo entonces publica latido. Si no alcanza alguna en 30 s, **sale con 1**: no se
declara sano un proceso que no puede trabajar.

## 2. Qué se construyó

| Ruta | Contenido |
|---|---|
| `packages/contracts/python/fincilia_contracts/` | dinero `Decimal` exacto, moneda explícita, contexto de tenancy, roles/permisos/SoD, errores RFC 7807 |
| `packages/platform/python/fincilia_platform/` | configuración tipada por servicio y sondas de dependencias |
| `apps/api/` | FastAPI, `/health/live`, `/health/ready`, `/health/config`, Dockerfile, lock con hashes |
| `workers/document/` | worker aislado con espera de dependencias y latido, Dockerfile, lock propio |
| `infra/local/compose.yaml` | cinco servicios, dos redes, healthchecks reales |

Las 22 pruebas de contratos incluyen una de **acuerdo** entre el dinero de producto y
la especificación ejecutable de `tools/completeness_engine`. Tener dos
implementaciones solo sirve si se comprueba que coinciden.

## 3. Cuatro hallazgos reales

**Docker ignora la publicación de puertos en una red `internal`.** El
`127.0.0.1:55430:5432` que declaraba `infra/local/compose.yaml` desde FNC-PLT-002
**nunca funcionó**; nadie lo notó porque CI siempre entra por dentro de la red. Se
resolvió con dos redes: `private` (`internal: true`, sin salida) para todo, y `edge`
solo para `api` y `objectstore`. La base y la caché **pierden** su puerto de
conveniencia a propósito: recuperarlo exigiría darles salida a internet.

**Un secreto en un servicio que no lo usa.** La primera configuración compartida
exigía `FINCILIA_AUTH_SIGNING_KEY` también al worker, que no emite ni valida tokens.
Ahora hay `ApiSettings` (la exige) y `WorkerSettings` (la **rechaza**).

**`Decimal(0).quantize()` serializa como `0E-12`.** Ya corregido en FNC-DOM-006; el
dinero de producto usa la misma forma canónica en punto fijo, y una prueba lo fija.

**El baseline de supply chain detectó su propio hueco.** Al añadir Dockerfiles y
`requirements.txt`, reportó siete `SUP-SOURCE-NOT-INVENTORIED` y un
`SUP-YAML-UNSCANNABLE`. En vez de silenciarlo:

- se añadieron extractores de `FROM` de Dockerfile y de manifest/lock de Python;
- se añadió `SUP-LOCKFILE-NO-HASHES`: fijar la versión sin fijar los bytes deja
  abierta la sustitución de la rueda en un mirror;
- se retiró el ancla YAML de `compose.yaml`, porque un fichero de infraestructura que
  un escáner de seguridad no puede leer es mal negocio;
- se corrigió `OCI_DIGEST`, que rechazaba `python@sha256:…` — una referencia **sin
  tag es más fija**, no menos;
- se dejó de exigir lockfile a un paquete interno con cero dependencias.

## 4. Decisiones de construcción

- **Lockfiles resueltos dentro del contenedor Linux/3.12**, no en Windows: `psycopg`
  trae ruedas distintas por plataforma y un lock resuelto en la máquina del
  desarrollador instalaría otra cosa en la imagen. Con `--generate-hashes` y
  `pip install --require-hashes`.
- **Toda imagen fijada por digest**, incluidas las bases de los Dockerfiles.
- **Los contenedores no corren como root** y van con `read_only: true` más `tmpfs`
  donde hace falta escribir.
- **Las zonas de evidencia las crea la API al arrancar**, solo en `local` y de forma
  idempotente. Un contenedor de un solo uso obligaba a `up --wait` a distinguir
  «terminó» de «se cayó».
- **`fincilia-raw` tiene versionado activado**: la evidencia que sostiene un cierre no
  puede cambiarse por una sobreescritura silenciosa.

## 5. Verificación

| Comando | Exit | Resultado |
|---|---:|---|
| `docker compose … up -d --wait` | 0 | 5/5 healthy desde volúmenes limpios |
| `curl /health/live`, `/ready`, `/config` | 200 | desde WSL y desde Windows |
| API tests dentro de la imagen | 0 | **21 pruebas, OK** |
| `unittest discover packages/contracts/python` | 0 | **22 pruebas, OK** |
| `python -m tools.local_stack.validate` | 0 | contrato del stack |
| `python -m unittest tools.local_stack.test_validate` | 0 | **16 pruebas** (antes 9) |
| `python -m unittest tools.supply_chain.test_validate` | 0 | **73 pruebas** (antes 68) |
| `python -m tools.runtime_config.validate` | 0 | 24 variables, `.env.example` alineado |
| `python -m tools.quality_gate.cli` | 0 | política de repositorio sobre el índice |
| Suite completa del repositorio | 0 | **1205 pruebas, OK** |

## 6. Lo que todavía no existe

- **No hay web.** El recorrido de usuario llega hasta la API.
- **No hay migraciones ni esquema de producto**: `postgres` arranca con el bootstrap
  de FNC-PLT-002 y nada más. Identidad, tenancy y RLS son P1.
- **No hay upload ni cuarentena**: las zonas existen, vacías. Es P2.
- **El worker no procesa nada todavía**: espera dependencias y late. Es deliberado que
  no sea un mock que devuelve constantes.

## 7. Riesgos y gaps que permanecen

| Riesgo | Owner | Estado |
|---|---|---|
| Procedencia de cadena de suministro no demostrada (SBOM, firma, attestation) | Security | 4 gaps declarados, DRG-00 |
| Cuatro alcances OCI de Compose sin monitor de actualizaciones | Platform | `SUP-UPDATES-UNMONITORED`, sin entradas ficticias |
| `apps/web` y `apps/mobile` sin ecosistema npm todavía | Platform | aparecerán al construir la web |

`real_data_enabled`, `ai_gateway_enabled` y `payments_enabled` siguen apagados **por
contrato**: ponerlos en `true` hace fallar el arranque, no imprime una advertencia.

## 8. Rollback

Eliminar `apps/api/`, `workers/document/src|Dockerfile|requirements*`,
`packages/contracts/`, `packages/platform/`, `docs/platform/LOCAL_DEVELOPMENT.md` y
revertir `infra/local/compose.yaml`, `.env.example`, `runtime-config.json`,
`dependabot.yml`, `ci.yml` y los tres validadores tocados. El stack volvería al
contrato de dos contenedores de FNC-PLT-002.

## 9. Siguiente

**P1 — identidad, tenancy y autorización real**: migraciones de `user`, `subject`,
`firm`, `company`, `engagement`, membresías, roles y `authorization_version`; RLS con
`FORCE ROW LEVEL SECURITY` y rol runtime no propietario; proveedor de identidad local
tras interfaz; y pruebas de aislamiento cruzado contra PostgreSQL real.
