"""Local web app: a small JSON API plus static files, standard library only.

The server listens on 127.0.0.1 only and works offline once data is cached.
One browser tab = one session. All times in the API are epoch milliseconds (UTC).
"""
from __future__ import annotations

import json
import math
import tempfile
import threading
import traceback
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from fxtm.analytics import EquityRecorder, performance, trades_frame
from fxtm.broker import AccountConfig, Broker, BrokerError, fixed_rates, replay_rates, split_symbol
from fxtm.compare import widen_spread
from fxtm.history import config_meta, save_run
from fxtm.importer import ImportedProvider, import_file, list_datasets
from fxtm.providers import DukascopyProvider
from fxtm.replay import Replay
from fxtm.session import Session
from fxtm.store import TickStore, default_data_dir
from fxtm.ticks import FxtmError, normalize_symbol, to_utc

MAX_DAYS = 7
MAX_CANDLES = 3000
MAX_UPLOAD_BYTES = 1 << 30
WEB_DIR = Path(__file__).parent / "web"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def _ms(value) -> int:
    return int(pd.Timestamp(value).value // 1_000_000)


def _clean(obj):
    """Make nested data JSON-safe (timestamps -> ms, timedeltas -> seconds, inf/nan -> None)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return _ms(obj)
    if isinstance(obj, (pd.Timedelta, timedelta)):
        return pd.Timedelta(obj).total_seconds()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if obj is pd.NaT:
        return None
    return obj


def _opt_float(value):
    return None if value in (None, "") else float(value)


class App:
    def __init__(self, data_dir=None, store: TickStore | None = None):
        self.data_dir = Path(data_dir or default_data_dir())
        self.store = store or TickStore(
            self.data_dir, DukascopyProvider(cache_dir=self.data_dir / "raw" / "dukascopy"))
        self.import_store = TickStore(self.data_dir, ImportedProvider(self.data_dir))
        self.lock = threading.RLock()
        self.status = {"state": "idle", "message": ""}
        self.params: dict | None = None
        self.ctx: dict | None = None
        self._tick_cache: dict = {}

    # ---- session setup -----------------------------------------------------
    def _load(self, store: TickStore, symbol: str, start, end, label: str):
        def progress(day, n):
            self.status = {"state": "loading", "message": f"{label} {day}: {n:,} ticks"}

        def hour_progress(done, total, hour):
            self.status = {"state": "loading", "message": f"{label} {hour:%Y-%m-%d %H}h ({done}/{total})"}

        if hasattr(store.provider, "progress"):
            store.provider.progress = hour_progress
        return store.load(symbol, start, end, progress=progress)

    def start(self, params: dict) -> dict:
        symbol = normalize_symbol(params["symbol"])
        base, quote = split_symbol(symbol)
        start, end = to_utc(params["start"]), to_utc(params["end"])
        if end <= start:
            raise ValueError("The end must be after the start.")
        if end - start > timedelta(days=MAX_DAYS):
            raise ValueError(f"Choose a period of at most {MAX_DAYS} days.")
        currency = str(params.get("currency") or "JPY").upper()
        parsed = {
            "symbol": symbol, "start": start, "end": end, "currency": currency,
            "balance": float(params.get("balance") or 1_000_000),
            "leverage": float(params.get("leverage") or 25),
            "stop_out_pct": float(params.get("stop_out_pct") or 100),
            "slippage_pips": float(params.get("slippage_pips") or 0),
            "extra_spread_pips": float(params.get("extra_spread_pips") or 0),
            "latency_s": float(params.get("latency_s") or 0),
            "fixed_rate": _opt_float(params.get("fixed_rate")),
        }
        if parsed["balance"] <= 0 or parsed["leverage"] < 1:
            raise ValueError("Balance must be positive and leverage at least 1.")
        use_imported = bool(params.get("use_imported"))
        store = self.import_store if use_imported else self.store
        parsed["source"] = "imported" if use_imported else self.store.provider.name
        self.status = {"state": "loading", "message": f"Loading {symbol}..."}
        try:
            ticks = self._load(store, symbol, start, end, symbol)
            if ticks.empty:
                if use_imported:
                    raise FxtmError(
                        f"None of your imported files for {symbol} covers this period. "
                        "Import a file for it, or untick 'Use my imported data'.")
                raise FxtmError(
                    "No ticks in this period. It may be a weekend or holiday, or the "
                    "data source has no data for this pair and date.")
            aux_symbol, aux_ticks = None, None
            if quote != currency and parsed["fixed_rate"] is None:
                for candidate in (f"{quote}{currency}", f"{currency}{quote}"):
                    found = self._load(store, candidate, start - timedelta(days=1), end, candidate)
                    if not found.empty:
                        aux_symbol, aux_ticks = candidate, found
                        break
                if aux_symbol is None:
                    raise FxtmError(
                        f"No data to convert {quote} to {currency}"
                        + (" in your imported files" if use_imported else "")
                        + f". Enter a fixed conversion rate ({currency} per 1 {quote}) "
                        "under 'Trading conditions' or use another account currency.")
            self.params = parsed
            self._source = {"ticks": ticks, "aux_symbol": aux_symbol, "aux_ticks": aux_ticks}
            with self.lock:
                self._build()
        except Exception:
            self.status = {"state": "idle", "message": ""}
            raise
        self.status = {"state": "ready", "message": ""}
        return self.state()

    def _build(self) -> None:
        p, src = self.params, self._source
        symbol = p["symbol"]
        quote = split_symbol(symbol)[1]
        digits = 3 if quote == "JPY" else 5
        pip = 0.01 if quote == "JPY" else 0.0001
        ticks = widen_spread(src["ticks"], p["extra_spread_pips"] * pip)
        replay = Replay(ticks)
        aux = []
        if p["fixed_rate"] is not None:
            rates = fixed_rates(p["currency"], {quote: p["fixed_rate"]})
        elif src["aux_symbol"]:
            aux_replay = Replay(src["aux_ticks"])
            aux = [aux_replay]
            rates = replay_rates(p["currency"], {src["aux_symbol"]: aux_replay})
        else:
            rates = fixed_rates(p["currency"], {})
        config = AccountConfig(
            currency=p["currency"], initial_balance=p["balance"], leverage=p["leverage"],
            stop_out_level=p["stop_out_pct"] / 100, slippage=p["slippage_pips"] * pip,
            latency=timedelta(seconds=p["latency_s"]))
        broker = Broker(config, rates)
        recorder = EquityRecorder(timedelta(seconds=60))
        session = Session(replay, broker, symbol, recorder, aux=aux)
        try:
            broker.margin_required(symbol, 1)
        except BrokerError as exc:
            raise FxtmError(f"{exc}. Enter a fixed conversion rate instead.") from exc
        self.ctx = {"replay": replay, "broker": broker, "recorder": recorder, "session": session,
                    "symbol": symbol, "digits": digits, "pip": pip, "quote": quote,
                    "events": [], "aux_symbol": src["aux_symbol"]}

    def restart(self) -> dict:
        with self.lock:
            self._need()
            self._build()
        return self.state()

    def _need(self) -> dict:
        if self.ctx is None:
            raise FxtmError("No session is running. Start one first.")
        return self.ctx

    # ---- state -------------------------------------------------------------
    def _candles(self, tf: str, since_ms) -> dict:
        frame = self.ctx["replay"].candles(tf)
        if frame.empty:
            return {"tf": tf, "full": since_ms is None, "data": []}
        times = frame["time"].dt.tz_localize(None).to_numpy(dtype="datetime64[ms]").astype("int64")
        if since_ms is not None:
            keep = times >= since_ms
            frame, times = frame[keep], times[keep]
        else:
            frame, times = frame.tail(MAX_CANDLES), times[-MAX_CANDLES:]
        rows = [[int(t), o, h, l, c, int(v)] for t, o, h, l, c, v in
                zip(times, frame["open"], frame["high"], frame["low"], frame["close"], frame["volume"])]
        return {"tf": tf, "full": since_ms is None, "data": rows}

    def state(self, tf: str = "1m", since_ms=None, events=()) -> dict:
        with self.lock:
            c = self._need()
            broker, replay = c["broker"], c["replay"]
            quote = replay.quote()
            summary = broker.summary()
            positions = [{
                "id": p.id, "side": p.side, "units": p.units, "open_price": p.open_price,
                "open_time": p.open_time, "sl": p.sl, "tp": p.tp, "pnl": broker.unrealized(p),
            } for p in broker.positions.values()]
            orders = [{
                "id": o.id, "side": o.side, "kind": o.kind, "units": o.units, "price": o.price,
                "sl": o.sl, "tp": o.tp,
            } for o in broker.pending_orders]
            trades = [{
                "id": t.id, "side": t.side, "units": t.units, "open_time": t.open_time,
                "open_price": t.open_price, "close_time": t.close_time, "close_price": t.close_price,
                "reason": t.reason, "pnl": t.pnl,
            } for t in broker.trades]
            level = summary["margin_level"]
            payload = {
                "ready": True, "symbol": c["symbol"], "digits": c["digits"], "pip": c["pip"],
                "currency": broker.config.currency, "quote_currency": c["quote"],
                "leverage": broker.config.leverage, "conversion_pair": c["aux_symbol"],
                "now": replay.now, "start": replay.start, "end": replay.end, "at_end": replay.at_end,
                "quote": None if quote is None else {"bid": quote[0], "ask": quote[1]},
                "account": {**summary, "margin_level": None if math.isinf(level) else level,
                            "floating": summary["equity"] - summary["balance"],
                            "initial": broker.config.initial_balance},
                "margin_per_unit": broker.margin_required(c["symbol"], 1),
                "positions": positions, "orders": orders, "trades": trades,
                "events": [self._event(e) for e in events],
                "candles": self._candles(tf, since_ms),
            }
        return _clean(payload)

    @staticmethod
    def _event(e) -> dict:
        return {"time": e.time, "kind": e.kind, "symbol": e.symbol, "price": e.price,
                "units": e.units, "ref": e.ref, "note": e.note}

    def _act(self, fn, tf, since_ms):
        """Run a state-changing action, record equity, return the new state with its events."""
        with self.lock:
            c = self._need()
            broker = c["broker"]
            before = len(broker.events)
            fn(c)
            c["recorder"].observe(broker, c["replay"].now, force=len(broker.events) > before)
            events = broker.events[before:]
        return self.state(tf, since_ms, events)

    # ---- actions -------------------------------------------------------------
    def advance(self, body: dict) -> dict:
        wall, speed = float(body.get("wall_seconds", 0)), float(body.get("speed", 1))
        if wall < 0 or speed <= 0:
            raise ValueError("wall_seconds must be >= 0 and speed > 0")
        return self._act(lambda c: c["session"].advance_wall(min(wall, 1.0), speed),
                         body.get("tf", "1m"), body.get("since"))

    def step(self, body: dict) -> dict:
        def run(c):
            if body.get("mode") == "tick":
                c["session"].next_tick()
            else:
                c["session"].advance(float(body.get("seconds", 1)))
        return self._act(run, body.get("tf", "1m"), body.get("since"))

    def jump(self, body: dict) -> dict:
        return self._act(lambda c: c["session"].run_until(to_utc(body["to"])),
                         body.get("tf", "1m"), body.get("since"))

    def order(self, body: dict) -> dict:
        def run(c):
            c["broker"].place_order(
                c["symbol"], body["side"], float(body["units"]), body.get("kind", "market"),
                _opt_float(body.get("price")), _opt_float(body.get("sl")), _opt_float(body.get("tp")))
        return self._act(run, body.get("tf", "1m"), body.get("since"))

    def close(self, body: dict) -> dict:
        def run(c):
            if body.get("all"):
                for pid in list(c["broker"].positions):
                    c["broker"].close(pid)
            else:
                c["broker"].close(int(body["id"]), _opt_float(body.get("units")))
        return self._act(run, body.get("tf", "1m"), body.get("since"))

    def modify(self, body: dict) -> dict:
        def run(c):
            kwargs = {k: _opt_float(body[k]) for k in ("sl", "tp") if k in body}
            c["broker"].modify(int(body["id"]), **kwargs)
        return self._act(run, body.get("tf", "1m"), body.get("since"))

    def cancel(self, body: dict) -> dict:
        return self._act(lambda c: c["broker"].cancel(int(body["id"])),
                         body.get("tf", "1m"), body.get("since"))

    # ---- own data files ------------------------------------------------------
    def datasets(self) -> list:
        return _clean([{**d, "ticks": d["ticks"]} for d in list_datasets(self.data_dir)])

    def import_upload(self, source_path: str, symbol: str, timezone: str) -> dict:
        info = import_file(self.data_dir, symbol, source_path, timezone)
        return _clean(info)

    # ---- results -------------------------------------------------------------
    def report(self) -> dict:
        with self.lock:
            c = self._need()
            c["recorder"].observe(c["broker"], c["replay"].now, force=True)
            perf = performance(c["broker"], c["recorder"])
            curve = c["recorder"].frame()
        if len(curve) > 600:
            curve = curve.iloc[np.linspace(0, len(curve) - 1, 600).astype(int)]
        perf["equity_curve"] = [[r.time, r.equity, r.balance] for r in curve.itertuples(index=False)]
        return _clean(perf)

    def save(self) -> dict:
        with self.lock:
            c = self._need()
            p = self.params
            meta = config_meta(
                c["broker"], provider=p["source"], symbol=c["symbol"],
                start=p["start"].isoformat(), end=p["end"].isoformat(),
                extra_spread_pips=p["extra_spread_pips"], conversion_pair=c["aux_symbol"],
                fixed_rate=p["fixed_rate"], replay_position=c["replay"].now.isoformat())
            path = self.data_dir / "runs.sqlite"
            run_id = save_run(path, c["broker"], c["recorder"], meta)
        return {"run_id": run_id, "path": str(path)}


def make_handler(app: App, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "fxtm"

        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._send(code, json.dumps(data).encode(), "application/json")

        def _host_ok(self) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin.split("://", 1)[-1] in allowed_hosts

        def _guard(self, fn) -> None:
            if not self._host_ok():
                return self._json(403, {"error": "Forbidden"})
            try:
                self._json(200, fn())
            except (FxtmError, ValueError, KeyError, TypeError) as exc:
                message = f"Missing field: {exc}" if isinstance(exc, KeyError) else str(exc)
                self._json(400, {"error": message})
            except Exception:  # noqa: BLE001 - report instead of crashing the thread
                traceback.print_exc()
                self._json(500, {"error": "Internal error. See the terminal for details."})

        def _upload(self, query) -> dict:
            """Receive a CSV as the raw request body, import it, and delete the temporary copy."""
            symbol = (query.get("symbol") or [""])[0]
            timezone = (query.get("timezone") or ["UTC"])[0]
            length = int(self.headers.get("Content-Length") or 0)
            if not symbol:
                raise ValueError("Enter the currency pair of the file first.")
            if length <= 0:
                raise ValueError("The file is empty.")
            if length > MAX_UPLOAD_BYTES:
                raise ValueError("The file is larger than 1 GB. Split it by month and import the parts.")
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "upload.csv"
                with open(target, "wb") as out:
                    remaining = length
                    while remaining > 0:
                        chunk = self.rfile.read(min(1 << 20, remaining))
                        if not chunk:
                            break
                        out.write(chunk)
                        remaining -= len(chunk)
                return app.import_upload(str(target), symbol, timezone)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in STATIC:
                if not self._host_ok():
                    return self._json(403, {"error": "Forbidden"})
                name, ctype = STATIC[url.path]
                return self._send(200, (WEB_DIR / name).read_bytes(), ctype)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            since = int(query["since"]) if query.get("since") else None
            if url.path == "/api/status":
                return self._guard(lambda: {**app.status, "ready": app.ctx is not None})
            if url.path == "/api/state":
                return self._guard(lambda: app.state(query.get("tf", "1m"), since))
            if url.path == "/api/report":
                return self._guard(app.report)
            if url.path == "/api/datasets":
                return self._guard(lambda: {"datasets": app.datasets()})
            self._json(404, {"error": "Not found"})

        def do_POST(self):
            url = urlparse(self.path)
            routes = {
                "/api/start": app.start, "/api/restart": lambda body: app.restart(),
                "/api/advance": app.advance, "/api/step": app.step, "/api/jump": app.jump,
                "/api/order": app.order, "/api/close": app.close, "/api/modify": app.modify,
                "/api/cancel": app.cancel, "/api/save": lambda body: app.save(),
            }
            if url.path == "/api/import":
                return self._guard(lambda: self._upload(parse_qs(url.query)))
            handler = routes.get(url.path)
            if handler is None:
                return self._json(404, {"error": "Not found"})

            def run():
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                return handler(body)
            self._guard(run)

    return Handler


def serve(data_dir=None, port: int = 8765, open_browser: bool = True, store: TickStore | None = None) -> None:
    app = App(data_dir, store)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    except OSError as exc:
        raise FxtmError(f"Cannot listen on port {port} ({exc}). Try another one: fxtm serve --port {port + 1}") from exc
    url = f"http://127.0.0.1:{port}/"
    print(f"FX Time Machine is running at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
