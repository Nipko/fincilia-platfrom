# Handoff FNC-DOM-001

- Estado: PARTIAL
- Agente: A2 Domain (subagente `/root/e0_tenancy`)
- Accountable owner: UNASSIGNED
- Revisores requeridos: Architecture, Accounting y Security independientes
- Base SHA: `f621236bc98c1fd26f8d2f3b078271ff20068ea8` (leído de `.git/HEAD` sin operar Git)
- Head SHA: pendiente de integración por Integration Steward
- Rama/worktree: filesystem compartido; Git reservado al agente raíz
- Objetivo y resultado: se completó el borrador del modelo de tenancy y cambio de firma con entidades, cardinalidades, estados, invariantes, rutas de autorización, invalidación, acceso directo/delegado/no humano y matriz TST-TEN-001 sintética.
- Paths modificados: `docs/domain/TENANCY_MODEL.md`; `docs/implementation/handoffs/FNC-DOM-001.md`
- Paths reservados que se liberan: `docs/domain/TENANCY_MODEL.md`; `docs/implementation/handoffs/FNC-DOM-001.md`
- ADR/contratos afectados: implementa ADR-003 sin modificarlo; documenta compatibilidad esperada con `docs/contracts/jobs/job-envelope.schema.json` v1.
- Migraciones/eventos/flags: ninguno; fuera del scope de la tarea.
- Decisiones y supuestos: company permanece frontera financiera; engagement no concede acceso; grants tienen una sola ruta; `authorization_version` v0 es company-wide y fail-closed; puede haber varios engagements activos, pero un solo operador contable primario con grants delegados de write/close.
- Riesgos de seguridad/privacidad/datos: la invalidación company-wide puede forzar refresh/reintento de principals legítimos; se privilegia fail-closed. Solo se usaron identificadores sintéticos, sin PII ni datos financieros.
- Compatibilidad y consumidores: RBAC/ABAC/SoD, API, RLS, jobs/workers, objetos, links, schedules, caché, proyecciones y pruebas TST-TEN-001 deben consumir la ruta y versión de autorización descritas.
- Rollback: restaurar el contenido anterior de `docs/domain/TENANCY_MODEL.md` y retirar este handoff antes de integración; no existe estado de datos que revertir.
- Comandos ejecutados: lecturas PowerShell/`rg` de instrucciones, ficha, ADR-003, plan §§6/14/29, DoD, RBAC/ABAC/SoD, threat model, glosario y job envelope; validaciones documentales registradas abajo.
- Resultado exacto de pruebas: PASS documental sobre los dos archivos: 306/26 líneas, cercas balanceadas (4/0), cero merge markers, cero pendientes anónimos, tablas consistentes; 23 IDs TST-TEN-001 positivos/negativos únicos y todos los marcadores de aceptación presentes. No existen pruebas ejecutables dentro del scope de diseño.
- Evidencia: cada criterio de aceptación está cubierto en `TENANCY_MODEL.md`: cardinalidades (§3), estados (§4), invariantes (§5), autorización (§6), invalidación (§7), cambio de firma (§8), TST-TEN-001 (§9).
- Fallos conocidos: no existen pruebas ejecutables todavía; este entregable es diseño previo a Sprint 1. Owners humanos y dependencia FNC-PRD-001 siguen sin resolver.
- Trabajo pendiente con IDs: FNC-DOM-001 — revisión independiente y materialización de TST-TEN-001; FNC-SEC-001 — sincronizar matriz RBAC/ABAC/SoD con las rutas y exclusividad definidas; FNC-ARC-001 — reflejar fronteras y flujos en C4.
- Bloqueos, owner y condición de desbloqueo: FNC-GOV-001 debe asignar owners; FNC-PRD-001 debe aprobar PRD provisional; Architecture, Accounting y Security deben revisar el borrador antes de `Ready`/`Accepted`.

Este handoff no cambia el estado global ni declara superado S1-READY.
