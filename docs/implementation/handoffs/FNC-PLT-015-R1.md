---
id: FNC-PLT-015-R1
status: REVIEW_PENDING
base_sha: 37b1814d6fbab0c7f6780d3b20bc44a40c399241
data_ceiling: synthetic_only_until_gate
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Finance, Platform/SRE, Security, Privacy, QA]
---

# Handoff FNC-PLT-015 R1 — preflight comercial previo a RDS

## Resultado

El controlador consulta el tipo y estado del plan de cuenta antes del primer
`apply` que necesita crear RDS. Si la base todavía no existe, sólo admite una
cuenta `PAID/ACTIVE`; bajo cualquier otra combinación se detiene antes de
escalar ECS, cambiar la protección del ALB o ejecutar OpenTofu.

La salida es mínima: no conserva identificador de cuenta, saldo de créditos,
instrumento de pago, ARN, endpoint ni secreto. El preflight observado confirmó
cuenta `FREE/ACTIVE`, RDS ausente y foundation no aplicable. El plan frío sigue
siendo válido: 7 altas, 2 lecturas, 5 actualizaciones y 0 borrados.

## Verificación

- `python3 -m unittest tools.aws_pilot_control.test_control -v`: 26 pruebas.
- `python3 -m tools.aws_pilot_control.cli ... commercial-preflight`: salida
  redactada, `foundation_apply_supported=false`, cero mutaciones.
- `python3 -m tools.aws_pilot_control.cli ... plan cold`: plan validado y sin
  borrados.

## Límites y siguiente acto

No se cambió el plan comercial AWS ni se aplicó infraestructura. El siguiente
acto requiere autorización explícita del Founder para el upgrade directo de la
cuenta a `PAID`; entrar en AWS Organizations o Control Tower no es sustituto.
Después deben regenerarse el preflight y el plan antes del apply frío.

La retención se mantiene en 14 días. DRG-00/01 continúan `not_met`, el runtime
permanece ausente y `real_data_authorized=false`.

## Rollback

Revertir código y documentación elimina el guard comercial, sin tocar AWS. No
hay estado cloud que deshacer.
