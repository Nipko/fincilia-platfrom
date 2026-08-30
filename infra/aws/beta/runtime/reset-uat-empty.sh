#!/usr/bin/env bash
# Reemplazo de los dos volumenes de datos del UAT legado `fincilia-beta`.
# El nombre fisico se conserva para no recrear EC2/EIP; la operacion sigue
# estando acotada al entorno UAT de fincilia.com y falla cerrada ante cualquier
# target inesperado.
set -euo pipefail

cd /opt/fincilia
source /opt/fincilia/runtime.env
source /opt/fincilia/deployment.env

PROJECT=fincilia-beta
PG_VOLUME=fincilia-beta_pgdata
OBJECT_VOLUME=fincilia-beta_objectdata
CADDY_DATA_VOLUME=fincilia-beta_caddy_data
CADDY_CONFIG_VOLUME=fincilia-beta_caddy_config
PLAN_FILE=/run/fincilia-uat-reset.plan
TOKEN_TTL_SECONDS=900

compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p "$PROJECT")

exec 9>/run/fincilia-uat-reset.lock
flock -n 9 || {
  printf 'another UAT reset operation is active\n' >&2
  exit 75
}

usage() {
  printf 'usage: %s --plan | --execute CONFIRMATION_TOKEN\n' "$0" >&2
  exit 64
}

verify_volume() {
  local volume=$1
  local component=$2
  local actual_project actual_component mountpoint
  actual_project="$(docker volume inspect "$volume" \
    --format '{{ index .Labels "com.docker.compose.project" }}')"
  actual_component="$(docker volume inspect "$volume" \
    --format '{{ index .Labels "com.docker.compose.volume" }}')"
  mountpoint="$(docker volume inspect "$volume" --format '{{ .Mountpoint }}')"
  test "$actual_project" = "$PROJECT"
  test "$actual_component" = "$component"
  case "$mountpoint" in
    /var/lib/docker/volumes/"$volume"/_data) ;;
    *) printf 'unsafe mountpoint for %s\n' "$volume" >&2; exit 65 ;;
  esac
}

volume_fingerprint() {
  docker volume inspect "$1" | sha256sum | cut -d ' ' -f 1
}

verify_inventory() {
  verify_volume "$PG_VOLUME" pgdata
  verify_volume "$OBJECT_VOLUME" objectdata
  verify_volume "$CADDY_DATA_VOLUME" caddy_data
  verify_volume "$CADDY_CONFIG_VOLUME" caddy_config

  mapfile -t project_volumes < <(docker volume ls \
    --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Name}}' | sort)
  expected=("$CADDY_CONFIG_VOLUME" "$CADDY_DATA_VOLUME" "$OBJECT_VOLUME" "$PG_VOLUME")
  test "${#project_volumes[@]}" -eq "${#expected[@]}"
  test "$(printf '%s\n' "${project_volumes[@]}")" = \
       "$(printf '%s\n' "${expected[@]}" | sort)"

  for target in "${project_volumes[@]}"; do
    case "$target" in
      *prod*|*production*)
        printf 'production-like target refused: %s\n' "$target" >&2
        exit 65
        ;;
    esac
  done
}

latest_backup_and_restore() {
  local manifest restore_result workdir manifest_key restore_key backup_key
  workdir=$1
  manifest_key="$(aws s3api list-objects-v2 \
    --bucket "$FINCILIA_BACKUP_BUCKET" --prefix "$FINCILIA_BACKUP_PREFIX/" \
    --query "reverse(sort_by(Contents[?ends_with(Key, 'manifest.sha256')], &LastModified))[0].Key" \
    --output text)"
  restore_key="$(aws s3api list-objects-v2 \
    --bucket "$FINCILIA_BACKUP_BUCKET" --prefix restore-checks/beta/ \
    --query "reverse(sort_by(Contents, &LastModified))[0].Key" --output text)"
  test -n "$manifest_key" && test "$manifest_key" != None
  test -n "$restore_key" && test "$restore_key" != None
  backup_key=${manifest_key%/manifest.sha256}
  aws s3 cp "s3://${FINCILIA_BACKUP_BUCKET}/$restore_key" \
    "$workdir/restore-result.json" --only-show-errors
  aws s3api head-object --bucket "$FINCILIA_BACKUP_BUCKET" --key "$manifest_key" \
    --query LastModified --output text > "$workdir/backup-time"
  aws s3api head-object --bucket "$FINCILIA_BACKUP_BUCKET" --key "$restore_key" \
    --query LastModified --output text > "$workdir/restore-time"
  python3 - "$workdir" "$backup_key" <<'PY'
import datetime as dt
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
backup_key = sys.argv[2]
payload = json.loads((root / "restore-result.json").read_text(encoding="utf-8"))
if payload.get("ok") is not True or payload.get("backup_key") != backup_key:
    raise SystemExit("restore result does not prove the latest backup")
now = dt.datetime.now(dt.timezone.utc)
for name in ("backup-time", "restore-time"):
    observed = dt.datetime.fromisoformat((root / name).read_text().strip()
                                          .replace("Z", "+00:00"))
    age = (now - observed).total_seconds()
    if age < 0 or age > 7200:
        raise SystemExit(f"{name} is not fresh: age={age}")
print(backup_key)
PY
}

