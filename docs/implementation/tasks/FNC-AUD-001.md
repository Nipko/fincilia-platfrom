---
id: FNC-AUD-001
title: Centro web company-scoped de accesos y auditoria
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 4983764
implementation_sha: c119f91
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security/Privacy, Web/Accessibility]
---

# Resultado

Convertir el registro append-only ya existente en una herramienta operativa para
contadores y auditores: búsqueda acotada, actor, resultado, paginación estable y
vista multiempresa que nunca confunde falta de permiso o fallo con cero eventos.

# Alcance reservado

- Consulta API y repositorio de auditoría; sin cambiar la tabla append-only.
- Cliente servidor, modelos y página `/auditoria` de la plataforma web.
- Navegación desde portafolio y empresa, pruebas API/web y handoff.

# Criterios

- RLS y `audit.read` se resuelven por empresa; no existe consulta agregada SQL
  entre empresas.
- Cursor opaco y estable por `(occurred_at, audit_event_id)`; filtros de acción,
  tipo y resultado usan vocabulario/forma acotados.
- Actor visible solo a quien ya puede leer la auditoría de esa empresa.
- Sin payload crudo, importes, documentos, secretos ni detalle libre en la vista.
- Revocación, 403 y 503 son estados distintos; ninguno se representa como cero.

# Limites

Solo datos sintéticos. Es exploración de trazabilidad, no certificación, SIEM,
detector de fraude ni export legal.

# Verificación requerida

- Security/Privacy: RLS, permiso `audit.read`, exposición de identidad laboral y
  exclusión de payload/referencias.
- Backend/Architecture: keyset, límites, filtros exactos y consulta por empresa.
- Web/Accessibility: estados parciales, tabla, filtros y navegación.
