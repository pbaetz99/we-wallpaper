#!/usr/bin/env bash
# Installiert we-wallpaper in den Benutzerpfad (kein root noetig).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"; SHARE="$HOME/.local/share/we-wallpaper"
APPS="$HOME/.local/share/applications"; UNITS="$HOME/.config/systemd/user"

miss=()
command -v python3 >/dev/null || miss+=("python3")
python3 -c "import PySide6" 2>/dev/null || miss+=("PySide6 (Fedora: python3-pyside6)")
command -v kscreen-doctor >/dev/null || miss+=("kscreen-doctor")
command -v ffprobe >/dev/null || echo "Hinweis: ffprobe fehlt - Videoaufloesungen werden nicht erkannt"
RENDERER="${WE_RENDERER:-$HOME/.local/src/linux-wallpaperengine/build/output/linux-wallpaperengine}"
[ -x "$RENDERER" ] || echo "Hinweis: Renderer nicht gefunden unter $RENDERER (WE_RENDERER setzen oder linux-wallpaperengine bauen)"
if [ ${#miss[@]} -gt 0 ]; then printf 'Fehlt: %s\n' "${miss[@]}"; exit 1; fi

mkdir -p "$BIN" "$SHARE" "$APPS" "$UNITS"
install -m 755 "$HERE"/bin/we-wallpaper "$HERE"/bin/we-wallpaper-gui "$HERE"/bin/we-wallpaper-watch "$BIN/"
install -m 644 "$HERE"/share/fullscreen-watch.js "$SHARE/"
install -m 755 "$HERE"/packaging/install-owe.sh "$SHARE/"
sed "s|^Exec=.*|Exec=$BIN/we-wallpaper-gui|" "$HERE/desktop/we-wallpaper-gui.desktop" > "$APPS/we-wallpaper-gui.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

if [ "${1:-}" = "--contrib" ]; then
  install -m 755 "$HERE/contrib/we-ambient-guard" "$BIN/"
  install -m 644 "$HERE/contrib/we-ambient-guard.service" "$UNITS/"
  systemctl --user daemon-reload
  echo "we-ambient-guard installiert; aktivieren mit: systemctl --user enable --now we-ambient-guard.service"
fi

case ":$PATH:" in *":$BIN:"*) ;; *) echo "Hinweis: $BIN ist nicht im PATH";; esac
echo "Installiert. Naechste Schritte:"
echo "  we-wallpaper list            # abonnierte Wallpaper"
echo "  we-wallpaper-gui             # zuweisen und Anwenden"
echo "  we-wallpaper install-service # als systemd-Dienste (empfohlen)"
