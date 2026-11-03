#!/bin/bash
set -euo pipefail
base=ghcr.io/games-on-whales/es-de:fedora
docker pull --platform linux/amd64 "$base" >&2
reference=$(docker image inspect "$base" --format '{{index .RepoDigests 0}}')
[[ "$reference" =~ ^ghcr.io/games-on-whales/es-de@sha256:[0-9a-f]{64}$ ]]
docker run --rm --network none --entrypoint bash \
  --mount "type=bind,src=$(pwd)/build/check-support.sh,dst=/check-support.sh,readonly" \
  "$reference" /check-support.sh >&2
printf '%s\n' "$reference"
