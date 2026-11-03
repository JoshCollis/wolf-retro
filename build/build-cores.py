#!/usr/bin/env python3
"""Build reviewed public source snapshots, retaining corresponding source."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    records = json.loads(Path('/build/sources.json').read_text())
    cores = Path('/assets/opt/retro-library/cores')
    sources = Path('/assets/usr/share/doc/wolf-retro/cores')
    cores.mkdir(parents=True)
    sources.mkdir(parents=True)
    (sources / 'build-tools.txt').write_text('\n'.join(sorted(subprocess.check_output([
        'rpm', '-qa'], text=True).splitlines())) + '\n')
    (sources / 'build-command.txt').write_text('make -C <directory> -f <makefile> -j2 platform=unix\n')
    for record in records:
        name = record['name']
        archive = sources / (name + '.tar.gz')
        run('curl', '-fSL', '--retry', '3', '--connect-timeout', '30',
            '--max-time', '180', record['url'], '-o', str(archive))
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == record['sha256'], name
        work = Path('/build') / name
        work.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter='data')
        root, = work.iterdir()
        directory = root / record['directory']
        run('make', '-C', str(directory), '-f', record['makefile'], '-j2', 'platform=unix')
        binary, = root.rglob(name + '_libretro.so')
        shutil.copy2(binary, cores / binary.name)
        record['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        for license_path in root.rglob('*'):
            if license_path.is_file() and license_path.name.lower().startswith(('license', 'copying')):
                target = sources / name / license_path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(license_path, target)
    (sources / 'sources.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
