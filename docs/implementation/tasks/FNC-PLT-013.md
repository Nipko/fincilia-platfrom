---
id: FNC-PLT-013
title: Ciclo frio y activacion temporal del piloto privado AWS
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 09e601a
gate: DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Platform/SRE, Privacy, QA]
---

# Resultado

El piloto permanece por defecto en modo `cold`: conserva VPC, datos cifrados,
llaves, identidad, secretos, ECR, auditoria y la base detenible, pero no mantiene
NAT, endpoints Interface, ALB/WAF, Valkey ni tareas ECS facturando. Un controlador
local genera y valida el plan exacto antes de crear o retirar ese plano temporal.

# Rutas

- Permitidas: `infra/aws/private-pilot`, `tools/aws_pilot_control`,
  `tools/aws_private_pilot`, `docs/platform`, este task, handoff, ADR-032,
  `CURRENT_PHASE.md` y backlog como Integration Steward.
- Prohibidas: datos, secretos o tfvars reales; migraciones; producto API/web;
  gates y decisiones humanas aceptadas.

# Invariantes

1. `cold` es el valor por defecto y no deja recursos runtime de costo alto.
2. S3, KMS, RDS, Cognito, Secrets Manager, ECR y CloudTrail nunca se destruyen
   al enfriar.
3. Enfriar escala ECS a cero antes de retirar el plano runtime y solicita detener
   RDS; es idempotente y siempre esta permitido.
4. Calentar crea el plano runtime con ECS en cero. Activar tareas exige DRG-00/01,
   secretos y evidencias externas; la CLI no firma ni acepta gates.
5. Todo plan rechaza borrados de recursos persistentes, cambio de cuenta/region,
   IP publica de tareas, egress general del worker o datos reales autoautorizados.
6. Ningun comando imprime secretos, tfvars, documentos, payload financiero ni
   el entorno completo.
7. Las acciones mutantes requieren `--apply`; sin ella solo se planifica.

# Verificacion

- Pruebas unitarias y mutaciones de los modos `cold`/`warm`.
- `tofu validate` y planes guardados reales en la cuenta autorizada, sin apply.
- Validador de plan ejecutado sobre ambos perfiles.
- Quality gate sobre el indice Git y handoff reproducible.

# Fuera de alcance

Aplicar la infraestructura definitiva, publicar DNS, cargar secretos, aceptar
DRG-00/01, encender datos reales, pentest o emitir revision independiente.