writers_are_stopped() {
  local service container running
  for service in caddy nginx web api worker; do
    container="$("${compose[@]}" ps -aq "$service")"
    if [ -n "$container" ]; then
      running="$(docker inspect "$container" --format '{{ .State.Running }}')"
      test "$running" = false || return 1
    fi
  done
}

workdir="$(mktemp -d /opt/fincilia/.uat-reset.XXXXXX)"
cleanup() {
  case "$workdir" in
    /opt/fincilia/.uat-reset.*) rm -rf -- "$workdir" ;;
    *) printf 'unsafe reset workdir\n' >&2 ;;
  esac
}
trap cleanup EXIT

case "${1:-}" in
  --plan)
    test "$#" -eq 1 || usage
    test "${FINCILIA_REAL_DATA_ENABLED:-false}" = false
    test "$FINCILIA_BACKUP_PREFIX" = backups/beta
    verify_inventory
    backup_key="$(latest_backup_and_restore "$workdir" | tail -n 1)"

    # Congelar el plano de escritura solo despues de probar backup y restore.
    "${compose[@]}" stop caddy nginx web api worker >/dev/null
    if ! writers_are_stopped; then
      /opt/fincilia/up.sh >/dev/null 2>&1 || true
      printf 'writers did not freeze\n' >&2
      exit 1
    fi

    token="$(openssl rand -hex 24)"
    token_digest="$(printf '%s' "$token" | sha256sum | cut -d ' ' -f 1)"
    expires_at="$(( $(date -u +%s) + TOKEN_TTL_SECONDS ))"
    pg_fingerprint="$(volume_fingerprint "$PG_VOLUME")"
    object_fingerprint="$(volume_fingerprint "$OBJECT_VOLUME")"
    umask 077
    {
      printf 'TOKEN_DIGEST=%s\n' "$token_digest"
      printf 'EXPIRES_AT=%s\n' "$expires_at"
      printf 'BACKUP_KEY=%s\n' "$backup_key"
      printf 'RELEASE_SHA=%s\n' "$FINCILIA_RELEASE_SHA"
      printf 'PG_FINGERPRINT=%s\n' "$pg_fingerprint"
      printf 'OBJECT_FINGERPRINT=%s\n' "$object_fingerprint"
    } > "$PLAN_FILE"
    printf 'environment=uat project=%s release=%s\n' "$PROJECT" "$FINCILIA_RELEASE_SHA"
    printf 'replace_volume=%s\nreplace_volume=%s\n' "$PG_VOLUME" "$OBJECT_VOLUME"
    printf 'preserve_volume=%s\npreserve_volume=%s\n' \
      "$CADDY_DATA_VOLUME" "$CADDY_CONFIG_VOLUME"
    printf 'backup_key=%s\nexpires_at_epoch=%s\nconfirmation_token=%s\n' \
      "$backup_key" "$expires_at" "$token"
    exit 0
    ;;
  --execute)
    test "$#" -eq 2 || usage
    test -s "$PLAN_FILE"
    # El plan lo escribio root con valores de formato cerrado; nunca incorpora
    # payloads de usuario ni nombres de recurso aportados por el cliente.
    source "$PLAN_FILE"
    [[ "$TOKEN_DIGEST" =~ ^[0-9a-f]{64}$ ]]
    [[ "$EXPIRES_AT" =~ ^[0-9]{10}$ ]]
    [[ "$BACKUP_KEY" =~ ^backups/beta/[0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9TZ]+$ ]]
    [[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]
    test "$(date -u +%s)" -le "$EXPIRES_AT"
    test "$(printf '%s' "$2" | sha256sum | cut -d ' ' -f 1)" = "$TOKEN_DIGEST"
    test "$FINCILIA_RELEASE_SHA" = "$RELEASE_SHA"
    verify_inventory
    test "$(volume_fingerprint "$PG_VOLUME")" = "$PG_FINGERPRINT"
    test "$(volume_fingerprint "$OBJECT_VOLUME")" = "$OBJECT_FINGERPRINT"
    writers_are_stopped
    ;;
  *) usage ;;
esac

failed() {
  aws cloudwatch put-metric-data --namespace Fincilia/UAT \
    --metric-data MetricName=ResetSuccess,Value=0,Unit=Count || true
  /opt/fincilia/up.sh >/dev/null 2>&1 || true
}
trap failed ERR

