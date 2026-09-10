# Contributing

Bug reports with the output of `we-wallpaper doctor` and
`journalctl --user -u we-wallpaper-watch.service -n 50` are the most useful
kind. Pull requests are welcome; please keep the rules below, they all come
from real breakage.

## Running the tests

```bash
tests/run.sh
```

Standard library `unittest` plus PySide6; the GUI tests run with
`QT_QPA_PLATFORM=offscreen`. The suite must stay green; CI runs it on every push.

## Rules that come from real bugs

- **Never look up processes with `pkill -f` / `pgrep -f`.** The pattern is part
  of the shell's own command line and the shell kills itself. Use
  `/proc/<pid>/exe` (see `stray_pids()`), a PID file, or an exact argv
  basename match with a `comm` check (see `kill_other_watchers()`).
- **Tests must never write the real configuration.** Override `CONF`,
  `UISTATE` and `CACHE` on the loaded module (see `tests/_load.py`). A test
  once wrote `fps: 75` into a live config.
- **A frozen renderer must always have a way to wake up.** Anything that sends
  `SIGSTOP` has to be matched by a thaw path that does not depend on the
  sender staying alive: the watchdog in `we-wallpaper-watch`, `rescue_frozen()`
  in `we-wallpaper status`, and `we-wallpaper thaw`.
- **The pause daemon must never call `we-wallpaper stop`.** Under systemd that
  stops the daemon's own unit mid-action and leaves orphaned renderers. Use
  `we-wallpaper toggle`, which touches only the renderer. For the same reason
  the watch unit has no `Requires=`/`Requisite=` on the renderer unit.
- **systemd user units:** `After=plasma-core.target`, never
  `After=plasma-workspace.target` together with `WantedBy=plasma-workspace.target`
  — that is an ordering cycle and systemd silently deletes the start job.
- **QtDBus signal slots in PySide6** need the `SLOT()` form with a leading
  digit: `"1onLockChanged(bool)"`.
- **Qt style sheets** cannot embed images or draw CSS triangles; generate small
  PNGs at runtime instead (see `make_arrow()`).
- **Do not derive aspect ratios from workshop preview images** — Steam crops
  them square. Only `ffprobe` on video wallpapers gives a real resolution.

## Changing the pause logic

Keep the decision in `decide()` in `bin/we-wallpaper-watch` pure and covered by
`tests/test_control.py::DecideTests`; the daemon only feeds it state and applies
the result. New pause reasons go into `reasons()`, new inputs into a D-Bus slot.

## Adding UI strings

German is the source language. Wrap every user-visible literal in `_()` and
add the English translation to `STRINGS` in `bin/we-wallpaper-gui`. Unknown
strings fall back to German rather than crashing; the CI check
`tests/test_gui.py::test_translation_table` covers the mechanism, and a quick
way to spot leftovers is to run the GUI with `WE_LANG=en` and look.

## Commit messages

Imperative subject line, a short body explaining *why*. No tooling trailers.
