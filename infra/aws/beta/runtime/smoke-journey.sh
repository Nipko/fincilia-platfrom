#!/usr/bin/env bash
set -euo pipefail

# Recorrido público sintético sin imprimir invitación, contraseña ni token.
# Crea evidencia operacional de identidad → empresa → carga → procesamiento.
cd /opt/fincilia
source /opt/fincilia/runtime.env

if [ "${FINCILIA_REAL_DATA_ENABLED:-false}" != "false" ]; then
  printf 'public synthetic smoke refused when real data is enabled\n' >&2
  exit 64
fi

exec 9>/run/fincilia-beta-smoke.lock
flock -n 9 || {
  printf 'another public synthetic smoke is active\n' >&2
  exit 75
}

invite_json="$(/opt/fincilia/invite.sh create 1 1)"
invite_code="$(printf '%s' "$invite_json" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["created"][0]["code"])')"
marker="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')"
username="journey-${marker}@demo.local"
secret="Smoke-9!$(python3 -c 'import secrets; print(secrets.token_hex(18))')"

compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta)
api_container="$("${compose[@]}" ps -q api)"
test -n "$api_container"

python_source="$(cat <<'PY'
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000/api/v1"


def call(method, path, *, token=None, payload=None, raw=None, content_type=None,
         idempotency_key=None):
    if payload is not None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        content_type = "application/json"
    headers = {"accept": "application/json"}
    if token:
        headers["authorization"] = "Bearer " + token
    if content_type:
        headers["content-type"] = content_type
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    request = urllib.request.Request(
        BASE + path, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        # El cuerpo puede contener datos de entrada. La evidencia solo conserva
        # etapa y código, nunca el payload ni credenciales.
        raise RuntimeError(f"request failed: {method} {path} http={error.code}") from None


invite_code, username, secret = sys.stdin.read().splitlines()
marker = username.removeprefix("journey-").removesuffix("@demo.local")

status, session = call("POST", "/auth/registration", payload={
    "username": username,
    "secret": secret,
    "display_name": "Persona recorrido sintético",
    "firm_name": "Firma recorrido sintético",
    "invite_code": invite_code,
})
if status != 201:
    raise RuntimeError(f"registration returned {status}")
token = session["token"]
subject_id = session["subject_id"]

status, authenticated = call("POST", "/auth/session", payload={
    "username": username,
    "secret": secret,
})
if status != 200 or authenticated["subject_id"] != subject_id:
    raise RuntimeError("fresh account could not authenticate")
token = authenticated["token"]

status, firms = call("GET", "/firms/manageable", token=token)
if status != 200 or len(firms) != 1:
    raise RuntimeError("registration did not create one manageable firm")

status, company = call(
    "POST", "/companies", token=token,
    idempotency_key="public-smoke-company-" + marker,
    payload={
        "firm_id": firms[0]["firm_id"],
        "legal_name": "Empresa recorrido sintético",
        "country_code": "CO",
        "tax_identifier": "SYN-TAX-" + marker,
        "setup": {
            "account_family": "bank_account",
            "account_name": "Cuenta sintética",
            "account_identifier": "SYN-ACCOUNT-" + marker,
            "currency_code": "COP",
            "source_family": "bank_account",
            "source_name": "Fuente sintética",
            "purpose_code": "operational",
            "timezone": "America/Bogota",
            "anchor_date": dt.date.today().isoformat(),
            "due_day_offset": 0,
            "grace_days": 3,
        },
    },
)
if status != 201:
    raise RuntimeError(f"company provisioning returned {status}")
company_id = company["company_id"]
source_id = company["source_id"]
token = company["refreshed_session"]["token"]

boundary = "fincilia-smoke-" + uuid.uuid4().hex
csv = (
    "fecha,descripcion,importe,referencia\n"
    "2026-08-01,Movimiento sintetico,1250.00,SYN-001\n"
).encode("utf-8")
multipart = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="recorrido-sintetico.csv"\r\n'
    "Content-Type: text/csv\r\n\r\n"
).encode("ascii") + csv + f"\r\n--{boundary}--\r\n".encode("ascii")
status, artifact = call(
    "POST",
    f"/companies/{company_id}/documents?data_source_id={source_id}",
    token=token,
    raw=multipart,
    content_type="multipart/form-data; boundary=" + boundary,
)
if status != 200:
    raise RuntimeError(f"document upload returned {status}")
artifact_id = artifact["artifact_id"]

deadline = time.monotonic() + 90
processing = {}
while time.monotonic() < deadline:
    status, detail = call(
        "GET", f"/companies/{company_id}/documents/{artifact_id}", token=token)
    if status != 200:
        raise RuntimeError(f"document read returned {status}")
    processing = {run["kind"]: run["status"] for run in detail["runs"]}
    if all(processing.get(kind) == "succeeded"
           for kind in ("scan", "profile", "extract")):
        break
    if any(value == "failed" for value in processing.values()):
        raise RuntimeError("synthetic document processing failed")
    time.sleep(2)
else:
    raise RuntimeError("synthetic document processing timed out")

print(json.dumps({
    "ok": True,
    "subject_id": subject_id,
    "company_id": company_id,
    "artifact_id": artifact_id,
    "registration": "passed",
    "authentication": "passed",
    "company_provisioning": "passed",
    "document_processing": processing,
}, sort_keys=True))
PY
)"

printf '%s\n%s\n%s\n' "$invite_code" "$username" "$secret" | \
  docker exec -i "$api_container" python -c "$python_source"

unset invite_json invite_code username secret python_source
