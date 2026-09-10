"""Backend 'owe': Protobuf-Codec, WebSocket-Client gegen einen Fake-Daemon,
Monitor-Zuordnung und die Backend-Umschaltung - ohne waywallen, Plasma oder
systemd anzufassen."""
import base64
import hashlib
import json
import pathlib
import socket
import struct
import tempfile
import threading
import unittest
from _load import load


def ws_accept(key):
    return base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()


class FakeDaemon(threading.Thread):
    """Minimaler WebSocket-Server, der Request-Frames dekodiert und je Anfrage
    ein ServerFrame{response{request_id,status,payload}} zurueckschickt."""

    def __init__(self, m, handler):
        super().__init__(daemon=True)
        self.m, self.handler = m, handler
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.seen = []

    def run(self):
        conn, _ = self.sock.accept()
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += conn.recv(4096)
        key = next(l.split(":", 1)[1].strip() for l in buf.decode().split("\r\n") if l.lower().startswith("sec-websocket-key"))
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {ws_accept(key)}\r\n\r\n").encode())
        buf = buf.split(b"\r\n\r\n", 1)[1]

        def read(n):
            nonlocal buf
            while len(buf) < n:
                chunk = conn.recv(65536)
                if not chunk:
                    raise ConnectionError
                buf += chunk
            out, buf = buf[:n], buf[n:]
            return out
        try:
            while True:
                b0, b1 = read(2)
                ln = b1 & 0x7F
                if ln == 126:
                    ln = struct.unpack(">H", read(2))[0]
                elif ln == 127:
                    ln = struct.unpack(">Q", read(8))[0]
                mask = read(4)
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(read(ln)))
                if b0 & 0x0F == 8:
                    return
                if b0 & 0x0F != 2:          # Pong o.ae. ist kein Request
                    continue
                req = self.m.pb_decode(data)
                self.seen.append(req)
                rid = self.m.pb_int(req, 1)
                fno = next(f for f, _wt, _v in req if f != 1)
                status, payload = self.handler(fno, self.m.pb_msg(req, fno) or [])
                resp = [(1, 0, rid), (2, 0, status), (fno, 2, payload)]
                if status != 1:
                    resp.append((3, 2, "kaputt"))
                frame = self.m.pb_encode([(1, 2, self.m.pb_encode(resp))])
                # Antwort absichtlich in zwei Fragmenten, plus ein Ping davor
                conn.sendall(bytes([0x89, 0x02]) + b"hi")
                half = len(frame) // 2
                conn.sendall(bytes([0x02, half]) + frame[:half])
                conn.sendall(bytes([0x80, len(frame) - half]) + frame[half:])
        except (ConnectionError, OSError):
            return
        finally:
            conn.close()


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.m = load("we-wallpaper", CONF=pathlib.Path(tempfile.mkdtemp()) / "c.json")

    def test_roundtrip_all_wire_types(self):
        m = self.m
        inner = [(1, 0, 300), (2, 2, "Blue Nebula"), (3, 2, b"\x00\xff")]
        fields = [(1, 0, 1), (5, 2, inner), (7, 1, b"\x01" * 8), (9, 5, b"\x02" * 4), (2 ** 20, 0, 2 ** 40)]
        enc = m.pb_encode(fields)
        dec = m.pb_decode(enc)
        self.assertEqual(m.pb_int(dec, 1), 1)
        self.assertEqual(m.pb_int(dec, 2 ** 20), 2 ** 40)
        self.assertEqual(m.pb_get(dec, 7), b"\x01" * 8)
        nested = m.pb_msg(dec, 5)
        self.assertEqual(m.pb_int(nested, 1), 300)
        self.assertEqual(m.pb_str(nested, 2), "Blue Nebula")
        self.assertEqual(m.pb_get(nested, 3), b"\x00\xff")
        self.assertEqual(m.pb_encode(dec), enc)          # unbekannte Felder ueberleben

    def test_set_replaces_and_keeps_rest(self):
        m = self.m
        fields = [(1, 0, 1), (16, 2, b"x"), (16, 2, b"y"), (20, 0, 5)]
        out = m.pb_set(fields, 16, 2, b"z")
        self.assertEqual(m.pb_all(out, 16), [b"z"])
        self.assertEqual(m.pb_int(out, 20), 5)

    def test_bool_and_missing(self):
        m = self.m
        dec = m.pb_decode(m.pb_encode([(1, 0, True)]))
        self.assertEqual(m.pb_int(dec, 1), 1)
        self.assertEqual(m.pb_int(dec, 2, -1), -1)
        self.assertEqual(m.pb_str(dec, 2, "leer"), "leer")
        self.assertIsNone(m.pb_msg(dec, 3))


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.m = load("we-wallpaper", CONF=pathlib.Path(tempfile.mkdtemp()) / "c.json")

    def test_call_roundtrip_with_fragments_and_ping(self):
        m = self.m

        def handler(fno, payload):
            if fno == m.OWE_REQ["autostart_get"]:
                return 1, m.pb_encode([(1, 0, 1)])
            if fno == m.OWE_REQ["wallpaper_list"]:
                self.assertEqual(m.pb_int(payload, 3), 200)      # page_size
                entries = [m.pb_encode([(1, 2, "25"), (2, 2, "Blue Nebula"), (3, 2, "scene"),
                                        (4, 2, "/ws/431960/2816552071/scene.pkg"), (15, 2, "2816552071")]),
                           m.pb_encode([(1, 2, "1"), (2, 2, "Arsenal"), (3, 2, "scene"),
                                        (4, 2, "/we/projects/defaultprojects/arsenal/scene.json")])]
                return 1, m.pb_encode([(1, 2, e) for e in entries] + [(2, 0, 2)])
            return 2, b""
        srv = FakeDaemon(m, handler)
        srv.start()
        ws = m.OweSocket(srv.port, timeout=5)
        r = ws.call("autostart_get")
        self.assertEqual(m.pb_int(r, 1), 1)
        cat = m.owe_catalog(ws)
        self.assertEqual([e["name"] for e in cat], ["Blue Nebula", "Arsenal"])
        self.assertEqual(m.owe_find(cat, "2816552071")["id"], "25")
        self.assertEqual(m.owe_find(cat, 2816552071)["id"], "25")
        self.assertIsNone(m.owe_find(cat, "999"))
        with self.assertRaises(RuntimeError) as cm:
            ws.call("wallpaper_scan")
        self.assertIn("kaputt", str(cm.exception))
        ws.close()
        self.assertEqual(m.pb_int(srv.seen[0], 1), 1)          # request_id zaehlt hoch
        self.assertEqual(m.pb_int(srv.seen[1], 1), 2)

    def test_pause_and_apply_payloads(self):
        m = self.m
        calls = []

        def handler(fno, payload):
            calls.append((fno, payload))
            if fno == m.OWE_REQ["display_list"]:
                return 1, m.pb_encode([(1, 2, m.pb_encode([(1, 0, 7), (2, 2, "qml-display"), (3, 0, 5120), (4, 0, 1440)]))])
            if fno == m.OWE_REQ["wallpaper_list"]:
                return 1, m.pb_encode([(1, 2, m.pb_encode([(1, 2, "25"), (2, 2, "Blue Nebula"), (15, 2, "2816552071")])), (2, 0, 1)])
            return 1, b""
        srv = FakeDaemon(m, handler)
        srv.start()
        ws = m.OweSocket(srv.port, timeout=5)
        m.owe_pause(True, ws)
        self.assertEqual(m.pb_int(calls[-1][1], 1), 1)
        m.owe_pause(False, ws)
        self.assertEqual(m.pb_int(calls[-1][1], 1), 0)
        self.assertEqual(m.owe_displays(ws), [{"id": 7, "name": "qml-display", "w": 5120, "h": 1440}])
        done = m.owe_apply_plan(ws, {7: "2816552071"})
        self.assertEqual(done, [("2816552071", "Blue Nebula", [7])])
        fno, payload = calls[-1]
        self.assertEqual(fno, m.OWE_REQ["wallpaper_apply"])
        self.assertEqual(m.pb_str(payload, 1), "25")
        self.assertEqual(m.pb_int(m.pb_decode(m.pb_get(payload, 5)), 1), 7)
        ws.close()

    def test_policy_sync_keeps_other_settings(self):
        m = self.m
        seen = {}
        other = m.pb_encode([(11, 2, "shuffle"), (16, 2, m.pb_encode([(13, 0, 3), (16, 0, 250)])), (25, 0, 1), (99, 2, b"zukunft")])

        def handler(fno, payload):
            if fno == m.OWE_REQ["settings_get"]:
                return 1, m.pb_encode([(1, 2, other), (2, 2, m.pb_encode([(1, 2, "plug")]))])
            if fno == m.OWE_REQ["settings_set"]:
                seen["set"] = payload
                return 1, b""
            return 2, b""
        srv = FakeDaemon(m, handler)
        srv.start()
        ws = m.OweSocket(srv.port, timeout=5)
        m.owe_sync_policy({"pause_on_fullscreen": True, "pause_on_maximized": False, "pause_on_lock": True}, ws)
        ws.close()
        g = m.pb_msg(seen["set"], 1)
        ar = m.pb_msg(g, 16)
        self.assertEqual(m.pb_int(ar, 13), m.OWE_ACTION["pause"])
        self.assertEqual(m.pb_int(ar, 12), m.OWE_ACTION["none"])
        self.assertEqual(m.pb_int(ar, 14), m.OWE_ACTION["pause"])
        self.assertEqual(m.pb_int(ar, 16), 250)                    # resume_delay bleibt
        self.assertEqual(m.pb_str(g, 11), "shuffle")               # andere Felder bleiben
        self.assertEqual(m.pb_get(g, 99), b"zukunft")
        self.assertEqual(len(m.pb_all(seen["set"], 2)), 1)         # Plugin-Map unveraendert


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.m = load("we-wallpaper", CONF=pathlib.Path(tempfile.mkdtemp()) / "c.json")

    def test_match_by_resolution(self):
        cfg = {"screens": {"DP-1": {"id": "100"}, "HDMI-A-1": {"id": "200"}}}
        displays = [{"id": 1, "w": 3840, "h": 2160}, {"id": 2, "w": 5120, "h": 1440}]
        sizes = {"DP-1": (5120, 1440), "HDMI-A-1": (3840, 2160)}
        self.assertEqual(self.m.owe_plan(cfg, displays, sizes), {2: "100", 1: "200"})

    def test_unmatched_gets_first_wallpaper(self):
        cfg = {"screens": {"DP-1": {"id": "100"}}}
        displays = [{"id": 1, "w": 1920, "h": 1080}, {"id": 2, "w": 5120, "h": 1440}]
        self.assertEqual(self.m.owe_plan(cfg, displays, {"DP-1": (5120, 1440)}), {2: "100", 1: "100"})
        self.assertEqual(self.m.owe_plan(cfg, displays, {}), {1: "100", 2: "100"})

    def test_nothing_assigned(self):
        self.assertEqual(self.m.owe_plan({"screens": {"DP-1": {"id": ""}}}, [{"id": 1, "w": 1, "h": 1}], {}), {})


class BackendOweTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.m = load("we-wallpaper", CONF=self.tmp / "c.json", STATE=self.tmp / "state",
                      KDE_PLUGIN_ROOTS=[self.tmp / "roots"])
        self.calls = []
        self.m.systemctl = lambda *a, **k: self.calls.append(("systemctl",) + a) or None
        self.m.service_enabled = lambda: True
        self.m.service_installed = lambda: True
        self.m.do_stop = lambda quiet=False: self.calls.append(("stop",))
        self.m.plasma_script = lambda js: self.calls.append(("plasma", js)) or "ok"
        self.m.owe_start_daemon = lambda wait=30: True
        self.m.owe_leave = lambda: self.calls.append(("leave",))
        self.m.build_native_restore_script = lambda: "restore"
        self.m.do_status = lambda: 0

    def test_refuses_when_missing(self):
        self.m.owe_missing = lambda: [("waywallen", "flatpak install ...")]
        self.assertEqual(self.m.do_backend("owe"), 2)
        self.assertNotIn(("stop",), self.calls)

    def test_switch_to_owe_and_back(self):
        m = self.m
        m.owe_missing = lambda: []
        m.save_conf({"screens": {"DP-1": {"id": "2816552071"}}, "pause_on_fullscreen": True})
        api = []

        class FakeWs:
            def call(self, name, payload=b""):
                api.append((name, payload))
                return []

            def close(self):
                pass
        m.owe_connect = lambda: FakeWs()
        m.owe_sync_policy = lambda cfg, ws=None: api.append(("policy", cfg.get("pause_on_fullscreen")))
        m.owe_apply = lambda cfg, ws=None: [("2816552071", "Blue Nebula", [1])]
        m.time.sleep = lambda s: None
        self.assertEqual(m.do_backend("owe"), 0)
        self.assertEqual(m.load_conf()["backend"], "owe")
        self.assertIn(("systemctl", "disable", "--now", m.UNIT_RENDER), self.calls)
        self.assertIn(("systemctl", "enable", "--now", m.UNIT_WATCH), self.calls)
        self.assertTrue(any(m.OWE_KDE_ID in js for k, js in [c for c in self.calls if c[0] == "plasma"]))
        self.assertEqual(api[0][0], "autostart_set")
        self.assertEqual(m.pb_int(m.pb_decode(api[0][1]), 1), 1)
        self.assertIn(("policy", True), api)
        # zurueck: Daemon abraeumen, eigener Renderer wieder an
        self.assertEqual(m.do_backend("native"), 0)
        self.assertIn(("leave",), self.calls)
        self.assertEqual(m.load_conf()["backend"], "native")
        self.assertIn(("systemctl", "enable", "--now", m.UNIT_RENDER, m.UNIT_WATCH), self.calls)


class WatcherOweTests(unittest.TestCase):
    def test_owe_reason_prefers_global(self):
        w = load("we-wallpaper-watch")
        self.assertEqual(w.owe_reason(["Sperre"], {"DP-1": ["Vollbild"]}), "Sperre")
        self.assertEqual(w.owe_reason([], {"DP-1": [], "HDMI-A-1": ["Vollbild"]}), "Vollbild")
        self.assertIsNone(w.owe_reason([], {"DP-1": []}))


if __name__ == "__main__":
    unittest.main()
