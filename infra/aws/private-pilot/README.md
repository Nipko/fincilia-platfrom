# Fincilia private-pilot foundation

Módulo OpenTofu de `FNC-PLT-012/FNC-PLT-013`. Crea una frontera AWS nueva con
modo `cold` por defecto. `warm` incorpora el plano temporal y mantiene ECS con
`desired_count = 0`. No comparte datos ni estado con T0/T1/closed-beta y no
autoriza documentos reales.

Lee primero:

- `docs/platform/AWS_PRIVATE_PILOT.md`
- `docs/platform/aws-private-pilot.json`
- `docs/platform/AWS_IMAGE_PUBLICATION.md`
- `docs/platform/aws-image-publication.json`
- `docs/security/DRG01_READINESS.md`
- `docs/adr/ADR-032-aws-private-real-data-pilot.md`

Copiar `pilot.auto.tfvars.example` como `pilot.auto.tfvars`; el segundo está
ignorado por Git y nunca lleva secretos. Usar `pilotctl.ps1 status`,
`commercial-preflight`, `plan-warm`, `warm -Apply`, `plan-cold` y
`cold -Apply` desde la raíz.

El primer `apply` solo puede crear foundation. ACM requiere publicar el challenge
DNS que aparece en `required_dns_records`; `certificate_ready` permanece `false`
hasta verificar que AWS emitió el certificado. Los cuatro secretos se crean sin
valor y deben poblarse fuera de OpenTofu.

La foundation crea además un proveedor GitHub OIDC y el rol
`fincilia-private-pilot-ecr-publisher`. Su confianza exige el sujeto inmutable
del repositorio y el ambiente `private-pilot`; el output
`github_ecr_publisher_role_arn` se configura como variable no secreta del
ambiente GitHub. El rol no despliega, no borra y no administra infraestructura.

No uses datos reales para validar la infraestructura. Un plan se revisa con:

```text
python -m tools.aws_private_pilot.validate --plan infra/aws/private-pilot/pilot-plan.json
python -m tools.aws_image_publication.cli validate --plan infra/aws/private-pilot/pilot-plan.json
```

La salida correcta antes de DRG-01 conserva `real_data_authorized: false`.
RDS puede reiniciarse automáticamente tras siete días detenido; `cold` reduce
cómputo, pero el plano persistente sigue teniendo costos de almacenamiento,
claves, secretos, auditoría e imágenes.

## Preparación de Stripe (apagada por defecto)

`real_data_enabled`, `payments_enabled` y `stripe_automatic_tax_enabled` nacen
en `false`. Las dos primeras variables expresan intención de arranque, no
aprobación: al ponerlas en `true`, la API exige además una atestación DRG-01
vigente, con dos aprobadores independientes y firma KMS válida. Si falta, el
contenedor no queda listo.

Solo cuando DRG-00/DRG-01 y DB-G03 estén aprobados, los planes comerciales estén
versionados y los precios se hayan creado en Stripe test mode:

1. agregar fuera de IaC `FINCILIA_STRIPE_SECRET_KEY` y
   `FINCILIA_STRIPE_WEBHOOK_SECRET` al secreto de aplicación existente;
2. registrar `https://fincilia.com/api/v1/billing/webhooks/stripe` en Stripe;
3. poner `real_data_enabled = true` y `payments_enabled = true` en el tfvars no
   versionado; Automatic Tax permanece apagado hasta decisión tributaria;
4. revisar el plan y desplegar una imagen fijada por digest.

Con pagos apagados los dos secretos ni siquiera se inyectan al task definition.
UAT rechaza claves `sk_live_`; la transición a cobro real pertenece a GA-01.
