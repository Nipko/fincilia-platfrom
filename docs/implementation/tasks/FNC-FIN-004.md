---
id: FNC-FIN-004
title: Activacion comercial y alertas de costo bruto AWS
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: a4d10c07accb2749a5e0e5c26d6437c379c7de93
gate: DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Finance, Platform/SRE, Security, QA]
---

# Resultado esperado

Habilitar la cuenta AWS para materializar la foundation UAT sin reducir los
controles de RDS y hacer observable el gasto bruto antes de créditos,
descuentos y reembolsos. El presupuesto alerta, pero nunca se presenta como
un límite duro ni como autorización de datos reales.

# Rutas

- Permitidas: `infra/aws/private-pilot/audit.tf`, `network.tf`, `database.tf`,
  contrato, validador y pruebas del private-pilot, runbook, esta ficha,
  handoff y archivos centrales por el Integration Steward.
- Estado externo autorizado: cambio directo de la cuenta exacta de `FREE` a
  `PAID`, apply frío validado y actualización del presupuesto administrado.
- Prohibidas: Organizations, Control Tower, reducir backup, encender ECS,
  introducir secretos, aceptar gates o procesar datos reales.

# Criterios de aceptación

1. La cuenta observada queda `PAID/ACTIVE` y el preflight comercial pasa.
2. La foundation fría queda completa, RDS cifrado/privado con 14 días y los
   once recursos runtime permanecen ausentes.
3. El presupuesto mensual conserva USD 120 y mide gasto account-wide antes de
   créditos, descuentos y reembolsos.
4. Existen alertas por correo a 50 % y 80 % ACTUAL y 100 % FORECASTED.
5. El plan que actualiza las alertas se valida sin borrados antes del apply.
6. El modelo y las pruebas fallan si se vuelven a incluir créditos o se elimina
   la alerta temprana.
7. `real_data_authorized=false`; DRG-00/01 no se mueven.
8. Security groups administran sus reglas con recursos VPC dedicados, sin
   mezclar argumentos inline que puedan sobrescribirlas.

# Verificacion

- Pruebas adversariales del contrato y del plan.
- `tofu fmt -check`, `tofu validate`, plan frío y validador del plan.
- Consultas AWS redactadas de plan comercial, foundation, RDS y Budgets.
- Quality gate sobre el índice Git y CI sobre el commit entregado.

# Resultado implementado

- Cuenta observada `PAID/ACTIVE`, sin Organizations ni Control Tower.
- Foundation fría completa `36/36`; runtime ausente `0/11`, ECS en cero y RDS
  detenido.
- Presupuesto mensual USD 120, account-wide y bruto antes de créditos,
  descuentos y reembolsos; alertas ACTUAL 50/80 y FORECASTED 100 aplicadas.
- RDS conserva cifrado, acceso privado, protección de borrado y 14 días de
  backup.
- El plan posterior al apply quedó en `147 no-op`, sin deriva.
- `real_data_authorized=false`; revisiones independientes y DRG-00/01 siguen
  pendientes.
