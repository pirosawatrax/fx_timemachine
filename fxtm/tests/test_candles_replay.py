import unittest

import pandas as pd

from fxtm.candles import CandleSeries, build_candles
from fxtm.replay import Replay

from helpers import ticks_from, utc

ROWS = [
    (utc(2024, 3, 4, 10, 0, 5), 1.1000, 1.1002),
    (utc(2024, 3, 4, 10, 0, 40), 1.1010, 1.1012),
    (utc(2024, 3, 4, 10, 0, 55), 1.0990, 1.0992),
    (utc(2024, 3, 4, 10, 1, 10), 1.1005, 1.1007),
    (utc(2024, 3, 4, 10, 1, 50), 1.1050, 1.1052),   # spike in the 2nd minute
    (utc(2024, 3, 4, 10, 6, 0), 1.1020, 1.1022),
]


class CandleTests(unittest.TestCase):
    def test_ohlc_and_gaps(self):
        c = build_candles(ticks_from(ROWS), "1m")
        self.assertEqual(len(c), 3)  # empty minutes 10:02-10:05 are omitted
        first = c.iloc[0]
        self.assertEqual((first.open, first.high, first.low, first.close, first.volume),
                         (1.1000, 1.1010, 1.0990, 1.0990, 3))
        self.assertEqual(c.iloc[0]["time"], pd.Timestamp(utc(2024, 3, 4, 10, 0)))

    def test_ask_and_mid_sources(self):
        t = ticks_from(ROWS)
        self.assertEqual(build_candles(t, "1m", "ask").iloc[0].open, 1.1002)
        self.assertAlmostEqual(build_candles(t, "1m", "mid").iloc[0].open, 1.1001)

    def test_higher_timeframes(self):
        c = build_candles(ticks_from(ROWS), "5m")
        self.assertEqual(len(c), 2)
        self.assertEqual(c.iloc[0].high, 1.1050)

    def test_incremental_equals_batch(self):
        t = ticks_from(ROWS)
        series = CandleSeries("1m")
        for i in range(len(t)):
            series.update(t.iloc[i : i + 1])
        pd.testing.assert_frame_equal(
            series.frame().reset_index(drop=True),
            build_candles(t, "1m").astype({"volume": "int64"}),
            check_dtype=False,
        )


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.replay = Replay(ticks_from(ROWS))

    def test_starts_at_first_tick(self):
        self.assertEqual(len(self.replay.visible_ticks()), 1)
        self.assertEqual(self.replay.quote(), (1.1000, 1.1002))

    def test_forming_candle_never_contains_the_future(self):
        self.replay.seek(utc(2024, 3, 4, 10, 1, 20))
        candles = self.replay.candles("1m")
        forming = candles.iloc[-1]
        self.assertEqual(forming.high, 1.1005)  # the 10:01:50 spike is not visible yet
        self.assertEqual(forming.close, 1.1005)
        self.replay.seek(utc(2024, 3, 4, 10, 1, 51))
        self.assertEqual(self.replay.candles("1m").iloc[-1].high, 1.1050)

    def test_advance_returns_new_ticks_only(self):
        new = self.replay.advance(30)
        self.assertEqual(len(new), 0)
        new = self.replay.advance(15)
        self.assertEqual(len(new), 1)
        self.assertEqual(new.iloc[0].bid, 1.1010)

    def test_wall_clock_speed(self):
        new = self.replay.advance_wall(1.0, speed=60)  # 60 s of market time
        self.assertEqual(len(new), 2)

    def test_seek_backwards_rebuilds_candles(self):
        self.replay.seek(utc(2024, 3, 4, 10, 6, 0))
        self.assertEqual(len(self.replay.candles("1m")), 3)
        self.replay.seek(utc(2024, 3, 4, 10, 0, 30))
        c = self.replay.candles("1m")
        self.assertEqual(len(c), 1)
        self.assertEqual(c.iloc[0].high, 1.1000)

    def test_cannot_advance_backwards(self):
        with self.assertRaises(ValueError):
            self.replay.advance(-1)

    def test_next_tick_and_end(self):
        seen = 0
        while self.replay.next_tick() is not None:
            seen += 1
        self.assertEqual(seen, len(ROWS) - 1)
        self.assertTrue(self.replay.at_end)


if __name__ == "__main__":
    unittest.main()
