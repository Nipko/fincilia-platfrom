# Handoff — FNC-DB-002: spike de invariantes de migración SQL-first

| Campo | Valor |
|---|---|
| Tarea | FNC-DB-002 |
| Estado | **`REVIEW_PENDING`** |
| Base declarada | `48b21d1` — entregada por el Integration Steward, **no verificada** |
| Verificación de la base | No se usó Git en ninguna forma |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | Database Migration Owner |
| Revisores independientes | Architecture, Security, QA |
| Gate | ADR-002-MIGRATIONS — `not_met` |

---

## 1. Rutas creadas

| Ruta | Acción |
|---|---|
| `docs/database/migration-spike.json` | creada — contrato autoritativo |
| `docs/database/MIGRATION_SPIKE.md` | creada — documentación |
| `spikes/FNC-DB-002/compose.yaml` | creada — laboratorio, proyecto `fincilia-db-spike` |
| `spikes/FNC-DB-002/db/init/001_spike_bootstrap.sql` | creada — tres roles separados |
| `spikes/FNC-DB-002/sql/apply_one.sql` | creada — driver de aplicación |
| `spikes/FNC-DB-002/sql/migrations/V0001..V0003` | creadas — migraciones de laboratorio |
| `spikes/FNC-DB-002/sql/cases/**` | creadas — 17 sondas y denegaciones |
| `spikes/FNC-DB-002/MANIFEST.json` | creada — 22 ficheros con SHA-256 |
| `tools/migration_spike/{__init__,manifest,contract,runner,suite,cli}.py` | creadas |
| `tools/migration_spike/test_validate.py` | creada — 105 pruebas |
| `docs/implementation/handoffs/FNC-DB-002.md` | este documento |

**No se tocó** `db/migrations`, ADR-002, `infra/local`, roles productivos, CI,
`CURRENT_PHASE.md`, backlog, trazabilidad, gates, decisiones, ownership, tareas ni
ningún contrato existente. `migration-tooling.json` pertenece a FNC-DB-001 y se leyó
sin modificarlo. Todas las rutas reservadas quedan liberadas.

---

## 2. Contrato y decisiones implementadas

- **Tres roles genuinamente distintos**: bootstrap, migrator y runtime, ninguno de los
  dos últimos SUPERUSER, BYPASSRLS, CREATEDB ni CREATEROLE.
- **Una transacción por migración** con `--single-transaction` y `ON_ERROR_STOP=1`.
- **`pg_advisory_xact_lock`** para serializar migradores, liberado al commit.
- **Checksum de contenido comprobado antes de ejecutar**, no después.
- **`applied_at` del servidor**, historial propiedad del migrator y solo legible por
  el runtime.
- **`FORCE ROW LEVEL SECURITY`** sobre la tabla company-scoped, de modo que ni el
  propietario queda exento.
- **Sin `down` destructivo ni rollback histórico automático**; el validador rechaza
  `DROP`, `TRUNCATE` y `DELETE FROM` en una migración.
- **Sin `CREATE INDEX CONCURRENTLY`, `VACUUM` ni `CREATE DATABASE`**: romperían la
  atomicidad que el spike existe para demostrar.
- **Limpieza confinada** al proyecto `fincilia-db-spike`, comprobada en el constructor
  del runner antes de construir ningún argv.
- **ADR-002 sigue `proposed` y `selected_tool` sigue `null`.**

---

## 3. Comandos exactos y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.migration_spike.test_validate` | 0 | **105 pruebas, OK** |
| `docker compose -f spikes/FNC-DB-002/compose.yaml -p fincilia-db-spike config --quiet` | 0 | Compose válido, ejecutado antes del run |
| `python -m tools.migration_spike.cli validate` | 0 | contrato y manifiesto válidos |
| `python -m tools.migration_spike.cli plan` | 0 | 3 pasos, digest `a36c161dbc784ab9…`, sin mutar |
| `python -m tools.migration_spike.cli run --suite all` | **0** | **12/12 pass** |
| `python -m tools.migration_spike.cli report` | 0 | casos, gates y límites declarados |

---

## 4. Evidencia Docker: **real, no simulada**

