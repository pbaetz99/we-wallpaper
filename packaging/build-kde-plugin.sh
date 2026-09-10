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
# qt6-qtwebsockets-devel ist KEIN reines Build-Paket: auf Fedora/Nobara liegt das
# QML-Modul QtWebSockets (/usr/lib64/qt6/qml/QtWebSockets) darin, und das Plugin
# braucht es zur Laufzeit. Ohne dieses Paket meldet plasmashell
# 'module "QtWebSockets" is not installed' und das Plugin laedt gar nicht.
DEPS=(cmake ninja-build extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel
      kf6-kpackage-devel libplasma-devel kf6-kconfig-devel kf6-kcoreaddons-devel
      kf6-ki18n-devel mpv-devel vulkan-headers vulkan-loader-devel glslang-devel
      python3-websockets qt6-qtwebengine qt6-qtwebchannel-devel qt6-qtwebsockets-devel)
missing=(); for p in "${DEPS[@]}"; do rpm -q "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Fehlende Pakete (Fedora/Nobara):"; printf '  %s\n' "${missing[@]}"
  echo "Installieren mit: sudo dnf install ${missing[*]}"; exit 1
fi
if rpm -q wallpaper-engine-kde-plugin >/dev/null 2>&1; then
  echo "Das COPR-Paket wallpaper-engine-kde-plugin ist installiert und belegt dieselben Pfade."
  echo "Vorher entfernen - mit --noautoremove, sonst nimmt dnf qt6-qtwebsockets-devel (QML-Modul!) mit:"
  echo "  sudo dnf remove --noautoremove wallpaper-engine-kde-plugin"; exit 1
fi
if [ -d "$SRC/.git" ]; then git -C "$SRC" pull -q --recurse-submodules; else
  git clone -q --recurse-submodules "$REPO" "$SRC"; fi
git -C "$SRC" submodule update --init --recursive -q
# Eigene Patches: ein defektes Szenenpaket darf plasmashell nicht mehr beenden
# (unbehandelte std::out_of_range -> std::terminate). Siehe kde-plugin-patches/.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for p in "$HERE"/kde-plugin-patches/0001-*.patch; do
  [ -f "$p" ] || continue
  if git -C "$SRC/src/backend_scene" apply --check "$p" 2>/dev/null; then
    git -C "$SRC/src/backend_scene" apply "$p" && echo "Patch angewendet: $(basename "$p")"
  else
    git -C "$SRC/src/backend_scene" apply --check --reverse "$p" 2>/dev/null && echo "Patch bereits enthalten: $(basename "$p")" || echo "WARNUNG: Patch passt nicht: $(basename "$p")"
  fi
done
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
