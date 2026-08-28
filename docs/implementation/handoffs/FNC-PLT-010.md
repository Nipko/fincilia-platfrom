---
task_id: FNC-PLT-010
status: REVIEW_PENDING
base_sha: c1ef454
implementation_sha: 0a531c0
integration_sha: 2fa832c
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Architecture, Platform, QA]
---

# Handoff FNC-PLT-010

## Resultado entregado

Fincilia dispone de un control plane AWS T0 reproducible en `sa-east-1`, autenticado
exclusivamente mediante credenciales temporales de `aws login`. OpenTofu `1.12.6` y el
provider AWS `6.59.0` están fijados y verificados por lockfile. El account ID se inyecta
localmente y no aparece en el repositorio.

Se aplicaron dos estados separados:

- Bootstrap local fuera del repo: 8 recursos administrados que crean y protegen el bucket
  de estado.
- Estado remoto S3 con locking nativo: 45 recursos administrados de red, almacenamiento,
  ECR, Cognito, IAM, CloudTrail y presupuesto.

Ambos planes posteriores terminaron en `No changes`. No se desplegaron servidores ni se
subieron datos.

## Controles efectivos

- S3: bloqueo público en cuatro banderas, TLS-only, `BucketOwnerEnforced`, versionado,
  SSE-S3 y lifecycle. El estado remoto tiene versión y cifrado `AES256` observados.
- ECR: tres repositorios, tags `IMMUTABLE`, scan on push y AES-256; lifecycle conserva las
  diez imágenes más recientes.
- Cognito: tier Essentials, MFA TOTP `ON`, alta exclusivamente administrativa, cliente
  OAuth authorization code sin secreto y cero usuarios observados.
- CloudTrail: single-region, management events, validación de logs, logging activo y sin
  errores de entrega o digest observados.
- IAM: rol de runtime sin access keys, trust solo EC2, SSM administrado y política inline
  limitada a prefijos sintéticos S3 y pull de los tres ECR.
- Red: VPC propia, una subred pública, dos privadas sin ruta por defecto, endpoint gateway
  S3 gratuito y security groups sin ingress público.
- Costos: presupuesto bruto mensual USD 5 con créditos excluidos del cómputo; Free Plan
  permanece activo y no se habilitaron Organizations ni Control Tower.

## Evidencia reproducible

- `tofu fmt -check -recursive infra/aws`: OK.
- `tofu validate` en bootstrap y T0: OK.
- `python3 -m unittest tools.aws_t0.test_validate`: 22 pruebas, OK.
- `python3 -m tools.aws_t0.validate`: OK.
- Plan bootstrap JSON: 8 create, 0 change, 0 destroy; allowlist OK.
- Plan T0 JSON: 45 create, 0 change, 0 destroy; allowlist OK.
- Plan bootstrap posterior: `No changes`.
- Plan T0 posterior: `No changes`.
- `python3 -m tools.quality_gate.cli` sobre el índice funcional: OK.
- Lectura directa AWS: CloudTrail logging true sin errores; Cognito MFA/admin-only/0 users;
  ECR 3/3 immutable y scan on push; S3 privado/versionado/cifrado.
- Inventario directo: 0 EC2, 0 RDS, 0 NAT Gateway, 0 load balancers y 0 ECS clusters.

Los planes, estados, outputs, IDs y account ID no se versionaron. El estado bootstrap vive
con modo `0600`; el principal vive en el backend S3.

## Hallazgos durante ejecución

1. Las etiquetas por `default_tags` aparecen en `tags_all` del plan JSON. El validador
   ahora une `tags` y `tags_all` y conserva la exigencia exacta de cinco tags.
2. Un apply puede seguir activo cuando la salida de la herramienta cliente se desprende.
   Se comprobó proceso, lock y estado antes de reintentar; no se ejecutó un segundo apply
   concurrente.
3. El archivo `/tmp` del primer plan principal no sobrevivió entre sesiones WSL. La
   ejecución final encadenó plan, JSON, validación y apply para garantizar identidad.
4. ECR expone `scanOnPush` en `imageScanningConfiguration`; el campo legacy es null. La
   propiedad efectiva quedó true en los tres repositorios.

## Límites y revisión pendiente

Esto no acepta ADR-029 para producción, no mueve A-02, S-01, DRG-00 ni DRG-01, y no
autoriza datos reales. Security debe revisar IAM, buckets y Cognito; Architecture, la
separación bootstrap/control plane; Platform, lifecycle/teardown/costo; QA, el validador
de planes. El implementador y `FOUNDER-01` no cuentan como revisores independientes.

## Rollback

La fecha operativa de expiración es 2026-09-27. El teardown requiere:

1. generar `tofu plan -destroy` del módulo T0;
2. inspeccionar el JSON y confirmar que solo contiene recursos T0;
3. retirar objetos sintéticos y logs de los buckets mediante una tarea destructiva
   explícitamente autorizada;
4. aplicar el destroy principal;
5. comprobar inventario vacío;
6. solo entonces retirar `prevent_destroy` del bootstrap y destruir el bucket de estado.

No usar `force_destroy`, `aws s3 rm --recursive`, prune global ni borrado manual fuera de
una tarea de teardown con targets resueltos.

## Rutas liberadas

`infra/aws/bootstrap`, `infra/aws/t0`, contrato/documentación/validador AWS T0, ADR-029,
ficha, catálogo de prueba y registros centrales de FNC-PLT-010.
