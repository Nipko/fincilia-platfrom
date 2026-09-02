---
task_id: FNC-MAP-001
status: REVIEW_PENDING
base_sha: 1ce4e4c87e456d2c178d7b0d94c2ec3c36e8301e
tested_head_sha: 84f03ff2c8886d7863f1d1ca14636f53a3879166
ci_run: 33601151681
ci_status: success
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Data, Database, Security, Backend/Architecture, QA]
---

# Handoff FNC-MAP-001 — integridad de fuente del mapeo

## Resultado

Una version de mapeo solo puede referenciar evidencia recibida por la misma
fuente inmutable que la plantilla. La regla vive en PostgreSQL y se aplica al
alta y a cualquier intento posterior de reetiquetar la evidencia. Evitar la API
no evita el control.

La API traduce exclusivamente `ck_mapping_artifact_source` a una negativa 403
neutral. No revela la fuente real ni convierte otras violaciones de integridad
en autorizacion. La creacion incompatible revierte plantilla y version juntas.

## Cambios

- V0053 valida filas previas, crea `enforce_mapping_artifact_source`, revoca
  `PUBLIC` y protege cada `INSERT`.
- V0054 agrega el guard forward-only para cambios de empresa, plantilla o
  artefacto, sin modificar el checksum de V0053.
- `create_mapping` y `create_mapping_version` traducen solo la restriccion
  nominal a `MappingReferenceRefused`.
- La fixture vertical carga cada documento bajo la fuente que declara; ya no
  fabrica combinaciones que el producto debe rechazar.
- La prueba adversarial cubre API, bypass SQL, rollback, reutilizacion de
  plantilla y mutacion posterior bajo RLS.

## Evidencia

| Verificacion | Resultado |
|---|---|
| V0053 y V0054 apply + replay | `head: V0054`, segundo run sin cambios y checksums previos intactos |
| Focal fuente sobre PostgreSQL/MinIO | API 403, SQLSTATE 23514, `ck_mapping_artifact_source`, cero escritura parcial |
| Caso de conciliacion antes inestable | 3 corridas consecutivas, OK |
| `db.tests.test_p3_vertical` | 45, OK |
| API completa dentro de imagen | 188, OK |
| contratos de migracion | 66, OK |
| P3 + conciliacion con V0055 incluida | 48, OK |
| work graph / quality gate | 134 tareas sin huerfanos; `ok: true`, cero hallazgos |
| CI del codigo definitivo | run `33601151681`: success; ciclo integral, navegador y WCAG incluidos |

## Hallazgos de ejecucion

1. La fixture de conciliacion subia siempre por una fuente estable y luego
   creaba el mapeo con otra; esa incoherencia explicaba el fallo intermitente
   `MAP-SCHEMA-DRIFT`.
2. El primer guard cubria el alta, pero el permiso `UPDATE` necesario para
   validar dejaba un borde posterior. Se cerro con V0054, sin reescribir V0053.
3. Una primera repeticion local uso una imagen `migrate` anterior: ejecutaba el
   test nuevo pero no contenia la migracion nueva. Se reconstruyo expresamente;
   V0054 se aplico y el trigger real fue inspeccionado antes de declarar exito.
4. La asercion final consultaba con el migrador sin contexto bajo `FORCE RLS` y
   veia cero filas. Se corrigio fijando la empresa; el rollback real permanece.
5. El primer CI completo encontro doce fixtures canonicas que aun creaban
   evidencia legacy sin fuente. Se migraron al flujo actual con fuente declarada
   y la suite completa paso 412 pruebas contra PostgreSQL real.

## Riesgos y revisiones

- Data/Database debe revisar que fuente de recepcion y fuente de plantilla sean
  la misma frontera semantica para todas las versiones nuevas.
- Security/Architecture debe revisar neutralidad del 403, orden de triggers y
  que las funciones no sean `SECURITY DEFINER`.
- QA debe revisar los intentos de bypass y el aislamiento RLS.
- No se movio S1-READY, DRG-00, DRG-01 ni una decision humana. Solo se usaron
  datos sinteticos.

## Commits y rollback

1. `3b8a979` — guard de alta, API, fixture y prueba base.
2. `6c5d395` — fase, backlog y trazabilidad.
3. `42a9389` — guard forward-only de UPDATE.
4. `6ff14cc` — verificacion de rollback bajo la empresa RLS correcta.
5. `84f03ff` — fixtures canonicas ligadas a fuente y negativa cross-company no
   reveladora.

V0053/V0054 son forward-only. Revertir codigo y pruebas no retira triggers de
una base aplicada; una correccion operativa futura debe ser otra migracion
compensatoria. No existe dato financiero real que purgar.
