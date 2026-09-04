---
id: FNC-GAT-007
title: Preflight ejecutable del entorno aislado DRG-00
status: review_pending
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

# Resultado integrado

- `status` concilia 36 direcciones mínimas de foundation y 11 del runtime sin
  leer valores del estado. El validador DRG consume este mismo catálogo para
  impedir que el bootstrap o un runtime nuevo dejen dos conteos paralelos.
- La consulta live del 3 de septiembre de 2026 confirmó cuenta/región exactas,
  inventario `0`, RDS/Valkey/ALB/ECS ausentes y cero NAT.
- El plan `cold` sobre `d466438` fue validado y resumido por digest: 142 altas,
  11 lecturas, cero actualizaciones y cero borrados; no se ejecutó `apply`.
- El agregador DRG ya no permite usar FNC-QA-001 como evidencia suficiente de
  `G00-ISOLATED-ENV`; exige un artefacto target distinto y estricto.
- El control permanece `pending`, los dos gates `not_met` y los datos reales
  desautorizados.

# Ronda de corrección R4

FNC-PLT-016 añadió roles de bootstrap, su secreto y una task definition. El
controlador los descubría, pero el agregador DRG conservaba literales 33/10.
Desde R4 los conteos se derivan de los conjuntos cerrados del controlador; una
evidencia completa ya no puede ser rechazada por deriva silenciosa entre
herramientas.
