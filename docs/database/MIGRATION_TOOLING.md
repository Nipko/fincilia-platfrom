# Migraciones SQL-first

## Recomendación para spike

Evaluar primero Flyway porque ofrece migraciones SQL versionadas, checksums y schema history.
No queda seleccionado: faltan licencia/distribución, runtime fijado, supply chain y ocho pruebas
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
