---
id: FNC-PLT-013
status: REVIEW_PENDING
base_sha: 09e601a
contract_sha: bfae09b
infra_sha: f06de25
controller_sha: 4799227
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, Privacy, QA]
---

# Handoff FNC-PLT-013 — ciclo de costo del piloto privado

## Resultado integrado

El entorno queda frío por defecto y separa explícitamente dos planos:

- Persistente: VPC, S3, KMS, RDS detenible, Cognito, secretos vacíos, ECR,
  CloudTrail, logs y backups.
- Temporal: NAT/EIP/rutas, seis endpoints Interface, ALB/listeners/WAF, Valkey,
  task definitions, servicios ECS y sus alarmas/logs exclusivos.

`pilotctl.ps1` ofrece `status`, `plan-cold`, `plan-warm`, `cold -Apply` y
`warm -Apply`. Cada operación verifica por STS la cuenta exacta y la región;
ninguna imprime variables, secretos o respuestas completas de identidad. Los
planes pasan por el validador antes del apply. `warm` conserva ECS a cero y no
autoriza datos. `cold` escala a cero antes de retirar runtime y solicita detener
RDS. No existe un camino que acepte DRG-00/01 desde la CLI.

## Evidencia

| Verificación | Resultado |
| --- | --- |
| `tofu validate` en directorio Linux limpio | OK |
| plan AWS `runtime_plane_enabled=false` | 139 creates; validator OK; sin NAT/ALB/Valkey/ECS/WAF |
| plan AWS `runtime_plane_enabled=true` | 164 creates; validator OK; ECS desired 0 |
| `python -m unittest tools.aws_private_pilot.test_validate` | 34 pruebas, OK |
| `python -m unittest tools.aws_pilot_control.test_control` | 14 pruebas, OK |
| `pilotctl.ps1 status` contra AWS | `mode=cold`; RDS/ALB/Valkey/ECS ausentes; NAT 0 |
| `pilotctl.ps1 warm` sin `-Apply` | rechazado antes de mutar AWS |
| quality gate sobre los commits funcionales | OK, 0 hallazgos |

Los planes se guardaron en `.terraform`, ruta ignorada, y no se aplicaron. No se
crearon recursos ni se cargaron datos en esta tarea.

## Controles de fallo

1. Un delete de recurso persistente invalida el plan.
2. Cuenta o región distinta detiene toda operación.
3. Un estado AWS desconocido no se interpreta como ausencia.
4. `cold` sólo deshabilita la protección del ALB después de escalar a cero; si
   el plan/apply falla antes de retirarlo, intenta reactivarla.
5. RDS en transición desconocida no se inicia ni detiene automáticamente.
6. El límite de parada RDS de siete días permanece visible: AWS puede reiniciar
   la instancia y el almacenamiento/auditoría siguen facturando en frío.

## Pendiente humano y externo

- Revisión independiente Security, Platform/SRE, Privacy y QA.
- Dominio definitivo, DNS/ACM, buzón presupuestal y tfvars local revisado.
- Apply inicial, secretos fuera de IaC, Google/Cognito, migración y evidencia
  sintética runtime.
- DRG-00/01 permanecen `not_met`; no se autorizan documentos financieros reales.
- Diseñar un watchdog administrado antes de depender de más de siete días de
  parada RDS; el controlador local no corre cuando el equipo está apagado.

## Rollback

`cold -Apply` es el rollback operativo previo a datos: capacidad cero, retiro
del plano temporal y solicitud de stop RDS. Después de datos autorizados no se
usa destroy; se ejecutan revocación, inventario, retención y purga conciliada.
