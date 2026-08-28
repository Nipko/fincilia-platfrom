---
task: FNC-ARC-003
revision: R1
status: REVIEW_PENDING
implementer: Integration Steward
base_sha: 55089a7f7e613af26aeb6b69a474e1fd56493e3e
data_used: synthetic_only
cloud_resources_created: false
cloud_spend_authorized_usd: 0
human_acceptance: preferred_candidate_only
---

# Handoff FNC-ARC-003-R1 — AWS Free Tier

## Entrega

- Dirección provisional del Founder registrada: evaluar primero AWS `sa-east-1` y Cognito
  por invitación, sin aceptar A-02.
- Evaluación ejecutable de doce servicios y tres niveles: spike sintético, laboratorio
  DRG-00 y producción.
- Restricciones que impiden convertir créditos temporales en una promesa de infraestructura
  gratuita.
- Cost traps explícitos: NAT Gateway, ALB, endpoints de interfaz, Fargate 24×7, Multi-AZ,
  logs y egress.
- Contrato que rechaza gasto, despliegue, datos reales, precio inventado o promoción de
  A-02.

## Decisión técnica

El Free Tier puede soportar un spike cloud de máximo 30 días y solo con datos sintéticos.
No cubre como promesa estable todos los controles del laboratorio real ni producción. La
cuenta AWS, su plan y su saldo de créditos no fueron inspeccionados, por lo que la
elegibilidad permanece desconocida y el precio mensual permanece `null`.

## Verificación

```powershell
python -m tools.aws_free_tier.validate
python -m unittest tools.aws_free_tier.test_validate -v
python -m tools.region_decision.validate
python -m unittest tools.region_decision.test_validate -v
```

Resultado observado: ambos contratos válidos; 20/20 pruebas AWS y 13/13 pruebas A-02 en
verde. `tools.test_catalog.cli validate` permaneció válido, sin findings bloqueantes, y sus
36 pruebas pasaron. `tools.quality_gate.cli` reportó `ok: true` sobre el índice Git previo a
la integración; debe repetirse después de indexar estas rutas.

## Pendientes humanos y externos

1. Founder aporta fecha de creación/plan/saldo de la cuenta y fija tope mensual.
2. Finance conserva un export del AWS Pricing Calculator para `sa-east-1` después de medir
   imágenes y memoria.
3. Legal/Privacy/Security/Architecture cierran `A02-G01..G10`; esta revisión no los mueve.
4. Ningún recurso se crea hasta una autorización separada de IaC y gasto.

## Rollback

Revertir el commit de esta revisión elimina exclusivamente evaluación, validador, pruebas y
referencias de gobierno. No hay infraestructura ni datos que destruir.
