#!/usr/bin/env bash
set -euo pipefail

cd /opt/fincilia

if [ ! -s runtime.env ]; then
  umask 077
  {
    printf 'FINCILIA_AUTH_SIGNING_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_AUTHORIZATION_CONTEXT_HMAC_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_IDENTIFIER_TOKENIZATION_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_OBJECT_ACCESS_KEY=%s\n' "$(openssl rand -hex 16)"
    printf 'FINCILIA_OBJECT_SECRET_KEY=%s\n' "$(openssl rand -hex 32)"
    printf 'FINCILIA_REAL_DATA_ENABLED=false\n'
    printf 'FINCILIA_AI_GATEWAY_ENABLED=false\n'
    printf 'FINCILIA_PAYMENTS_ENABLED=false\n'
  } > runtime.env
fi
chmod 0600 runtime.env

compose=(docker compose --env-file /opt/fincilia/runtime.env -f /opt/fincilia/compose.yaml -p fincilia-t1)

"${compose[@]}" stop api worker web 2>/dev/null || true
"${compose[@]}" up -d --wait postgres valkey objectstore
"${compose[@]}" --profile migrate run --rm migrate
"${compose[@]}" --profile migrate run --rm migrate python -m db.seed.local
"${compose[@]}" up -d --wait --force-recreate api worker web

"${compose[@]}" exec -T api python -c '
import json
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=10) as response:
    payload = json.load(response)
if payload.get("status") != "ready":
    raise SystemExit("API not ready")
'
