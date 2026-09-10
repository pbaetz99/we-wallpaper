import json, pathlib, tempfile, unittest
from _load import load


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        ws = self.tmp / "workshop"
        for wid in ("100", "200", "300", "400"):
            (ws / wid).mkdir(parents=True)
            (ws / wid / "project.json").write_text(json.dumps({"title": "T" + wid, "type": "scene"}))
        self.m = load("we-wallpaper", WORKSHOP=ws, CONF=self.tmp / "c.json",
                      LEGACY=self.tmp / "legacy.conf", STATE=self.tmp / "state")
        self.m.enabled_outputs = lambda: {"DP-1", "HDMI-A-1"}
        self.m.service_enabled = lambda: False

    def base(self, **kw):
        cfg = {"fps": 30, "volume": 15, "silent": False, "noautomute": True,
               "rotation": {}, "profiles": {}, "screens": {}, "spans": []}
        cfg.update(kw)
        return cfg

    def test_args_single_screen_with_properties(self):
        cfg = self.base(screens={"DP-1": {"id": "100", "scaling": "fit", "clamp": "border",
                                          "properties": {"a": "1", "col": "0.1 0.2 0.3"}}})
        args, skipped = self.m.build_args(cfg)
        joined = " ".join(args)
        self.assertIn("--screen-root DP-1 --bg 100 --scaling fit --clamp border", joined)
        self.assertIn("--set-property a=1", joined)
        self.assertIn("--set-property col=0.1 0.2 0.3", joined)
        self.assertIn("--volume 15", joined)
        self.assertEqual(skipped, [])

    def test_silent_replaces_volume(self):
        cfg = self.base(silent=True, screens={"DP-1": {"id": "100"}})
        args, _ = self.m.build_args(cfg)
        self.assertIn("--silent", args)
        self.assertNotIn("--volume", args)

    def test_disabled_output_is_skipped(self):
        self.m.enabled_outputs = lambda: {"DP-1"}
        cfg = self.base(screens={"DP-1": {"id": "100"}, "HDMI-A-1": {"id": "200"}})
        args, skipped = self.m.build_args(cfg)
        self.assertIn("--screen-root DP-1", " ".join(args))
        self.assertNotIn("HDMI-A-1", " ".join(args))
        self.assertTrue(any("ausgeschaltet" in s for s in skipped))

    def test_invalid_and_missing_ids(self):
        cfg = self.base(screens={"DP-1": {"id": "abc"}, "HDMI-A-1": {"id": "999"}})
        args, skipped = self.m.build_args(cfg)
        self.assertEqual(args, [])
        self.assertEqual(len(skipped), 2)

    def test_span_takes_precedence(self):
        cfg = self.base(spans=[{"outputs": ["DP-1", "HDMI-A-1"], "id": "300", "scaling": "fill"}],
                        screens={"DP-1": {"id": "100"}})
        args, skipped = self.m.build_args(cfg)
        j = " ".join(args)
        self.assertIn("--screen-span DP-1,HDMI-A-1 --bg 300", j)
        self.assertNotIn("--screen-root DP-1", j)
        self.assertTrue(any("Span belegt" in s for s in skipped))

    def test_span_falls_back_when_output_off(self):
        self.m.enabled_outputs = lambda: {"DP-1"}
        cfg = self.base(spans=[{"outputs": ["DP-1", "HDMI-A-1"], "id": "300"}],
                        screens={"DP-1": {"id": "100"}})
        args, _ = self.m.build_args(cfg)
        self.assertIn("--screen-root DP-1 --bg 100", " ".join(args))
        self.assertNotIn("--screen-span", args)

    def test_layer_flag(self):
        for layer in ("background", "bottom"):
            args, _ = self.m.build_args(self.base(layer=layer, screens={"DP-1": {"id": "100"}}))
            self.assertIn(f"--layer {layer}", " ".join(args))
        args, _ = self.m.build_args(self.base(layer="nonsense", screens={"DP-1": {"id": "100"}}))
        self.assertNotIn("--layer", args)

    def test_rotation_sequential_cycles_pool(self):
        pool = ["100", "200", "300"]
        cfg = self.base(screens={"DP-1": {"id": "100", "properties": {"x": "1"}}},
                        rotation={"pool": pool, "order": "sequential", "index": 0})
        seen = []
        for _ in range(4):
            self.assertTrue(self.m.advance_rotation(cfg))
            seen.append(cfg["screens"]["DP-1"]["id"])
        self.assertEqual(seen, ["200", "300", "100", "200"])
        self.assertEqual(cfg["screens"]["DP-1"]["properties"], {})

    def test_rotation_random_never_repeats(self):
        cfg = self.base(screens={"DP-1": {"id": "100"}},
                        rotation={"pool": ["100", "200", "300", "400"], "order": "random"})
        prev = "100"
        for _ in range(40):
            self.m.advance_rotation(cfg)
            cur = cfg["screens"]["DP-1"]["id"]
            self.assertNotEqual(cur, prev)
            prev = cur

    def test_rotation_needs_two(self):
        cfg = self.base(screens={"DP-1": {"id": "100"}}, rotation={"pool": ["100"]})
        self.assertFalse(self.m.advance_rotation(cfg))

    def test_legacy_migration(self):
        self.m.LEGACY.write_text('SCREENS=(\n  "DP-1=100:fit"   # x\n  "HDMI-A-1=200"\n)\nFPS=24\n')
        cfg = self.m.load_conf()
        self.assertEqual(cfg["screens"]["DP-1"], {"id": "100", "scaling": "fit", "clamp": "clamp", "properties": {}})
        self.assertEqual(cfg["screens"]["HDMI-A-1"]["scaling"], "fill")
        self.assertEqual(cfg["fps"], 24)
        self.assertTrue(self.m.CONF.is_file())

    def test_conf_roundtrip_and_defaults(self):
        self.m.save_conf({"fps": 12})
        cfg = self.m.load_conf()
        self.assertEqual(cfg["fps"], 12)
        self.assertEqual(cfg["rotation"]["order"], "random")
        self.assertIn("pause_on_lock", cfg)

    def test_renderer_override_from_config(self):
        self.m.save_conf({"renderer": "~/custom/lwe"})
        self.m.load_conf()
        self.assertTrue(str(self.m.BIN).endswith("custom/lwe"))


