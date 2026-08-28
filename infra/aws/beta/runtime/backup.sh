#!/usr/bin/env bash
set -euo pipefail

cd /opt/fincilia
source /opt/fincilia/runtime.env
source /opt/fincilia/deployment.env

exec 9>/run/fincilia-beta-backup.lock
flock -n 9 || exit 0

workdir="$(mktemp -d /opt/fincilia/.backup.XXXXXX)"
compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta)
resumed=false

cleanup() {
  case "$workdir" in
    /opt/fincilia/.backup.*) rm -rf -- "$workdir" ;;
    *) printf 'unsafe backup path: %s\n' "$workdir" >&2 ;;
  esac
}

resume_writers() {
  if [ "$resumed" = false ]; then
    "${compose[@]}" up -d --wait objectstore api worker >/dev/null
    resumed=true
  fi
}

failed() {
  resume_writers || true
  aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
    --metric-data MetricName=BackupSuccess,Value=0,Unit=Count || true
}

trap cleanup EXIT
trap failed ERR

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
key="${FINCILIA_BACKUP_PREFIX}/$(date -u +%Y/%m/%d)/$timestamp"

# Detener escritores da un punto consistente entre PostgreSQL y objetos. La web
# permanece arriba y muestra un error transitorio durante esta ventana corta.
"${compose[@]}" stop api worker >/dev/null
"${compose[@]}" exec -T postgres pg_dump \
  -U fincilia_beta_admin -d fincilia_beta \
  --format=custom --compress=9 --no-owner --no-acl > "$workdir/database.dump"

schema_head="$("${compose[@]}" exec -T postgres psql \
  -U fincilia_beta_admin -d fincilia_beta -Atqc \
  'SELECT version FROM fincilia.schema_history ORDER BY version DESC LIMIT 1')"

"${compose[@]}" stop objectstore >/dev/null
object_mount="$(docker volume inspect fincilia-beta_objectdata --format '{{.Mountpoint}}')"
case "$object_mount" in
  /var/lib/docker/volumes/*/_data) ;;
  *) printf 'unsafe object volume mount: %s\n' "$object_mount" >&2; exit 1 ;;
esac
tar --numeric-owner -C "$object_mount" -czf "$workdir/objects.tar.gz" .
resume_writers

printf '{"data_class":"synthetic_only","release_sha":"%s","schema_head":"%s","created_at":"%s"}\n' \
  "$FINCILIA_RELEASE_SHA" "$schema_head" "$timestamp" > "$workdir/metadata.json"

(cd "$workdir" && sha256sum database.dump objects.tar.gz metadata.json > manifest.sha256)
aws s3 cp "$workdir/" "s3://${FINCILIA_BACKUP_BUCKET}/$key/" \
  --recursive --sse AES256 --only-show-errors

aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
  --metric-data MetricName=BackupSuccess,Value=1,Unit=Count
trap - ERR
