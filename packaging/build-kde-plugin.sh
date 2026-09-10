#!/usr/bin/env bash
# Baut wallpaper-engine-kde-plugin (catsout) aus EINEM Quellstand und installiert
# beide Haelften systemweit: das Plasma-Paket (/usr/share/plasma/wallpapers/...)
# und das QML-Modul (/usr/lib64/qt6/qml/com/github/catsout/...).
#
# Warum nicht das COPR-Paket? Es enthaelt nur das QML-Modul; ein QML-Paket aus
# einem anderen Stand rendert dann schwarz. Ein Eigenbau vermeidet den Versatz.
set -euo pipefail
SRC="${1:-$HOME/.local/src/wallpaper-engine-kde-plugin}"
REPO="https://github.com/catsout/wallpaper-engine-kde-plugin.git"
DEPS=(cmake ninja-build extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel
      kf6-kpackage-devel libplasma-devel kf6-kconfig-devel kf6-kcoreaddons-devel
      kf6-ki18n-devel mpv-devel vulkan-headers vulkan-loader-devel glslang-devel
      python3-websockets qt6-qtwebengine qt6-qtwebchannel-devel)
missing=(); for p in "${DEPS[@]}"; do rpm -q "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Fehlende Pakete (Fedora/Nobara):"; printf '  %s\n' "${missing[@]}"
  echo "Installieren mit: sudo dnf install ${missing[*]}"; exit 1
fi
if rpm -q wallpaper-engine-kde-plugin >/dev/null 2>&1; then
  echo "Das COPR-Paket wallpaper-engine-kde-plugin ist installiert und belegt dieselben Pfade."
  echo "Vorher entfernen: sudo dnf remove wallpaper-engine-kde-plugin"; exit 1
fi
if [ -d "$SRC/.git" ]; then git -C "$SRC" pull -q --recurse-submodules; else
  git clone -q --recurse-submodules "$REPO" "$SRC"; fi
git -C "$SRC" submodule update --init --recursive -q
cmake -S "$SRC" -B "$SRC/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/usr -DKDE_INSTALL_USE_QT_SYS_PATHS=ON
cmake --build "$SRC/build" -j"$(nproc)"
echo; echo "Installation braucht root:"; echo "  sudo cmake --install $SRC/build"
if [ "${2:-}" = "--install" ]; then sudo cmake --install "$SRC/build"; fi
# Benutzerlokale Kopien ueberdecken das Systempaket - entfernen:
if [ -d "$HOME/.local/share/plasma/wallpapers/com.github.catsout.wallpaperEngineKde" ]; then
  kpackagetool6 -t Plasma/Wallpaper -r com.github.catsout.wallpaperEngineKde || true
fi
echo "Danach: we-wallpaper backend kde-plugin"
