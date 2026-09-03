---
id: FNC-FIN-002
title: Sobre de costo verificable para AWS private-pilot
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: c77e6b7
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Finance, Platform/SRE, Security]
---

# Resultado esperado

Convertir el plan `cold` observado de FNC-GAT-007 en un sobre de costo
ejecutable y redactado. Debe distinguir cantidad de recursos de servicios
facturables, separar piso fijo conocido de consumo variable y bloquear cualquier
autorización mientras falten cotización regional, tope nominal y revisión.

# Rutas

- Permitidas: `tools/aws_cost_envelope`, `docs/platform/aws-private-pilot-cost-envelope.*`,
  esta ficha, evidencia y handoff; archivos centrales sólo por Integration Steward.
- Sólo lectura: plan OpenTofu ignorado, IaC `private-pilot`, contratos AWS y
  evidencia FNC-GAT-007.
- Prohibidas: cambios IaC, `apply`, secretos, estado/outputs completos, API/web,
  migraciones, datos reales y decisiones de gate.

# Criterios de aceptación

1. El contrato se liga al digest del plan y sus 142/11/0/0 acciones.
2. Los 142 recursos se agrupan por tipo sin serializar valores del plan.
3. El piso conocido sólo usa tarifas primarias verificables y no se presenta
   como estimación mensual completa.
4. RDS, almacenamiento, logs, eventos, imágenes y plano `warm` permanecen
   explícitamente sin cotizar hasta obtener precios regionales vigentes.
5. Créditos, presupuesto y Free Tier no se confunden con costo cero ni con un
   hard cap.
6. `apply_authorized`, `deployment_authorized` y `real_data_authorized` quedan
   en `false`; una mutación de cualquiera debe fallar.

# Verificación

- Pruebas positivas y adversariales del contrato.
- Validador de AWS private-pilot y DRG-01.
- Grafo de trabajo, quality gate y CI.

# Fuera de alcance

Cotizar mediante una sesión AWS vencida, aceptar un precio, fijar el tope del
Founder, aplicar recursos o superar DRG-00/DRG-01.

# Resultado integrado

- 142 altas agrupadas en 41 tipos y ligadas por digest al plan observado.
- Piso conocido USD 6,60/mes, marcado como incompleto por construcción.
- Nueve costos fríos y siete calientes continúan visibles y sin cotizar.
- 17 pruebas adversariales, validadores y CI `33705645858` verdes.
- Ninguna autorización de apply, despliegue, gasto o datos reales fue emitida.
