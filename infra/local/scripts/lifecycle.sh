#!/bin/sh
set -eu

mode="${1:-initial}"
probe_id="synthetic-lifecycle-probe-v1"

admin_query() {
  psql --no-psqlrc --set=ON_ERROR_STOP=1 --tuples-only --no-align --command "$1"
}

app_query() {
  PGPASSWORD="$FINCILIA_LOCAL_APP_PASSWORD" PGUSER=fincilia_app \
    psql --no-psqlrc --set=ON_ERROR_STOP=1 --tuples-only --no-align --command "$1"
}

marker="$(admin_query "SELECT data_class FROM platform.local_environment WHERE environment_id = 'fincilia-local-e0';")"
[ "$marker" = "synthetic_only" ] || { echo "synthetic marker missing" >&2; exit 1; }

role_flags="$(admin_query "SELECT rolsuper::text || ':' || rolbypassrls::text || ':' || rolcreatedb::text || ':' || rolcreaterole::text FROM pg_roles WHERE rolname = 'fincilia_app';")"
[ "$role_flags" = "false:false:false:false" ] || { echo "application role is privileged" >&2; exit 1; }

if PGPASSWORD="$FINCILIA_LOCAL_APP_PASSWORD" PGUSER=fincilia_app \
  psql --no-psqlrc --set=ON_ERROR_STOP=1 --command "CREATE TABLE public.must_not_exist(id integer);" >/dev/null 2>&1; then
  echo "application role can create in public" >&2
  exit 1
fi

case "$mode" in
  initial)
    app_query "CREATE TABLE IF NOT EXISTS app.lifecycle_probe (probe_id text PRIMARY KEY, data_class text NOT NULL CHECK (data_class = 'synthetic_only'));"
    app_query "INSERT INTO app.lifecycle_probe(probe_id, data_class) VALUES ('$probe_id', 'synthetic_only') ON CONFLICT (probe_id) DO NOTHING;"
    ;;
  persisted)
    persisted="$(app_query "SELECT data_class FROM app.lifecycle_probe WHERE probe_id = '$probe_id';")"
    [ "$persisted" = "synthetic_only" ] || { echo "persistence probe missing" >&2; exit 1; }
    ;;
  *)
    echo "unsupported lifecycle mode: $mode" >&2
    exit 1
    ;;
esac

echo "lifecycle $mode: PASS"