Docker **sí** estaba disponible en esta máquina, dentro de WSL. Se comprobó antes de
construir nada:

```
adapter: wsl · Docker 29.7.2 · docker compose v5.5.0
imagen: postgres:17.11-alpine3.24@sha256:18cfe3ef5e68…  (ya cacheada por digest)
postgres (PostgreSQL) 17.11 · psql (PostgreSQL) 17.11
```

No se descargó ninguna imagen nueva: la referencia es exactamente la ya adjudicada en
`infra/local/compose.yaml` y estaba en la caché local por digest.

### Resultado por caso

| Caso | Resultado | Detalle observado |
|---|---|---|
| `DBS-BLANK` | **pass** | `FNC_SPIKE_OK head_state` |
| `DBS-REPLAY` | **pass** | 3 filas para 3 versiones; ningún `APPLYING` en el replay |
| `DBS-TAMPER` | **pass** | denegado con `FNC_SPIKE_CHECKSUM_MISMATCH` |
| `DBS-PARTIAL-FAILURE` | **pass** | `partial_artifact` no existe; V0009 no está en el historial |
| `DBS-PRIVILEGES` | **pass** | ni superuser, ni bypassrls, ni createdb, ni createrole; runtime no es propietario |
| `DBS-RUNTIME-DENIAL` | **pass** | 5 rutas de escritura denegadas, lectura del historial preservada |
| `DBS-RLS` | **pass** | dos compañías aisladas; escritura cruzada denegada; sin contexto falla cerrado |
| `DBS-FORCE-RLS` | **pass** | `relrowsecurity` y `relforcerowsecurity` verdaderas, con política |
| `DBS-CONCURRENCY` | **pass** | 3 versiones, 3 aplicaciones, 3 contendientes que hallaron el trabajo hecho |
| `DBS-CHECKSUM-ORDER` | **pass** | plan estable al invertir el manifiesto |
| `DBS-UNKNOWN-MIGRATION` | **pass** | 5 planes malformados rechazados, cada uno con su código |
| `DBS-CLEANUP-SCOPE` | **pass** | todo argv fija proyecto y fichero del spike |

### Limpieza

`docker compose -f spikes/FNC-DB-002/compose.yaml -p fincilia-db-spike down --volumes --remove-orphans`
se ejecutó automáticamente al terminar. Comprobado después: **0 contenedores, 0
volúmenes, 0 redes**. El proyecto `fincilia-local` no se levantó en ningún momento.

---

## 5. Dos defectos propios corregidos durante la ejecución

Se dejan escritos porque quien construya el driver productivo tropezará con lo mismo.

**1. `psql` no interpola variables dentro de un bloque `DO $$…$$`.** El primer driver
metía `:'version'` y `:'checksum'` dentro del bloque y fallaba con un error de
sintaxis en las nueve pruebas de PostgreSQL. La corrección es pasar los valores por
`SET LOCAL` —que sí admite interpolación— y leerlos con `current_setting`.

**2. La carrera de concurrencia estaba mal modelada.** Lanzaba las tres versiones a la
vez y V0002 fallaba legítimamente porque V0001 aún no había commiteado. Eso no es una
carrera: es desordenar el plan. El caso correcto lanza dos migradores **por versión**,
y además exige que el segundo encuentre el trabajo ya hecho. Sin esa segunda
condición el caso habría podido pasar sin contienda alguna.

---

## 6. Pruebas negativas y qué demostraron

| Degradación aplicada | Regla que mordió |
|---|---|
| digest OCI flotante / sin digest | `MSC-IMAGE-PIN` |
| SQL fuera de `sql/migrations/` | `MSP-SQL-OUTSIDE` |
| checksum alterado o mal formado | `MSP-CHECKSUM` |
| versión duplicada | `MSP-VERSION-DUPLICATE` |
| hueco en la secuencia | `MSP-VERSION-GAP` |
| fichero `.sql` no manifestado | `MSP-FILE-NOT-MANIFESTED` |
| manifiesto que apunta fuera del spike | `MSP-PATH-UNSAFE` |
| symlink como fuente | `MSP-PATH-UNSAFE` |
| comando shell o argv que no es lista | `SpikeRunnerError` |
| nombre de proyecto alterado | `SpikeRunnerError` + `MSP-PROJECT` |
| volumen o Compose externo | `SpikeRunnerError` |
| rol privilegiado / runtime propietario | `MSC-POLICY`, `MSC-ROLES` |
| RLS omitida | `MSC-POLICY` |
| historial mutable por el runtime | `MSC-POLICY` |
| migración sin transacción | `MSC-POLICY`, `MSP-NON-TRANSACTIONAL` |
| `DROP` destructivo no aprobado | `MSP-DESTRUCTIVE` |
| aceptación automática de ADR-002 | `MSC-ADR-ACCEPTED` |
| evidencia runtime fabricada (`passed` sin `evidence_ref`) | `MSC-EVIDENCE-FABRICATED` |

