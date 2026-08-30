---
id: FNC-ADM-001
title: Plano de administración y superadmin inicial
status: review_pending
implementer: Codex principal dev + Integration Steward
gate: DRG-00
gate_effect: none
data_ceiling: synthetic_or_explicitly_authorized_uat
independent_reviewers: [Security, Privacy/Legal, Architecture/Database, SRE, QA]
---

# Resultado

Fincilia dispone de un plano de control separado de los roles contables, con
bootstrap único del primer superadmin, diagnósticos minimizados, administración
de identidades/organizaciones y auditoría sin acceso financiero implícito.

# Rutas

- `db/migrations/V0044*`, `db/admin/platform_admin.py` y pruebas focales.
- `apps/api/src/fincilia_api/platform_admin.py`, rutas y pruebas.
- `apps/web/src/app/plataforma`, navegación, cliente API y pruebas.
- `docs/security/platform-administration*`, ADR-033 y handoff.

# Criterios de aceptación

1. La reclamación inicial exige binding Google verificado y referencia HMAC
   preconfigurada; dos reclamaciones concurrentes no crean dos superadmins.
2. Nadie puede enviar un rol desde el navegador ni autoconcedérselo.
3. `/me` publica solo roles/capacidades internas de plataforma.
4. Los endpoints administrativos fallan cerrados para sujetos ordinarios.
5. El overview y diagnósticos no exponen montos, archivos, celdas, tax ID,
   correo o `sub` externos.
6. Suspender/reactivar y administrar roles es auditado; el último superadmin no
   puede quedar inactivo.
7. La consola web solo aparece y responde para una autoridad válida.
8. Break-glass permanece deshabilitado y separado.
9. PostgreSQL real, API, web, build y verificadores quedan verdes.

# Rollback

Revocar la ruta web/API y las ejecuciones de funciones preserva las asignaciones
y la auditoría para investigación. El esquema es forward-only.
