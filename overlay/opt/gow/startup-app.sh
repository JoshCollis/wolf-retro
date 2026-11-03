#!/bin/bash
set -e
# shellcheck source=/dev/null
source /opt/gow/bash-lib/utils.sh
# shellcheck source=/dev/null
source /opt/gow/launch-comp.sh
launcher "/opt/emulators/esde/squashfs-root/AppRun --no-update-check"
