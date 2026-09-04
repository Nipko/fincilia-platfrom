---
id: FNC-PLT-016
title: Bootstrap seguro de roles y secretos PostgreSQL para AWS
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: ae8aeb7fd77b0440d025749dbd3446b5474b2f0a
gate: DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Database, Security, Platform/SRE, QA]
---

# Resultado esperado

Cerrar el hueco entre la instancia RDS administrada y el aplicador de
migraciones: crear o rotar de forma idempotente los roles PostgreSQL de minimo
privilegio que exige el esquema, sin exponer la credencial maestra ni contrasenas
de runtime en argumentos, logs, archivos o estado OpenTofu.

# Autorizacion y limites

El Founder autorizo el 3 de septiembre de 2026 montar en AWS lo necesario para
dejar Fincilia utilizable. Esta tarea prepara el bootstrap y el job de migracion,
pero no enciende servicios, no acepta gates y no autoriza datos reales.

- Permitidas: `db/bootstrap`, `infra/aws/private-pilot`,
  `tools/database_bootstrap`, documentacion de plataforma, esta ficha, handoff,
  backlog y `CURRENT_PHASE.md`.
- Prohibidas: guardar valores secretos en Git o OpenTofu, usar el usuario master
  como runtime, conceder `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `BYPASSRLS` o
  propiedad del esquema a la aplicacion, iniciar ECS o mover DRG-00/DRG-01.

# Criterios de aceptacion

1. El bootstrap acepta credenciales solo por variables de entorno inyectadas
   desde Secrets Manager y nunca imprime sus valores.
2. Crea exactamente `fincilia_app`, `fincilia_worker` y
   `fincilia_migrator` con login, y `fincilia_dispatch` y
   `fincilia_identity` sin login; todos sin privilegios globales peligrosos.
3. Repetirlo rota las tres credenciales login sin ampliar privilegios y conserva
   los roles autoridad sin login.
4. El migrador recibe solo pertenencia `NOINHERIT` a dispatch/identity y `CREATE`
   sobre la base exacta; `PUBLIC` pierde `CREATE` sobre el esquema `public`.
5. Un task definition separado usa la credencial maestra administrada por RDS,
   una ejecucion IAM separada y red privada; los servicios normales no pueden
   leer la credencial maestra.
6. El migrador sigue siendo un job separado, posterior al bootstrap y anterior
   al arranque de API/worker.
7. Pruebas unitarias, pruebas contra PostgreSQL real, OpenTofu validate, quality
   gate y CI prueban tanto el camino feliz como privilegios negados.

# Fuera de alcance

Upgrade comercial de AWS, ejecutar el bootstrap en la cuenta, aplicar
migraciones remotas, poblar atestaciones KMS, encender runtime, aceptar ADR o
usar datos reales.
