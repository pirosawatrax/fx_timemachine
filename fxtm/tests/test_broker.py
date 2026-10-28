import unittest
from datetime import timedelta

from fxtm.broker import AccountConfig, Broker, BrokerError, OrderError, fixed_rates
from fxtm.replay import Replay
from fxtm.session import Session

from helpers import ticks_from, utc

T0 = utc(2024, 3, 4, 10, 0, 0)


def at(seconds):
    return T0 + timedelta(seconds=seconds)


def make_broker(**overrides):
    cfg = AccountConfig(currency="USD", initial_balance=10_000, leverage=10, **overrides)
    broker = Broker(cfg, fixed_rates("USD", {}))
    broker.on_tick("EURUSD", at(0), 1.1000, 1.1002)
    return broker


class OrderAndPnlTests(unittest.TestCase):
    def test_buy_fills_at_ask_and_closes_at_bid(self):
        b = make_broker()
        pos = b.positions[b.market("EURUSD", "buy", 10_000).position_id]
        self.assertEqual(pos.open_price, 1.1002)
        b.on_tick("EURUSD", at(1), 1.1012, 1.1014)
        trade = b.close(pos.id)
        self.assertAlmostEqual(trade.pnl, 10.0)
        self.assertAlmostEqual(b.balance, 10_010.0)
        self.assertFalse(b.positions)

    def test_sell_fills_at_bid_and_closes_at_ask(self):
        b = make_broker()
        pos_id = b.market("EURUSD", "sell", 10_000).position_id
        self.assertEqual(b.positions[pos_id].open_price, 1.1000)
        b.on_tick("EURUSD", at(1), 1.0988, 1.0990)
        self.assertAlmostEqual(b.close(pos_id).pnl, 10.0)

    def test_margin_and_equity(self):
        b = make_broker()
        b.market("EURUSD", "buy", 10_000)
        self.assertAlmostEqual(b.used_margin(), 10_000 * 1.1001 / 10)
        self.assertAlmostEqual(b.equity(), 10_000 + (1.1000 - 1.1002) * 10_000)
        self.assertAlmostEqual(b.free_margin(), b.equity() - b.used_margin())

    def test_insufficient_margin_is_rejected(self):
        b = make_broker()
        with self.assertRaises(OrderError):
            b.market("EURUSD", "buy", 100_000)
        self.assertFalse(b.positions)
        self.assertFalse(b.all_orders)

    def test_partial_close(self):
        b = make_broker()
        pos_id = b.market("EURUSD", "buy", 10_000).position_id
        b.on_tick("EURUSD", at(1), 1.1012, 1.1014)
        trade = b.close(pos_id, 4_000)
        self.assertEqual(trade.units, 4_000)
        self.assertEqual(b.positions[pos_id].units, 6_000)

    def test_slippage_is_against_the_trader(self):
        b = make_broker(slippage=0.0002)
        pos_id = b.market("EURUSD", "buy", 1_000).position_id
        self.assertAlmostEqual(b.positions[pos_id].open_price, 1.1004)
        b.on_tick("EURUSD", at(1), 1.1100, 1.1102)
        self.assertAlmostEqual(b.close(pos_id).close_price, 1.1098)

    def test_validation(self):
        b = make_broker()
        with self.assertRaises(OrderError):
            b.market("EURUSD", "buy", 1_000, sl=1.2000)  # SL above entry
        with self.assertRaises(OrderError):
            b.market("EURUSD", "sell", 1_000, tp=1.2000)  # TP above entry of a short
        with self.assertRaises(OrderError):
            b.stop("EURUSD", "buy", 1_000, 1.1000)  # buy stop not above the ask
        with self.assertRaises(OrderError):
            b.market("EURUSD", "buy", 0)

    def test_account_currency_conversion(self):
        cfg = AccountConfig(currency="JPY", initial_balance=1_000_000, leverage=25)
        b = Broker(cfg, fixed_rates("JPY", {"CHF": 150.0}))
        b.on_tick("EURCHF", at(0), 1.2000, 1.2004)
        pos_id = b.market("EURCHF", "buy", 10_000).position_id
        self.assertAlmostEqual(b.used_margin(), 10_000 * 1.2002 * 150 / 25)
        b.on_tick("EURCHF", at(1), 1.2100, 1.2104)
        self.assertAlmostEqual(b.close(pos_id).pnl, (1.2100 - 1.2004) * 10_000 * 150)

    def test_missing_conversion_rate(self):
        b = Broker(AccountConfig(currency="USD"), fixed_rates("USD", {}))
        b.on_tick("EURCHF", at(0), 1.2000, 1.2004)
        with self.assertRaises(BrokerError):
            b.market("EURCHF", "buy", 1_000)


