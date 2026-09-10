# we-wallpaper

Wallpaper Engine workshop wallpapers on **KDE Plasma 6 / Wayland**, with the
quality-of-life pieces the bare renderer does not have: a graphical library and
properties editor, per-monitor assignment, profiles, a slideshow, global
shortcuts, and — most importantly — **automatic pausing** so the renderer stops
burning GPU power whenever nobody can see the wallpaper.

Built on [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine)
by Almamu, which does the actual rendering. This project only drives it.

> **Status:** built for one machine (Nobara 44, Plasma 6.7 on Wayland, NVIDIA
> RTX 4080, a 32:9 ultrawide). It works there and every feature below was
> tested there. Expect rough edges elsewhere. UI strings and code comments are
> in German.

## Why the pausing matters

Measured on the reference machine with a scene wallpaper at 5120×1440:

| state                | GPU power | GPU util | CPU  |
|----------------------|-----------|----------|------|
| rendering at 60 fps  | ~61 W     | 37 %     | 6.5 %|
| rendering at 30 fps  | ~53 W     | 35 %     | 2.5 %|
| frozen (`SIGSTOP`)   | ~45 W     | 25 %     | 0 %  |

The wallpaper is invisible while the screen is locked, while a game runs
fullscreen, or while a maximized window covers every monitor. `we-wallpaper-watch`
freezes the renderer in exactly those situations and thaws it afterwards.

## The one hard limitation

On Plasma/Wayland the renderer draws into a layer-shell surface that always sits
**above Plasma's desktop containment** — with every `--layer` setting. That means
**desktop icons are hidden** while the wallpaper runs. This was tested three ways
(renderer off → icons visible; `bottom` and `background` layers → icons hidden).

