# Migraciones SQL-first

## Decisión vigente — IMP-017

`FOUNDER-01` aceptó ADR-002 y seleccionó el migrador SQL-first propio en
`db/migrate/apply.py`. Flyway permanece como alternativa evaluada, no como dependencia.
La aceptación permite migraciones de producto dentro del techo sintético actual; no
supera S1-READY ni autoriza despliegues compartidos. Database y Security independientes
deben revisar migraciones y funciones privilegiadas antes del gate correspondiente.

## Recomendación histórica para spike

Se recomendó evaluar primero Flyway porque ofrece migraciones SQL versionadas, checksums y schema history.
No fue seleccionado: requería licencia/distribución, runtime fijado, supply chain y ocho pruebas
contra PostgreSQL 17. Dbmate es más liviano, pero su tabla aplicada registra la versión y no
el contenido; exigiría un manifiesto de checksums externo. node-pg-migrate encaja con Node y
locking, pero debe probar que no debilita SQL-first/revisión y checksum.

Producción será forward-only. “Rollback” normal significa aplicación compatible o forward-fix;
no ejecutar `down` destructivo. Las migraciones corren con rol dedicado, nunca al arrancar cada
réplica ni con el runtime owner/BYPASSRLS.

Fuentes: [Flyway migrations](https://github.com/flyway/flywaydb.org/blob/gh-pages/documentation/concepts/migrations.md),
[Dbmate](https://github.com/amacneil/dbmate),
[node-pg-migrate](https://salsita.github.io/node-pg-migrate/migrations/).

Validación: `python -m tools.migration_readiness.validate`.

## V0022 — transición expand de trabajos autorizados

La firma nueva de `enqueue_processing_run` exige un `issued_context_id`; la API y
los trabajos derivados ya la usan. `claim_next_run`, `hold_processing_lease` y
`finish_run` vuelven a comprobar expiración, revocación, versión y autoridad viva.
La columna queda nullable exclusivamente para vaciar trabajos creados antes del
despliegue. Retirar la firma de tres argumentos e imponer `NOT NULL` requiere una
migración contract posterior y evidencia de que no quedan productores antiguos.

`fincilia_dispatch` continúa siendo un rol sin login y sin DDL permanente. V0022
le concede lectura de la ruta mínima de identidad porque la revalidación online no
puede inferirse solo de la versión si una escritura administrativa defectuosa no la
incrementó. El worker no recibe esas lecturas, la clave HMAC ni UPDATE de cola.
