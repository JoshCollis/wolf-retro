"""Real Unix permissions regression inside a disposable exact-runtime container.

The fixture is not a Wayland protocol server: it isolates the production socket
ownership failure without mounting a host socket, disabling security or a GPU.
"""
import errno
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys

RUNTIME = Path('/run/user/wolf')
PARENT = RUNTIME / 'wayland-1'
PAYLOAD = b'wolf-retro-parent-connect'


def metadata(path):
    info = path.stat()
    return info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), info.st_ino


def connect():
    assert os.getuid() == os.getgid() == 1000
    assert os.environ['XDG_RUNTIME_DIR'] == str(RUNTIME)
    assert os.environ['WAYLAND_DISPLAY'] == os.environ['EXPECTED_DISPLAY']
    display = Path(os.environ['WAYLAND_DISPLAY'])
    path = display if display.is_absolute() else RUNTIME / display
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(path))
        client.sendall(PAYLOAD)


def denied_client():
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)
    try:
        connect()
    except PermissionError as error:
        assert error.errno == errno.EACCES
        print('PASS actual UID 1000 connect denied before hook', flush=True)
        return
    raise AssertionError('Root-owned 0755 parent socket unexpectedly writable')


def run(command, env):
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=25)
    print(result.stdout, result.stderr, sep='', flush=True)
    return result


def main():
    assert os.getuid() == 0
    os.umask(0o022)
    RUNTIME.mkdir(parents=True)
    # Match the directory state supplied by existing user init, so pre-hook
    # EACCES proves socket permissions, not an inaccessible ancestor directory.
    RUNTIME.chmod(0o700)
    os.chown(RUNTIME, 1000, 1000)
    sibling_directory = RUNTIME / 'other-lobby'
    sibling_directory.mkdir(mode=0o751)
    marker = sibling_directory / 'marker'
    marker.write_text('Unrelated lobby; must remain root-owned.\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(RUNTIME), PUID='1000', PGID='1000', RUN_SWAY='1')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener, \
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sibling:
        listener.bind(str(PARENT))
        listener.listen(2)
        listener.settimeout(5)
        sibling_path = RUNTIME / 'wayland-other'
        sibling.bind(str(sibling_path))
        sibling.listen(1)
        PARENT.chmod(0o755)
        sibling_path.chmod(0o755)
        protected = [RUNTIME.parent, RUNTIME, sibling_directory, marker, sibling_path]
        before = {path: metadata(path) for path in protected}
        for display in ['wayland-1', str(PARENT)]:
            os.chown(PARENT, 0, 0)
            original = metadata(PARENT)
            assert original[:3] == (0, 0, 0o755)
            env.update(WAYLAND_DISPLAY=display, EXPECTED_DISPLAY=display)
            denied = run(['python3', '/test/wayland_socket.py', 'denied-client'], env)
            assert denied.returncode == 0
            result = run(['/entrypoint.sh', 'exec gosu "$UNAME" python3 /test/wayland_socket.py client'], env)
            assert result.returncode == 0, 'Normal entrypoint did not restore parent socket access'
            assert metadata(PARENT) == (1000, 1000, 0o755, original[3])
            with listener.accept()[0] as connection:
                connection.settimeout(3)
                _, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                assert (uid, gid) == (1000, 1000)
                assert connection.recv(len(PAYLOAD)) == PAYLOAD
            assert {path: metadata(path) for path in protected} == before
            print('PASS normal entrypoint: selected socket only; env/sibling socket/directories unchanged:', display, flush=True)
        for display in ['wayland-missing', str(marker)]:
            env.update(WAYLAND_DISPLAY=display, EXPECTED_DISPLAY=display)
            result = run(['/entrypoint.sh', 'exit 0'], env)
            assert result.returncode == 1
            assert 'Wolf parent Wayland socket missing:' in result.stderr
            assert {path: metadata(path) for path in protected} == before
            print('PASS missing/non-socket parent fails closed:', display, flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        main()
    elif sys.argv[1] == 'client':
        connect()
    elif sys.argv[1] == 'denied-client':
        denied_client()
    else:
        raise ValueError(sys.argv[1])
