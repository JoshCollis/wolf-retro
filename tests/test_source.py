import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(ROOT / 'overlay/usr/local/bin' / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.launch = load('retro-launch')

    def test_core_contract(self):
        self.assertEqual(set(self.launch.CORES.values()),
                         {'genesis_plus_gx', 'fceumm', 'snes9x', 'mgba', 'mupen64plus_next'})
        with tempfile.NamedTemporaryFile(suffix='.txt') as sentinel:
            with patch.object(self.launch.subprocess, 'call', return_value=0) as call:
                for system, core in self.launch.CORES.items():
                    self.assertEqual(self.launch.main([system, sentinel.name]), 0)
                    command = call.call_args.args[0]
                    self.assertIn('/opt/retro-library/cores/' + core + '_libretro.so', command)
                    self.assertIn(str(Path.home() / '.config/retroarch/retroarch.cfg'), command)
                    self.assertEqual(command[-1], sentinel.name)
                    self.assertEqual(call.call_args.kwargs['env']['QT_QPA_PLATFORM'], 'xcb')

    def test_missing_file_never_launches(self):
        with patch.object(self.launch, 'message') as message, patch.object(self.launch.subprocess, 'call') as call:
            self.assertEqual(self.launch.main(['nes', '/definitely-not-a-game']), 2)
            message.assert_called_once()
            call.assert_not_called()

    def test_bios_gate(self):
        with tempfile.NamedTemporaryFile() as sentinel, patch.object(self.launch.pathlib.Path, 'glob', return_value=[]):
            with patch.object(self.launch, 'message') as message, patch.object(self.launch.subprocess, 'call') as call:
                self.assertEqual(self.launch.main(['ps2', sentinel.name]), 2)
                self.assertEqual(message.call_args.args[0], 'PS2 BIOS needed')
                call.assert_not_called()

    def test_focus_concrete_dolphin_renderer_not_workspace(self):
        tree = {'type': 'workspace', 'id': 1, 'pid': 42, 'nodes': [
            {'type': 'con', 'window': 5, 'id': 6, 'pid': 42, 'window_properties': {'window_role': 'main'}},
            {'type': 'con', 'window': 7, 'id': 8, 'pid': 42, 'window_properties': {'window_role': 'renderer'}}]}
        with patch.object(self.launch.subprocess, 'check_output', side_effect=[json.dumps(tree), '[{"success": true}]']) as call:
            self.assertTrue(self.launch.focus_game_window(42, 'gc'))
            self.assertEqual(call.call_args.args[0][1], '[con_id=8] fullscreen enable; [con_id=8] focus')

    def test_no_renderer_or_failed_ipc_does_not_claim_focus(self):
        with patch.object(self.launch.subprocess, 'check_output', return_value='{"nodes": []}'):
            self.assertFalse(self.launch.focus_game_window(42, 'gc'))
        node = {'type': 'con', 'app_id': 'test', 'id': 4, 'pid': 5}
        with patch.object(self.launch.subprocess, 'check_output', side_effect=[json.dumps(node), '[{"success": false}]']):
            self.assertFalse(self.launch.focus_game_window(5, 'nes'))

    def test_input_combines_keyboard_and_gamepad(self):
        module = load('dolphin-input')
        keyboard, hotkeys = module.render(None)
        self.assertIn('Buttons/A = `X`', keyboard)
        self.assertNotIn('SDL/0/', keyboard)
        self.assertIn('General/Stop = `Escape`', hotkeys)
        combined, hotkeys = module.render('Example Controller')
        self.assertIn('Buttons/A = `X` | `SDL/0/Example Controller:Button A`', combined)
        self.assertIn(':Back` & `SDL/0/Example Controller:Start`)', hotkeys)
        self.assertEqual(len(module.PAIRS), 22)


class PolicyTests(unittest.TestCase):
    def test_parent_wayland_hook_is_packaged_and_required(self):
        hook = 'overlay/etc/cont-init.d/05-retro-runtime.sh'
        for name in ['.dockerignore', '.gitignore']:
            self.assertIn(hook, (ROOT / name).read_text())
        self.assertIn('05-retro-runtime.sh', (ROOT / 'Dockerfile').read_text())
        self.assertIn('/test/wayland_socket.py', (ROOT / 'tests/image.sh').read_text())
        text = (ROOT / hook).read_text()
        self.assertIn('[[ ! -S $WOLF_RETRO_PARENT_WAYLAND ]]', text)
        self.assertEqual(text.count('chown --'), 1)
        self.assertNotIn('export XDG_RUNTIME_DIR', text)
        self.assertNotIn('export WAYLAND_DISPLAY', text)

    def test_support_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'os-release'
            for contents, expected in [
                ('ID=fedora\nVERSION_ID=44\nSUPPORT_END=2999-01-01\n', 0),
                ('ID=fedora\nVERSION_ID=44\nSUPPORT_END=2025-01-01\n', 1),
                ('ID=ubuntu\nVERSION_ID=25.04\nSUPPORT_END=2999-01-01\n', 1),
                ('ID=fedora\nVERSION_ID=44\n', 1),
                ('ID=fedora\nVERSION_ID=44\nSUPPORT_END=unknown\n', 1),
                ('ID=fedora\nVERSION_ID=44\nSUPPORT_END=2999-99-99\n', 1),
            ]:
                path.write_text(contents)
                result = subprocess.run(['bash', str(ROOT / 'build/check-support.sh'), str(path)], capture_output=True)
                self.assertEqual(result.returncode == 0, expected == 0, contents)

    def test_pinned_public_sources_and_no_binary_payload(self):
        records = json.loads((ROOT / 'build/sources.json').read_text())
        self.assertEqual(len(records), 4)
        for record in records:
            self.assertRegex(record['url'], r'^https://codeload.github.com/libretro/[^/]+/tar.gz/[a-f0-9]{40}$')
            self.assertRegex(record['sha256'], r'^[a-f0-9]{64}$')
        for directory in ('overlay', 'build', 'examples'):
            for path in (ROOT / directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    self.assertNotIn(b'\0', path.read_bytes(), str(path))

    def test_ci_privilege_and_exact_image_policy(self):
        workflow = (ROOT / '.github/workflows/image.yml').read_text()
        self.assertIn("cron: '23 6 * * 1'", workflow)
        for action in re.findall(r'uses: (\S+)', workflow):
            self.assertRegex(action, r'^[\w/-]+@[a-f0-9]{40}$')
        build, publish = workflow.split('\n  publish:')
        self.assertNotIn('packages: write', build)
        self.assertIn('packages: write', publish)
        self.assertNotIn('docker build', publish)
        self.assertIn('docker save wolf-retro:local-review', build)
        self.assertLess(build.index('bash tests/image.sh'), build.index('docker save'))
        self.assertIn('--no-cache-filter core-builder,runtime-deps,runtime', build)
        self.assertIn('--platform linux/amd64', build)
        self.assertIn('tested-image.id', publish)
        self.assertIn("github.event_name != 'pull_request'", publish)
        self.assertIn('base_bytes * 5 + 6 * 1024 * 1024 * 1024', build)
        self.assertIn('before < required', build)
        self.assertIn('"$RUNNER_ENVIRONMENT" == github-hosted', build)
        self.assertLess(build.index('Check build and exact-image export disk budget'),
                        build.index('Build candidate runtime with fresh'))

    def test_private_and_artifact_paths_ignored(self):
        self.assertFalse((ROOT / 'seed-private').exists())
        paths = ['seed-private/Dockerfile', 'artifacts/log.txt', 'cache/blob', 'library/game.nes',
                 'overlay/accident.bin', 'overlay/private.txt', 'overlay/secret.env',
                 'overlay/.env', 'build/bad.so']
        for path in paths:
            result = subprocess.run(['git', 'check-ignore', '--no-index', path], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, path)


if __name__ == '__main__':
    unittest.main()
