# wolf-retro

Focused ES-DE retro frontend for [Games-on-Whales Wolf](https://github.com/games-on-whales/wolf),
built for `linux/amd64`. No games, BIOS, private profiles or account data are included.

## Runtime contract

- ES-DE, RetroArch, Dolphin and PCSX2. Five core names: `genesis_plus_gx`, `fceumm`,
  `snes9x`, `mgba`, `mupen64plus_next`.
- Existing frontend/emulator paths remain:
  `/opt/emulators/{esde,dolphin,pcsx2}/squashfs-root/AppRun`,
  `/opt/retro-library/cores/*_libretro.so`, `/opt/retro-library/assets`.
- `/usr/local/bin/retro-launch SYSTEM FILE` supports `megadrive`, `nes`, `snes`,
  `gba`, `n64`, `gc`, `ps2`. Missing content and missing PS2 BIOS show safe dialogs.
  `/usr/local/bin/library-help` reads `/Library/README.txt` with a safe fallback.
- `/home/retro` is the **existing provisioned persistent HOME**. ES-DE custom XML,
  RetroArch config, PCSX2 settings, Dolphin settings and all saves stay there.
  Startup only creates missing directories, not default configs or game lists.
  This is not a fresh-profile provisioning tool: bring your own legally obtained
  content and generic/custom configuration. No private XML or profile is shipped.
- Mount `/ROMs`, `/BIOS` and `/Library` separately. The launcher checks `/BIOS/ps2`
  for `.bin`/`.rom` files; presence is not BIOS validity. Native emulator validation
  remains authoritative. Never place BIOS or ROM data in the source/build context.

Defaults: `UNAME=retro`, `PUID=1000`, `PGID=1000`, `HOME=/home/retro`, `UMASK=022`,
`TZ=UTC`. Init creates a passwd entry and drops to that user through the official
GoW entrypoint. Existing numeric groups work. Conflicting identities fail rather
than deleting users or their home. Only HOME/runtime-dir top-level ownership is
set; existing files are **not recursively chowned**. Provision correct permissions
before launch. Root application identities are refused.

Use [examples/wolf-retro.toml](examples/wolf-retro.toml) in a separate test app.
Wolf provides Wayland/audio sockets and GPU/input devices. Keep `RUN_SWAY=1` and
**leave `RUN_GAMESCOPE` unset** (upstream treats even `false` as enabled). The
minimal fullscreen Sway config and GoW frontend startup are retained.

Before dropping privileges, `05-retro-runtime.sh` resolves the exact injected
parent Wayland socket (absolute `WAYLAND_DISPLAY`, or relative to the existing
`XDG_RUNTIME_DIR`). A configured display must be a real socket or startup fails
closed. Only that socket is chowned to numeric `PUID:PGID`, allowing nonroot Sway
to connect when Wolf supplies a root-owned mode-0755 listener. Its mode, sibling
sockets and directories are not changed by this hook; there is no recursive
socket-tree/HOME ownership change or daemon umask workaround. Both display
environment variables remain unchanged for GoW's Sway helper. Without
`WAYLAND_DISPLAY`, the hook is a no-op for standalone software tests.

Dolphin runs through native Fedora Qt/Xwayland with the same explicit `--user`
directory, Vulkan renderer and renderer-leaf focus retry. The managed
`GCPadNew.ini`/`Hotkeys.ini` are regenerated per Dolphin launch: keyboard plus the
first SDL controller when available, Escape or Back+Start to stop. Other Dolphin
settings and saves are not changed. Keys: X/Z/A/S = A/B/X/Y, E = Z, Enter = Start,
arrows = stick, I/K/J/L = C-stick, Q/W = triggers, T/G/F/H = D-pad. Streamed input,
Vulkan rendering and renderer focus still require an isolated Wolf acceptance run.

## Supported base and versions

Default: official `ghcr.io/games-on-whales/es-de:fedora`. On 2026-11-03 this is
Fedora 44 with `SUPPORT_END=2027-05-19`. Build/resolution tests reject non-Fedora,
missing/invalid support dates and dates at or beyond EOL; there is no fallback to
the obsolete Ubuntu 25.04 historical image. The current official amd64 base has
an **ARM ES-DE AppImage**: this recipe explicitly replaces it with the reviewed,
checksum-pinned official **x64 ES-DE 3.5.0** release, and launches it in acceptance.

Fedora native `dolphin-emu`, RetroArch, assets and mGBA follow signed distribution
repositories. Fedora's PCSX2 1.6/i686 package is not used: the base's modern PCSX2
AppImage is extracted and its library/plugin environment is wrapped. Four cores
are built from reviewed, pinned public source archives; source and binary hashes,
full corresponding sources and licences accompany the image. mGBA and assets are
mapped from Fedora paths. No host binary cores/assets or moving nightly downloads
are used. See [NOTICE.md](NOTICE.md) for redistribution restrictions and provenance.
Pinned upstream sources do not automatically become upstream "latest"; updating
them needs review. Native RPMs follow the maintained release, not unreviewed feeds.
The source-built N64 core uses upstream's default Unix GLideN64/HLE build, not
the optional paraLLEl RDP/RSP plugins. Review persisted N64 core options before
adoption; no existing options file is rewritten to force a different renderer.

CI resolves the official base digest **every run**, uses `--pull`, and invalidates
all package/source/runtime stages. It refreshes selected image runtime RPMs and
their dependencies within the same Fedora release; no global host/system upgrade,
cross-release migration, user-core updater or mass save/prefix migration is run.
Evidence inside `/usr/share/wolf-retro/` records the base reference, OS, AppImage
hashes and installed RPM versions/licences. `/opt/retro-library/sources.json`
records built cores. CI retains these, actual version output and runtime logs.
Before building, CI checks free space for compiler/runtime layers, BuildKit blobs
and exact-image export (five times uncompressed Docker image size plus 6 GiB;
26.51 GB for the reviewed 4.01 GB base, not its smaller registry transfer size).
Only if below budget may the disposable GitHub-hosted
runner remove its unused Android/.NET/GHC SDK caches; local hosts are never
cleaned. Insufficient space still fails before the build.

## Build and test

```sh
bash tests/lint.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
base=$(bash build/resolve-base.sh)
docker buildx build --pull --load --platform linux/amd64 \
  --no-cache-filter core-builder,runtime-deps,runtime --target runtime \
  --build-arg BASE_IMAGE="$base" --build-arg BASE_DIGEST="${base#*@}" \
  -t wolf-retro:local-review .
bash tests/image.sh wolf-retro:local-review
```

Docker/network access is needed for builds. Acceptance uses the **exact runtime
image ID**, with no test layer or dependency install, no network/ROMs/BIOS/GPU or
production mounts. Tests create and remove their own home volume and containers,
run official init, inspect nonroot passwd/group handling, dynamically load all five
real core libraries and query their libretro API, and preserve HOME fixture hashes,
permissions, ownership and mtimes across recreation. Real software-rendered ES-DE,
RetroArch, Dolphin and PCSX2 windows must map under Xvfb; safe Zenity dialogs are dismissed
via real X11 events. Checks are bounded and fail on missing dependencies or an
early frontend exit. Unit tests additionally cover exact paths and Sway renderer
selection. `artifacts/` is private/ignored; set host `TMPDIR` to your approved
scratch directory when running probes. Optional installed ShellCheck/actionlint
are used by `tests/lint.sh`.

**Limits:** no commercial ROM or BIOS is opened. Dynamic core loading and GUI
startup do not prove emulation, BIOS compatibility, audio, controller gameplay,
save-state compatibility, Wolf/Moonlight delivery, physical GPU performance or
actual Dolphin renderer focus. Validate those in a separate disposable Wolf
profile with your own content before adopting the image. Existing provisioned
profiles are not touched by these tests. Fresh homes need operator provisioning.

## Publication and adoption

Pushes to `main`, PRs, manual runs and **Monday 06:23 UTC** builds run source and
runtime tests. PRs/non-main runs never publish. Successful main runs export the
exact tested runtime and ID/checksum to an artifact; a separate `packages: write`
job loads and verifies it **without rebuilding**, then publishes:

```text
ghcr.io/joshcollis/wolf-retro:latest
ghcr.io/joshcollis/wolf-retro:run-<run-id>-<attempt>
ghcr.io/joshcollis/wolf-retro:sha-<commit>-<run-id>-<attempt>
```

Run/SHA tags are unique identities (CI does not reuse them); pin deployment by
registry digest. The same commit can produce refreshed RPMs/base content later.
After first publication, set GHCR package visibility to **Public** separately.
The workflow does not deploy, pull onto production, restart sessions or adopt an
image. Hermes owns source publication and deployment; review the payload first,
back up HOME, save games and choose a maintenance window before adoption.

## Licence

Integration: MIT, Copyright 2026 Joshua Collis. Dependencies retain their own
licences, including noncommercial core restrictions; the whole image is not MIT.
