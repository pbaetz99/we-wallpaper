# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

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
