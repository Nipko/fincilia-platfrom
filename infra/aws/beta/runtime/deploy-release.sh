#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf 'usage: deploy-release.sh s3://exact-release-bundle\n' >&2
  exit 64
fi

bundle_uri="${1%/}"
if ! printf '%s' "$bundle_uri" | grep -Eq \
  '^s3://fincilia-[0-9]{12}-t0-objects-sa-east-1/deployment/beta/[0-9a-f]{40}$'; then
  printf 'release bundle URI is outside the closed-beta namespace\n' >&2
  exit 64
fi

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

for required in deployment.env compose.yaml up.sh deploy-release.sh; do
  test -s "$staging/$required"
done
source "$staging/deployment.env"
test "$bundle_uri" = "${bundle_uri%/*}/$FINCILIA_RELEASE_SHA"

chmod 0700 "$staging"/up.sh "$staging"/invite.sh \
  "$staging"/smoke-journey.sh \
  "$staging"/backup.sh "$staging"/restore-check.sh \
  "$staging"/deploy-release.sh
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

if systemctl restart fincilia-beta.service; then
  systemctl enable --now fincilia-beta-backup.timer \
    fincilia-beta-restore-check.timer
  aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
    --metric-data MetricName=ReleaseDeploymentSuccess,Value=1,Unit=Count
  printf 'release=%s rollback=%s\n' "$FINCILIA_RELEASE_SHA" "$previous"
  exit 0
fi

mv /opt/fincilia "$failed"
mv "$previous" /opt/fincilia
install_units /opt/fincilia
systemctl reset-failed fincilia-beta.service || true
systemctl restart fincilia-beta.service || true
aws cloudwatch put-metric-data --namespace Fincilia/ClosedBeta \
  --metric-data MetricName=ReleaseDeploymentSuccess,Value=0,Unit=Count || true
printf 'deployment failed; prior release restored; failed bundle=%s\n' "$failed" >&2
exit 1
