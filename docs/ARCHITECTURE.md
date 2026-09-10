# Architecture

Three processes and one KWin script, held together by a JSON file and D-Bus.

```
 ┌──────────────────────┐   writes    ┌─────────────────────────────┐
 │  we-wallpaper-gui    │────────────▶│ ~/.config/we-wallpaper.json │
 │  (PySide6)           │             └──────────────┬──────────────┘
 └──────────┬───────────┘                            │ reads
            │ runs                                   ▼
            ▼                              ┌───────────────────┐   execv    ┌──────────────────────┐
 ┌──────────────────────┐   status/toggle  │   we-wallpaper    │──────────▶│ linux-wallpaperengine│
 │  KWin  (compositor)  │                  │  (control script) │            │  (renderer, layer-   │
 │  fullscreen-watch.js │                  └─────────┬─────────┘            │   shell surface)     │
 └──────────┬───────────┘                            │ starts                └──────────▲───────────┘
            │ callDBus(org.wewallpaper.Watch)        ▼                                  │ SIGSTOP / SIGCONT
            └────────────────────────────▶ ┌───────────────────┐ ───────────────────────┘
                                           │ we-wallpaper-watch│ ◀── org.freedesktop.ScreenSaver.ActiveChanged
                                           │ (pause daemon)    │
                                           └───────────────────┘
```

## Control script — `bin/we-wallpaper`

Owns the configuration and the renderer's command line. `build_args()` turns
the JSON into `--screen-root`/`--screen-span`, `--bg`, `--scaling`, `--clamp`,
`--set-property`, `--layer`, `--fps` and the audio/effect flags, skipping
outputs that `kscreen-doctor -j` reports as disabled and wallpapers that are
not subscribed.

Two ways of running the renderer:

- **Direct:** `spawn()` starts it detached and writes
  `~/.local/state/we-wallpaper.pid`.
- **systemd:** `run-renderer` `execv`s the renderer in the foreground so
  systemd supervises the real process (`Restart=on-failure`). The PID file is
  written before `execv` because the PID survives it.

When the units are enabled, `start`/`stop`/`restart` delegate to `systemctl`.
`stop` additionally sweeps stray renderers found through `/proc/<pid>/exe`,
`toggle` stops or starts only the renderer (the daemon calls it), `next`
advances the slideshow, `thaw` sends `SIGCONT`, `doctor` checks prerequisites.

### Per-output mode

`build_arg_groups()` splits the command line into one group per
`--screen-root` (spans stay together). With `"per_output": true`, `spawn()`
starts one renderer per group and writes `~/.local/state/we-wallpaper-outputs.json`
(`{pid: [outputs]}`); under systemd `run-renderer` stays alive as a supervisor
that restarts a crashed child after 3 s and forwards `SIGTERM`.

### Backend switch

`we-wallpaper backend kde-plugin` stops the own renderer and the pause daemon,
then runs a Plasma script over `org.kde.PlasmaShell.evaluateScript` that sets
`wallpaperPlugin` of every desktop to the plugin id read from its
`metadata.json` and writes its config group. `backend native` restores
`org.kde.image` and re-enables the units. `WallpaperSource` must be the
plugin's packed form `<folder>/<file>+<type>`; the type selects the plugin's
backend (Mpv, QtWebView, Scene). Scene wallpapers are refused without
`--force` after a plasmashell crash with the scene backend.

