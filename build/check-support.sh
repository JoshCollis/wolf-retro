#!/bin/bash
set -euo pipefail
# shellcheck disable=SC1090
source "${1:-/etc/os-release}"
[[ "$ID" == fedora && "$VERSION_ID" =~ ^[0-9]+$ ]]
[[ "${SUPPORT_END:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]
[[ "$(date -u -d "$SUPPORT_END" +%F)" == "$SUPPORT_END" ]]
[[ "$(date -u +%F)" < "$SUPPORT_END" ]] || {
  echo "Refusing unsupported Fedora $VERSION_ID (support ends $SUPPORT_END)" >&2
  exit 1
}
