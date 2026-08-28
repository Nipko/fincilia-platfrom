---
id: FNC-PLT-012
title: Entorno AWS separado para piloto privado con datos reales
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 8cdb5f4
gate: DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Platform/SRE, QA]
---

# Resultado

Un módulo OpenTofu crea la frontera `private-pilot` separada del laboratorio y
de la beta sintética. La infraestructura puede existir vacía, pero ninguna
tarea de aplicación procesa datos reales hasta recibir una atestación DRG-01
firmada en KMS que el binario verifica al arrancar.

# Arquitectura comprometida

- VPC propia en `sa-east-1`, dos zonas para el ALB y los stores.
- ALB HTTPS con ACM y WAF; no se publica API, worker, base, cache ni S3.
- API/web en Fargate privado; worker en segmento sin ruta general a Internet.
- PostgreSQL RDS, Valkey administrado y cuatro buckets por zona de evidencia.
- Claves KMS separadas para cuarentena, evidencia, auditoría y base.
- Cognito nominal, invitación de un uso y federación Google configurada sin
  guardar su secreto en OpenTofu.
- Secrets Manager contiene valores cargados fuera de IaC; el estado solo conoce
  nombres y ARN.
- SSM/ECS Exec, CloudTrail y logs cifrados; no hay SSH.

# Criterios de aceptación

1. El plan falla si usa otra cuenta, región o estado compartido con beta.
2. ALB usa dos subredes públicas y la aplicación no recibe IP pública.
3. Worker no tiene NAT/default route; solo alcanza stores y endpoints aprobados.
4. RDS no es público, fuerza TLS, cifra con CMK, conserva backups y protege borrado.
5. Todos los buckets bloquean acceso público, exigen TLS, versionan y cifran por zona.
6. IAM distingue ejecución, aplicación, worker y migración con recursos exactos.
7. Los secretos no tienen `secret_string` ni valores sensibles en HCL o estado.
8. Servicios empiezan con capacidad cero; activarlos no cambia por sí solo
   `real_data_authorized`.
9. WAF, CloudTrail, alarmas y budget existen antes de cualquier invitación.
10. El contrato y un plan JSON se validan con mutaciones adversariales.

# Fuera de alcance

Aplicar recursos, validar el dominio, cargar secretos, federar Google, aprobar
DRG-00/01, ejecutar pentest, emitir concepto legal o cargar un documento real.

# Evidencia integrada

- Contrato ejecutable: `04bf2bc`.
- Foundation OpenTofu, validadores y estado visual web: `5b88ea2`.
- Handoff: `docs/implementation/handoffs/FNC-PLT-012.md`.
- Estado: implementación lista para revisión; plan/apply, evidencia runtime y
  revisiones independientes permanecen pendientes.
