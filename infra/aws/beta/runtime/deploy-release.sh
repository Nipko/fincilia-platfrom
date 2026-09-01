#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf 'usage: deploy-release.sh s3://exact-release-bundle\n' >&2
  exit 64
fi

bundle_uri="${1%/}"
if [[ ! "$bundle_uri" =~ ^s3://fincilia-([0-9]{12})-t0-objects-sa-east-1/deployment/beta/([0-9a-f]{40})$ ]]; then
  printf 'release bundle URI is outside the closed-beta namespace\n' >&2
  exit 64
fi
account_id="${BASH_REMATCH[1]}"
requested_release="${BASH_REMATCH[2]}"

exec 9>/run/fincilia-beta-deploy.lock
flock -n 9 || {
  printf 'another beta deployment is active\n' >&2
  exit 75
}

for unit in fincilia-beta-backup.service fincilia-beta-restore-check.service; do
  if systemctl is-active --quiet "$unit"; then
    printf '%s is active; deployment refused\n' "$unit" >&2
    exit 75
  fi
done

staging="$(mktemp -d /opt/fincilia-next.XXXXXX)"
previous=''
failed=''

cleanup() {
  case "$staging" in
    /opt/fincilia-next.*) [ ! -d "$staging" ] || rm -rf -- "$staging" ;;
    *) printf 'unsafe staging path: %s\n' "$staging" >&2 ;;
  esac
}
trap cleanup EXIT

aws s3 cp "$bundle_uri/" "$staging/" --recursive --only-show-errors
(cd "$staging" && sha256sum -c manifest.sha256)

for required in deployment.env compose.yaml up.sh deploy-release.sh reset-uat-empty.sh; do
  test -s "$staging/$required"
done
source "$staging/deployment.env"
test "$FINCILIA_RELEASE_SHA" = "$requested_release"
test "$FINCILIA_BACKUP_PREFIX" = "backups/beta"
test "$FINCILIA_RUNTIME_PARAMETER" = "/fincilia/closed-beta/runtime-env-v1"
test "$FINCILIA_REGISTRY" = \
  "${account_id}.dkr.ecr.sa-east-1.amazonaws.com"
[[ "$FINCILIA_UAT_DOMAIN" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]]

validate_staged_compose() {
  FINCILIA_EXPECTED_REGISTRY="$FINCILIA_REGISTRY" \
    python3 - "$staging/compose.yaml" <<'PY'
import os
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
registry = os.environ["FINCILIA_EXPECTED_REGISTRY"]
images = re.findall(r"^\s*image:\s*([^\s]+)\s*$", text, re.MULTILINE)
for component in ("api", "web", "worker"):
    expected = re.compile(
        rf"^{re.escape(registry)}/fincilia/t0/{component}@sha256:[0-9a-f]{{64}}$")
    if not any(expected.fullmatch(image) for image in images):
        raise SystemExit(f"missing pinned {component} image in the T0 registry")
if text.count('FINCILIA_REAL_DATA_ENABLED: "false"') < 3:
    raise SystemExit("real-data fail-closed flags are incomplete")
if 'FINCILIA_REAL_DATA_ENABLED: ' + '"true"' in text:
    raise SystemExit("real data cannot be enabled by this UAT deployer")
if text.count('FINCILIA_AI_GATEWAY_ENABLED: "false"') < 3:
    raise SystemExit("AI fail-closed flags are incomplete")
if 'FINCILIA_AI_GATEWAY_ENABLED: ' + '"true"' in text:
    raise SystemExit("external AI cannot be enabled by this UAT deployer")
if text.count('FINCILIA_REGISTRATION_INVITE_REQUIRED: "true"') != 2:
    raise SystemExit("synthetic UAT must keep API and web invitation-only")
if 'FINCILIA_OIDC_ENABLED: "true"' in text:
    raise SystemExit("Google OIDC remains disabled before DRG-00")
PY
}

