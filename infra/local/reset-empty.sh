#!/usr/bin/env sh
# Reemplaza exclusivamente el plano de datos local y lo reconstruye desde
# migraciones. No acepta globs, overrides de volumen ni otros proyectos Compose.
set -eu

PROJECT=fincilia-local
PG_VOLUME=fincilia_local_pgdata
OBJECT_VOLUME=fincilia_local_objectdata
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$HERE/compose.yaml"
MIGRATIONS_DIR="$HERE/../../db/migrations"

migration_files=$(find "$MIGRATIONS_DIR" -maxdepth 1 -type f \
  -name 'V[0-9][0-9][0-9][0-9]__*.sql' -print | sort)
EXPECTED_MIGRATION_COUNT=$(printf '%s\n' "$migration_files" | sed '/^$/d' | \
  wc -l | tr -d ' ')
EXPECTED_MIGRATION_HEAD=$(printf '%s\n' "$migration_files" | tail -n 1 | \
  sed -E 's|.*/(V[0-9]{4})__.*|\1|')

case "$EXPECTED_MIGRATION_COUNT:$EXPECTED_MIGRATION_HEAD" in
  [1-9][0-9]*:V[0-9][0-9][0-9][0-9]) ;;
  *)
    printf 'refusing reset: migration source inventory is invalid (%s:%s)\n' \
      "$EXPECTED_MIGRATION_COUNT" "$EXPECTED_MIGRATION_HEAD" >&2
    exit 66
    ;;
esac

usage() {
  printf 'usage: %s --plan | --execute fincilia-local\n' "$0" >&2
  exit 64
}

compose() {
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}

verify_volume() {
  volume=$1
  expected_component=$2
  actual_project=$(docker volume inspect "$volume" \
    --format '{{ index .Labels "com.docker.compose.project" }}')
  actual_component=$(docker volume inspect "$volume" \
    --format '{{ index .Labels "com.docker.compose.volume" }}')
  mountpoint=$(docker volume inspect "$volume" --format '{{ .Mountpoint }}')
  [ "$actual_project" = "$PROJECT" ] || {
    printf 'refusing volume %s: project=%s\n' "$volume" "$actual_project" >&2
    exit 65
  }
  [ "$actual_component" = "$expected_component" ] || {
    printf 'refusing volume %s: component=%s\n' "$volume" "$actual_component" >&2
    exit 65
  }
  case "$mountpoint" in
    /var/lib/docker/volumes/"$volume"/_data) ;;
    *)
      printf 'refusing volume %s: mountpoint=%s\n' "$volume" "$mountpoint" >&2
      exit 65
      ;;
  esac
}

verify_targets() {
  [ -f "$COMPOSE_FILE" ] || {
    printf 'compose file missing\n' >&2
    exit 66
  }
  verify_volume "$PG_VOLUME" fincilia_local_pgdata
  verify_volume "$OBJECT_VOLUME" fincilia_local_objectdata
}

case "${1:-}" in
  --plan)
    [ "$#" -eq 1 ] || usage
    verify_targets
    printf 'environment=local project=%s\n' "$PROJECT"
    printf 'replace_volume=%s\n' "$PG_VOLUME"
    printf 'replace_volume=%s\n' "$OBJECT_VOLUME"
    printf 'preserve=source,images,networks,other_compose_projects\n'
    printf 'postcondition=migrations_replayed,user_tables_empty,objects_empty\n'
    exit 0
    ;;
  --execute)
    [ "$#" -eq 2 ] && [ "$2" = "$PROJECT" ] || usage
    ;;
  *) usage ;;
esac

verify_targets

echo "==> detener solamente $PROJECT"
compose down --remove-orphans

# Se vuelve a resolver cada target despues de detener los contenedores. Asi un
# cambio concurrente entre el plan y la eliminacion no reutiliza el inventario.
verify_targets
echo "==> reemplazar los dos volumenes de datos adjudicados"
docker volume rm "$PG_VOLUME" "$OBJECT_VOLUME"

