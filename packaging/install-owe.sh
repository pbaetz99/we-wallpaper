#!/usr/bin/env bash
# Richtet das Backend "owe" ein: waywallen (Flatpak), die Plasma-Erweiterung
# org.waywallen.kde und das Plugin Open Wallpaper Engine. Danach optional
# direkt umschalten. Alles landet im Home des Nutzers, kein root noetig.
#
#   packaging/install-owe.sh            # installieren und umschalten
#   packaging/install-owe.sh --no-switch
set -euo pipefail

WW_APP="org.waywallen.waywallen"
KDE_VERSION="0.3.3"
OWE_VERSION="0.2.9"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|aarch64) ;;
  *) echo "Architektur $ARCH wird von waywallen nicht unterstuetzt (x86_64, aarch64)"; exit 1 ;;
esac
KDE_URL="https://github.com/waywallen/waywallen-display/releases/download/v${KDE_VERSION}/waywallen-kde-${KDE_VERSION}-${ARCH}-embed.zip"
OWE_URL="https://github.com/waywallen/open-wallpaper-engine/releases/download/v${OWE_VERSION}/org.waywallen.open-wallpaper-engine-${OWE_VERSION}-linux-${ARCH}.zip"
# Pruefsummen der x86_64-Archive (bei anderen Architekturen nur Warnung)
declare -A SHA=(
  ["kde-x86_64"]="d121ae4f2fca2d2664b6cd6a6f5c771ad89c530388dc24155b244d8733ae059e"
  ["owe-x86_64"]="30cfee5a043320e0fb194b447cc7a07dec5df8ab238121f2f362c8f7b6820278"
)
PLUGIN_ROOT="$HOME/.var/app/$WW_APP/data/waywallen/plugins"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

need() { command -v "$1" >/dev/null 2>&1 || { echo "fehlt: $1 ($2)"; exit 1; }; }
need flatpak "Fedora/Nobara: sudo dnf install flatpak"
need kpackagetool6 "Teil von KDE Plasma 6"
need unzip "sudo dnf install unzip"
need curl "sudo dnf install curl"

check_sha() {   # Datei Schluessel
  local want="${SHA[$2]:-}"
  if [ -z "$want" ]; then echo "  (keine Pruefsumme fuer $2 hinterlegt - uebersprungen)"; return; fi
  local got; got="$(sha256sum "$1" | cut -d' ' -f1)"
  [ "$got" = "$want" ] || { echo "Pruefsumme von $1 stimmt nicht: $got"; exit 1; }
  echo "  Pruefsumme ok"
}

echo "1/4 waywallen (Flatpak, Flathub, Benutzerinstallation)"
if flatpak info --user "$WW_APP" >/dev/null 2>&1; then
  echo "  bereits installiert: $(flatpak info --user "$WW_APP" 2>/dev/null | awk '/Version/ {print $2}')"
else
  flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install --user -y flathub "$WW_APP"
fi

echo "2/4 Plasma-Erweiterung org.waywallen.kde $KDE_VERSION"
curl -fsSL -o "$TMP/kde.zip" "$KDE_URL"
check_sha "$TMP/kde.zip" "kde-$ARCH"
if [ -d "$HOME/.local/share/plasma/wallpapers/org.waywallen.kde" ]; then
  kpackagetool6 --type Plasma/Wallpaper -u "$TMP/kde.zip" >/dev/null
else
  kpackagetool6 --type Plasma/Wallpaper -i "$TMP/kde.zip" >/dev/null
fi
echo "  installiert nach ~/.local/share/plasma/wallpapers/org.waywallen.kde"

echo "3/4 Open Wallpaper Engine $OWE_VERSION (etwa 150 MB)"
if [ -x "$PLUGIN_ROOT/org.waywallen.open-wallpaper-engine/bin/waywallen-wescene-renderer" ]; then
  echo "  bereits vorhanden: $PLUGIN_ROOT/org.waywallen.open-wallpaper-engine"
else
  curl -fL --progress-bar -o "$TMP/owe.zip" "$OWE_URL"
  check_sha "$TMP/owe.zip" "owe-$ARCH"
  mkdir -p "$PLUGIN_ROOT"
  unzip -q -o "$TMP/owe.zip" -d "$PLUGIN_ROOT"
  echo "  entpackt nach $PLUGIN_ROOT"
fi

echo "4/4 plasmashell neu starten, damit die QML-Erweiterung geladen wird"
if systemctl --user is-active plasma-plasmashell.service >/dev/null 2>&1; then
  systemctl --user restart plasma-plasmashell.service
  sleep 4
else
  echo "  plasmashell laeuft nicht als systemd-Unit - bitte selbst neu starten (plasmashell --replace &)"
fi

if [ "${1:-}" != "--no-switch" ]; then
  CTL="$(command -v we-wallpaper || echo "$HOME/.local/bin/we-wallpaper")"
  if [ -x "$CTL" ]; then
    echo; "$CTL" backend owe
  else
    echo "we-wallpaper ist nicht installiert (./install.sh) - spaeter: we-wallpaper backend owe"
  fi
fi
