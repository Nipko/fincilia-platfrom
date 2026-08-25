---
id: FNC-ONB-001
title: Alta transaccional de empresa y espacio operativo
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: f19b162
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado

Un owner o administrador de firma crea desde la web una empresa y su
engagement sin editar semillas. En la misma transaccion puede crear cuenta,
fuente, vinculo principal y ciclo mensual, y queda con acceso owner inmediato.

# Alcance de codigo

- Migracion forward-only V0019 y pruebas PostgreSQL.
- Contrato de permisos de firma, dominio y rutas API de aprovisionamiento.
- Semilla local definitiva: una cuenta fundadora con roles acumulables reales;
  las identidades auxiliares solo sostienen pruebas de SoD entre sujetos.
- Web `/empresas/nueva`, accion de servidor, pruebas unitarias, E2E y a11y.
- Integracion, CI y handoff por Integration Steward.

# Criterios

- Solo membresia viva `owner` o `firm_admin` puede aprovisionar en esa firma.
- Company sigue sin `firm_id`; el acceso nace por engagement y grant.
- La operacion completa es atomica, idempotente y company-scoped.
- NIT e identificador de cuenta se tokenizan y nunca aparecen en respuesta,
  auditoria, error o log.
- El propietario inicial se concede mediante la autoridad de aprovisionamiento,
  no se autoasigna un rol.
- La cuenta fundadora local puede ejercer todos los roles con el modelo RBAC
  productivo, sin bypass ni modo especial; la SoD por objeto permanece activa.
- La empresa queda navegable inmediatamente y sin datos financieros reales.
- Unitarias, PostgreSQL real, E2E, accesibilidad, quality gate y CI pasan.

# Limites

Sin conectores, mensajeria, cobro, datos reales ni aceptacion de gates humanos.