**Contraste deliberado:** un comentario que menciona `DROP TABLE` **no** dispara
`MSP-DESTRUCTIVE`; la regla lee código, no prosa.

---

## 7. Hallazgos fuera de scope

Ninguno nuevo. `docs/database/migration-tooling.json` mantiene su `spike_matrix` con
los ocho casos en `not_run`; **este spike no la edita** porque pertenece a FNC-DB-001.
La correspondencia entre ambos está declarada en `relation_to_fnc_db_001`: cubre
DBS-01, 02, 04, 05, 06 y 07; **no** cubre DBS-03 ni DBS-08.

---

## 8. Riesgos y gaps que permanecen

| ID | Riesgo | Owner | Gate |
|---|---|---|---|
| `GAP-DB-UPGRADE` | no hay release anterior contra la que probar un upgrade real | Database Migration Owner | ADR-002-MIGRATIONS |
| `GAP-DB-EXPAND-CONTRACT` | N/N+1 exige dos versiones de la aplicación corriendo | Architecture | ADR-002-MIGRATIONS |
| `GAP-DB-TOOLING-LICENSE` | licencia y cadena de suministro de la herramienta candidata | Security | ADR-002-MIGRATIONS |
| `GAP-DB-VOLUME` | nada aquí dice nada sobre tiempo de bloqueo ni volumen real | Platform | ADR-002-MIGRATIONS |

**ADR-002 sigue `Proposed` y ningún agente lo acepta.** Que los invariantes se cumplan
con `psql` no dice cuál herramienta los cumple mejor.

---

## 9. Rollback

Eliminar `spikes/FNC-DB-002/`, `tools/migration_spike/`,
`docs/database/migration-spike.json` y `docs/database/MIGRATION_SPIKE.md`. El
laboratorio es descartable por diseño y no dejó estado fuera de su propio proyecto de
Compose. Dependencias entrantes: el check `data-migration-spike` de FNC-PLT-007 y
`chk-migration-spike` más el `evidence_baseline` de FNC-GAT-003; si se revierte,
retirar esas entradas.

---

## 10. Pasos para el Integration Steward

1. **Indexar** las rutas de §1.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí.
3. **CI**: `run --suite all` necesita Docker. Los tres casos estáticos y `validate`
   corren sin él. Decidir si el spike entra como lane propio o queda bajo demanda.
4. **Adjudicar** con Architecture, Platform y Security si estos invariantes bastan para
   mover ADR-002, y qué herramienta los implementará.
5. **Catálogo y trazabilidad**: el contrato no declara `required_tests`, así que no
   introduce IDs nuevos. Confirmar con `test_catalog validate` tras indexar.
6. **Digests golden/mutation**: `migration-spike.json` no es input de ningún caso
   golden ni de ninguna mutación registrada, así que no derivan digests. Si más
   adelante se registra como input, habrá que re-adjudicar.
7. **`evidence_baseline` de FNC-GAT-003** referencia `migration-spike.json` y
   `spikes/FNC-DB-002/MANIFEST.json` por digest: cualquier cambio en ellos deja esa
   evidencia `stale_evidence` hasta reejecutar el spike.
8. **Liberar reservas** de FNC-DB-002.

Estado final: **`REVIEW_PENDING`**. Evidencia Docker real, 12/12, sin simular nada. No
se declara aceptación, integración, head SHA, CI remoto ni revisión humana
inexistentes, y no se acepta ADR-002.
