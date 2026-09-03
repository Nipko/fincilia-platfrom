---
id: FNC-FIN-002
status: REVIEW_PENDING
base_sha: c77e6b790959f027a0e17071e62b7348ce4a0cd7
code_shas:
  - 3aaad1d86e34475343f43c3005212e13f8942224
  - 9cf2714a3ad1945e68ecebcf68db624a918c68a6
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_gate
author: Codex principal dev + Integration Steward
independent_reviewers: [Finance, Platform/SRE, Security]
---

# Handoff FNC-FIN-002 — sobre de costo AWS private-pilot

## Resultado

El plan `cold` de FNC-GAT-007 quedó convertido en un contrato ejecutable de
costo. Las 142 altas se desglosan en 41 tipos y están ligadas al plan por dos
digests: plan
`c99de724cfed0d804129d1ef62634c23054c4893bdc29cd265d1a8a938aaa914` e
inventario canónico
`aab161a070367cd4d872676f69a34c7fde31b7128263cd9d9b4b3b5b8f7713c2`.

El único piso mensual adjudicado es USD 6,60: cinco llaves KMS a USD 1 y cuatro
secretos declarados a USD 0,40. El modelo impide llamarlo estimación completa.
Nueve componentes `cold` y siete drivers `warm` permanecen explícitamente sin
cotizar, incluidos RDS, almacenamiento, logs/eventos, imágenes, NAT, endpoints,
ALB, WAF, Valkey y Fargate cuando la capacidad sea mayor que cero.

## Evidencia

- `tools.aws_cost_envelope`: contrato, CLI y 17 pruebas adversariales, OK.
- Suite combinada costo + controlador: 36 pruebas, OK.
- AWS private-pilot, DRG-01 y grafo de trabajo: válidos; 137 tareas/361 aristas.
- Quality gate sobre ambos índices de integración: OK, cero hallazgos.
- CI `33705645858` sobre `9cf2714`: `success`, incluidos PostgreSQL, API,
  worker, navegador y accesibilidad.
- Fuentes primarias: páginas de precios AWS para KMS, Secrets Manager, RDS,
  VPC, PrivateLink y ElastiCache, con corte 2026-09-03.

La ejecución indiscriminada de `unittest discover` desde el Python anfitrión no
es una suite válida: carece de `psycopg` y `tools/` no es un start directory
importable. No se contó como regresión. Las mismas suites DB se ejecutaron en la
imagen fijada de CI y pasaron.

## Bloqueos y decisiones pendientes

La sesión temporal AWS expiró antes de consultar el catálogo regional. Por eso
no se inventaron precios ni un total mensual. Antes de aplicar se requieren:
sesión nueva, cotización completa `sa-east-1`, límite de horas `warm`, tope
mensual del Founder, regeneración si hay drift, autorización ligada al digest y
revisión independiente Finance/Platform/Security.

Los USD 100 reportados por el Founder son créditos, no hard cap ni prueba de
costo cero. La autorización histórica de 27 recursos no cubre este plan.

## Límites

No se modificó IaC, no se ejecutó `apply`, no se creó ni cambió ningún recurso
AWS y no se leyó ningún secreto. `apply_authorized=false`,
`deployment_authorized=false` y `real_data_authorized=false`. Los 13 blockers
DRG permanecen.

## Rollback

Revertir `9cf2714` y `3aaad1d` elimina exclusivamente contrato, evidencia y
validador de costo. No existe rollback cloud porque no hubo mutación.
