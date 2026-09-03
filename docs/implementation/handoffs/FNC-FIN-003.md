---
id: FNC-FIN-003
status: REVIEW_PENDING
base_sha: 592bb442cf603eb0a54d1585efdbcc33a0a1d27b
code_shas:
  - be76bf0e3103005b8795d1a63d83a2646f3794d7
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_gate
author: Codex principal dev + Integration Steward
independent_reviewers: [Finance, Platform/SRE, Security]
---

# Handoff FNC-FIN-003 — decisión de costo UAT AWS

## Resultado

Se verificó la identidad temporal AWS y se consultaron, en modo exclusivamente
read-only, EC2, EBS, Elastic IP, RDS, Budgets, Cost Explorer y Price List API.
La evidencia persistida sólo conserva conteos, capacidad y coincidencia de
cuenta; no contiene cuenta, ARN, resource ID, credencial ni código OAuth.

El UAT que sirve `fincilia.com` cuesta USD 31,826/mes de base regional:
`t3.small` USD 24,528, 24 GB gp3 USD 3,648 y una IPv4 USD 3,65. El volumen gp3
de 16 GB perteneciente al T1 detenido añade USD 2,432, por lo que la base fija
de la cuenta es USD 34,258 antes de uso variable. AWS Budgets observó USD 1,666
brutos y mantiene la alerta vigente en USD 35; Cost Explorer reportó costo neto
aproximadamente cero tras ajustes del programa.

La alternativa `private-pilot` resulta materialmente más costosa:

- `cold`: USD 36,20/mes.
- `warm` con servicios detenidos: USD 257,36/mes.
- `warm` con aplicación y worker mínimos: USD 319,264/mes.

Los totales calientes excluyen LCU, GB procesados, logs y solicitudes. La
recomendación es mantener y endurecer el host UAT existente y posponer el plano
privado administrado hasta que carga, disponibilidad o regulación lo justifiquen.

## Evidencia y verificación

- Diecisiete tarifas `sa-east-1` con SKU, unidad y fecha de vigencia.
- `python -m unittest tools.aws_cost_envelope.test_uat_model tools.aws_cost_envelope.test_model`:
  33 pruebas, OK.
- `python -m tools.aws_cost_envelope.cli uat-validate`: `ok: true`.
- `python -m tools.aws_cost_envelope.cli uat-report`: cinco subtotales exactos,
  `apply_authorized=false` y `real_data_authorized=false`.
- `python -m tools.aws_cost_envelope.cli validate`: FNC-FIN-002 sin regresión.
- Quality gate sobre el índice del código: OK, cero hallazgos.
- CI `33707969541` fue lanzado sobre `be76bf0`; estado al sellar: `in_progress`.

## Hallazgos

1. NAT y seis endpoints de interfaz suman USD 159,87/mes antes de tráfico; son
   el principal motivo para no aplicar el plano privado ahora.
2. La alerta actual de USD 35 queda a sólo USD 0,742 de la base fija calculada
   de la cuenta. Se recomienda USD 45 para absorber consumo variable, pero no se
   modificó porque AWS Budgets no es un hard cap y requiere decisión nominal.
3. Detener una instancia no elimina su EBS. El T1 detenido sigue añadiendo USD
   2,432/mes; eliminarlo o preservarlo como snapshot es una acción destructiva
   separada y no autorizada.
4. Los créditos explican que el neto pueda ser cercano a cero, pero no reducen
   la base bruta ni impiden un sobrecosto.

## Decisiones pendientes

- Founder: aceptar o rechazar elevar la alerta bruta de USD 35 a USD 45.
- Founder + Platform: conservar el T1 detenido hasta su expiración o preparar
  una retirada recuperable con evidencia.
- Finance/Platform/Security independientes: revisar tarifas, límites y postura.
- DRG-00/DRG-01: permanecen cerrados; no hay autorización de datos reales.

## Límites y rollback

No hubo escritura AWS, `apply`, despliegue, borrado ni lectura de datos de
negocio. Revertir `be76bf0` y el commit de este handoff retira únicamente el
modelo, pruebas, documentación y seguimiento. No existe rollback cloud.
