# Third-party software and provenance

Joshua Collis's integration code, including the curated text launcher contract,
is MIT licensed. CI structure follows the JoshCollis wolf-lutris, wolf-steam and
wolf-plasma repositories. This does **not** relicense the image's dependencies.

- Official base: https://github.com/games-on-whales/gow (MIT integration).
  CI resolves `ghcr.io/games-on-whales/es-de:fedora` to an immutable digest.
  Its GoW entrypoint, device groups, NVIDIA hooks and compositor launcher remain.
  The unsafe delete-and-recreate-user hook is replaced without deleting HOME.
- ES-DE: https://gitlab.com/es-de/emulationstation-de, MIT application plus its
  separately licensed dependencies/themes. Official **x64 3.5.0** package file
  357718352, SHA-256 `abc2999a12385f85775bd3f986fa891c76b69df3791f7c12e4c783cf3c3630f5`.
  This explicitly repairs the ARM AppImage present in the reviewed amd64 base.
  Corresponding release source: https://gitlab.com/es-de/emulationstation-de/-/tree/v3.5.0 .
- PCSX2: https://github.com/PCSX2/pcsx2 (GPL-3.0-or-later and component notices).
  The official GoW base's unmodified AppImage is extracted; a wrapper sets its
  bundled library/plugin paths. Its binary version and SHA are recorded at build
  and test time. Retain upstream corresponding source for that exact version
  when redistributing. The inherited unrelated emulator AppImages remain base
  content, not supported launchers in this focused project.
- Dolphin: https://dolphin-emu.org and https://src.fedoraproject.org/rpms/dolphin-emu,
  GPL-2.0-or-later; use the signed Fedora native package, not a host binary.
- mGBA core: https://src.fedoraproject.org/rpms/libretro-mgba (MPL-2.0 and
  component notices), signed Fedora RPM mapped to the compatibility core path.
- Four additional cores are built from checksum-pinned public source archives
  in `build/sources.json`: Genesis Plus GX (noncommercial/custom component
  licences; **not unrestricted commercial-use software**), FCEUmm (GPL-2.0),
  Snes9x (custom noncommercial licence), Mupen64Plus-Next (GPL-2.0 and component
  licences). Full corresponding archives and recursively collected licence
  notices accompany the binaries in `/usr/share/doc/wolf-retro/cores/` together
  with build URLs, source hashes and binary hashes. Build commands are in this
  repository. No nightly buildbot binary, host core or host UI asset is copied.
- RetroArch (GPL-3.0-or-later), UI assets, Sway, Qt, SDL, Mesa and other RPMs
  retain licences under `/usr/share/licenses` and RPM metadata. Exact package
  versions/licences are in `/usr/share/wolf-retro/packages.tsv`; corresponding
  Fedora/RPM Fusion sources are available through their source repositories.
  The official base already enables signed RPM Fusion repositories; this project
  adds no third-party repository, COPR or PPA.

Preserve all component notices and corresponding-source obligations on public
redistribution. This project is not an official Wolf, emulator or console product.
No ROMs, BIOS, games, private profile configuration or credentials are included.
