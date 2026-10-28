import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import timedelta
from http.server import ThreadingHTTPServer

import numpy as np

from fxtm.store import TickStore
from fxtm.ticks import make_ticks
from fxtm.webapp import App, make_handler

from helpers import ns, utc


class SyntheticProvider:
    """A deterministic random walk, 2 ticks per second, for any pair."""
    name = "synthetic"

    def fetch_ticks(self, symbol, start, end):
        step = 2_000_000_000
        t0, t1 = ns(start), ns(end)
        times = np.arange(t0, t1, step, dtype="int64")
        rng = np.random.default_rng(abs(hash(symbol)) % 1000 if False else sum(map(ord, symbol)))
        base = {"EURUSD": 1.1000, "EURCHF": 1.2000, "USDJPY": 120.0, "CHFJPY": 125.0}.get(symbol, 1.0)
        walk = base + np.cumsum(rng.normal(0, base * 2e-6, len(times)))
        half = base * 1e-4 / 2
        return make_ticks(times, walk - half, walk + half, np.ones(len(times)), np.ones(len(times)))


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        store = TickStore(cls.tmp.name, SyntheticProvider(), now=lambda: utc(2030, 1, 1))
        cls.app = App(cls.tmp.name, store)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
        cls.port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass = make_handler(cls.app, cls.port)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def call(self, path, body=None, headers=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def start(self, **overrides):
        body = {"symbol": "EUR/USD", "start": "2024-03-04 10:00", "end": "2024-03-04 11:00",
                "currency": "USD", "balance": 10_000, "leverage": 10}
        body.update(overrides)
        return self.call("/api/start", body)

    def test_static_files_are_served(self):
        for path in ("/", "/app.js", "/style.css"):
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)

    def test_requires_a_session_first(self):
        fresh = App(self.tmp.name, self.app.store)
        with self.assertRaises(Exception):
            fresh.state()

    def test_full_flow(self):
        code, st = self.start()
        self.assertEqual(code, 200)
        self.assertEqual((st["symbol"], st["currency"], st["digits"]), ("EURUSD", "USD", 5))
        self.assertIsNotNone(st["quote"])
        self.assertEqual(len(st["candles"]["data"]), 1)

        code, st = self.call("/api/advance", {"wall_seconds": 1.0, "speed": 600, "tf": "1m", "since": None})
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(st["candles"]["data"]), 9)  # about ten minutes of candles
        since = st["candles"]["data"][-1][0]

        code, st = self.call("/api/order", {"side": "buy", "units": 1000, "kind": "market", "tf": "1m", "since": since})
        self.assertEqual(code, 200)
        self.assertEqual(len(st["positions"]), 1)
        self.assertEqual([e["kind"] for e in st["events"]], ["open"])
        self.assertFalse(st["candles"]["full"])

        pos_id = st["positions"][0]["id"]
        code, st = self.call("/api/modify", {"id": pos_id, "sl": st["quote"]["bid"] - 0.01})
        self.assertEqual(code, 200)
        self.assertIsNotNone(st["positions"][0]["sl"])

        code, st = self.call("/api/close", {"id": pos_id})
        self.assertEqual((code, len(st["trades"]), len(st["positions"])), (200, 1, 0))

        code, report = self.call("/api/report")
        self.assertEqual(code, 200)
        self.assertEqual(report["stats"]["trades"], 1)
        self.assertGreaterEqual(len(report["equity_curve"]), 2)

        code, saved = self.call("/api/save", {})
        self.assertEqual(code, 200)
        self.assertEqual(saved["run_id"], 1)

        code, st = self.call("/api/restart", {})
        self.assertEqual((code, len(st["trades"])), (200, 0))

    def test_rejected_and_invalid_requests(self):
        self.start()
        code, body = self.call("/api/order", {"side": "buy", "units": 10_000_000, "kind": "market"})
        self.assertEqual(code, 400)
        self.assertIn("margin", body["error"])
        code, body = self.call("/api/order", {"side": "buy", "kind": "market"})
        self.assertEqual(code, 400)
        code, body = self.start(start="2024-03-04", end="2024-03-20")
        self.assertEqual(code, 400)
        self.assertIn("7 days", body["error"])

    def test_conversion_pair_is_loaded_for_other_account_currencies(self):
        code, st = self.start(symbol="EUR/CHF", currency="JPY", balance=1_000_000, leverage=25)
        self.assertEqual(code, 200)
        self.assertEqual(st["conversion_pair"], "CHFJPY")
        code, st = self.call("/api/order", {"side": "buy", "units": 10_000, "kind": "market"})
        self.assertEqual(code, 200)
        self.assertGreater(st["account"]["used_margin"], 0)

    def test_fixed_rate_and_extra_spread(self):
        code, plain = self.start(symbol="EUR/CHF", currency="JPY", fixed_rate=150, extra_spread_pips=0)
        code, wide = self.start(symbol="EUR/CHF", currency="JPY", fixed_rate=150, extra_spread_pips=10)
        self.assertEqual(code, 200)
        spread = lambda s: s["quote"]["ask"] - s["quote"]["bid"]
        self.assertAlmostEqual(spread(wide) - spread(plain), 0.001, places=6)

    def test_other_hosts_and_origins_are_rejected(self):
        code, _ = self.call("/api/status", headers={"Host": "evil.example"})
        self.assertEqual(code, 403)
        code, _ = self.call("/api/restart", {}, headers={"Origin": "http://evil.example"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
