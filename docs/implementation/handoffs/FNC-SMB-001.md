# Handoff — FNC-SMB-001..006: pyme modo simple

- Fecha: 2026-11-04
- Rama: `feat/pyme-modo-simple` desde `main` `b3f5110` (sin commit al preparar este handoff)
- Decisión: FNC-PRD-002 · ADR-039
- Datos: exclusivamente sintéticos
- Estado: Review pending; requiere revisión independiente de Security, Database y Accounting

## Resultado

Una pyme de una o dos personas puede subir su extracto y sus facturas, revisar
solo lo que no cuadra, confirmar sola, crear reglas «¿aplicar siempre?» y cerrar
el periodo como `self_reviewed`. Su contador certifica después. En perfil
`estricto` la segregación de funciones conserva errcode, mensaje y nombre de
constraint anteriores.

## Migraciones

| Migración | Contenido |
|---|---|
| V0067 | `company.operating_profile`, historial append-only owner-only, `review_mode` en 9 tablas con SoD, `certification` del cierre y tabla de certificación |
| V0068 | Localizadores `xml_element` y `mt940_tag` en `raw_record` |
| V0069 | Señales de tolerancia, `amount_difference`, reglas versionadas, aprobaciones, `approved_rule` restringido y reversión append-only |
| V0070 | `platform_admin_approve_engine_release` (SECURITY DEFINER) para publicar sin CLI |
| V0071 | Cadencia de carga owner-only y recordatorio in-app que nunca sale por correo ni WhatsApp |

## Evidencia ejecutada (proyectos Docker aislados en WSL, `down -v` al final)

| Suite | Resultado |
|---|---|
| PostgreSQL `db/tests` | 455 OK, 1 skip (perf lane bajo demanda) |
| API | 262 OK |
| Worker documentos | 40 OK |
| Worker notificaciones | 7 OK |
| Playwright + axe (`infra/local/test-web-isolated.ps1`) | bootstrap 1, e2e 52, a11y 30 verdes |
| Contratos | 441 OK |
| Web | tsc, eslint, `next build` OK; Vitest 346 OK |
| Validadores | quality gate, migration readiness y work graph OK |

Fallos previos en `main`, no introducidos aquí: `tools.migration_readiness.test_validate`
(1 failure) y `tools.release_candidate` (1 error).

## Riesgos y pendientes

- Plantillas bancarias: columnas supuestas, sin fuente pública. `calibration = synthetic_hypothesis`.
- Tolerancia por defecto del modo simple (5 % y COP 20.000), patrón Bre-B y días de
  recordatorio: hipótesis para calibrar con corpus autorizado.
- `same_counterparty_id` se deriva de «NIT …» en descripción/referencia; el modelo
  canónico no tiene contraparte.
- Las reglas se aplican con un botón; no hay ejecución programada. Los recordatorios
  se crean al cambiar la cadencia o sincronizar; no hay job periódico.
- Buzón de correo para extractos y canales externos: pendientes por DRG-00/ADR-037.
- `infra/local/scripts/e2e_fixture.py` cambió (par sintético de facturas en ESPIGA);
  es infraestructura compartida.
- La base de demo local (`fincilia_local_pgdata`) recibió V0067–V0069 con checksums
  previos durante el desarrollo; debe reiniciarse antes de usarla.
- No hay endpoint para editar una regla en una versión nueva (el esquema lo soporta).
