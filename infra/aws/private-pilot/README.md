# Fincilia private-pilot foundation

Módulo OpenTofu de `FNC-PLT-012`. Crea una frontera AWS nueva y servicios ECS
con `desired_count = 0`. No comparte datos ni estado con T0/T1/closed-beta y no
autoriza documentos reales.

Lee primero:

- `docs/platform/AWS_PRIVATE_PILOT.md`
- `docs/platform/aws-private-pilot.json`
- `docs/security/DRG01_READINESS.md`
- `docs/adr/ADR-032-aws-private-real-data-pilot.md`

El primer `apply` solo puede crear foundation. ACM requiere publicar el challenge
DNS que aparece en `required_dns_records`; `certificate_ready` permanece `false`
hasta verificar que AWS emitió el certificado. Los cuatro secretos se crean sin
valor y deben poblarse fuera de OpenTofu.

No uses datos reales para validar la infraestructura. Un plan se revisa con:

```text
python -m tools.aws_private_pilot.validate --plan infra/aws/private-pilot/pilot-plan.json
```

La salida correcta antes de DRG-01 conserva `real_data_authorized: false`.
