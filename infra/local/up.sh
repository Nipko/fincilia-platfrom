#!/usr/bin/env sh
# Deja el producto funcionando en local, desde cero, en un solo comando:
#
#     sh infra/local/up.sh
#
# El orden importa y no es un detalle de implementacion. Las aplicaciones no se
# declaran sanas contra una base sin esquema: el worker prefiere salir con 1 a
# reportar salud sin poder trabajar, y la API responde 503 en `ready` nombrando
# el esquema. Por eso primero va la infraestructura, luego la migracion, y solo
# despues el resto. Es el mismo orden que en un despliegue real.
#
# Este script **no** borra nada. Empezar de cero es una decision aparte:
#
#     docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes
set -eu

PROJECT=fincilia-local
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$HERE/compose.yaml"

compose() {
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}

echo "==> imagenes de esta revision"
compose --profile migrate build api worker web migrate

# Si ya habia una revision local ejecutandose, no debe observar el esquema nuevo
# mientras migra ni sobrevivir con una imagen anterior. `stop` conserva datos,
# volumenes y contenedores; el `up --force-recreate` posterior los reemplaza.
echo "==> detener aplicaciones anteriores"
compose stop api worker web

echo "==> infraestructura"
compose up -d --wait postgres valkey objectstore

echo "==> esquema"
compose --profile migrate run --rm migrate

echo "==> datos sinteticos de demo"
compose --profile migrate run --rm migrate python -m db.seed.local

echo "==> aplicaciones"
compose up -d --wait --force-recreate api worker web

echo "==> readiness de producto y esquema"
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

WEB_PORT=${FINCILIA_LOCAL_WEB_PORT:-53000}
API_PORT=${FINCILIA_LOCAL_API_PORT:-58080}
echo
echo "Web:  http://127.0.0.1:${WEB_PORT}"
echo "API:  http://127.0.0.1:${API_PORT}/docs"
echo "Entra como ana@demo.local con la contrasena sintetica de la semilla."
