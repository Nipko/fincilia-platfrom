#!/usr/bin/env bash
set -euo pipefail

cd /opt/fincilia
source /opt/fincilia/runtime.env

compose=(docker compose --env-file /opt/fincilia/runtime.env \
  -f /opt/fincilia/compose.yaml -p fincilia-beta --profile migrate)

case "${1:-}" in
  create)
    hours="${2:-72}"
    count="${3:-1}"
    "${compose[@]}" run --rm migrate python -m db.admin.invitations create \
      --hours "$hours" --count "$count"
    ;;
  list)
    "${compose[@]}" run --rm migrate python -m db.admin.invitations list
    ;;
  revoke)
    test -n "${2:-}"
    "${compose[@]}" run --rm migrate python -m db.admin.invitations revoke \
      --invitation "$2"
    ;;
  *)
    printf 'usage: invite.sh create [hours] [count] | list | revoke <UUID>\n' >&2
    exit 2
    ;;
esac
