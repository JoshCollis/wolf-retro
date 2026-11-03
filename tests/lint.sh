#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import ast
import json
import pathlib
import subprocess
import tomllib
root = pathlib.Path('.')
for directory in ('build', 'tests', 'overlay'):
    for path in (root / directory).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        text = path.read_text()
        if path.suffix == '.py' or text.startswith('#!/usr/bin/env python3'):
            ast.parse(text, filename=str(path))
        elif path.suffix == '.sh' or text.startswith('#!/bin/bash'):
            subprocess.run(['bash', '-n', str(path)], check=True)
json.loads(pathlib.Path('build/sources.json').read_text())
tomllib.loads(pathlib.Path('examples/wolf-retro.toml').read_text())
print('Python, shell, JSON and TOML source checks passed')
PY
if command -v shellcheck >/dev/null; then
  shellcheck -x build/*.sh tests/*.sh overlay/etc/cont-init.d/*.sh \
    overlay/opt/gow/*.sh overlay/usr/local/bin/library-help \
    overlay/opt/emulators/*/squashfs-root/AppRun
fi
if command -v actionlint >/dev/null; then actionlint; fi