if __name__ == "__main__":
    unittest.main()


class BackendTests(unittest.TestCase):
    """Diese Tests duerfen NIE die echte Plasma-Sitzung anfassen: Plugin-Suchorte
    zeigen auf ein Temp-Verzeichnis, und alles, was das System veraendert
    (Plasma-Skript, systemctl, Renderer stoppen/starten), ist ersetzt."""
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.m = load("we-wallpaper", HOME=self.tmp, WORKSHOP=self.tmp / "ws",
                      CONF=self.tmp / "c.json", STATE=self.tmp / "state")
        self.m.KDE_PLUGIN_ROOTS = [self.tmp / ".local/share/plasma/wallpapers"]
        self.scripts = []
        self.m.plasma_script = lambda js: (self.scripts.append(js) or "ok:stub")
        self.m.systemctl = lambda *a, **k: None
        self.m.service_enabled = lambda: False
        self.m.service_installed = lambda: False
        self.m.do_stop = lambda quiet=False: True
        self.m.spawn = lambda cfg: True
        self.m.do_status = lambda: 0
        self.m.time.sleep = lambda s: None

    def wallpaper(self, wid, wtype="video", wfile="movie.mp4"):
        d = self.m.WORKSHOP / wid; d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(json.dumps({"file": wfile, "type": wtype, "title": "T" + wid}))
        return d

    def fake_plugin(self, plugin_id="com.github.catsout.wallpaperEngineKde"):
        d = self.tmp / ".local/share/plasma/wallpapers" / plugin_id
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({"KPlugin": {"Id": plugin_id}}))
        return d

    def test_detection_absent_and_present(self):
        self.assertFalse(self.m.kde_plugin_installed())
        self.fake_plugin()
        self.assertTrue(self.m.kde_plugin_installed())
        self.assertEqual(self.m.kde_plugin_id(), "com.github.catsout.wallpaperEngineKde")

    def test_plugin_script_contents(self):
        self.fake_plugin()
        wp = self.m.WORKSHOP / "123"; wp.mkdir(parents=True)
        (wp / "project.json").write_text(json.dumps({"file": "movie.mp4", "type": "Video"}))
        cfg = {"screens": {"DP-1": {"id": "123"}}, "fps": 24, "volume": 40, "silent": True, "disable_mouse": True}
        js = self.m.build_kde_plugin_script(cfg, "123")
        # gepacktes Format des Plugins: <Ordner>/<Datei>+<typ> (Typ kleingeschrieben)
        self.assertIn(f'writeConfig("WallpaperSource", "{wp}/movie.mp4+video")', js)
        for needle in ('d.wallpaperPlugin = "com.github.catsout.wallpaperEngineKde"',
                       'writeConfig("WallpaperWorkShopId", "123")', 'writeConfig("Fps", 24)',
                       'writeConfig("Volume", 40)', 'writeConfig("MuteAudio", true)',
                       'writeConfig("MouseInput", false)', 'writeConfig("SteamLibraryPath", "file://'):
            self.assertIn(needle, js)
        self.assertIn(str(self.m.WORKSHOP / "123"), js)

    def test_plugin_script_defaults_to_scene(self):
        self.fake_plugin()
        js = self.m.build_kde_plugin_script({"screens": {}, "fps": 30}, "999")   # kein project.json
        self.assertIn('/999/scene.json+scene"', js)

    def test_restore_script_targets_only_plugin(self):
        self.fake_plugin()
        js = self.m.build_native_restore_script()
        self.assertIn('=== "com.github.catsout.wallpaperEngineKde"', js)
        self.assertIn('"org.kde.image"', js)

    def test_backend_refuses_without_plugin(self):
        self.wallpaper("123")
        self.m.save_conf({"screens": {"DP-1": {"id": "123"}}})
        import io, contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = self.m.do_backend("kde-plugin")
        self.assertEqual(rc, 2)
        self.assertIn("nicht installiert", err.getvalue())
        self.assertEqual(self.m.load_conf().get("backend", "native"), "native")

    def test_backend_switch_video_and_back(self):
        self.fake_plugin(); self.wallpaper("123", "video")
        self.m.save_conf({"screens": {"DP-1": {"id": "123"}}})
        self.assertEqual(self.m.do_backend("kde-plugin"), 0)
        self.assertEqual(self.m.load_conf()["backend"], "kde-plugin")
        self.assertIn('WallpaperSource", "', self.scripts[-1]); self.assertIn("movie.mp4+video", self.scripts[-1])
        self.assertEqual(self.m.do_backend("native"), 0)
        self.assertEqual(self.m.load_conf()["backend"], "native")
        self.assertIn('"org.kde.image"', self.scripts[-1])

    def test_backend_refuses_scene_unless_forced(self):
        import io, contextlib
        self.fake_plugin(); self.wallpaper("777", "scene", "scene.json")
        self.m.save_conf({"screens": {"DP-1": {"id": "777"}}})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.m.do_backend("kde-plugin"), 3)
        self.assertIn("scene", err.getvalue()); self.assertEqual(self.scripts, [])
        self.assertEqual(self.m.do_backend("kde-plugin", force=True), 0)
        self.assertIn("scene.json+scene", self.scripts[-1])
        self.m.save_conf({"screens": {"DP-1": {"id": "777"}}, "kde_plugin_allow_scene": True})
        self.assertEqual(self.m.do_backend("kde-plugin"), 0)


class PerOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        ws = self.tmp / "ws"
        for wid in ("100", "200"):
            (ws / wid).mkdir(parents=True); (ws / wid / "project.json").write_text("{}")
        self.m = load("we-wallpaper", WORKSHOP=ws, CONF=self.tmp / "c.json", STATE=self.tmp / "state")
        self.m.enabled_outputs = lambda: {"DP-1", "HDMI-A-1"}
        self.base = {"fps": 30, "volume": 15, "rotation": {}, "profiles": {}, "spans": [],
                     "screens": {"DP-1": {"id": "100"}, "HDMI-A-1": {"id": "200"}}}

    def test_single_group_by_default(self):
        groups, _ = self.m.build_arg_groups(dict(self.base))
        self.assertEqual(len(groups), 1)
        self.assertEqual(sorted(groups[0][0]), ["DP-1", "HDMI-A-1"])
        self.assertIn("--fps", groups[0][1])

    def test_per_output_groups(self):
        groups, _ = self.m.build_arg_groups(dict(self.base, per_output=True))
        self.assertEqual([g[0] for g in groups], [["DP-1"], ["HDMI-A-1"]])
        for outs, args in groups:
            self.assertEqual(args.count("--screen-root"), 1)
            self.assertIn("--fps", args, "jeder Prozess bekommt die globalen Flags")
            self.assertIn(outs[0], args)

    def test_span_stays_one_process(self):
        cfg = dict(self.base, per_output=True,
                   spans=[{"outputs": ["DP-1", "HDMI-A-1"], "id": "100"}], screens={})
        groups, _ = self.m.build_arg_groups(cfg)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], ["DP-1", "HDMI-A-1"])


class DecideTests(unittest.TestCase):
    def setUp(self):
        import os as _os
        _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        self.w = load("we-wallpaper-watch")

    def test_global_reason_freezes_everything(self):
        d = self.w.decide({1: ["DP-1"], 2: ["HDMI-A-1"]}, ["Handpause"], {"DP-1": [], "HDMI-A-1": []})
        self.assertEqual(d, {1: "Handpause", 2: "Handpause"})

    def test_per_output_only_affected_process(self):
        d = self.w.decide({1: ["DP-1"], 2: ["HDMI-A-1"]}, [], {"DP-1": ["Vollbild"], "HDMI-A-1": []})
        self.assertEqual(d, {1: "Vollbild", 2: None})

    def test_single_process_needs_all_outputs(self):
        per = {"DP-1": ["Fenster maximiert"], "HDMI-A-1": []}
        self.assertEqual(self.w.decide({7: ["*"]}, [], per), {7: None})
        per["HDMI-A-1"] = ["Fenster maximiert"]
        self.assertEqual(self.w.decide({7: ["*"]}, [], per), {7: "Fenster maximiert"})

    def test_no_outputs_known(self):
        self.assertEqual(self.w.decide({7: ["*"]}, [], {}), {7: None})
