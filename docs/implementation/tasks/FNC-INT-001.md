---
task: FNC-INT-001
title: Due diligence ejecutable de conectividad financiera
status: review_pending
implementer: Integration Steward
base_sha: 52bf75f
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, Finance, Legal]
---

# Resultado esperado

Comparar conectividad directa, agregadores y fallback por archivos con evidencia oficial,
criterios comerciales y gates de seguridad. Preparar tres solicitudes de cotización sin
contactar proveedores ni inventar cobertura, SLA o precios.

## Rutas

- `docs/integrations/CONNECTIVITY_DUE_DILIGENCE.md`
- `docs/integrations/provider-evaluation.json`
- `docs/integrations/RFQ_TEMPLATE.md`
- `tools/provider_evaluation/**`
- `docs/implementation/handoffs/FNC-INT-001.md`

## Criterios

1. Archivos siguen siendo canal permanente y único disponible en E0.
2. Cobertura pública se diferencia de cobertura contractual nominal.
3. Ningún precio, SLA, banco empresarial o método de acceso se presume.
4. Credenciales bancarias nunca entran a Fincilia.
5. Tres RFQ comparables quedan listos; cotizaciones siguen pendientes de acción humana.
6. El modelo impide seleccionar proveedor o habilitar producción con evidencia incompleta.
