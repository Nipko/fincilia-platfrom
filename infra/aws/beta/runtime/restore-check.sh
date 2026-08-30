#!/usr/bin/env bash
set -euo pipefail

cd /opt/fincilia
source /opt/fincilia/runtime.env
source /opt/fincilia/deployment.env

exec 9>/run/fincilia-beta-restore-check.lock
flock -n 9 || exit 0

workdir="$(mktemp -d /opt/fincilia/.restore-check.XXXXXX)"
container="fincilia-beta-restore-$RANDOM-$$"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  case "$workdir" in
    /opt/fincilia/.restore-check.*) rm -rf -- "$workdir" ;;
    *) printf 'unsafe restore path: %s\n' "$workdir" >&2 ;;
  esac
}

failed() {
  aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
    --metric-data MetricName=RestoreCheckSuccess,Value=0,Unit=Count || true
}

trap cleanup EXIT
trap failed ERR

latest_manifest="$(aws s3api list-objects-v2 \
  --bucket "$FINCILIA_BACKUP_BUCKET" \
  --prefix "$FINCILIA_BACKUP_PREFIX/" \
  --query "reverse(sort_by(Contents[?ends_with(Key, 'manifest.sha256')], &LastModified))[0].Key" \
  --output text)"
if [ -z "$latest_manifest" ] || [ "$latest_manifest" = None ]; then
  printf 'no beta backup manifest found\n' >&2
  exit 1
fi
backup_key="${latest_manifest%/manifest.sha256}"

for name in manifest.sha256 database.dump objects.tar.gz metadata.json; do
  aws s3 cp "s3://${FINCILIA_BACKUP_BUCKET}/$backup_key/$name" "$workdir/$name" \
    --only-show-errors
done
(cd "$workdir" && sha256sum -c manifest.sha256)
tar -tzf "$workdir/objects.tar.gz" >/dev/null

restore_password="$(openssl rand -hex 24)"
docker run -d --name "$container" --network none \
  -e POSTGRES_PASSWORD="$restore_password" -e POSTGRES_DB=fincilia_restore \
  postgres:17.11-alpine3.24@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73 >/dev/null

for _ in $(seq 1 60); do
  # La imagen levanta un servidor temporal, crea la base y lo reinicia. pg_isready
  # puede observar el primero y provocar una carrera contra ese apagado.
  if docker exec "$container" psql -U postgres -d fincilia_restore \
    -Atqc 'SELECT 1' 2>/dev/null | grep -qx 1; then
    break
  fi
  sleep 1
done
test "$(docker exec "$container" psql -U postgres -d fincilia_restore \
  -Atqc 'SELECT 1')" = 1

# El dump conserva las politicas RLS y sus roles objetivo, pero --no-owner y
# --no-acl deliberadamente no trasladan roles ni credenciales. Los placeholders
# NOLOGIN permiten reconstruir la semantica del esquema sin copiar accesos.
docker exec "$container" psql -U postgres -d fincilia_restore \
  --set ON_ERROR_STOP=on -c '
    CREATE ROLE fincilia_app NOLOGIN;
    CREATE ROLE fincilia_migrator NOLOGIN;
    CREATE ROLE fincilia_worker NOLOGIN;
    CREATE ROLE fincilia_dispatch NOLOGIN;
    CREATE ROLE fincilia_identity NOLOGIN;
  ' >/dev/null
docker exec -i "$container" pg_restore -U postgres -d fincilia_restore \
  --no-owner --no-acl < "$workdir/database.dump"

restored_head="$(docker exec "$container" psql -U postgres -d fincilia_restore \
  -Atqc 'SELECT version FROM fincilia.schema_history ORDER BY version DESC LIMIT 1')"
expected_head="$(sed -n 's/.*"schema_head":"\([^"]*\)".*/\1/p' "$workdir/metadata.json")"
test -n "$expected_head"
test "$restored_head" = "$expected_head"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
printf '{"data_class":"synthetic_only","backup_key":"%s","schema_head":"%s","checked_at":"%s","ok":true}\n' \
  "$backup_key" "$restored_head" "$timestamp" > "$workdir/restore-result.json"
aws s3 cp "$workdir/restore-result.json" \
  "s3://${FINCILIA_BACKUP_BUCKET}/restore-checks/beta/$timestamp.json" \
  --sse AES256 --only-show-errors
aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
  --metric-data MetricName=RestoreCheckSuccess,Value=1,Unit=Count
trap - ERR
