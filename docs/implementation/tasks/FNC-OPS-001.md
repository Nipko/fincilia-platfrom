---
id: FNC-OPS-001
alias: FNC-P4.10
title: Centro operativo de ciclos y recordatorios web
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: d38bc299171bbd30ee82b9b6fbdf5680e0ed13a6
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/Accounting, Security/Privacy, Backend/Architecture, Accessibility/QA]
---

# Resultado esperado

Un contador que atiende varias empresas puede ver en una sola bandeja los
periodos esperados, vencidos y proximos a vencer, con su empresa, fuente,
responsable y siguiente accion. La misma superficie permite consultar el
historico y sus volumenes operativos sin mezclar empresas, agregar dinero ni
presentar un recordatorio visual como una notificacion efectivamente enviada.

# Autoridad y limites

- `source_cycle` define el calendario y `source_expectation` conserva cada
  periodo materializado, sus fechas historicas y su satisfaccion. No se crea un
  segundo calendario ni se recalculan fechas historicas.
- El estado temporal se deriva en servidor contra su fecha actual; la web no
  decide si algo esta vencido y no puede aportar un `company_id` autorizado.
- La bandeja consulta cada empresa por separado, con `company_context`,
  `data_source.manage` y RLS. No existe una lectura privilegiada de firma.
- "Recordatorio" significa señal dentro de la plataforma. Correo, push, SMS,
  jobs programados y constancia de entrega quedan fuera hasta definir canal,
  consentimiento, quiet hours, retries, retencion y proveedor.
- La vista contiene conteos y fechas, nunca importes, salud financiera, fraude,
  cierre certificado ni una afirmacion de completitud contable.

# Definition of Ready

- Base declarada integrada, arbol limpio y CI verde.
- FNC-WEB-003 aporta portafolio company-by-company y ciclos historicos.
- FNC-QA-006 aporta bootstrap y recorridos E2E reproducibles.
- Integration Steward reserva API, web, pruebas y registros centrales.
- No se requieren migraciones, datos reales, conectores, IA, movil o servicios
  de mensajeria.

# Rutas permitidas

- `apps/api/src/fincilia_api/operations.py`, `routes.py` y pruebas API.
- `db/tests/test_operational_reminders.py`.
- `apps/web/src/app/recordatorios/**`, navegacion web, estilos y pruebas.
- `apps/web/src/lib/operations.ts`, `api.ts` y pruebas.
- Ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- Migraciones o mutacion de `source_cycle`/`source_expectation` desde la bandeja.
- Bypass RLS, endpoints firm-wide o autorizacion reconstruida en el navegador.
- Envio de correo, push, SMS, webhooks o integracion con calendarios externos.
- Waivers, excepciones contables, cierre, saldos certificados o agregacion de
  importes.
- Datos reales, IA, movil, secretos, ADR Accepted o cambios de gates.

# Criterios de aceptacion

- **AC-01.** La API devuelve periodos de una sola empresa con filtros cerrados,
  limite acotado y cursor keyset estable; la fecha de evaluacion es server-side.
- **AC-02.** Estados `overdue`, `due_today`, `due_soon`, `upcoming`, `satisfied`
  y `waived` se derivan sin reescribir fechas o estados historicos.
- **AC-03.** Resumen e historico cuentan periodos por estado, fuente y horizonte
  sin sumar dinero. Ventanas truncadas se divulgan y nunca se presentan como
  totales completos.
- **AC-04.** La API exige `data_source.manage`, resuelve empresa server-side y
  consulta bajo RLS; permiso ausente, revocacion y cross-company fallan neutros.
- **AC-05.** Responsable, elegibilidad y `assigned_to_me` se resuelven en la base;
  la respuesta no expone correo, identidad externa ni membresias de otra firma.
- **AC-06.** La web consulta company-by-company con concurrencia acotada,
  conserva filtros en URL y distingue acceso restringido, fallo parcial, vacio
  exitoso y resultados truncados.
- **AC-07.** La interfaz muestra prioridad, vencimiento, periodo, empresa,
  fuente, responsable y enlace accionable; explica que son recordatorios
  internos y no prueba de entrega, saldo, fraude o cierre.
- **AC-08.** Unitarias API/web, PostgreSQL cross-company, E2E, Axe, lint, tipos,
  build, quality gate, handoff y CI pasan sobre el head entregado.

# Rollout y rollback

Solo entorno local sintetico. El rollback elimina endpoint, proyeccion web y
enlace de navegacion; no hay tabla, mensaje enviado ni estado financiero que
revertir.

# Definition of Done

- AC-01..AC-08 con evidencia reproducible y commits incrementales.
- Revision humana pendiente declarada; ningun gate o ADR cambia de estado.
- Rutas liberadas, handoff `REVIEW_PENDING` y CI verde.
