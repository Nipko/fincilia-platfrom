---
id: FNC-PLT-017
title: Ejecucion temporal del bootstrap y migraciones private-pilot AWS
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 4687604
gate: DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Database, Security, Platform/SRE, QA]
---

# Resultado esperado

Demostrar en la cuenta AWS real que la foundation puede calentarse con los
servicios en cero, preparar secretos fuera de IaC y ejecutar en orden el
bootstrap de roles y las migraciones. Tras capturar evidencia redactada, el
plano temporal vuelve a frío para evitar costo o exposición innecesarios.

# Autorización y alcance

El Founder autorizó completar en AWS el flujo necesario para UAT usando los
créditos elegibles y alertas de costo. Esta tarea no autoriza datos reales,
usuarios, DNS, tráfico público ni aceptación de gates.

- Permitidas: estado AWS `private-pilot`, `tools/database_bootstrap`,
  `infra/aws/private-pilot`, documentación/evidencia de plataforma, esta ficha,
  handoff y archivos centrales por Integration Steward.
- Prohibidas: cambiar secretos por argumentos o archivos, sembrar datos,
  escalar API/worker sobre cero, apuntar DNS, habilitar el listener sin
  certificado, aceptar DRG-00/01 o usar documentos reales.

# Criterios de aceptación

1. Los tres digests ECR exactos existen y corresponden a la release admitida.
2. El plan warm validado no contiene borrados, mantiene `desired_count=0` y
   `real_data_authorized=false`.
3. Warm deja el plano apto para bootstrap, inicia RDS y mantiene toda capacidad
   en cero. Mientras ACM no esté validado, reporta como bloqueos explícitos el
   listener HTTPS y el servicio de aplicación; no los sustituye por HTTP.
4. `prepare-secrets` escribe por stdin cuatro secretos independientes y no
   expone valores, endpoint, ARN ni credenciales.
5. Bootstrap termina antes del migrador; ambos one-off salen con código cero,
   sin IP pública ni ECS Exec.
6. Las migraciones llegan a la última versión sin ejecutar semillas.
7. El cierre cold retira el runtime, detiene RDS y el plan posterior queda
   convergente sin tocar storage persistente.
8. Pruebas, validadores, work graph, quality gate y CI permanecen verdes.

# Rollback

El controlador `cold` elimina sólo el plano temporal autorizado, conserva RDS,
S3, KMS, ECR, secretos, logs y backups, escala ECS a cero y detiene RDS. Nunca
se usa `tofu destroy`.
