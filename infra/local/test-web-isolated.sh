#!/usr/bin/env sh
# Lifecycle Docker cerrado del runtime E2E. No ejecutar directamente: el
# orquestador PowerShell conserva WSL, corre Playwright y garantiza el `down` en
# un bloque finally. Este helper nunca acepta nombres de recursos ni puertos.
set -eu

EXPECTED_PROJECT=fincilia-e2e
PROJECT=fincilia-e2e
PGDATA_VOLUME=fincilia_e2e_pgdata
OBJECTDATA_VOLUME=fincilia_e2e_objectdata
PRIVATE_NETWORK=fincilia_e2e_private
EDGE_NETWORK=fincilia_e2e_edge
WEB_PORT=53100
API_PORT=58180
OBJECT_PORT=59100
OBJECT_CONSOLE_PORT=59101

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$HERE/compose.yaml"

validate_constants() {
  [ "$PROJECT" = "$EXPECTED_PROJECT" ] || {
    echo "refusing unexpected Compose project" >&2
    exit 3
  }
  [ "$PGDATA_VOLUME" = "fincilia_e2e_pgdata" ] || exit 3
  [ "$OBJECTDATA_VOLUME" = "fincilia_e2e_objectdata" ] || exit 3
  [ "$PRIVATE_NETWORK" = "fincilia_e2e_private" ] || exit 3
  [ "$EDGE_NETWORK" = "fincilia_e2e_edge" ] || exit 3
  [ "$WEB_PORT" = "53100" ] || exit 3
  [ "$API_PORT" = "58180" ] || exit 3
  [ "$OBJECT_PORT" = "59100" ] || exit 3
  [ "$OBJECT_CONSOLE_PORT" = "59101" ] || exit 3
  [ -f "$COMPOSE_FILE" ] || {
    echo "allowlisted Compose file does not exist" >&2
    exit 3
  }
}

export FINCILIA_LOCAL_PGDATA_VOLUME="$PGDATA_VOLUME"
export FINCILIA_LOCAL_OBJECTDATA_VOLUME="$OBJECTDATA_VOLUME"
export FINCILIA_LOCAL_PRIVATE_NETWORK="$PRIVATE_NETWORK"
export FINCILIA_LOCAL_EDGE_NETWORK="$EDGE_NETWORK"
export FINCILIA_LOCAL_WEB_PORT="$WEB_PORT"
export FINCILIA_LOCAL_API_PORT="$API_PORT"
export FINCILIA_LOCAL_OBJECT_PORT="$OBJECT_PORT"
export FINCILIA_LOCAL_OBJECT_CONSOLE_PORT="$OBJECT_CONSOLE_PORT"

compose() {
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}

assert_isolated() {
  ids=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")
  [ -n "$ids" ] || {
    echo "isolated project has no containers" >&2
    exit 1
  }

  for id in $ids; do
    actual_project=$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$id")
    [ "$actual_project" = "$PROJECT" ] || {
      echo "container belongs to an unexpected project" >&2
      exit 1
    }

    mounts=$(docker inspect --format '{{range .Mounts}}{{if .Name}}{{println .Name}}{{end}}{{end}}' "$id")
    for mount in $mounts; do
      case "$mount" in
        "$PGDATA_VOLUME"|"$OBJECTDATA_VOLUME") ;;
        *) echo "unexpected named volume attached to E2E container" >&2; exit 1 ;;
      esac
    done

    networks=$(docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$id")
    for network in $networks; do
      case "$network" in
        "$PRIVATE_NETWORK"|"$EDGE_NETWORK") ;;
        *) echo "unexpected network attached to E2E container" >&2; exit 1 ;;
      esac
    done

    host_ips=$(docker inspect --format '{{range $port, $bindings := .HostConfig.PortBindings}}{{range $bindings}}{{println .HostIp}}{{end}}{{end}}' "$id")
    for host_ip in $host_ips; do
      [ "$host_ip" = "127.0.0.1" ] || {
        echo "E2E port is not bound to loopback" >&2
        exit 1
      }
    done
  done

  docker volume inspect "$PGDATA_VOLUME" "$OBJECTDATA_VOLUME" >/dev/null
  docker network inspect "$PRIVATE_NETWORK" "$EDGE_NETWORK" >/dev/null
}

assert_absent() {
  ids=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")
  [ -z "$ids" ] || {
    echo "disposable containers remain after cleanup" >&2
    exit 1
  }
  for volume in "$PGDATA_VOLUME" "$OBJECTDATA_VOLUME"; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
      echo "disposable volume remains after cleanup" >&2
      exit 1
    fi
  done
  for network in "$PRIVATE_NETWORK" "$EDGE_NETWORK"; do
    if docker network inspect "$network" >/dev/null 2>&1; then
      echo "disposable network remains after cleanup" >&2
      exit 1
    fi
  done
}

up() {
  echo "==> preclean exact disposable project"
  compose down --volumes --remove-orphans
  assert_absent

  echo "==> build current revision"
  compose --profile migrate build api worker web migrate

  echo "==> isolated dependencies"
  compose up -d --wait postgres valkey objectstore

  echo "==> verified schema"
  compose --profile migrate run --rm migrate

  echo "==> synthetic seed"
  compose --profile migrate run --rm migrate python -m db.seed.local

  echo "==> isolated applications"
  compose up -d --wait --force-recreate api worker web

  echo "==> product readiness"
  compose exec -T api python -c '
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=10) as response:
    payload = json.load(response)
if payload.get("status") != "ready":
    raise SystemExit("API not ready")
schema = [item for item in payload.get("dependencies", []) if item.get("name") == "schema"]
if len(schema) != 1 or schema[0].get("status") != "up":
    raise SystemExit("schema not ready")
'

  echo "==> runtime isolation"
  assert_isolated
}

down() {
  echo "==> cleanup exact disposable project"
  compose down --volumes --remove-orphans
}

validate_constants
[ "$#" -eq 1 ] || {
  echo "usage: test-web-isolated.sh {up|down|assert-isolated|assert-clean}" >&2
  exit 3
}

case "$1" in
  up) up ;;
  down) down ;;
  assert-isolated) assert_isolated ;;
  assert-clean) assert_absent ;;
  *) echo "unsupported isolated lifecycle action" >&2; exit 3 ;;
esac
