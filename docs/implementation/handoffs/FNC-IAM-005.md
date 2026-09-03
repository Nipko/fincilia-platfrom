---
task: FNC-IAM-005
status: REVIEW_PENDING
base_sha: 378f6de76deb6da08030f940d6558b17c81d30a6
implementation_sha: 6ff3d64
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-IAM-005 — preflight Google UAT

## Resultado

La sonda Cognito puede descubrir pool, cliente publico y dominio directamente
desde los outputs T0 sin imprimirlos ni pedir que el operador los copie. OpenTofu
y AWS usan vectores de argumentos con `shell=False`; errores, truncamiento,
traversal, rutas externas y outputs incompletos fallan con mensajes neutros.

Los 16 controles de Cognito siguen declarando `activation_authorized=false` y
`real_data_authorized=false` aun si todos pasan. FNC-IAM-004 ya dejo evidencia
live 16/16; durante esta ronda la repeticion encontro la sesion temporal AWS
expirada y fallo redactada, sin cambiar infraestructura.

## Verificacion

- `python -m unittest tools.identity_readiness.test_probe
  tools.identity_readiness.test_aws_cli tools.identity_readiness.test_cli
  tools.identity_readiness.test_tofu -v`: 16, OK.
- `python -m tools.quality_gate.cli`: cero hallazgos sobre el indice.
- Ningun ID, ARN, correo, token OAuth o secreto se escribio en los artefactos.

## Bloqueos

Google no debe activarse en el runtime UAT sintetico: ADR-012 exige DRG-00 para
tratar identidad real y el runtime administrado separado. Permanecen
`G00-ISOLATED-ENV`, Legal, Retention, Region y el dictamen independiente. El
Founder no cuenta como revisor independiente.

## Rollback

Revertir `6ff3d64` retira el modo de descubrimiento y la guia; no existe rollback
AWS porque esta tarea solo hizo lecturas y pruebas.
