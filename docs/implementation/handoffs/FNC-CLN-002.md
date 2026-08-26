---
task_id: FNC-CLN-002
status: REVIEW_PENDING
base_sha: 97d9122
reservation_sha: 56ca1f1
backend_schema_sha: f6b6b91
web_sha: f882c2f
integration_sha: d90d6cb
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Database, Product, QA]
---

# Handoff FNC-CLN-002 — aplicación reproducible de correcciones

## Resultado entregado

Una persona con `dataset.map` puede aplicar en bloque las correcciones aprobadas
de un dataset validado. La operación crea otra versión `validated`; nunca muta el
dataset base, no publica, no concilia y no cierra. El historial enlaza versión
base y resultante y deja el conjunto exacto de overlays en un manifiesto sin
copiar valores financieros.

La web revalida documento, dataset, estado y revisiones server-side. Solo ofrece
la aplicación cuando existe al menos una propuesta aprobada y no queda ninguna
pendiente. Después muestra el resultado y permite abrir la nueva versión.

## Persistencia, seguridad y reproducibilidad

- V0023 agrega `supersedes_dataset_version_id`, los ledgers append-only
  `field_overlay_application`/`field_overlay_application_item`, RLS forzada,
  claves company-scoped y el tipo de trabajo `overlay_apply`.
- V0024 agrega `record_overlay_application_run`, función `SECURITY DEFINER` de
  `fincilia_dispatch`. Revalida capability durable, versión de autorización,
  sujeto, membresía, engagement, grant, revocación, empresa y artefacto antes de
  registrar un trabajo síncrono completado. `PUBLIC` está revocado y solo
  `fincilia_app` recibe `EXECUTE`.
- Un advisory lock por empresa/dataset y una unicidad por reproducción dejan una
  sola versión bajo competencia. Los demás invocadores reciben replay de la
  misma versión.
- Cada movimiento y source record se clona con identificadores nuevos; monto usa
  `Decimal`, se recalculan field digest y dedupe fingerprint, y los anteriores
  permanecen inmutables.
- El manifiesto fija base, mapping, release, esquema, artefacto, locale, timezone,
  semilla, overlay set ordenado y digests. No contiene el valor propuesto.
- Cada campo aplicado agrega `lineage_row_override` y un item digest-only que
  conecta movimiento base, movimiento resultante y overlay aprobado.
- La ruta API usa savepoint: un fallo revierte toda fila funcional ya escrita y
  la transacción exterior conserva el evento de auditoría de la negativa.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| Migración PostgreSQL 17 real | V0023/V0024 aplicadas; segunda pasada head V0024, `mutated: false` |
| `db.tests.test_correction_application` | 4 pruebas, OK, PostgreSQL + API + MinIO reales |
| API completa en imagen | 115 pruebas, OK |
| Web lint + TypeScript | OK |
| Web unitarias | 174 pruebas en 28 ficheros, OK |
| Web build Next production | OK; `/mapeo` dinámica |
| Migration readiness | 64 pruebas, OK; validador del repositorio OK |
| Work graph y quality gate | OK; quality gate sobre cada índice funcional |
| Navegador integrado | Sofia propone → Beto revisa → Sofia aplica → abre versión derivada |

La prueba visual produjo la versión sintética
`1ef0e390-6dbc-4beb-81ba-12f7631d8d1f`. La fila corregida muestra
`1.234,57 COP`, mientras la versión base
`23012abc-9c13-47fc-84e2-d100724f9ae5` conserva `1.234,56 COP`. La consulta
directa de evidencia confirmó `supersedes_dataset_version_id`, un overlay en el
manifiesto y ausencia del texto `1234.57` dentro de `deterministic_config`.

## Negativas y concurrencia cubiertas

- empresa ajena y recurso invisible;
- rol sin `dataset.map`;
- dataset no validado, cero aprobadas o revisión pendiente;
- digest base o digest propuesto con drift;
- orden de fechas inválido;
- paso de linaje ausente;
- replay y dos aplicaciones concurrentes;
- UPDATE/DELETE negados sobre ambos ledgers;
- publicación posterior por revisor independiente, nunca automática.

## Hallazgos durante la ejecución

1. Una excepción de dominio después de escribir filas parciales podía dejar que
   la sesión exterior confirmara esas filas. El savepoint de la ruta revierte el
   dominio y conserva solamente la auditoría de la negativa.
2. El validador de migraciones confundía un `REVOKE` partido en dos líneas con
   una función abierta a `PUBLIC`. Ahora normaliza whitespace y tiene prueba de
   regresión; no se editó ninguna migración aplicada.
3. No todos los targets que FNC-CLN-001 permite proponer tienen hoy un paso
   publicado en cada plan de transformación histórico. CLN-002 falla cerrado con
   `correction-lineage-step-missing`; no inventa linaje ni reutiliza otro campo.
4. El render posterior a aplicar conserva la URL base y muestra el overlay como
   aplicado con enlace explícito. La versión resultante no hereda propuestas
   pendientes y muestra el valor corregido.

## Revisión pendiente y límites

ADR-026 continúa `Proposed`. Accounting debe revisar semántica y recálculo;
Security y Database, V0023/V0024, RLS y la función privilegiada; Product y QA,
lenguaje, navegación y el fallo cerrado de targets sin plan. El implementador y
`FOUNDER-01` no cuentan como revisores independientes.

DB-G03 sigue pendiente para todas las funciones `SECURITY DEFINER`. Esta entrega
no supera S1-READY, DRG-00 ni DRG-01; no habilita datos reales, IA, móvil,
auto-match, cierre, conectores ni publicación automática.

Trabajo siguiente recomendado: decidir si se restringen los targets de
corrección al conjunto realmente materializado por cada plan o se versiona el
plan para incluir posted date, value date, accounting date, currency y direction
antes de permitir aplicarlos.

## Rollback

Retirar primero formulario/acción web y endpoint. Después de existir ledgers,
la reversión normal es forward-only: deshabilitar nuevas aplicaciones y conservar
lectura, manifiestos y linaje. Antes de cualquier dato permitido —hoy todo es
sintético— una migración de retirada revisada puede eliminar función, grants,
tablas y columna en orden inverso. Nunca se reescriben V0023/V0024 aplicadas.

## Rutas liberadas

V0023/V0024, pruebas PostgreSQL, dominio/ruta/pruebas API, cliente/acciones/
formularios/página/pruebas web, declaración de migration tooling, validador de
migraciones y registros de FNC-CLN-002.
