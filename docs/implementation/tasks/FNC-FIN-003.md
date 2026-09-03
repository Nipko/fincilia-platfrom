---
id: FNC-FIN-003
title: Decisión de costo regional para UAT en AWS
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 592bb442cf603eb0a54d1585efdbcc33a0a1d27b
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Finance, Platform/SRE, Security]
---

# Resultado esperado

Contrastar con tarifas oficiales de `sa-east-1` el entorno UAT que ya sirve
`fincilia.com` y el plano `private-pilot` de FNC-PLT-012. La salida debe permitir
elegir la arquitectura de pruebas sin confundir créditos con costo cero ni
autorizar cambios cloud.

# Rutas

- Permitidas: `tools/aws_cost_envelope`, `docs/platform/aws-uat-cost-decision.*`,
  esta ficha, evidencia y handoff; archivos centrales sólo por Integration Steward.
- Sólo lectura: AWS Pricing, Cost Explorer, Budgets, inventario EC2/RDS y los
  contratos FNC-BET-001/FNC-PLT-012/FNC-FIN-002.
- Prohibidas: `apply`, cambios IaC, escritura en AWS, secretos, identificadores
  cloud en evidencia, API/web, migraciones, datos reales y decisiones de gate.

# Criterios de aceptación

1. La identidad AWS se verifica sin persistir cuenta, ARN ni credenciales.
2. El inventario live se reduce a tipo, estado, capacidad y conteo.
3. Cada tarifa regional conserva SKU, unidad, vigencia y fuente primaria.
4. Los escenarios mensuales usan `Decimal`, 730 horas y aritmética reproducible.
5. Se separa el costo del UAT vigente, el plano privado frío, el plano caliente
   detenido y el plano caliente activo.
6. La recomendación no modifica recursos ni convierte el presupuesto en hard cap.
7. `apply`, despliegue, datos reales y promoción a producción permanecen falsos.

# Verificación

- Pruebas positivas y mutaciones adversariales del contrato.
- Validadores FNC-FIN-002, AWS private-pilot y DRG-01.
- Grafo de trabajo, quality gate y CI.

# Fuera de alcance

Subir el presupuesto, destruir el laboratorio detenido, aplicar private-pilot,
habilitar documentos reales o aceptar revisiones independientes.
