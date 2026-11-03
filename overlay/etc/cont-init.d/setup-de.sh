#!/bin/bash
set -e
# Configurations are provisioned in persistent HOME, never replaced here.
# Create as the application user, not root; preserve all existing save files.
gosu "$UNAME" mkdir -p "$HOME/.config/retroarch" "$HOME/.config/PCSX2/inis" \
  "$HOME/.local/share/dolphin-emu/Config" "$HOME/ES-DE/custom_systems" \
  "$HOME/ES-DE/settings" "$HOME/ES-DE/gamelists" \
  "$HOME/Saves/retroarch" "$HOME/States/retroarch"
