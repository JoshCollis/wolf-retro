# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=ghcr.io/games-on-whales/es-de:fedora
# CI supplies a resolved official digest; local builds use the explicit tag.
# hadolint ignore=DL3006
FROM ${BASE_IMAGE} AS core-builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY build/check-support.sh /build/check-support.sh
# Intentionally track fresh signed distribution dependencies, not old RPM pins.
# hadolint ignore=DL3041
RUN bash /build/check-support.sh && \
    dnf install -y --refresh --setopt=install_weak_deps=False \
      gcc gcc-c++ make nasm python3 curl zlib-devel libpng-devel mesa-libGL-devel && dnf clean all
COPY build/sources.json build/build-cores.py /build/
RUN python3 /build/build-cores.py

# hadolint ignore=DL3006
FROM ${BASE_IMAGE} AS runtime-deps
ARG BASE_IMAGE
ARG BASE_DIGEST=unrecorded-local-build
ARG IMAGE_SOURCE=https://github.com/JoshCollis/wolf-retro
ARG IMAGE_REVISION=local
LABEL org.opencontainers.image.title="wolf-retro" \
      org.opencontainers.image.description="Focused Wolf retro frontend; no games or BIOS included" \
      org.opencontainers.image.source=${IMAGE_SOURCE} \
      org.opencontainers.image.revision=${IMAGE_REVISION} \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.base.name=${BASE_IMAGE} \
      org.opencontainers.image.base.digest=${BASE_DIGEST}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY build/check-support.sh /usr/local/libexec/wolf-retro/check-support
# Refresh only the image's selected runtime packages/dependencies, never a host,
# cross-release upgrade, user core updater or game-prefix migration.
# hadolint ignore=DL3041
RUN bash /usr/local/libexec/wolf-retro/check-support && \
    test "$(uname -m)" = x86_64 && \
    dnf upgrade -y --refresh --setopt=install_weak_deps=False \
      retroarch retroarch-assets libretro-mgba sway xorg-x11-server-Xwayland \
      mesa-dri-drivers mesa-vulkan-drivers vulkan-loader SDL3 sdl2-compat qt6-qtbase && \
    dnf install -y --setopt=install_weak_deps=False \
      dolphin-emu retroarch retroarch-assets libretro-mgba zenity python3 \
      xorg-x11-server-Xvfb xorg-x11-xauth xprop xwininfo xdotool \
      sdl2-compat mesa-dri-drivers mesa-vulkan-drivers vulkan-loader \
      libxcb xcb-util-cursor libxkbcommon-x11 qt6-qtwayland \
      grim wtype procps-ng file binutils && dnf clean all

FROM runtime-deps AS runtime
ARG BASE_IMAGE
ARG BASE_DIGEST=unrecorded-local-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# The reviewed official Fedora amd64 base accidentally includes an ARM ES-DE.
# Replace it with the exact official x64 3.5.0 release, never a first-asset query.
# Extraction needs separate working directories within this one layer.
# hadolint ignore=DL3003
RUN curl -fSL --retry 3 --connect-timeout 30 --max-time 180 \
      https://gitlab.com/es-de/emulationstation-de/-/package_files/357718352/download \
      -o /Applications/esde.AppImage && \
    echo 'abc2999a12385f85775bd3f986fa891c76b69df3791f7c12e4c783cf3c3630f5  /Applications/esde.AppImage' | sha256sum -c - && \
    chmod 0755 /Applications/esde.AppImage && \
    mkdir -p /opt/emulators/{esde,pcsx2} /opt/retro-library /usr/share/wolf-retro && \
    cd /opt/emulators/esde && /Applications/esde.AppImage --appimage-extract >/dev/null && \
    cd /opt/emulators/pcsx2 && /Applications/pcsx2-emu.AppImage --appimage-extract >/dev/null && \
    rm /opt/emulators/pcsx2/squashfs-root/AppRun && \
    ln -s /usr/share/libretro/assets /opt/retro-library/assets && \
    cp /etc/os-release /usr/share/wolf-retro/base-os-release && \
    printf '%s\n' "$BASE_IMAGE" > /usr/share/wolf-retro/base-image.txt && \
    printf '%s\n' "$BASE_DIGEST" > /usr/share/wolf-retro/base-digest.txt && \
    sha256sum /Applications/*.AppImage > /usr/share/wolf-retro/appimages.sha256
COPY --from=core-builder /assets/ /
COPY overlay/ /
COPY LICENSE NOTICE.md /usr/share/doc/wolf-retro/
RUN ln -s /usr/lib64/libretro/mgba_libretro.so /opt/retro-library/cores/mgba_libretro.so && \
    chmod 0755 /usr/local/bin/{retro-launch,library-help,dolphin-input} \
      /opt/emulators/dolphin/squashfs-root/AppRun \
      /opt/emulators/pcsx2/squashfs-root/AppRun \
      /etc/cont-init.d/{10-setup_user.sh,setup-de.sh} /opt/gow/startup-app.sh && \
    rm -f /etc/cont-init.d/init-gamescope.sh && \
    rpm -qa --qf '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\t%{LICENSE}\n' | sort > /usr/share/wolf-retro/packages.tsv && \
    rpm -q retroarch retroarch-assets dolphin-emu libretro-mgba > /usr/share/wolf-retro/emulator-packages.txt && \
    cp /usr/share/doc/wolf-retro/cores/sources.json /opt/retro-library/sources.json
ENV UNAME=retro HOME=/home/retro PUID=1000 PGID=1000 UMASK=022 TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8
WORKDIR /home/retro
# Keep the official entrypoint, device setup, NVIDIA injection and Sway launcher.