echo "==> reconstruir desde migraciones sin semilla demo"
sh "$HERE/up.sh" --empty

echo "==> verificar que todas las tablas de producto estan vacias"
actual_history=$(compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U fincilia_local_admin -d fincilia_local -At -F '|' \
  -c "SELECT count(*), coalesce(max(version), '') FROM fincilia.schema_history")
[ "$actual_history" = "$EXPECTED_MIGRATION_COUNT|$EXPECTED_MIGRATION_HEAD" ] || {
  printf 'migration history mismatch: expected=%s|%s actual=%s\n' \
    "$EXPECTED_MIGRATION_COUNT" "$EXPECTED_MIGRATION_HEAD" "$actual_history" >&2
  exit 67
}

compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U fincilia_local_admin -d fincilia_local <<'SQL'
DO $verify_empty$
DECLARE
  table_row record;
  row_count bigint;
BEGIN
  FOR table_row IN
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'fincilia'
      AND tablename NOT IN (
        'schema_history', 'subject', 'legal_document_version',
        'billing_plan_version'
      )
    ORDER BY tablename
  LOOP
    EXECUTE format('SELECT count(*) FROM fincilia.%I', table_row.tablename)
      INTO row_count;
    IF row_count <> 0 THEN
      RAISE EXCEPTION 'table %.% is not empty', 'fincilia', table_row.tablename;
    END IF;
  END LOOP;
END
$verify_empty$;

DO $verify_system_rows$
BEGIN
  IF (SELECT count(*) FROM fincilia.subject) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.subject
       WHERE subject_id = '4d1d048f-07af-5ccd-bd76-abace2124b63'
         AND subject_kind = 'service_principal'
         AND display_name = 'Fincilia Provisioning Authority'
         AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'unexpected subject survived the empty reset';
  END IF;

  IF (SELECT count(*) FROM fincilia.legal_document_version) <> 2
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.legal_document_version
       WHERE document_kind = 'terms'
         AND document_version = 'terms-2026-08-29'
         AND active_for_registration
     )
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.legal_document_version
       WHERE document_kind = 'privacy'
         AND document_version = 'privacy-2026-08-29'
         AND active_for_registration
     ) THEN
    RAISE EXCEPTION 'legal registration references are not canonical';
  END IF;

  IF (SELECT count(*) FROM fincilia.billing_plan_version) <> 3
     OR (SELECT array_agg(plan_code ORDER BY plan_code)
         FROM fincilia.billing_plan_version)
        <> ARRAY['accountant', 'business', 'starter']::text[]
     OR EXISTS (
       SELECT 1 FROM fincilia.billing_plan_version
       WHERE version <> 1 OR catalog_state <> 'evaluation'
          OR currency_code IS NOT NULL OR unit_amount_minor IS NOT NULL
          OR trial_days IS NOT NULL
     ) THEN
    RAISE EXCEPTION 'billing evaluation catalog is not canonical';
  END IF;
END
$verify_system_rows$;
SQL

echo "==> verificar que las zonas de objetos no contienen objetos"
compose --profile migrate run --rm migrate python -c '
import os
import boto3
from botocore.client import Config

client = boto3.client(
    "s3",
    endpoint_url=os.environ["FINCILIA_OBJECT_STORE_ENDPOINT"],
    region_name=os.environ.get("FINCILIA_OBJECT_REGION", "us-east-1"),
    aws_access_key_id=os.environ["FINCILIA_OBJECT_ACCESS_KEY"],
    aws_secret_access_key=os.environ["FINCILIA_OBJECT_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
)
for bucket in ("fincilia-quarantine", "fincilia-raw", "fincilia-derived", "fincilia-exports"):
    payload = client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    if payload.get("KeyCount", 0):
        raise SystemExit(f"bucket not empty: {bucket}")
print("object zones empty")
'

echo "reset local completo: plano de datos vacio y esquema vigente"
