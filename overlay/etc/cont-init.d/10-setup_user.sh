#!/bin/bash
# Sourced by the official GoW entrypoint. Never delete an existing UID or HOME.
set -e
[[ "$UNAME" != root && "$PUID" =~ ^[1-9][0-9]*$ && "$PGID" =~ ^[1-9][0-9]*$ ]]
if getent passwd "$PUID" >/dev/null; then
  [[ "$(id -un "$PUID")" == "$UNAME" ]]
elif getent passwd "$UNAME" >/dev/null; then
  echo "UNAME already exists with a different UID" >&2
  exit 1
else
  if ! getent group "$PGID" >/dev/null; then groupadd -g "$PGID" "$UNAME"; fi
  useradd --no-create-home -d "$HOME" -u "$PUID" -g "$PGID" -s /bin/bash "$UNAME"
fi
[[ "$(id -g "$UNAME")" == "$PGID" ]]
umask "${UMASK:-022}"
mkdir -p "$HOME"
chown "$PUID:$PGID" "$HOME"
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  mkdir -p "$XDG_RUNTIME_DIR"
  chown "$PUID:$PGID" "$XDG_RUNTIME_DIR"
  chmod 0700 "$XDG_RUNTIME_DIR"
fi
