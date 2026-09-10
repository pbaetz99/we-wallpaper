# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [0.3.0] – 2026-09-11

### Added
- Backend `owe`: waywallen + Open Wallpaper Engine. Renders inside Plasma's
  wallpaper layer, so desktop icons stay visible for scene, video and web
  wallpapers — including the scene that crashed the KDE plugin. `we-wallpaper
  backend owe` stops the own renderer, starts the daemon, enables its autostart,
  sets `org.waywallen.kde` on every desktop, copies the `pause_on_*` settings
  into waywallen's pause policy and applies the assigned wallpaper by Workshop
  ID. Apply, slideshow and `next` re-apply through waywallen.
- `we-wallpaper owe status|list|apply|pause|scan|prop|start|stop` for direct
  control; `doctor` checks the Flatpak, the Plasma extension and the plugin.
- `packaging/install-owe.sh`: installs the Flatpak, the Plasma extension
  (`kpackagetool6`) and the OWE bundle with SHA-256 verification, all in the
  user's home.
- Dependency-free WebSocket client and Protobuf wire codec for waywallen's
  control protocol; `share/wwproto/` documents the messages and field numbers.
- GUI: third entry in the *Backend* box with a setup hint when something is
  missing.
- Tests: codec round trips, the client against an in-process fake daemon
  (fragmented frames, pings, error responses), policy sync leaving unknown
  settings intact, monitor-to-display planning, the backend switch with stubs.

### Changed
- In `owe` mode the pause daemon no longer freezes processes; waywallen pauses
  on fullscreen/maximized/lock itself. The daemon forwards only the manual
  pause (Meta+Shift+P) and keeps recording the reason for `status`.
  Meta+Shift+W toggles waywallen's pause instead of killing a renderer.

## [0.2.3] – 2026-09-11

### Added
- `span_pause_any`: a wallpaper spanning several monitors pauses as soon as
  one of them is covered by a fullscreen or maximized window; the default keeps
  waiting for all of them. Checkbox in the GUI, covered by `DecideTests`.

## [0.2.2] – 2026-09-10

### Added
- `packaging/kde-plugin-patches/`: the KDE plugin's scene backend no longer
  terminates plasmashell on a broken scene (try/catch around scene parsing and
  render-graph construction; unknown render targets are dropped from the
  material). `build-kde-plugin.sh` applies the patches. Verified with the scene
  that crashed 0.2.1: same errors logged, plasmashell survives.
- `doctor` checks the `QtWebSockets` QML module when the plugin is installed.

### Changed
- `build-kde-plugin.sh` lists `qt6-qtwebsockets-devel` (carries the QML module
  on Fedora/Nobara) and warns to remove the COPR package with `--noautoremove`.

## [0.2.1] – 2026-09-10

### Fixed
- `backend kde-plugin` writes `WallpaperSource` in the plugin's packed
  `<folder>/<file>+<type>` form. With a bare path the plugin had no backend
  ("Source is empty") and the desktop stayed black.

### Added
- `packaging/build-kde-plugin.sh`: builds wallpaper-engine-kde-plugin from one
  source tree (library and Plasma package), which is what makes it render.
- Scene guard: the switch refuses scene wallpapers because the plugin's scene
  backend crashed plasmashell here; `--force` or `kde_plugin_allow_scene`.
- Verified on the reference machine: a video wallpaper through the plugin
  **with desktop icons visible**.

### Changed
- Backend tests no longer touch the running session: plugin search roots and
  every system call are replaced in the test.

## [0.2.0] – 2026-09-10

### Added
- **Backend switch** (`we-wallpaper backend`, *Backend* box in the GUI):
  hand the desktop over to `wallpaper-engine-kde-plugin` through Plasma's
  scripting interface and back. The plugin keeps the desktop icons visible.
- **Per-output pausing** (`"per_output": true`): one renderer process per
  monitor with a supervisor in the systemd unit; the pause daemon freezes only
  the process whose monitor is covered by a fullscreen or maximized window.
- **`--screen-span` verified at runtime** on two monitors (5120×1440 + 4K).
- **RPM packaging**: `packaging/we-wallpaper.spec` and `build-rpm.sh`; the
  package runs the test suite in `%check`.
- **English UI.** The GUI now follows the system locale (`LANG`/`LC_MESSAGES`);
  force a language with `WE_LANG=de` or `WE_LANG=en`.
- `we-wallpaper doctor` checks every prerequisite (Wayland/KDE session,
  renderer binary, Wallpaper Engine assets, workshop folder, PySide6 with
  QtDBus, `kscreen-doctor`, `ffprobe`, KWin scripting over D-Bus, user systemd,
  `PATH`, configuration, assigned monitors, service state) and prints a hint
  for each missing piece.
- `renderer` key in the configuration as an alternative to `WE_RENDERER`.
- Test suite under `tests/` (standard-library `unittest`, no pytest needed):
  argument building, spans, layer flag, slideshow order, legacy migration,
  config round-trips, condition evaluation, colour conversion, UI-state
  round-trip, property-editor widget construction. Runs in CI on every push.
- Documentation: `docs/ARCHITECTURE.md`, `CONTRIBUTING.md`, this changelog.

### Changed
- Sort order is stored in the UI state as an index, so it survives a language
  switch.

## [0.1.0] – 2026-09-10

First public release: control script, PySide6 GUI with properties editor and
live preview, pause daemon with KWin script (fullscreen, lock, maximized,
manual; global shortcuts Meta+Shift+W/N/P), systemd user units,
`contrib/we-ambient-guard` for the OpenRGB plugin deadlock.
