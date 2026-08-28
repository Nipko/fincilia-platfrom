---
id: FNC-PLT-012
status: REVIEW_PENDING
base_sha: 8cdb5f4
contract_sha: 04bf2bc
integration_sha: 5b88ea2
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy/Legal, Platform/SRE, QA]
---

# Handoff FNC-PLT-012 — foundation AWS private-pilot

## Resultado integrado

`infra/aws/private-pilot` materializa una frontera separada para el futuro
piloto con datos propios. Su estado, VPC, buckets, secretos, base, cache,
identidad y logs no se comparten con T0/T1 ni con la beta sintética.

- ALB en dos zonas, ACM, WAF y únicamente 80/443 públicos.
- API/web en Fargate privado y worker en una subred sin default route.
- RDS PostgreSQL 17 privado con TLS forzado, CMK, backups de 14 días,
  credencial master administrada por RDS y protección contra borrado.
- Valkey privado, cifrado y explícitamente efímero.
- Buckets `quarantine`, `raw`, `derived` y `exports` separados, versionados,
  sin acceso público y cifrados por claves de zona.
- CloudTrail con CMK, logs de WAF/RDS/runtime cifrados y tres alarmas.
- Cognito exige MFA, Code + PKCE y scopes mínimos. Google se configura fuera de
  IaC para que su client secret no entre al estado.
- Roles distintos de ejecución, aplicación, worker y migración; el runtime
  puede `kms:Verify` pero nunca `kms:Sign`.
- Los cuatro secretos se crean sin valor. Foundation fija ambos servicios en
  `desired_count = 0` y los tres contenedores mantienen datos reales apagados.

## Evidencia reproducible

| Verificación | Resultado |
| --- | --- |
| `tofu init -backend=false` en directorio temporal Linux | provider AWS 6.59.0 fijado, OK |
| `tofu validate` | configuración válida |
| `tofu fmt -check -recursive` | OK |
| `python -m tools.aws_private_pilot.validate` | contrato y fuentes válidos; despliegue/datos no autorizados |
| `python -m unittest tools.aws_private_pilot.test_validate` | 21 pruebas adversariales, OK |
| `python -m tools.runtime_config.validate` | 52 variables, OK |
| `python -m unittest tools.runtime_config.test_validate` | 11 pruebas, OK |
| build Next.js/TypeScript + lint | OK |
| Vitest web | 39 archivos, 244 pruebas, OK |
| `python -m tools.quality_gate.cli` sobre índice | `ok: true`, 0 hallazgos |

La revisión visual confirmó las etiquetas “Piloto privado” y “acceso por
invitación” sin afirmar que DRG-01 ya esté cumplido.

## Decisiones y divergencias visibles

1. Application Load Balancer exige dos subredes de AZ distintas; el módulo crea
   la VPC completa para no reutilizar la frontera sintética.
2. ALB access logs usan un bucket separado con SSE-S3 porque AWS no permite
   SSE-KMS para esos logs. CloudTrail y los demás logs conservan CMK. El contrato
   hace fallar una mutación que oculte esta restricción.
3. La aplicación usa un NAT para Cognito; el worker no recibe esa ruta y consume
   ECR, S3, Logs, Secrets Manager, KMS y SSM por endpoints privados.
4. El plan inicial crea recursos de costo continuo; no cabe en una afirmación de
   capa gratuita. Los créditos son financiación temporal, no un control.

## Trabajo externo pendiente

1. Renovar la sesión AWS, aportar dominio/prefijo Cognito y generar un plan
   contra la cuenta exacta. No se ejecutó `plan` ni `apply` en esta entrega.
2. Revisar en el plan disponibilidad/precio regional de PostgreSQL 17.11,
   `db.t4g.micro`, Valkey 8.1 y `cache.t4g.micro`.
3. Publicar challenge DNS de ACM y mantener `certificate_ready=false` hasta que
   el certificado figure `ISSUED`.
4. Poblar Secrets Manager sin imprimir valores; configurar Google en Cognito;
   ejecutar migración y luego pruebas sintéticas en el entorno vacío.
5. Demostrar inventario, borrado, restore, RLS/cross-tenant, cuarentena,
   canales deshabilitados, supply chain e incidente.
6. Obtener revisores nominales independientes. DRG-00/01 siguen `not_met`; el
   reporte válido conserva 21 bloqueos y `real_data_authorized=false`.

## Rollback

Antes de almacenar datos, conservar `desired_count=0` y retirar listeners/DNS es
reversible. Después de cualquier dato, no se usa `destroy` como atajo: primero
se revocan sesiones, se preservan auditoría/delete ledger y se concilian RDS,
S3, backups y retención.
