---
id: FNC-PLT-015
title: Materializacion segura de la foundation private-pilot AWS
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 5967f3e72303e01aa3de2e87eee4a62ac79aa214
gate: DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Finance, Platform/SRE, Security, Privacy, QA]
---

# Resultado esperado

Aplicar de forma reanudable el plano frio de `private-pilot` previamente
validado, sin crear el plano runtime costoso ni habilitar datos reales. La
entrega debe reconciliar cualquier apply parcial, conservar los controles de
backup y producir evidencia redactada del estado observado.

# Autorizacion y limites

El Founder solicito el 3 de septiembre de 2026 montar en AWS lo necesario para
dejar la plataforma preparada. La autorizacion de esta tarea cubre solo la
foundation fria ya cotizada: cero borrados planificados, servicios ECS en cero
y `real_data_authorized=false`.

- Permitidas: `infra/aws/private-pilot`, `tools/aws_pilot_control`,
  `tools/aws_private_pilot`, `tools/aws_image_publication`, documentación de
  plataforma, evidencia, esta ficha, handoff, backlog y `CURRENT_PHASE.md`.
- Prohibidas: reducir retención o aislamiento para satisfacer el plan gratuito,
  activar tareas ECS, publicar datos reales, poblar secretos en archivos,
  aceptar DRG-00/01 o atribuir una revisión humana inexistente.

# Criterios de aceptación

1. El controlador usa el mismo valor de modo al planificar y aplicar un plan
   guardado, con pruebas para `cold` y `warm`.
2. Un apply parcial puede reanudarse después del refresh normalizado del
   proveedor OIDC sin aceptar otro issuer o audience.
3. Todo recurso creado parcialmente queda reconciliado con el estado remoto;
   nunca se elimina ni recrea a ciegas.
4. La retención RDS permanece en 14 días; una restricción comercial de AWS se
   reporta como bloqueo y no se disfraza como éxito.
5. El plano runtime permanece ausente, RDS no público y los datos reales siguen
   desautorizados.
6. La evidencia no contiene secretos, valores del estado, correos, ARN ni
   request IDs.

# Verificación

- Pruebas unitarias de ambos controladores y validadores del plan.
- Plan `cold` live contra la cuenta/región exactas.
- Inventario de estado por direcciones, sin leer valores.
- Quality gate, work graph y CI antes de integrar.

# Fuera de alcance

Upgrade comercial de la cuenta, DNS de ACM/ALB, valores Google o de base,
runtime caliente, migraciones, restore target, pentest, revisiones humanas y
activación de datos reales.