**Why can't the own renderer sit under the icons?** Even with `--layer
background` and KWin's stacking order confirming the renderer below
plasmashell's desktop window, and a transparent wallpaper plugin loaded, the
desktop stayed black: KWin composites plasmashell's desktop window opaque, so
nothing beneath it is visible. The plugin is detected under
`~/.local/share/plasma/wallpapers` and `/usr/share/plasma/wallpapers`.

### OWE backend (waywallen + Open Wallpaper Engine)

`backend owe` hands rendering to the waywallen daemon. Its Plasma extension
(`org.waywallen.kde`, a kpackage with an embedded QML plugin) draws inside
Plasma's wallpaper layer, which is the only place a wallpaper can sit *under*
the desktop icons — the compositor paints Plasma's desktop window opaque, so a
layer-shell surface can never show through, whatever `--layer` it uses.

Control path, all in the control script and dependency-free:

1. `busctl --user get-property org.waywallen.waywallen.Daemon
   /org/waywallen/waywallen/Daemon org.waywallen.waywallen.Daemon1 WsPort`
   finds the daemon's WebSocket port (also `Version`, `CurrentWallpaperId`).
2. `OweSocket` is a ~60-line RFC 6455 client (masked binary frames, ping/pong,
   fragment reassembly). Each request is a raw
   `Request{request_id=1, <payload field>}`; the server answers with
   `ServerFrame{response=1}` carrying `Response{request_id, status=2 (OK=1),
   message=3, error_code=4, <payload>}`.
3. `pb_encode/pb_decode` are a generic Protobuf wire codec: messages are lists
   of `(field, wire type, value)`; nested messages and strings stay raw bytes,
   so unknown fields survive a decode → modify → encode round trip. That is
   what `owe_sync_policy` relies on: `settings_get`, replace only
   `GlobalSettings.auto_replay` (16) → `fullscreen` (13), `maximized` (12),
   `session_locked` (14), `settings_set` with everything else untouched.
   Generated `*_pb2.py` bindings were rejected on purpose: Fedora's
   `python3-protobuf` (3.19) cannot load code generated by protoc 7.x.
4. Wallpapers are matched by Workshop ID: waywallen's catalogue IDs are plain
   counters, the Workshop ID sits in `WallpaperEntry.external_id` (15) or in
   the resource path. `owe_plan` maps configured monitors to waywallen
   displays by resolution (`kscreen-doctor -j` vs. `display_list`), because
   the extension registers every display as `qml-display`; unmatched displays
   get the first assigned wallpaper. One `wallpaper_apply` per wallpaper with
   its `PresentationTarget{display_id}` list.

Switching: stop and disable the own renderer unit, start the daemon
(`flatpak run --command=waywallen org.waywallen.waywallen --no-ui`, same as
its autostart entry, the KDE backend is auto-detected), `autostart_set(true)`
(the daemon uses the XDG background portal, which writes
`~/.config/autostart/org.waywallen.waywallen.desktop`), set every desktop's
`wallpaperPlugin` to `org.waywallen.kde` through `evaluateScript`, sync the
pause policy, apply. Leaving: `autostart_set(false)`, `flatpak kill`, restore
`org.kde.image`, re-enable the units.

Pausing in this mode is waywallen's job — its extension reports a window-state
bitmask per display (`nonmin/active/max/full`) and the daemon applies the
`auto_replay` policy (verified in its debug log: `pause renderer … (auto-action)`
on a fullscreen window). The pause daemon therefore only forwards the manual
pause (`global_pause_set`) and records the reason; it must not mirror automatic
reasons, or it would undo a pause the user set in waywallen's tray.

## Pause daemon — `bin/we-wallpaper-watch`

A `QCoreApplication` that registers `org.wewallpaper.Watch` on the session bus
and loads `share/fullscreen-watch.js` into KWin over
`org.kde.kwin.Scripting`. It keeps four booleans — fullscreen, locked, covered,
manual — and one rule: if any reason applies (and its config flag is on) the
renderer gets `SIGSTOP`, otherwise `SIGCONT`. The reason is written to
`~/.local/state/we-wallpaper-pause.json` for `status`.

| source                                | sets       |
|---------------------------------------|------------|
| KWin script: any window `fullScreen`  | fullscreen |
| `org.freedesktop.ScreenSaver.ActiveChanged` | locked |
| KWin script: every output covered by a maximized/fullscreen window | covered |
| Meta+Shift+P                          | manual     |

Safety nets, because a stopped process cannot wake itself:

1. On start the daemon thaws whatever is frozen and takes over the D-Bus name
   from an older instance (`ReplaceExistingService`).
2. A 5-second watchdog corrects any mismatch between the reasons and the
   process state.
3. `we-wallpaper status` thaws a frozen renderer when no daemon is alive; the
   GUI polls status every 5 s.
4. `we-wallpaper thaw` for humans.
5. On exit — including `SIGTERM` from systemd — the daemon thaws and unloads
   the script.

## KWin script — `share/fullscreen-watch.js`

Runs inside KWin, so it sees window state directly and may register global
shortcuts. It cannot start programs, hence D-Bus. It handles both the Plasma 6
API (`workspace.windowList`, `windowAdded`) and the older `client*` names.
The renderer's own layer-shell surface appears in the window list and is
excluded by `resourceClass`. `maximizeMode === 3` is `MaximizeFull`; the enum
constant is not visible to scripts.

## GUI — `bin/we-wallpaper-gui`

Single window: toolbar (search, filters, sort, profile, thumbnail size), monitor
list with per-monitor scaling/clamp/span, wallpaper grid, details pane with
animated preview, description and the properties editor, bottom bar with global
flags and the status pill, plus a tray icon.

`PropertyEditor` builds widgets from the wallpaper's `project.json` schema
(`bool`, `slider`, `color`, `combo`, `textinput`, `file`, `group`) and evaluates
the author's `condition` strings (`x.value >= 1 && y.value == 0`) to show or
hide rows. Values are stored per monitor and passed as `--set-property`.

Live preview runs the renderer once with `--window` and `--screenshot` at the
monitor's aspect ratio. Real resolutions come from `ffprobe` (video wallpapers
only) and are cached in `~/.cache/we-wallpaper/resolutions.json`.

UI state (geometry, filters, sort index, thumbnail size, last selection) lives
in `~/.local/state/we-wallpaper-ui.json` and is saved on close and every 20 s
when it changed.

## Why not X?

- **Why SIGSTOP instead of killing the renderer?** Resuming is instant and keeps
  the wallpaper's state; a restart takes seconds and flickers. The price is the
  safety-net machinery above.
- **Why one renderer process?** `linux-wallpaperengine` renders all outputs
  from one process, so pausing is all-or-nothing. Per-output pausing would need
  one process per output (roadmap).
- **Why a KWin script for fullscreen?** KWin does not implement
  `wlr-foreign-toplevel-management`, which the renderer would use to detect
  fullscreen windows itself.
- **Why can't the desktop icons show?** The layer-shell surface always sits
  above Plasma's desktop containment, on every layer. Only rendering inside
  Plasma's wallpaper layer (a KDE wallpaper plugin) fixes that.