If you need desktop icons *and* an animated wallpaper, use
[wallpaper-engine-kde-plugin](https://github.com/catsout/wallpaper-engine-kde-plugin)
instead, which renders inside Plasma's own wallpaper layer. This project offers
the next best thing: **Meta+Shift+W** toggles the wallpaper off and on instantly,
so the icons are one keystroke away.

## Components

| file | role |
|------|------|
| `bin/we-wallpaper` | control script: start/stop/restart/status, profiles, slideshow, `toggle`, `next`, `thaw`, systemd install |
| `bin/we-wallpaper-gui` | PySide6 application: library grid, filters, favourites, properties editor, live preview, profiles, tray icon |
| `bin/we-wallpaper-watch` | pause daemon: freezes the renderer on fullscreen / lock / maximized / manual; owns the KWin script and the global shortcuts |
| `share/fullscreen-watch.js` | KWin script: detects fullscreen and maximized windows, registers the shortcuts, reports over D-Bus |
| `systemd/*.service` | user units (auto-restart on crash, bound to the Plasma session) |
| `contrib/we-ambient-guard` | unrelated to wallpapers: works around an OpenRGB Effects-plugin deadlock and duplicate OpenRGB starts; see below |

## Requirements

- KDE Plasma 6 on Wayland (KWin must support `wlr-layer-shell`; it does).
- A built `linux-wallpaperengine` (default path
  `~/.local/src/linux-wallpaperengine/build/output/linux-wallpaperengine`,
  override with `WE_RENDERER=/path/to/binary`).
- **Wallpaper Engine installed through Steam** (via Proton) — the renderer needs
  its `assets/` folder — plus subscribed Workshop wallpapers in
  `~/.local/share/Steam/steamapps/workshop/content/431960/`.
- Python 3 with `PySide6` (Fedora: `python3-pyside6`), `kscreen-doctor`,
  `ffprobe` (for real video resolutions).

## Install

```bash
git clone https://github.com/pbaetz99/we-wallpaper.git
cd we-wallpaper
./install.sh            # copies to ~/.local/bin, ~/.local/share, adds the menu entry
we-wallpaper list       # shows your subscribed wallpapers
we-wallpaper-gui        # assign wallpapers, click "Anwenden"
```

To run as systemd user services (recommended — auto-restart, session-bound):

```bash
we-wallpaper install-service
```

This removes any `~/.config/autostart/we-wallpaper.desktop` so nothing starts
twice. `we-wallpaper uninstall-service` reverts it.

## Usage

```
we-wallpaper start|stop|restart|status|list
we-wallpaper toggle            # renderer off/on, keeps the watcher alive
we-wallpaper next              # advance the slideshow now
we-wallpaper thaw              # emergency: wake a frozen renderer
we-wallpaper profile <name>    # apply a saved profile
we-wallpaper profiles
```

Global shortcuts (registered by the KWin script; change them in
System Settings → Shortcuts → KWin):

| shortcut | action |
|----------|--------|
| Meta+Shift+W | wallpaper off / on (frees the desktop icons) |
| Meta+Shift+N | next wallpaper from the slideshow pool |
| Meta+Shift+P | manual pause / resume |

## Configuration

`~/.config/we-wallpaper.json` is the single source of truth; the GUI writes it.

```jsonc
{
  "screens": {
    "DP-1": { "id": "2941300170", "scaling": "fit", "clamp": "clamp",
              "properties": { "schemecolor": "0.9 0.1 0.1" } }
  },
  "spans": [],                 // [{outputs:[...], id, scaling, clamp, properties}]
  "layer": "bottom",           // background|bottom|top|overlay
  "fps": 30, "volume": 15, "silent": false, "noautomute": true,
  "disable_particles": false, "disable_mouse": false, "disable_parallax": false,
  "pause_on_fullscreen": true, "pause_on_lock": true, "pause_on_maximized": true,
  "rotation": { "enabled": false, "minutes": 30, "pool": [], "order": "random" },
  "profiles": {}, "favorites": [], "hidden": []
}
```

Per-wallpaper properties are the ones the wallpaper author exposes in
`project.json`; the GUI renders them as switches, sliders, colour pickers and
combos, honouring the author's `condition` rules. They are passed to the
renderer as `--set-property name=value`.

## How the pausing works

KWin on Wayland does not implement `wlr-foreign-toplevel-management`, so the
renderer cannot detect fullscreen windows by itself. `fullscreen-watch.js` runs
inside KWin, watches window state, and calls `we-wallpaper-watch` over D-Bus
(`org.wewallpaper.Watch`). The daemon freezes the renderer with `SIGSTOP` and
resumes it with `SIGCONT`.

A frozen process depends on somebody waking it up, so there are several safety
nets: the daemon wakes the renderer on start and on exit, a watchdog checks
every 5 s that the process state matches the pause reasons, `we-wallpaper status`
frees a frozen renderer when no daemon is alive (the GUI polls status every
5 s), and `we-wallpaper thaw` exists for emergencies. The current reason is
written to `~/.local/state/we-wallpaper-pause.json` and shown by `status`.

## contrib: we-ambient-guard (OpenRGB)

Not about wallpapers. On the reference machine the OpenRGB Effects plugin's
"Ambient" effect died every time the display powered off: both the Effects and
VisualMap plugins hit a Qt deadlock (`Dead lock detected in
BlockingQueuedConnection`) and the effect thread never recovered. The guard
follows the journal for that message and restarts OpenRGB through its systemd
unit. It also removes duplicate OpenRGB instances that Plasma's session restore
starts on top of the autostart entry (`excludeApps` in `ksmserverrc` did not
prevent that on the Wayland path).

Set `WE_OPENRGB_UNIT` if your autostart unit is not
`app-OpenRGB@autostart.service`. Note that a restarted OpenRGB only brings the
effect back if an effect profile with *AutoStart* is saved in the plugin.

## Things that bit me (so they don't bite you)

- `pkill -f name` matches the shell that runs it. Every process lookup here
  goes through `/proc/<pid>/exe` or an exact argv basename instead.
- Own systemd user units must not be `After=plasma-workspace.target` *and*
  `WantedBy=plasma-workspace.target` — that is an ordering cycle and systemd
  silently deletes the start job. Use `After=plasma-core.target`.
- `QDBusConnection.connect(...)` in PySide6 wants the slot in `SLOT()` form:
  `"1onLockChanged(bool)"`, with the leading digit.
- Steam's workshop preview images are square crops; they say nothing about a
  wallpaper's aspect ratio. Only video wallpapers have a measurable resolution.
- Qt style sheets cannot embed image data or draw CSS triangles; the combo-box
  arrows are PNGs generated at runtime.

## Roadmap / known gaps

Ordered by how much they would matter day to day.

1. **Desktop icons.** The layer-shell approach cannot show them; the real fix is
   to render inside Plasma's wallpaper layer, i.e. become (or build on) a KDE
   wallpaper plugin. Everything above the renderer — GUI, profiles, pausing —
   would carry over.
2. **Per-output pausing.** There is one renderer process for all monitors, so
   "maximized window on every monitor" is the only safe rule. One process per
   output would allow pausing a single screen.
3. **`--screen-span` is untested at runtime.** The argument building is covered
   by tests; the second monitor of the reference machine was off. Needs a real
   dual-monitor check.
4. **Renderer path in the config** instead of only `WE_RENDERER`.
5. **English UI** (strings are German) and a proper translation setup.
6. **Packaging** — RPM/COPR spec, so `install.sh` becomes optional.
7. **Tests as a suite.** The checks that exist (config round-trips, condition
   evaluation, argument building, pause state machine) live in the development
   history, not in `tests/`.

## License

MIT — see `LICENSE`. `linux-wallpaperengine` has its own license; this project
only launches it as a separate process.