class TriggerTests(unittest.TestCase):
    def test_long_stop_loss_gap_fills_at_the_gapped_price(self):
        b = make_broker()
        b.market("EURUSD", "buy", 10_000, sl=1.0950, tp=1.1100)
        events = b.on_tick("EURUSD", at(1), 1.0940, 1.0942)  # gaps through the stop
        self.assertEqual([e.kind for e in events], ["close"])
        trade = b.trades[-1]
        self.assertEqual((trade.reason, trade.close_price), ("sl", 1.0940))
        self.assertAlmostEqual(trade.pnl, -62.0)

    def test_long_take_profit_fills_at_its_price(self):
        b = make_broker()
        b.market("EURUSD", "buy", 10_000, sl=1.0950, tp=1.1100)
        b.on_tick("EURUSD", at(1), 1.1105, 1.1107)
        self.assertEqual((b.trades[-1].reason, b.trades[-1].close_price), ("tp", 1.1100))
        self.assertAlmostEqual(b.trades[-1].pnl, 98.0)

    def test_short_stop_loss_uses_the_ask(self):
        b = make_broker()
        b.market("EURUSD", "sell", 10_000, sl=1.1050, tp=1.0900)
        b.on_tick("EURUSD", at(1), 1.1058, 1.1060)
        self.assertEqual(b.trades[-1].reason, "sl")
        self.assertAlmostEqual(b.trades[-1].pnl, (1.1000 - 1.1060) * 10_000)

    def test_resting_limit_fills_at_its_price(self):
        b = make_broker()
        order = b.limit("EURUSD", "buy", 10_000, 1.0990)
        self.assertEqual(order.status, "pending")
        b.on_tick("EURUSD", at(1), 1.0995, 1.0997)
        self.assertEqual(order.status, "pending")
        b.on_tick("EURUSD", at(2), 1.0985, 1.0987)
        self.assertEqual(order.status, "filled")
        self.assertEqual(b.positions[order.position_id].open_price, 1.0990)

    def test_marketable_limit_fills_at_the_current_quote(self):
        b = make_broker()
        order = b.limit("EURUSD", "buy", 10_000, 1.1010)
        self.assertEqual(order.status, "filled")
        self.assertEqual(b.positions[order.position_id].open_price, 1.1002)

    def test_stop_order_gap_fills_at_the_worse_price(self):
        b = make_broker()
        order = b.stop("EURUSD", "buy", 10_000, 1.1020)
        b.on_tick("EURUSD", at(1), 1.1028, 1.1030)
        self.assertEqual(b.positions[order.position_id].open_price, 1.1030)

    def test_cancel(self):
        b = make_broker()
        order = b.limit("EURUSD", "buy", 1_000, 1.0900)
        b.cancel(order.id)
        b.on_tick("EURUSD", at(1), 1.0890, 1.0892)
        self.assertEqual(order.status, "cancelled")
        self.assertFalse(b.positions)

    def test_modify_stop_loss(self):
        b = make_broker()
        pos_id = b.market("EURUSD", "buy", 10_000, sl=1.0950).position_id
        b.modify(pos_id, sl=1.0990, tp=None)
        b.on_tick("EURUSD", at(1), 1.0989, 1.0991)
        self.assertEqual(b.trades[-1].reason, "sl")
        with self.assertRaises(OrderError):
            b.modify(b.market("EURUSD", "buy", 1_000).position_id, sl=1.2000)

    def test_latency_delays_market_orders(self):
        b = make_broker(latency=timedelta(seconds=5))
        order = b.market("EURUSD", "buy", 1_000)
        self.assertEqual(order.status, "pending")
        b.on_tick("EURUSD", at(3), 1.1001, 1.1003)
        self.assertEqual(order.status, "pending")
        b.on_tick("EURUSD", at(6), 1.1003, 1.1005)
        self.assertEqual(b.positions[order.position_id].open_price, 1.1005)

    def test_stop_out_closes_the_worst_position(self):
        cfg = AccountConfig(currency="USD", initial_balance=10_000, leverage=100)
        b = Broker(cfg, fixed_rates("USD", {}))
        b.on_tick("EURUSD", at(0), 1.1000, 1.1002)
        b.market("EURUSD", "buy", 100_000)
        events = b.on_tick("EURUSD", at(1), 1.0100, 1.0102)
        self.assertEqual(b.trades[-1].reason, "stopout")
        self.assertFalse(b.positions)
        self.assertAlmostEqual(b.balance, 10_000 + (1.0100 - 1.1002) * 100_000)
        self.assertEqual(events[-1].note, "stopout")

    def test_no_stop_out_while_margin_level_is_healthy(self):
        b = make_broker()
        b.market("EURUSD", "buy", 10_000)
        b.on_tick("EURUSD", at(1), 1.0800, 1.0802)
        self.assertTrue(b.positions)


class SessionTests(unittest.TestCase):
    def test_replay_drives_the_broker_without_leaking_the_future(self):
        ticks = ticks_from([
            (at(0), 1.1000, 1.1002),
            (at(10), 1.0990, 1.0992),
            (at(20), 1.0940, 1.0942),
            (at(30), 1.0900, 1.0902),
        ])
        broker = Broker(AccountConfig(currency="USD", initial_balance=10_000, leverage=10),
                        fixed_rates("USD", {}))
        session = Session(Replay(ticks), broker, "EUR/USD")
        broker.market("EURUSD", "buy", 10_000, sl=1.0950)
        self.assertEqual(session.advance(15), [])
        events = session.advance(10)  # reveals the 10:00:20 tick
        self.assertEqual([e.kind for e in events], ["close"])
        self.assertEqual(broker.trades[0].close_price, 1.0940)
        self.assertEqual(len(session.replay.visible_ticks()), 3)  # 10:00:30 still hidden

    def test_session_cannot_go_back(self):
        ticks = ticks_from([(at(0), 1.1000, 1.1002), (at(10), 1.1001, 1.1003)])
        broker = Broker(AccountConfig(currency="USD"), fixed_rates("USD", {}))
        session = Session(Replay(ticks), broker, "EURUSD")
        session.advance(5)
        with self.assertRaises(ValueError):
            session.run_until(at(1))


if __name__ == "__main__":
    unittest.main()
