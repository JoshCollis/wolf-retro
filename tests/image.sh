#!/bin/bash
set -euo pipefail
image=${1:?Usage: bash tests/image.sh IMAGE}
mkdir -p artifacts
image_id=$(docker image inspect "$image" --format '{{.Id}}')
printf '%s\n' "$image_id" > artifacts/tested-image.id
volume=$(docker volume create)
container="wolf-retro-test-${volume:0:12}"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null
}
trap cleanup EXIT
# Inspect the actual exported image before init, with no permissive HOME fixture.
# Any inherited root-owned profile scaffold must be removed at BUILD time only.
timeout 30 docker run --rm --name "$container" --network none --entrypoint python3 \
  "$image_id" -c 'from pathlib import Path; p=Path("/home/retro"); assert not list(p.iterdir()), list(p.iterdir()); print("PASS image-baked HOME is empty before init")' \
  2>&1 | tee artifacts/runtime-baked-home.log
# Expand UNAME only inside the container.
# shellcheck disable=SC2016
timeout 30 docker run --rm --name "$container" --network none \
  --mount "type=bind,src=$(pwd)/tests,dst=/test,readonly" \
  -e XDG_RUNTIME_DIR=/run/user/1000 \
  "$image_id" 'exec gosu "$UNAME" python3 /test/runtime.py identity' \
  2>&1 | tee artifacts/runtime-default-identity.log
for assignment in UNAME=root PUID=81; do
  # Root and a conflicting distribution UID must fail without deleting a user.
  if timeout 30 docker run --rm --name "$container" --network none \
    -e "$assignment" "$image_id" 'exit 0' > "artifacts/refusal-$assignment.log" 2>&1; then
    echo "Unsafe identity was accepted: $assignment" >&2
    exit 1
  else
    test "$?" -eq 1
  fi
done
for phase in seed check gui check; do
  # Variables expand inside the container's official command handler.
  # shellcheck disable=SC2016
  timeout 180 docker run --rm --name "$container" --network none \
    --mount "type=volume,src=$volume,dst=/home/retro" \
    --mount "type=bind,src=$(pwd)/tests,dst=/test,readonly" \
    -e PGID=100 -e XDG_RUNTIME_DIR=/run/user/1000 \
    -e TEST_PHASE="$phase" -e PYTHONDONTWRITEBYTECODE=1 \
    "$image_id" 'exec gosu "$UNAME" python3 /test/runtime.py "$TEST_PHASE"' \
    2>&1 | tee "artifacts/runtime-$phase.log"
done
test "$(docker image inspect "$image" --format '{{.Id}}')" = "$image_id"
echo "PASS: exact runtime $image_id; init, existing numeric group, recreation and real software UIs"