require_recent_object() {
  local prefix="$1" suffix="$2" maximum_age_seconds="$3" label="$4"
  local latest object_key modified modified_epoch now age
  latest="$(aws s3api list-objects-v2 \
    --bucket "$FINCILIA_BACKUP_BUCKET" --prefix "$prefix" \
    --query "reverse(sort_by(Contents[?ends_with(Key, '$suffix')], &LastModified))[0].[Key,LastModified]" \
    --output text)"
  read -r object_key modified <<< "$latest"
  if [ -z "$object_key" ] || [ "$object_key" = None ] || [ -z "$modified" ]; then
    printf 'no %s evidence found\n' "$label" >&2
    return 1
  fi
  modified_epoch="$(date -u -d "$modified" +%s)"
  now="$(date -u +%s)"
  age=$((now - modified_epoch))
  if [ "$age" -lt 0 ] || [ "$age" -gt "$maximum_age_seconds" ]; then
    printf '%s evidence is stale\n' "$label" >&2
    return 1
  fi
  printf '%s\n' "$object_key"
}

public_https_smoke() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 20 \
      "https://${FINCILIA_UAT_DOMAIN}/entrar" | grep -q 'Fincilia'; then
      return 0
    fi
    sleep 2
  done
  return 1
}

validate_staged_compose
backup_evidence="$(require_recent_object \
  "$FINCILIA_BACKUP_PREFIX/" 'manifest.sha256' 93600 'backup')"
restore_evidence="$(require_recent_object \
  'restore-checks/beta/' '.json' 691200 'restore-check')"

chmod 0700 "$staging"/up.sh "$staging"/invite.sh \
  "$staging"/smoke-journey.sh \
  "$staging"/backup.sh "$staging"/restore-check.sh \
  "$staging"/deploy-release.sh "$staging"/reset-uat-empty.sh
chmod 0600 "$staging/deployment.env"
chmod 0444 "$staging"/bootstrap.sh "$staging"/Caddyfile \
  "$staging"/nginx.conf "$staging"/compose.yaml

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
previous="/opt/fincilia-rollback-$timestamp"
failed="/opt/fincilia-failed-$timestamp"
mv /opt/fincilia "$previous"
mv "$staging" /opt/fincilia

install_units() {
  local root="$1"
  for unit in \
    fincilia-beta.service \
    fincilia-beta-backup.service \
    fincilia-beta-backup.timer \
    fincilia-beta-restore-check.service \
    fincilia-beta-restore-check.timer; do
    install -m 0644 "$root/$unit" "/etc/systemd/system/$unit"
  done
  systemctl daemon-reload
}

install_units /opt/fincilia
systemctl reset-failed fincilia-beta.service \
  fincilia-beta-backup.service fincilia-beta-restore-check.service || true

deployment_ready=false
if systemctl restart fincilia-beta.service && public_https_smoke; then
  deployment_ready=true
fi

persist_success_evidence() {
  local deployed_at evidence
  systemctl enable --now fincilia-beta-backup.timer \
    fincilia-beta-restore-check.timer || return 1
  deployed_at="$(date -u +%Y%m%dT%H%M%SZ)"
  evidence="$(mktemp /run/fincilia-uat-deploy.XXXXXX.json)" || return 1
  printf '{"data_class":"synthetic_only","environment":"uat","release_sha":"%s","deployed_at":"%s","backup_verified":true,"restore_verified":true,"public_https_smoke":true}\n' \
    "$FINCILIA_RELEASE_SHA" "$deployed_at" > "$evidence" || return 1
  aws s3 cp "$evidence" \
    "s3://${FINCILIA_BACKUP_BUCKET}/deployment-evidence/uat/${FINCILIA_RELEASE_SHA}/${deployed_at}.json" \
    --sse AES256 --only-show-errors || {
      rm -f -- "$evidence"
      return 1
    }
  rm -f -- "$evidence" || return 1
  aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
    --metric-data MetricName=ReleaseDeploymentSuccess,Value=1,Unit=Count || return 1
  printf 'release=%s rollback=%s backup=%s restore=%s\n' \
    "$FINCILIA_RELEASE_SHA" "$previous" "$backup_evidence" "$restore_evidence" || return 1
}

if [ "$deployment_ready" = true ] && persist_success_evidence; then
  exit 0
fi

mv /opt/fincilia "$failed"
mv "$previous" /opt/fincilia
install_units /opt/fincilia
systemctl reset-failed fincilia-beta.service || true
systemctl restart fincilia-beta.service || true
public_https_smoke >/dev/null 2>&1 || true
aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
  --metric-data MetricName=ReleaseDeploymentSuccess,Value=0,Unit=Count || true
printf 'deployment failed; prior release restored; failed bundle=%s\n' "$failed" >&2
exit 1
