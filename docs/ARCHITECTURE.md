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
`org.kde.image` and re-enables the units. The plugin is detected under
`~/.local/share/plasma/wallpapers` and `/usr/share/plasma/wallpapers`.

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