"${compose[@]}" down --remove-orphans
verify_inventory

# La base y objetos se reemplazan; Caddy y su material TLS se preservan. Rotar
# el SecureString completo invalida sesiones y retira las claves del UAT viejo.
if aws ssm get-parameter --name "$FINCILIA_RUNTIME_PARAMETER" \
     --query Parameter.Name --output text >/dev/null 2>&1; then
  aws ssm delete-parameter --name "$FINCILIA_RUNTIME_PARAMETER"
  for _ in $(seq 1 30); do
    if ! aws ssm get-parameter --name "$FINCILIA_RUNTIME_PARAMETER" \
         --query Parameter.Name --output text >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if aws ssm get-parameter --name "$FINCILIA_RUNTIME_PARAMETER" \
       --query Parameter.Name --output text >/dev/null 2>&1; then
    printf 'runtime parameter deletion did not converge\n' >&2
    exit 1
  fi
fi
rm -f /opt/fincilia/runtime.env
docker volume rm "$PG_VOLUME" "$OBJECT_VOLUME"

/opt/fincilia/up.sh

source /opt/fincilia/runtime.env
compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p "$PROJECT")

"${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U fincilia_beta_admin -d fincilia_beta <<'SQL'
DO $verify_empty$
DECLARE
  table_row record;
  row_count bigint;
BEGIN
  FOR table_row IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'fincilia'
      AND tablename NOT IN (
        'schema_history', 'subject', 'legal_document_version', 'engine_release'
      )
    ORDER BY tablename
  LOOP
    EXECUTE format('SELECT count(*) FROM fincilia.%I', table_row.tablename)
      INTO row_count;
    IF row_count <> 0 THEN
      RAISE EXCEPTION 'table %.% is not empty', 'fincilia', table_row.tablename;
    END IF;
  END LOOP;

  IF (SELECT count(*) FROM fincilia.subject) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.subject
       WHERE subject_id = '4d1d048f-07af-5ccd-bd76-abace2124b63'
         AND subject_kind = 'service_principal'
         AND display_name = 'Fincilia Provisioning Authority'
         AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'unexpected subject exists after reset';
  END IF;
  IF (SELECT count(*) FROM fincilia.legal_document_version) <> 2 THEN
    RAISE EXCEPTION 'registration legal references are not canonical';
  END IF;
  IF (SELECT count(*) FROM fincilia.engine_release) <> 1
     OR NOT EXISTS (SELECT 1 FROM fincilia.engine_release WHERE state = 'draft') THEN
    RAISE EXCEPTION 'runtime release reference is not canonical';
  END IF;
END
$verify_empty$;
SQL

"${compose[@]}" --profile migrate run --rm migrate python -c '
import os
import boto3
from botocore.client import Config

client = boto3.client(
    "s3",
    endpoint_url=os.environ["FINCILIA_OBJECT_STORE_ENDPOINT"],
    region_name=os.environ.get("FINCILIA_OBJECT_REGION", "sa-east-1"),
    aws_access_key_id=os.environ["FINCILIA_OBJECT_ACCESS_KEY"],
    aws_secret_access_key=os.environ["FINCILIA_OBJECT_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
)
for bucket in ("fincilia-quarantine", "fincilia-raw", "fincilia-derived", "fincilia-exports"):
    if client.list_objects_v2(Bucket=bucket, MaxKeys=1).get("KeyCount", 0):
        raise SystemExit(f"bucket not empty: {bucket}")
print("UAT object zones empty")
'

schema_head="$("${compose[@]}" exec -T postgres psql \
  -U fincilia_beta_admin -d fincilia_beta -Atqc \
  'SELECT version FROM fincilia.schema_history ORDER BY version DESC LIMIT 1')"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
printf '{"environment":"uat","operation":"replace_data_plane","release_sha":"%s","backup_key":"%s","schema_head":"%s","user_rows":0,"objects":0,"secrets_rotated":true,"bootstrap":"not_configured","real_data_authorized":false,"completed_at":"%s"}\n' \
  "$FINCILIA_RELEASE_SHA" "$BACKUP_KEY" "$schema_head" "$timestamp" \
  > "$workdir/evidence.json"
aws s3 cp "$workdir/evidence.json" \
  "s3://${FINCILIA_BACKUP_BUCKET}/reset-evidence/uat/$timestamp.json" \
  --sse AES256 --only-show-errors
aws cloudwatch put-metric-data --namespace Fincilia/UAT \
  --metric-data MetricName=ResetSuccess,Value=1,Unit=Count
rm -f "$PLAN_FILE"
trap - ERR
printf 'UAT data plane reset complete; bootstrap remains explicitly unconfigured\n'
