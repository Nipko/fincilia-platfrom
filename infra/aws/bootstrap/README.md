# Bootstrap de estado AWS T0

Este modulo solo crea el bucket versionado del estado remoto. El estado bootstrap se
guarda fuera del repositorio y no contiene credenciales.

```bash
install -d -m 700 /home/nirlevin/.local/share/fincilia
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/bootstrap init -reconfigure \
  -backend-config='path=/home/nirlevin/.local/share/fincilia/aws-t0-bootstrap.tfstate'
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/bootstrap plan -out=/tmp/fincilia-aws-t0-bootstrap.plan
env AWS_PROFILE=fincilia-sandbox TF_VAR_expected_account_id='<ACCOUNT_ID>' \
  tofu -chdir=infra/aws/bootstrap apply /tmp/fincilia-aws-t0-bootstrap.plan
```

`prevent_destroy` protege el bucket. Su eliminacion requiere una tarea de teardown,
retirar el bloqueo conscientemente y comprobar antes que no queda ningun estado vigente.
