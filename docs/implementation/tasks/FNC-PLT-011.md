---
task: FNC-PLT-011
title: Laboratorio remoto AWS T1 con runtime sintetico
status: in_progress
implementer: Integration Steward
base_sha: 6a6822b
gate: T1-SYNTHETIC-RUNTIME
data_ceiling: synthetic_only
cloud_provider: AWS
cloud_region: sa-east-1
independent_reviewers: [Security, Architecture, Platform, QA]
---

# Resultado esperado

Ejecutar la plataforma web completa en un unico host EC2 temporal, sin ingress publico,
para pruebas operativas reales con usuarios humanos y datos exclusivamente sinteticos.
El laboratorio no se presenta como staging ni produccion y no habilita DRG-00/DRG-01.

## Autorizacion y presupuesto

- El Founder solicito avanzar hasta pruebas reales sobre la cuenta AWS Free el 2026-08-28.
- Tipo maximo: `t3.small`, on-demand, creditos `standard`, una sola instancia.
- Precio observado por Pricing API: USD 0.0336/h en `sa-east-1`.
- Cada arranque programa apagado del host a las cuatro horas.
- Sin Elastic IP, RDS, NAT, ALB, Fargate, Route53 ni dominio.

## Rutas

- `infra/aws/t1/**`
- `docs/platform/AWS_T1_REMOTE_LAB.md`
- `docs/platform/aws-t1-remote-lab.json`
- `docs/adr/ADR-030-aws-t1-remote-lab.md`
- `tools/aws_t1/**`
- `docs/implementation/handoffs/FNC-PLT-011.md`
- Registros centrales integrados por Integration Steward.

## Criterios de aceptacion

1. Imagen Amazon Linux 2023 x86_64, tipo `t3.small` y volumen gp3 cifrado de 16 GiB.
2. IMDSv2 obligatorio, hop limit 1, sin key pair y sin ingress.
3. Creditos CPU `standard`, apagado iniciado por instancia produce `stop` y timer maximo 4h.
4. Acceso humano solo mediante Session Manager port forwarding a loopback.
5. Imagenes API/web/worker publicadas por digest inmutable en ECR.
6. PostgreSQL, Valkey y MinIO solo en la red Docker interna; web/API ligadas a loopback.
7. Claves de laboratorio se generan en el host, modo 0600, y no entran a user data,
   OpenTofu, S3, Git, logs ni AWS Parameter Store.
8. Migraciones y seed sintetico ocurren antes de API/worker/web.
9. Plan JSON solo permite creaciones allowlisted y cero RDS/NAT/ALB/ECS/KMS/secrets.
10. Smoke, E2E, tenancy, backup/restore y apagado se verifican con evidencia.

## Fuera de alcance

- Datos financieros reales, conectores, IA externa, pagos o correo real.
- IdP Cognito en la aplicacion; el laboratorio usa las identidades sinteticas existentes.
- Alta disponibilidad, dominio, HTTPS publico, WAF, RDS o produccion.
- Aceptar ADR-030 o superar S1-READY, DRG-00, DRG-01 o GA-01.
