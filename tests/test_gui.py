import os, json, pathlib, tempfile, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["WE_LANG"] = "de"   # Tests pruefen die deutschen Quellstrings
from PySide6.QtWidgets import QApplication
from _load import load

_app = QApplication.instance() or QApplication([])


class LogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = pathlib.Path(tempfile.mkdtemp())
        cls.m = load("we-wallpaper-gui", CONF=tmp / "c.json", UISTATE=tmp / "ui.json",
                     CACHE=tmp / "cache")

    def test_conditions(self):
        v = {"n": 3, "mode": 1}
        for cond, want in [("n.value >= 1", True), ("n.value >= 4", False), ("n.value == 3", True),
                           ("mode.value != 1", False), ("n.value >= 2 && mode.value == 1", True),
                           ("n.value >= 9 || mode.value == 1", True), ("", True), ("garbage(", True)]:
            self.assertEqual(self.m.cond_ok(cond, v), want, cond)

    def test_color_roundtrip(self):
        c = self.m.col_to_qcolor("0.04706 0.27059 0.46275")
        self.assertEqual(c.name(), "#0c4576")
        self.assertEqual(self.m.col_to_qcolor(self.m.qcolor_to_we(c)).name(), "#0c4576")
        self.assertEqual(self.m.col_to_qcolor("nonsense").name(), "#ffffff")

    def test_translation_table(self):
        self.assertEqual(self.m._("Anwenden"), "Anwenden")
        m_en = load("we-wallpaper-gui", LANG="en", CONF=self.m.CONF, UISTATE=self.m.UISTATE, CACHE=self.m.CACHE)
        self.assertEqual(m_en._("Anwenden"), "Apply")
        self.assertEqual(m_en.nice_label("ui_browse_properties_scheme_color", "x"), "Scheme colour")
        self.assertEqual(m_en._("unbekannt"), "unbekannt", "unbekannte Strings fallen auf die Quelle zurueck")

    def test_nice_label(self):
        self.assertEqual(self.m.nice_label("ui_browse_properties_scheme_color", "x"), "Schemafarbe")
        self.assertEqual(self.m.nice_label("", "my_key"), "My Key")
        self.assertEqual(self.m.nice_label("Camera Shake", "k"), "Camera Shake")

    def test_ui_state_roundtrip(self):
        st = self.m.load_ui()
        st["thumb"] = 300; st["last_id"] = "42"
        self.m.save_ui(st)
        again = self.m.load_ui()
        self.assertEqual((again["thumb"], again["last_id"]), (300, "42"))
        self.assertEqual(again["sort"], 0)

    def test_property_editor_builds_all_types(self):
        schema = {
            "b": {"type": "bool", "value": True, "text": "B", "order": 1},
            "s": {"type": "slider", "min": 0, "max": 1, "step": 0.01, "fraction": True, "value": 0.5, "order": 2},
            "i": {"type": "slider", "min": 0, "max": 10, "value": 3, "order": 3},
            "c": {"type": "color", "value": "1 0 0", "order": 4},
            "k": {"type": "combo", "options": [{"label": "A", "value": "0"}, {"label": "B", "value": "1"}], "value": "1", "order": 5},
            "t": {"type": "textinput", "value": "hi", "order": 6},
            "g": {"type": "group", "text": "Group", "order": 0},
            "dep": {"type": "bool", "value": False, "condition": "b.value == 0", "order": 7},
        }
        changes = []
        ed = self.m.PropertyEditor(lambda k, v: changes.append((k, v)))
        ed.build(schema, {"t": "override"}, editable=True)
        self.assertEqual(len(ed.rows), 8)
        self.assertEqual(ed.values["t"], "override")
        self.assertEqual(changes, [], "kein Autofeuer beim Aufbau")
        self.assertFalse(ed.rows["dep"][1].isVisibleTo(ed.body), "Bedingung b==0 nicht erfuellt")
        ed.changed("b", "0")
        self.assertTrue(ed.rows["dep"][1].isVisibleTo(ed.body))
        self.assertEqual(changes, [("b", "0")])
        ed.build(schema, {}, editable=False)
        self.assertTrue(all(not w.isEnabled() for k, (_l, w, s) in ed.rows.items() if s.get("type") != "group"))


if __name__ == "__main__":
    unittest.main()
