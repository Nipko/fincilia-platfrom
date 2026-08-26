---
task: FNC-ONB-001
status: REVIEW_PENDING
base_sha: f19b162
tested_head_sha: c99dc20
implementation_commits: [c99dc20]
data_ceiling: synthetic_only
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado

La plataforma web ya permite que un `owner` o `firm_admin` cree una empresa sin
editar semillas. Una sola transaccion crea `company`, version de autorizacion,
engagement primario y grant `owner`; opcionalmente crea tambien la primera
cuenta, fuente, vinculo principal y ciclo mensual. La respuesta renueva la
sesion y la empresa queda navegable inmediatamente.

# Implementacion y controles

- V0019 incorpora el aprovisionamiento company-scoped, atomico e idempotente.
- V0020 concede a `fincilia_app` solamente `SELECT` sobre `firm`; RLS limita las
  filas a firmas con membresia activa. `INSERT`, `UPDATE` y `DELETE` siguen
  denegados.
- La API resuelve sujeto y firma server-side. Solo una membresia viva con rol
  `owner` o `firm_admin` autoriza el alta.
- NIT e identificador de cuenta se convierten en huellas con clave antes de
  persistirse y no aparecen en respuesta, auditoria ni errores.
- La web ofrece `/empresas/nueva`, inicio operativo opcional, redireccion segura
  y degradacion cerrada si no puede resolver firmas administrables.
- Las rutas principales estan en `db/migrations/V0019*`, `db/migrations/V0020*`,
  `apps/api/src/fincilia_api/company_onboarding.py`, `apps/api/src/fincilia_api/routes.py`,
  `apps/web/src/app/empresas/nueva`, contratos de tenancy y sus pruebas.

# Evidencia ejecutada

- PostgreSQL 17 real: 13 pruebas OK, incluidas concurrencia, rollback,
  idempotencia, RLS positiva/negativa y denegacion de escritura sobre `firm`.
- Migrador local repetido: `head=V0020`, `applied=[]`, `mutated=false`.
- API: 107 pruebas OK. Contrato de firma/tenancy: 23 pruebas OK.
- Web: typecheck, lint y build de produccion OK; 164 pruebas unitarias OK.
- Chromium: 2 recorridos de alta/denegacion OK. Accesibilidad: 12 recorridos OK.
- `tools.work_graph.validate` y `tools.quality_gate.cli`: OK, cero hallazgos.

# Limites, revision y rollback

Solo se admiten datos sinteticos mientras DRG-00 permanezca cerrado. No se
habilitaron conectores, datos reales, cobro, cierre, auto-match, IA ni
aceptacion de gates. Product/Accounting, Security, Backend/Architecture y
Accessibility/QA deben realizar revision independiente.

Rollback: retirar primero consumidores web y rutas API. V0020 se compensa
revocando `SELECT` a `fincilia_app` y eliminando la politica RLS agregada;
V0019 se compensa solo despues de retirar el productor y preservando empresas
ya creadas para una migracion de datos explicita. No se reescriben migraciones
aplicadas.
