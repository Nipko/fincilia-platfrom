---
id: FNC-GAT-007
title: Preflight ejecutable del entorno aislado DRG-00
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: aadef53f37c4043190a1fff6b7375d690212b30e
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Platform/SRE, QA]
---

# Resultado

El controlador de solo lectura concilia el inventario remoto de OpenTofu con
un conjunto mínimo cerrado de recursos persistentes y temporales del entorno
`private-pilot`. El reporte separa ausencia, estado parcial y completitud, y
nunca convierte la mera existencia de infraestructura en aceptación del gate.

# Rutas

- Permitidas: `tools/aws_pilot_control`, `infra/aws/private-pilot/pilotctl.ps1`,
  documentación de plataforma/seguridad, esta ficha, evidencia y handoff;
  archivos centrales únicamente por el Integration Steward.
- Prohibidas: `apply`, datos o secretos, valores de Secrets Manager, estado
  OpenTofu completo, producto API/web, migraciones y decisiones humanas.

# Criterios de aceptación

1. La consulta verifica cuenta y región antes de observar el entorno.
2. Solo lee direcciones mediante `tofu state list`; nunca serializa valores,
   outputs, endpoints, credenciales ni el entorno de proceso.
3. Un estado remoto ausente, parcial o ilegible no se presenta como completo.
4. Foundation y runtime usan inventarios mínimos distintos y enumeran cada
   dirección faltante de forma determinista.
5. Incluso un inventario completo conserva `G00-ISOLATED-ENV=pending` hasta
   admisión del release, drill en el target y revisión independiente.
6. `real_data_authorized` permanece siempre en `false`.

# Verificación

- Pruebas positivas y adversariales del controlador.
- Validadores de IaC, publicación de imágenes, DRG y grafo de trabajo.
- Consulta live read-only en la cuenta exacta cuando exista sesión temporal.
- Quality gate, CI verde y handoff reproducible.

# Fuera de alcance

Crear los recursos del piloto, leer secretos, publicar imágenes, admitir un
release, ejecutar el drill target, aceptar DRG-00/01 o emitir la revisión de
Security/Platform/QA.
