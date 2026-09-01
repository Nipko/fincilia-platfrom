# AWS closed synthetic beta

This is the operator runbook for `FNC-BET-001`. It deliberately does **not**
authorize DRG-00 or DRG-01: every name, email, company, identifier, document and
movement used by invitees must be invented.

## What is deployed

One `t3.small` in `sa-east-1`, with a stable EIP and an encrypted 24 GiB root
volume. Only TCP 80/443 are public. Caddy obtains TLS and redirects HTTP; Nginx
adds bounded request rates and body limits. Web, API, worker, PostgreSQL, Valkey
and MinIO are not published. Administration is through Session Manager; there is
no key pair and no SSH ingress.

At first boot the host generates the database, signing, authorization,
tokenization and object-store secrets. It writes them locally with mode `0600`
and copies the bundle to the single exact SSM SecureString
`/fincilia/closed-beta/runtime-env-v1`. The value is never an IaC resource, so it
does not enter OpenTofu state. A replacement host recovers it before restoring a
backup and fails closed if SSM is unavailable.

This is a cost-conscious beta, not a production topology. The estimate is about
USD 35/month before credits, driven by EC2, public IPv4 and EBS. AWS credits may
offset the charge; this module does not claim that the runtime is free.

## Required local inputs

Keep these values outside Git and shell history where practical:

- exact lower-case beta FQDN, for example `beta.example.com`;
- DNS provider/control needed to create one `A` record;
- T0 state bucket name and account ID;
- a release SHA and API/web/worker ECR references pinned by digest.

The module never creates DNS because the account currently has no Route53 hosted
zone. `tofu output required_dns_record` returns the exact record after apply.

## Plan and apply

From `infra/aws/beta`, initialize the separate state and use a local, ignored
`beta.auto.tfvars`:

```text
tofu init -backend-config="bucket=<T0_STATE_BUCKET>"
tofu validate
tofu plan -out=beta.plan
tofu show -json beta.plan > beta-plan.json
python -m tools.aws_beta.validate --plan infra/aws/beta/beta-plan.json
tofu apply beta.plan
```

Never use `beta.example.invalid`: an apply-time guard rejects that placeholder.
After apply, create the output `A` record, wait for propagation, and let Caddy
complete ACME. The beta deliberately stores no personal notification target
before DRG-00; the operator reviews the three CloudWatch alarms and budget in the
AWS console during the closed test window.

## First invited account

Start an SSM shell using `tofu output ssm_command`, then create a short-lived
code. It is printed once; only its SHA-256 digest remains in PostgreSQL.

```text
sudo docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta --profile migrate \
  run --rm migrate python -m db.admin.invitations create --hours 72 --count 1
```

Send the code to the invited tester through a private channel. Do not put it in
Git, an issue, logs, S3, email automation or a prompt. Revoke an unused invite:

```text
sudo docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta --profile migrate \
  run --rm migrate python -m db.admin.invitations revoke --invitation <UUID>
```

The seed creates no people, credentials, firms or companies. It creates only the
engine release in `draft`; `FOUNDER-01` must approve that release explicitly
before testers publish canonical datasets.

## Verification before invitations

1. `curl -I http://<domain>` returns a permanent HTTPS redirect.
2. `curl -fsS https://<domain>/entrar` succeeds with a valid certificate.
3. An external port scan observes only 80/443; 22, 3000, 5432, 6379 and 9000 fail.
4. Registration without a code fails; one code succeeds once and replay fails.
5. Login, company onboarding, synthetic CSV/XLSX intake, cleaning, mapping,
   reconciliation and logout pass in Chromium.
6. Security headers and `Secure`, `HttpOnly`, `SameSite=Lax` session cookies are
   present; logs contain no code, secret, username or uploaded value.
7. `sudo systemctl start fincilia-beta-backup.service` succeeds.
8. `sudo systemctl start fincilia-beta-restore-check.service` succeeds and its
   CloudWatch metric becomes 1.

No friend receives an invitation until Security, Platform, Privacy/Legal and QA
have independently reviewed this evidence.

## Actualización de release UAT

El bundle nuevo se acepta únicamente si sus tres imágenes de aplicación apuntan
al ECR T0 por digest, mantiene datos reales, IA externa y OIDC apagados, y existe
un backup menor a 26 horas con restore-check menor a ocho días. Tras el reinicio,
`deploy-release.sh` comprueba `https://<dominio>/entrar` y guarda evidencia
minimizada bajo `deployment-evidence/uat/<release_sha>/`. Un fallo de arranque,
HTTPS, temporizadores o persistencia de evidencia restaura los archivos del
release anterior y registra la métrica de fallo.

## Incident and rollback

For an application fault, keep the EIP and restore the previous release bundle
and three previous image digests, then restart `fincilia-beta.service`. For a
suspected disclosure, first remove the DNS record, stop the instance, revoke all
unused invitations, preserve the encrypted volume and audit evidence, and rotate
credentials before reopening.

Rotating the runtime SecureString invalidates sessions and affects tokenized
identifiers. In this synthetic beta the safe rotation procedure is to close
access, take evidence, delete all beta data, remove the exact parameter and
recreate the environment; never overwrite it while retaining the old database.

To end the beta, remove DNS, take and verify a final synthetic backup, then destroy
the module using its exact saved plan. Do not delete the T0 bucket or shared T0
control plane. S3 lifecycle expiration remains the retention mechanism.
