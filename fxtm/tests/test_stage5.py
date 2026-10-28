import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import pandas as pd

from fxtm.analytics import EquityRecorder, format_report, max_drawdown, performance, trade_stats, trades_frame
from fxtm.broker import AccountConfig, Broker, fixed_rates
from fxtm.compare import ScriptedOrder, compare_scenarios, run_scenario
from fxtm.history import config_meta, delete_run, list_runs, load_equity, load_trades, save_run
from fxtm.replay import Replay
from fxtm.session import Session

from helpers import ticks_from, utc

T0 = utc(2024, 3, 4, 10, 0, 0)


def at(seconds):
    return T0 + timedelta(seconds=seconds)


def price_path():
    """Mid price rises, then falls: 1.1000 -> 1.1100 (t=300) -> 1.0900 (t=600)."""
    rows = []
    for s in range(0, 601, 30):
        mid = 1.1000 + 0.0100 * (s / 300) if s <= 300 else 1.1100 - 0.0200 * ((s - 300) / 300)
        rows.append((at(s), round(mid - 0.0001, 5), round(mid + 0.0001, 5)))
    return ticks_from(rows)


class DrawdownTests(unittest.TestCase):
    def test_max_drawdown(self):
        idx = pd.date_range("2024-01-01", periods=6, freq="h", tz="UTC")
        dd = max_drawdown(pd.Series([100, 120, 90, 110, 80, 130], index=idx, dtype=float))
        self.assertEqual(dd["abs"], 40.0)
        self.assertAlmostEqual(dd["pct"], 40 / 120 * 100)
        self.assertEqual((dd["peak"], dd["trough"]), (120.0, 80.0))
        self.assertEqual((dd["peak_time"], dd["trough_time"]), (idx[1], idx[4]))

    def test_no_drawdown_when_always_rising(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
        self.assertEqual(max_drawdown(pd.Series([1.0, 2.0, 3.0], index=idx))["abs"], 0.0)

    def test_empty(self):
        self.assertEqual(max_drawdown(pd.Series(dtype="float64"))["abs"], 0.0)


class StatsTests(unittest.TestCase):
    def make_broker(self):
        b = Broker(AccountConfig(currency="USD", initial_balance=10_000, leverage=10), fixed_rates("USD", {}))
        b.on_tick("EURUSD", at(0), 1.1000, 1.1002)
        for exit_bid in (1.1012, 1.0992, 1.1022):  # +10, -10, +20 (approximately, before the spread)
            pos_id = b.market("EURUSD", "buy", 10_000).position_id
            b.on_tick("EURUSD", at(1), exit_bid, exit_bid + 0.0002)
            b.close(pos_id)
            b.on_tick("EURUSD", at(2), 1.1000, 1.1002)
        return b

    def test_stats(self):
        st = trade_stats(trades_frame(self.make_broker()))
        self.assertEqual((st["trades"], st["wins"], st["losses"]), (3, 2, 1))
        self.assertAlmostEqual(st["win_rate"], 2 / 3)
        self.assertAlmostEqual(st["total_pnl"], 10 - 10 + 20)
        self.assertAlmostEqual(st["profit_factor"], 3.0)
        self.assertAlmostEqual(st["best"], 20.0)
        self.assertAlmostEqual(st["worst"], -10.0)

    def test_no_trades(self):
        st = trade_stats(trades_frame(Broker(AccountConfig(currency="USD"), fixed_rates("USD", {}))))
        self.assertEqual(st["trades"], 0)
        self.assertIsNone(st["win_rate"])

    def test_report_text(self):
        text = format_report(performance(self.make_broker()))
        self.assertIn("Trades: 3", text)
        self.assertIn("Profit factor: 3.00", text)


class RecorderTests(unittest.TestCase):
    def run_session(self, interval):
        ticks = ticks_from([(at(s), 1.1000, 1.1002) for s in range(0, 301, 10)])
        broker = Broker(AccountConfig(currency="USD", initial_balance=10_000, leverage=10), fixed_rates("USD", {}))
        recorder = EquityRecorder(interval)
        session = Session(Replay(ticks), broker, "EURUSD", recorder)
        session.advance(300)
        return recorder.frame()

    def test_interval_sampling(self):
        frame = self.run_session(timedelta(seconds=60))
        self.assertEqual(len(frame), 6)  # t = 0, 60, ..., 300

    def test_every_tick(self):
        self.assertEqual(len(self.run_session(timedelta(0))), 31)

    def test_events_force_a_sample(self):
        ticks = ticks_from([(at(0), 1.1000, 1.1002), (at(5), 1.1000, 1.1002), (at(10), 1.0900, 1.0902)])
        broker = Broker(AccountConfig(currency="USD", initial_balance=10_000, leverage=10), fixed_rates("USD", {}))
        recorder = EquityRecorder(timedelta(hours=1))
        session = Session(Replay(ticks), broker, "EURUSD", recorder)
        broker.market("EURUSD", "buy", 10_000, sl=1.0950)
        session.advance(10)  # the stop-loss fires on the last tick
        frame = recorder.frame()
        self.assertEqual(len(frame), 2)  # first tick + the forced sample at the event
        self.assertAlmostEqual(frame["balance"].iloc[-1], broker.balance)


class HistoryTests(unittest.TestCase):
    def test_roundtrip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "runs.sqlite"
        result = run_scenario(
            price_path(), "EURUSD",
            [ScriptedOrder(at(0), "buy", 10_000, close_at=at(300))],
            AccountConfig(currency="USD", initial_balance=10_000, leverage=10),
        )
        meta = config_meta(result.broker, provider="fake", symbol="EURUSD", note="test")
        run_id = save_run(db, result.broker, result.recorder, meta)
        trades = load_trades(db, run_id)
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades["pnl"].iloc[0], result.broker.trades[0].pnl)
        self.assertEqual(str(trades["open_time"].dt.tz), "UTC")
        self.assertEqual(len(load_equity(db, run_id)), len(result.recorder.frame()))
        runs = list_runs(db)
        self.assertEqual(runs["meta"].iloc[0]["provider"], "fake")
        self.assertEqual(runs["meta"].iloc[0]["account"]["leverage"], 10)
        delete_run(db, run_id)
        self.assertTrue(list_runs(db).empty)
        self.assertTrue(load_trades(db, run_id).empty)


