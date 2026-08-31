---
id: FNC-SUP-003
title: Publicación OIDC de imágenes inmutables al piloto privado
epic: FNC-EP-PLATFORM
phase: F0
iteration: E1
type: implementation
status: in_progress
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Platform/SRE
implementer: Codex principal dev + Integration Steward
independent_reviewer: Security + QA + Platform/SRE
base_sha: f15ae9c
plan_refs: [29, 32, 36, 54]
adr_refs: [ADR-020, ADR-032, ADR-034]
dependencies: [FNC-SUP-002, FNC-PLT-012, FNC-PLT-013]
gate: DRG-01
gate_effect: evidence_only
allowed_data: synthetic_only
security_impact: high
privacy_impact: low
---

# Resultado esperado

Fincilia dispone de una ruta manual y fail-closed para publicar las imágenes
API, web y worker de un commit exacto en los repositorios ECR del entorno
`private-pilot`. GitHub obtiene credenciales AWS temporales mediante OIDC; no
existen access keys persistentes, permisos administrativos ni capacidad para
crear, borrar o volver mutables los repositorios.

Publicar una imagen no despliega servicios, no enciende el plano runtime, no
acepta gates y no autoriza datos reales.

# Base y alcance

- Base de reserva: `f15ae9c` sobre `main`.
- Datos autorizados: exclusivamente sintéticos.
- Rutas permitidas: `.github/workflows/publish-private-pilot.yml`,
  `infra/aws/private-pilot/**`, `tools/aws_image_publication/**`,
  `tools/aws_private_pilot/**`, `tools/aws_pilot_control/**`,
  `tools/quality_gate/**`, `tools/supply_chain/**`, `docs/platform/**`,
  `docs/adr/ADR-034-github-oidc-ecr-publication.md`,
  `docs/architecture/adr-readiness.json`, `tools/adr_readiness/**`, esta ficha,
  su handoff, CI y registros centrales modificados por el Integration Steward.
- Rutas prohibidas: producto API/web/worker, migraciones, secretos, fixtures,
  datos, aceptación de gates y cambios de semántica financiera.

# Invariantes

1. El workflow sólo usa `workflow_dispatch`, ambiente GitHub
   `private-pilot`, runner hospedado y los permisos GitHub estrictamente
   necesarios: `contents: read`, `id-token: write` y `attestations: write`.
2. La confianza AWS exige audiencia `sts.amazonaws.com` y el `sub` inmutable
   exacto del repositorio y ambiente; no admite comodines.
3. El rol sólo publica y consulta escaneo en
   `fincilia/private-pilot/{api,web,worker}`. No crea ni borra repositorios,
   imágenes, políticas, llaves, servicios o infraestructura.
4. Las Actions externas están fijadas a SHA completo y se inventarían por el
   baseline de cadena de suministro.
5. Se verifica que el SHA solicitado es un commit completo alcanzable desde
   `main`; la etiqueta usa el SHA completo y los outputs productivos son digests
   `sha256`, nunca tags mutables.
6. Las tres imágenes se construyen, prueban y publican en la misma ejecución.
   Un fallo en cualquier imagen deja el release incompleto y no genera un
   manifiesto apto para despliegue.
7. La publicación espera el escaneo ECR y falla ante hallazgos `CRITICAL` o
   estado distinto de `COMPLETE`.
8. El manifiesto final no contiene credenciales, tokens, payloads ni datos;
   liga commit, repositorio, digest y verificación de escaneo de las tres
   imágenes.
9. Ningún archivo de configuración local ignorado se vuelve fuente aprobada o
   entra al repositorio.

# Verificación

- Unitarias positivas y mutaciones negativas del contrato OIDC/IAM/workflow.
- `tofu fmt -check`, `tofu validate` y plan frío validado sin apply.
- Quality gate y supply-chain discovery sobre el índice Git.
- Revisión manual del plan antes de crear cualquier recurso AWS.

# Fuera de alcance

- Aplicar la fundación AWS, crear el ambiente GitHub o ejecutar el publicador.
- Poblar Secrets Manager, migrar, levantar ECS, cambiar DNS o cargar documentos.
- Declarar DRG-00/01, TM-005 o una revisión independiente como satisfechos.

# Rollback

Retirar el workflow y la política OIDC antes del apply. Después de un apply,
revocar primero la confianza del rol; las imágenes inmutables se conservan hasta
que la retención y el inventario autoricen su purga.
