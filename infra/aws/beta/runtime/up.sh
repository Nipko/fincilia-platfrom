#!/usr/bin/env bash
set -euo pipefail

cd /opt/fincilia
source /opt/fincilia/deployment.env

if [ ! -s runtime.env ]; then
  if aws ssm get-parameter --name "$FINCILIA_RUNTIME_PARAMETER" \
    --with-decryption --query Parameter.Value --output text \
    > runtime.env.download 2> runtime.env.download.error; then
    mv runtime.env.download runtime.env
    rm -f runtime.env.download.error
  elif grep -q 'ParameterNotFound' runtime.env.download.error; then
    rm -f runtime.env.download runtime.env.download.error
  else
    rm -f runtime.env.download runtime.env.download.error
    printf 'runtime secret recovery failed closed\n' >&2
    exit 1
  fi
fi

if [ ! -s runtime.env ]; then
  umask 077
  {
    printf 'FINCILIA_DB_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_DB_APP_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_DB_MIGRATOR_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_DB_WORKER_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_AUTH_SIGNING_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_AUTHORIZATION_CONTEXT_HMAC_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_IDENTIFIER_TOKENIZATION_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_OBJECT_ACCESS_KEY=%s\n' "$(openssl rand -hex 16)"
    printf 'FINCILIA_OBJECT_SECRET_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_REAL_DATA_ENABLED=false\n'
    printf 'FINCILIA_AI_GATEWAY_ENABLED=false\n'
    printf 'FINCILIA_PAYMENTS_ENABLED=false\n'
    printf 'FINCILIA_REGISTRATION_INVITE_REQUIRED=true\n'
  } > runtime.env
  aws ssm put-parameter --name "$FINCILIA_RUNTIME_PARAMETER" \
    --type SecureString --value file:///opt/fincilia/runtime.env >/dev/null
fi
chmod 0600 runtime.env

compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta)

aws ecr get-login-password --region sa-east-1 | \
  docker login --username AWS --password-stdin \
  "$FINCILIA_REGISTRY" 2>/dev/null

"${compose[@]}" pull --quiet
"${compose[@]}" stop caddy nginx web api worker 2>/dev/null || true
"${compose[@]}" up -d --wait postgres valkey objectstore
"${compose[@]}" --profile migrate run --rm migrate python -c '
import os
from types import SimpleNamespace

from fincilia_platform.probes import ensure_buckets

settings = SimpleNamespace(
    object_credentials_source="local_static",
    object_store_endpoint=os.environ["FINCILIA_OBJECT_STORE_ENDPOINT"],
    object_region=os.environ["FINCILIA_OBJECT_REGION"],
    object_access_key=os.environ["FINCILIA_OBJECT_ACCESS_KEY"],
    object_secret_key=os.environ["FINCILIA_OBJECT_SECRET_KEY"],
    object_bucket_raw="fincilia-raw",
    buckets=(
        "fincilia-quarantine",
        "fincilia-raw",
        "fincilia-derived",
        "fincilia-exports",
    ),
)
created = ensure_buckets(settings)
print("object storage ready; created=" + (",".join(created) or "none"))
'
"${compose[@]}" --profile migrate run --rm migrate
"${compose[@]}" --profile migrate run --rm migrate python -m db.seed.beta
"${compose[@]}" up -d --wait --force-recreate api worker web nginx caddy

"${compose[@]}" exec -T api python -c '
import json
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=10) as response:
    payload = json.load(response)
if payload.get("status") != "ready":
    raise SystemExit("API not ready")
'

aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
  --metric-data MetricName=ApplicationReady,Value=1,Unit=Count
