# AWS T0: control plane sintetico

Este modulo crea solamente controles y servicios base. No contiene EC2, RDS, NAT,
ALB, Fargate, secretos ni datos reales.

## Plan y validacion

El bootstrap debe existir y se debe usar una sesion temporal de `aws login`:

```bash
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/t0 init -reconfigure \
  -backend-config='bucket=<STATE_BUCKET>'
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/t0 plan -out=/tmp/fincilia-aws-t0.plan
tofu -chdir=infra/aws/t0 show -json /tmp/fincilia-aws-t0.plan \
  > /tmp/fincilia-aws-t0-plan.json
python -m tools.aws_t0.validate --plan /tmp/fincilia-aws-t0-plan.json
```

Solo se aplica exactamente el plan binario que paso el validador:

```bash
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/t0 apply /tmp/fincilia-aws-t0.plan
```

## Teardown

Antes de la fecha `ExpiresAt`, un operador revisa `tofu plan -destroy`, lo convierte a
JSON y confirma que solo elimina recursos T0. El bucket de estado se conserva hasta
comprobar que no queda ningun recurso principal. No se usa `force_destroy` ni se vacian
buckets automaticamente para evitar perdida accidental.
