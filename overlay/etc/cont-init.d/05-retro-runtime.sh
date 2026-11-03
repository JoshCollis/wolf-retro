#!/bin/bash
# Sourced before user setup. Adapted from wolf-plasma's exact-parent-socket hook.
# Keep GoW's XDG_RUNTIME_DIR and WAYLAND_DISPLAY contract unchanged for Sway.
if [[ -n ${WAYLAND_DISPLAY:-} ]]; then
  [[ "${PUID:-1000}" =~ ^[1-9][0-9]*$ && "${PGID:-1000}" =~ ^[1-9][0-9]*$ ]] || exit 1
  if [[ $WAYLAND_DISPLAY = /* ]]; then
    WOLF_RETRO_PARENT_WAYLAND="$WAYLAND_DISPLAY"
  else
    WOLF_RETRO_PARENT_WAYLAND="${XDG_RUNTIME_DIR:?Wolf runtime directory required}/$WAYLAND_DISPLAY"
  fi
  if [[ ! -S $WOLF_RETRO_PARENT_WAYLAND ]]; then
    printf 'Wolf parent Wayland socket missing: %s\n' "$WOLF_RETRO_PARENT_WAYLAND" >&2
    exit 1
  fi
  # Only the injected parent socket, never its directory, siblings or HOME.
  chown -- "${PUID:-1000}:${PGID:-1000}" "$WOLF_RETRO_PARENT_WAYLAND"
fi
