"""Runs inside the exact runtime, as the GoW init-created nonroot user.

No ROM/BIOS mounts, downloads, host devices or production profiles are used.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import time

HOME = Path.home()
FIXTURES = {
    '.config/retroarch/retroarch.cfg': 'video_driver = "gl"\naudio_driver = "null"\nconfig_save_on_exit = "false"\n',
    '.config/PCSX2/inis/PCSX2.ini': '; Existing profile marker, not an image default\n',
    '.local/share/dolphin-emu/Config/Dolphin.ini': '[General]\nShowLag = False\n',
    'ES-DE/custom_systems/persistent-marker.txt': 'Keep existing curated configuration\n',
    'Saves/retroarch/persistence.txt': 'SAVE-FIXTURE-not-a-ROM\n',
    'States/retroarch/persistence.txt': 'STATE-FIXTURE-not-a-ROM\n',
}


def run(*args, **kwargs):
    timeout = kwargs.pop('timeout', 30)
    expected_returncode = kwargs.pop('expected_returncode', 0)
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout, **kwargs)
    print('$', ' '.join(args), '\n', result.stdout, flush=True)
    assert result.returncode == expected_returncode, (
        args, result.returncode, 'expected', expected_returncode)
    return result.stdout


def identity():
    assert os.getuid() == int(os.environ['PUID']) != 0
    assert os.getgid() == int(os.environ['PGID'])
    user = pwd.getpwuid(os.getuid())
    assert user.pw_name == os.environ['UNAME']
    assert user.pw_dir == str(HOME)
    assert HOME.stat().st_uid == os.getuid()
    for relative in ['.config', '.config/retroarch', '.config/PCSX2/inis',
                     '.local', '.local/share', '.local/share/dolphin-emu/Config', 'ES-DE/settings',
                     'Saves/retroarch', 'States/retroarch']:
        directory = HOME / relative
        assert os.access(directory, os.W_OK), relative
        assert directory.stat().st_uid == os.getuid(), relative
        assert directory.stat().st_gid == os.getgid(), relative
    print('PASS nonroot identity/passwd; HOME directories are UID/GID-owned and writable', flush=True)


def fingerprint(path):
    info = path.stat()
    return [hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(info.st_mode),
            info.st_uid, info.st_gid, info.st_mtime_ns]


def seed():
    assert not list(HOME.rglob('*.cfg')), 'startup must not copy upstream defaults'
    for relative, contents in FIXTURES.items():
        target = HOME / relative
        target.write_text(contents)
        target.chmod(0o640)
    snapshot = {relative: fingerprint(HOME / relative) for relative in FIXTURES}
    (HOME / '.test-snapshot.json').write_text(json.dumps(snapshot))
    print('PASS seeded disposable existing HOME', flush=True)


class SystemInfo(ctypes.Structure):
    _fields_ = [('library_name', ctypes.c_char_p), ('library_version', ctypes.c_char_p),
                ('valid_extensions', ctypes.c_char_p), ('need_fullpath', ctypes.c_bool),
                ('block_extract', ctypes.c_bool)]


def core_contract():
    source_records = json.loads(Path('/opt/retro-library/sources.json').read_text())
    for record in source_records:
        archive = Path('/usr/share/doc/wolf-retro/cores') / (record['name'] + '.tar.gz')
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == record['sha256']
        core = Path('/opt/retro-library/cores') / (record['name'] + '_libretro.so')
        assert hashlib.sha256(core.read_bytes()).hexdigest() == record['binary_sha256']
    for name in ['genesis_plus_gx', 'fceumm', 'snes9x', 'mgba', 'mupen64plus_next']:
        path = Path('/opt/retro-library/cores') / (name + '_libretro.so')
        assert path.is_file(), path
        lib = ctypes.CDLL(str(path), mode=os.RTLD_NOW | os.RTLD_LOCAL)
        assert lib.retro_api_version() == 1
        lib.retro_get_system_info.argtypes = [ctypes.POINTER(SystemInfo)]
        info = SystemInfo()
        lib.retro_get_system_info(ctypes.byref(info))
        assert info.library_name and info.library_version and info.valid_extensions
        print('PASS loaded real core', name, info.library_name.decode(), info.library_version.decode(), flush=True)
    assert Path('/opt/retro-library/assets/xmb').is_dir()
    assert Path('/opt/retro-library/cores/mgba_libretro.so').resolve() == Path('/usr/lib64/libretro/mgba_libretro.so')


def check():
    snapshot = json.loads((HOME / '.test-snapshot.json').read_text())
    for relative, expected in snapshot.items():
        assert fingerprint(HOME / relative) == expected, relative
    run('bash', '/usr/local/libexec/wolf-retro/check-support')
    run('rpm', '-q', 'retroarch', 'retroarch-assets', 'libretro-mgba', 'dolphin-emu')
    run('retroarch', '--version')
    for relative in ['esde', 'dolphin', 'pcsx2']:
        path = Path('/opt/emulators') / relative / 'squashfs-root/AppRun'
        assert path.is_file() and os.access(path, os.X_OK), path
    core_contract()
    print('PASS unchanged HOME hashes, permissions, ownership, mtimes after recreation', flush=True)


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def visible_window(process, pattern):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        assert process.poll() is None, f'{pattern} exited early: {process.returncode}'
        result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', pattern],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            window = result.stdout.splitlines()[-1]
            details = run('xwininfo', '-id', window)
            assert 'Map State: IsViewable' in details
            time.sleep(1)
            assert process.poll() is None, pattern
            return window
        time.sleep(0.2)
    raise AssertionError('No mapped real window: ' + pattern)


def dismiss_window(window):
    # Real XTEST events, not synthetic per-window SendEvent key releases racing
    # the dialog's destruction. Xvfb needs no window manager for keyboard focus.
    run('xdotool', 'windowfocus', '--sync', window)
    run('xdotool', 'key', 'Return')


def gui_inner():
    # No real curated XML is shipped. An empty public test home displays ES-DE's
    # no-games configuration screen; a window must actually map under Mesa.
    env = os.environ.copy()
    env.update(LIBGL_ALWAYS_SOFTWARE='1', QT_QPA_PLATFORM='xcb', GDK_BACKEND='x11',
               SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy', GSK_RENDERER='cairo')
    env.pop('RUN_SWAY', None)
    env.pop('RUN_GAMESCOPE', None)
    retro_config = HOME / '.test-retroarch.cfg'
    retro_config.write_text('video_driver = "gl"\naudio_driver = "null"\n'
                           'assets_directory = "/opt/retro-library/assets"\n'
                           'menu_driver = "xmb"\nconfig_save_on_exit = "false"\n')
    commands = [
        (['/opt/emulators/esde/squashfs-root/AppRun', '--version'], None),
        (['/opt/emulators/dolphin/squashfs-root/AppRun', '--version'], None),
        (['/opt/gow/startup-app.sh'], 'ES-DE|EmulationStation'),
        (['retroarch', '--menu', '--config', str(retro_config)], 'RetroArch'),
        (['/opt/emulators/dolphin/squashfs-root/AppRun', '--user', str(HOME / '.test-dolphin')], 'Dolphin'),
        (['/opt/emulators/pcsx2/squashfs-root/AppRun', '-help'], None),
    ]
    for command, pattern in commands:
        if pattern is None:
            # PCSX2 2.8.2 QtHost.cpp returns false from help/version parsing,
            # which main translates to exit 1. Require that exact CLI contract;
            # real mapped PCSX2 GUI acceptance below is still mandatory.
            expected = 1 if command[-1] == '-help' else 0
            output = run(*command, env=env, expected_returncode=expected)
            assert any(name in output for name in ['ES-DE', 'EmulationStation', 'Dolphin', 'PCSX2'])
            if command[-1] == '-help':
                assert '-batch:' in output and '-fullscreen:' in output
            continue
        log = HOME / ('.test-' + pattern.replace('|', '-') + '.log')
        with log.open('w') as stream:
            process = subprocess.Popen(command, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                visible_window(process, pattern)
                print('PASS real mapped software frontend:', pattern, flush=True)
            finally:
                stop(process)
                print(log.read_text(), flush=True)
    # Modern PCSX2 must also map its UI without a BIOS or game, not only print help.
    with (HOME / '.test-pcsx2.log').open('w') as stream:
        pcenv = dict(env, XDG_CONFIG_HOME=str(HOME / '.test-pcsx2-config'))
        process = subprocess.Popen(['/opt/emulators/pcsx2/squashfs-root/AppRun'], env=pcenv,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            visible_window(process, 'PCSX2')
            print('PASS real mapped PCSX2 without content/BIOS', flush=True)
        finally:
            stop(process)
            print((HOME / '.test-pcsx2.log').read_text(), flush=True)
    # Native SDL discovery runs for real; unit tests additionally cover a named pad.
    run('/usr/local/bin/dolphin-input', env=env)
    gamepad = HOME / '.local/share/dolphin-emu/Config/GCPadNew.ini'
    assert 'Buttons/A = `X`' in gamepad.read_text()
    # A text sentinel proves the BIOS check precedes opening content. This is not
    # a ROM, and the only process launched must be the real Zenity safe dialog.
    sentinel = HOME / '.test-not-a-game.txt'
    sentinel.write_text('Not game data. Must never be opened by an emulator.\n')
    for system, content, title in [
        ('nes', '/ROMs/no-such-game.nes', 'Game file missing'),
        ('ps2', str(sentinel), 'PS2 BIOS needed'),
        ('unknown', str(sentinel), 'Unsupported system'),
    ]:
        process = subprocess.Popen(['/usr/local/bin/retro-launch', system, content],
                                   env=env, start_new_session=True)
        try:
            window = visible_window(process, title)
            dismiss_window(window)
            assert process.wait(timeout=10) == 2
            print('PASS real safe dialog:', title, flush=True)
        finally:
            stop(process)
    # Help is also a missing-mount-safe real dialog.
    process = subprocess.Popen(['/usr/local/bin/library-help'], env=env, start_new_session=True)
    try:
        window = visible_window(process, 'Retro Library')
        dismiss_window(window)
        assert process.wait(timeout=10) == 0
    finally:
        stop(process)


def main():
    identity()
    phase = sys.argv[1]
    if phase == 'identity':
        return
    elif phase == 'seed':
        seed()
    elif phase == 'check':
        check()
    elif phase == 'gui':
        run('xvfb-run', '-a', '-s', '-screen 0 1280x720x24 +extension GLX',
            'dbus-run-session', '--', 'python3', '/test/runtime.py', 'gui-inner', timeout=150)
    elif phase == 'gui-inner':
        gui_inner()
    else:
        raise ValueError(phase)


if __name__ == '__main__':
    main()
