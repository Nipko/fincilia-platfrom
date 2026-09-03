# Sobre de costo del private-pilot AWS

Estado: **revisión técnica lista; cotización y autorización pendientes**.

## Resultado

El plan `cold` observado crea 142 recursos declarativos, pero ese número no es
una estimación de factura. La mayoría son políticas, rutas, asociaciones y
controles sin precio unitario independiente. El piso mensual que sí puede
demostrarse con tarifas públicas es USD 6,60: cinco llaves KMS administradas por
el cliente y cuatro secretos declarados. Es un piso, no un total.

Faltan cotizar RDS y su almacenamiento/backup/secreto administrado, S3, eventos
de datos CloudTrail, logs/métricas, imágenes ECR y cualquier transferencia. El
modo `warm` agrega los mayores costos fijos: NAT, seis interface endpoints, ALB,
WAF, Valkey y, sólo cuando se escale por encima de cero, Fargate.

## Decisión operativa

No se debe autorizar el plan por su cantidad de recursos ni por disponer de
créditos. Primero se necesita una cotización completa para `sa-east-1`, horas
mensuales máximas del plano caliente y un tope mensual nominal. Luego se
regenera el plan y la autorización debe nombrar su digest exacto.

La sesión temporal AWS usada para el inventario expiró antes de completar la
consulta regional de precios. El contrato conserva esos componentes como no
cotizados, sin inventar cifras ni rebajar el control.

## Fuentes primarias

- [AWS KMS pricing](https://aws.amazon.com/kms/pricing/)
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [Amazon RDS for PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/)
- [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/)
- [Amazon ElastiCache pricing](https://aws.amazon.com/elasticache/pricing/)

El modelo ejecutable está en `aws-private-pilot-cost-envelope.json`. No autoriza
`apply`, despliegue ni datos reales.
