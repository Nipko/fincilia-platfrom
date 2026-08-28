---
task: FNC-PLT-010
title: Control plane AWS T0 exclusivamente sintetico
status: in_progress
implementer: Integration Steward
base_sha: c1ef454
gate: T0-SYNTHETIC
data_ceiling: synthetic_only
cloud_provider: AWS
cloud_region: sa-east-1
independent_reviewers: [Security, Architecture, Platform, QA]
---

# Resultado esperado

Crear por OpenTofu un control plane AWS temporal, reproducible y fail-closed para validar
estado remoto, red, almacenamiento, registro de imagenes, identidad administrada, auditoria
y control de costos sin desplegar EC2, RDS, NAT, ALB, Fargate ni informacion real.

## Autorizacion y limites

- El Founder autorizo iniciar el despliegue T0 el 2026-08-28 sobre la cuenta Free activa.
- Cuenta, perfil y creditos se verifican en preflight pero no se versionan.
- La autorizacion cubre el control plane definido en esta ficha, no runtime ni DRG-00.
- `FINCILIA_REAL_DATA_ENABLED` y cualquier IA externa permanecen deshabilitados.
- El entorno expira el 2026-09-27 y debe conservar un runbook de destruccion.

## Rutas

- `infra/aws/bootstrap/**`
- `infra/aws/t0/**`
- `docs/platform/AWS_T0_DEPLOYMENT.md`
- `docs/platform/aws-t0-deployment.json`
- `docs/adr/ADR-029-opentofu-aws-t0.md`
- `tools/aws_t0/**`
- `docs/implementation/handoffs/FNC-PLT-010.md`
- Archivos centrales integrados por Integration Steward.

## Criterios de aceptacion

1. OpenTofu y AWS provider quedan fijados por version y lockfile.
2. La sesion proviene de `aws login`; no hay access keys ni secretos versionados.
3. El account guard rechaza otra cuenta y la region es exactamente `sa-east-1`.
4. El estado principal usa S3 cifrado, versionado y lockfile nativo.
5. Buckets bloquean acceso publico, HTTP y conservan versionado/lifecycle sintetico.
6. Cognito deshabilita autorregistro y no asigna roles financieros por claims del cliente.
7. CloudTrail conserva una copia regional de management events con validacion de logs.
8. ECR usa tags inmutables y scan on push.
9. El plan inicial contiene cero EC2, RDS, NAT, ALB, Fargate, KMS administrado por cliente,
   IA, conectores o recursos multi-region.
10. El plan se inspecciona como JSON antes de aplicar y solo permite creaciones allowlisted.
11. El apply deja evidencia reproducible y el destroy queda ensayable, sin ejecutarlo.

## Fuera de alcance

- Desplegar la aplicacion o una base de datos.
- Cargar archivos reales o autorizar DRG-00/DRG-01.
- Aceptar ADR-020, S-01, L-01 o riesgos residuales.
- Convertir la cuenta a Paid, AWS Organizations o Control Tower.