class CompareTests(unittest.TestCase):
    orders = [ScriptedOrder(at(0), "buy", 10_000, close_at=at(300))]
    base = AccountConfig(currency="USD", initial_balance=10_000, leverage=10)

    def test_scripted_order_runs_end_to_end(self):
        result = run_scenario(price_path(), "EURUSD", self.orders, self.base)
        trade = result.broker.trades[0]
        self.assertEqual(trade.reason, "manual")
        self.assertAlmostEqual(trade.open_price, 1.1001)
        self.assertAlmostEqual(trade.close_price, 1.1099)
        self.assertAlmostEqual(result.broker.balance, 10_000 + (1.1099 - 1.1001) * 10_000)

    def test_spread_comparison(self):
        table = compare_scenarios(price_path(), "EURUSD", self.orders, self.base, {
            "tight": {}, "wide": {"extra_spread": 0.0004}})
        self.assertAlmostEqual(table.loc["tight", "total_pnl"] - table.loc["wide", "total_pnl"], 4.0)

    def test_leverage_comparison(self):
        big = [ScriptedOrder(at(0), "buy", 100_000, close_at=at(300))]
        table = compare_scenarios(price_path(), "EURUSD", big, self.base, {
            "10x": {"leverage": 10}, "100x": {"leverage": 100}})
        self.assertEqual((table.loc["10x", "trades"], table.loc["10x", "rejected"]), (0, 1))
        self.assertEqual((table.loc["100x", "trades"], table.loc["100x", "rejected"]), (1, 0))

    def test_stop_out_shows_up_in_the_table(self):
        # 100,000 units at 100x leverage on a small account: the fall to 1.0900 triggers a stop-out
        big = [ScriptedOrder(at(0), "buy", 100_000)]
        small = AccountConfig(currency="USD", initial_balance=1_500, leverage=10)
        table = compare_scenarios(price_path(), "EURUSD", big, small, {"100x": {"leverage": 100}})
        self.assertEqual(table.loc["100x", "stop_outs"], 1)
        self.assertGreater(table.loc["100x", "max_dd_pct"], 50)


if __name__ == "__main__":
    unittest.main()
