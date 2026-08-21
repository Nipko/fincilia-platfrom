# Definition of Done

Una tarea pasa a Done únicamente cuando:

- Todos los criterios de aceptación tienen evidencia.
- El diff respeta el scope y no contiene cambios incidentales.
- Formato, lint, tipos, build y pruebas aplicables pasan.
- Existen pruebas unitarias, integración y contrato según el riesgo.
- Parsing o dinero incluyen golden/property tests.
- Tenancy o autorización incluyen pruebas positivas y negativas cross-tenant.
- Idempotencia, retry, completitud y linaje se prueban cuando aplican.
- Migración forward y rollback/restauración están descritos y verificados.
- Logs, métricas y errores no exponen información sensible.
- Contratos, ADR, documentación y ejemplos están sincronizados.
- Dependencias nuevas están justificadas, fijadas y evaluadas.
- No hay secretos, PII, datos reales o artefactos grandes accidentales.
- Feature flags tienen owner, expiración y rollback.
- Existe revisión independiente para seguridad, privacidad, migraciones y semántica financiera.
- El handoff contiene base/head SHA, rutas, comandos, resultados, riesgos y trabajo pendiente.
- No quedan TODO sin ID de tarea.
- CI está verde sobre el commit entregado.

Done de una tarea no modifica un gate. Solo el owner del gate puede consolidarlo.

