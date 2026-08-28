# Evaluación AWS Free Tier para el arranque de Fincilia

Estado: **evaluación técnica completa; despliegue y gasto no autorizados** · Revisión
`FNC-ARC-003-R1` · Corte de evidencia: 2026-08-28.

## Veredicto

Sí podemos usar AWS para una primera prueba cloud con datos exclusivamente sintéticos y
mantener el desembolso en cero si la cuenta resulta elegible y el consumo permanece dentro
de sus créditos/asignaciones. No podemos sostener con rigor que el laboratorio `DRG-00`, y
mucho menos producción, sea completamente gratuito.

La separación es deliberada:

| Nivel | ¿Puede arrancar sin desembolso? | Qué demuestra | Qué no demuestra |
|---|---|---|---|
| T0, spike sintético | Condicional | IaC, Cognito/OIDC, S3, RDS, migraciones/RLS, tamaño y latencia | Seguridad de datos reales, disponibilidad productiva o A-02 |
| T1, laboratorio DRG-00 | No como promesa permanente | Investigación limitada una vez firmados todos los gates | Piloto real o producción |
| T2, producción | No | Operación resiliente y gobernada | — |

La dirección aprobada por el Founder es evaluar primero AWS `sa-east-1` (São Paulo). Esto
no marca A-02 como aceptada, no autoriza gasto ni permite información real.

## Por qué el Free Tier sí ayuda

- El programa vigente para cuentas nuevas ofrece un plan gratuito de hasta seis meses o
  hasta agotar créditos, con USD 100 al registro y hasta USD 100 adicionales. Los créditos
  vencen a los doce meses. La elegibilidad exacta depende de la fecha y plan de la cuenta.
- Cognito Essentials conserva una asignación gratuita de 10.000 usuarios activos mensuales
  para acceso directo/social, permite desactivar el autorregistro, crear usuarios por
  invitación y usar passkeys.
- El volumen máximo inicial aprobado —10 archivos de 25 MiB— suma 250 MiB de entrada, muy
  por debajo de la asignación documentada de 5 GB de S3, aunque derivados, versiones y
  auditoría también consumen espacio.
- RDS PostgreSQL ofrece una asignación inicial Single-AZ elegible con 750 horas, 20 GB de
  almacenamiento y 20 GB de backup. Es suficiente para un spike pequeño, no para declarar
  alta disponibilidad.
- El primer trail de eventos de administración de CloudTrail puede mantenerse con costo de
  servicio nulo; S3 y eventos de datos siguen teniendo costo/consumo propio.

Fuentes: [AWS Free Tier](https://aws.amazon.com/free/), [FAQ vigente](https://aws.amazon.com/free/free-tier-faqs/),
[Cognito](https://aws.amazon.com/cognito/pricing/), [RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/),
[S3](https://docs.aws.amazon.com/hands-on/latest/backup-files-to-amazon-s3/backup-files-to-amazon-s3.html) y
[CloudTrail](https://aws.amazon.com/cloudtrail/pricing/).

## Por qué no debemos llamar gratis al laboratorio real

Los controles que `FNC-SEC-003` exige para un corpus financiero real incluyen llaves
separadas, secretos rotables, rutas privadas, auditoría, restore y una identidad con
autenticación resistente a phishing. Varios generan costo desde el inicio:

- cada llave administrada por el cliente en KMS cuesta USD 1/mes más solicitudes aplicables;
- Secrets Manager cobra por secreto y llamadas (la referencia pública usa USD 0,40 por
  secreto/mes);
- Fargate cobra vCPU, memoria y almacenamiento mientras ejecuta;
- NAT Gateway cobra por hora y por GB;
- un Application Load Balancer cobra por hora y LCU;
- los interface endpoints privados se cobran por AZ y hora, aunque el gateway endpoint de
  S3 no añade cargo;
- Multi-AZ RDS no forma parte de la asignación gratuita descrita.

Fuentes: [KMS](https://aws.amazon.com/kms/pricing/), [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/),
[Fargate](https://aws.amazon.com/fargate/pricing/), [VPC/NAT](https://aws.amazon.com/vpc/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/) y
[gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html).

Además, Cognito soporta passkeys pero no impone attestation del autenticador. Por eso es una
buena opción para probar invitaciones e identidad, pero todavía no demuestra por sí solo el
step-up AAL3 exigido por `IAM-04` del laboratorio.

## Topología T0 recomendada

- Cuenta AWS independiente y temporal, sin AWS Organizations ni Control Tower: incorporarla
  finaliza el Free Plan según el FAQ vigente.
- Región `sa-east-1`; solo datos sintéticos.
- Cognito Essentials, autorregistro deshabilitado e invitaciones administrativas.
- S3 con bloqueo público, versionado y planos separados por política.
- RDS PostgreSQL micro elegible, Single-AZ, 20 GB y restore ensayado.
- Un host EC2 para web/API y worker bajo demanda; Valkey efímero en el mismo host. El tipo de
  instancia no se elige hasta medir memoria e imágenes, y ARM64 no se presume.
- ECR privado solo si las tres imágenes comprimidas caben en la asignación; siempre por
  digest.
- CloudTrail básico y un gateway endpoint S3.
- Sin NAT Gateway, ALB, Fargate 24×7, WAF, IA externa, PDF, conectores ni datos reales.

Esta topología preserva los contenedores actuales. Reescribir FastAPI/Next/worker a Lambda
solo para perseguir gratuidad generaría una segunda arquitectura y no se recomienda.

## Condiciones antes de crear un recurso

1. Confirmar fecha de creación, plan, créditos y vencimiento de la cuenta AWS.
2. Medir memoria, CPU y tamaño comprimido de las tres imágenes.
3. Exportar una estimación del AWS Pricing Calculator para `sa-east-1`.
4. El Founder fija un tope mensual; hoy la autorización de gasto es USD 0.
5. Crear alertas de presupuesto/anomalías, etiquetas de expiración y runbook de destrucción.
6. Desplegar por IaC reproducible y destruir T0 en un máximo de 30 días.
7. Mantener `FINCILIA_REAL_DATA_ENABLED=false` y `FINCILIA_AI_GATEWAY_ENABLED=false`.

El contrato ejecutable completo, fuentes y condiciones están en
`aws-free-tier-evaluation.json`.
