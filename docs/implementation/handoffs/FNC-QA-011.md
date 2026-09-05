---
task_id: FNC-QA-011
status: REVIEW_PENDING
base_sha: c16e60d
reservation_sha: a216721
initial_isolation_sha: 88781f7
final_isolation_sha: d4a3c25
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [QA, Database]
---

# Handoff FNC-QA-011 — aislamiento determinista PostgreSQL

## Resultado

La suite PostgreSQL integral puede ejecutarse sobre un volumen recién migrado y
repetirse sobre ese mismo volumen sin depender del orden accidental de otras
suites ni de consumidores de aplicación concurrentes. La segunda corrida
ejecutó 431 pruebas correctamente, con una omisión explícita por diseño.

El arnés vertical drena los trabajos globales hasta quiescencia con un límite
finito y falla si la cola no converge. Las lecturas de auditoría validan primero
la respuesta HTTP. Ningún cambio alteró producto, migraciones, RLS, permisos o
semántica financiera.

## Defectos demostrados y corregidos

1. El protocolo de despacho conserva evidencia terminal para Ana y sus intentos
   sólo son visibles al rol de despacho bajo `FORCE RLS`. La suite operativa
   intentaba reutilizar y limpiar ese mismo sujeto, por lo que la FK impedía
   borrar una entrega cuyo intento era deliberadamente invisible. El fixture de
   recordatorios usa ahora a Sofia como sujeto independiente y conserva filtros
   por empresa y sujeto sin borrar la evidencia de otra suite.
2. El caso de Checkout deshabilitado enviaba una petición sin cuerpo y medía
   validación HTTP 422 en vez del cierre seguro 503. Ahora suministra un contrato
   válido antes de comprobar el proveedor apagado.
3. El reset vacío esperaba dos versiones legales históricas aunque V0056/V0057
   materializan seis y activan las dos versiones inglesas vigentes. La
   postcondición comprueba el catálogo completo, las dos activas exactas y que no
   exista otra versión activa.
4. El recorrido vertical podía observar trabajos creados por un worker externo.
   La evidencia integral se obtuvo con API, web y worker detenidos, dejando sólo
   PostgreSQL, object storage y Valkey como dependencias reales del arnés.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `python -m unittest db.tests.test_operational_reminders` | 3 pruebas, OK; 0,891 s |
| `python -m unittest discover -s /app/db/tests -t /app` | 431 pruebas, OK; 1 omitida; 144,977 s |
| Repetición sobre el mismo volumen persistente | OK; sin residuos ni dependencia de orden |
| Prueba de escala incluida | 100.000 movimientos; 46,7 s total; 274,4 MiB pico |
| `python -m unittest tools.local_stack.test_validate` | 41 pruebas, OK |
| `sh -n infra/local/reset-empty.sh` | OK |
| Reset completo desde cero | V0001–V0066; tablas de producto y object zones vacías |
| Readiness local posterior | PostgreSQL, MinIO, Valkey, API, worker y web sanos |
| Quality gate sobre índice | `ok: true`, cero hallazgos |

Todos los datos usados fueron sintéticos. El reset eliminó exclusivamente
`fincilia_local_pgdata` y `fincilia_local_objectdata` tras validar proyecto,
labels y rutas exactas; no tocó volúmenes ajenos.

## Revisión, límites y rollback

QA debe revisar la separación de fixtures, el límite de quiescencia y las
postcondiciones del reset. Database debe confirmar el orden referencial y que la
solución preserva `FORCE RLS`. El implementador y `FOUNDER-01` no cuentan como
revisores independientes; por eso el estado permanece `REVIEW_PENDING`.

S1-READY, DRG-00 y DRG-01 no cambian. No se autoriza información financiera
real ni operación piloto. El rollback revierte `d4a3c25` y `88781f7`; no exige
migración. Para recuperar un entorno local vacío después del rollback se
reaplican migraciones sobre los dos volúmenes adjudicados.

## Rutas liberadas

Las tres suites PostgreSQL, el reset local, su validador y pruebas, ficha,
handoff y registros centrales quedan liberados.
