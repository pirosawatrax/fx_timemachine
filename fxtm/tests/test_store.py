import tempfile
import unittest
from datetime import date

from fxtm.store import TickStore

from helpers import FakeProvider, ticks_from, utc


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.provider = FakeProvider(ticks_from([
            (utc(2024, 3, 4, 10, 0, 1), 1.1000, 1.1002),
            (utc(2024, 3, 4, 23, 59, 59), 1.1010, 1.1012),
            (utc(2024, 3, 5, 0, 0, 1), 1.1020, 1.1022),
        ]))
        self.store = TickStore(self.tmp.name, self.provider, now=lambda: utc(2024, 3, 10))

    def test_roundtrip_and_cache_hit(self):
        first = self.store.load("EUR/USD", utc(2024, 3, 4), utc(2024, 3, 6))
        self.assertEqual(len(first), 3)
        calls = self.provider.calls
        again = self.store.load("EUR/USD", utc(2024, 3, 4), utc(2024, 3, 6))
        self.assertEqual(self.provider.calls, calls)  # served from disk
        self.assertEqual(len(again), 3)
        self.assertEqual(str(again["time"].dt.tz), "UTC")
        self.assertAlmostEqual(again.loc[0, "bid"], 1.1000)

    def test_range_is_half_open(self):
        df = self.store.load("EURUSD", utc(2024, 3, 4, 10), utc(2024, 3, 5))
        self.assertEqual(len(df), 2)

    def test_empty_day_is_cached(self):
        self.assertTrue(self.store.load_day("EURUSD", date(2024, 3, 9)).empty)
        calls = self.provider.calls
        self.assertTrue(self.store.load_day("EURUSD", date(2024, 3, 9)).empty)
        self.assertEqual(self.provider.calls, calls)

    def test_empty_weekday_is_not_trusted(self):
        # Monday 2024-03-11 has no ticks in the fake data: probably a failed download, so never cache it
        monday = date(2024, 3, 11)
        self.assertTrue(self.store.load_day("EURUSD", monday).empty)
        calls = self.provider.calls
        self.store.load_day("EURUSD", monday)
        self.assertEqual(self.provider.calls, calls + 1)

    def test_empty_weekday_left_on_disk_is_fetched_again(self):
        monday = date(2024, 3, 4)
        stale = self.store._path("EURUSD", monday, self.store.fmt)  # an empty file from an older failed run
        from fxtm.store import write_ticks
        from fxtm.ticks import empty_ticks
        write_ticks(stale, empty_ticks(), self.store.fmt)
        self.assertEqual(len(self.store.load_day("EURUSD", monday)), 2)  # real ticks, not the stale emptiness

    def test_unfinished_day_is_not_cached(self):
        store = TickStore(self.tmp.name, self.provider, now=lambda: utc(2024, 3, 4, 12))
        store.load_day("EURUSD", date(2024, 3, 4))
        calls = self.provider.calls
        store.load_day("EURUSD", date(2024, 3, 4))
        self.assertEqual(self.provider.calls, calls + 1)

    def test_csv_roundtrip_with_mixed_fractional_seconds(self):
        provider = FakeProvider(ticks_from([
            (utc(2024, 3, 4, 0, 0, 0), 1.1000, 1.1002),                    # whole second first
            (utc(2024, 3, 4, 0, 0, 0, 500_000), 1.1001, 1.1003),           # then a fraction
            (utc(2024, 3, 4, 0, 0, 1, 120_000), 1.1002, 1.1004),
        ]))
        store = TickStore(self.tmp.name, provider, now=lambda: utc(2024, 3, 10))
        store.fmt = "csv.gz"
        first = store.load("EURUSD", utc(2024, 3, 4), utc(2024, 3, 5))
        again = store.load("EURUSD", utc(2024, 3, 4), utc(2024, 3, 5))  # read back from disk
        self.assertEqual(len(again), 3)
        self.assertEqual(list(again["time"]), list(first["time"]))

    def test_refresh_downloads_again(self):
        self.store.load_day("EURUSD", date(2024, 3, 4))
        calls = self.provider.calls
        self.store.load_day("EURUSD", date(2024, 3, 4), refresh=True)
        self.assertEqual(self.provider.calls, calls + 1)


if __name__ == "__main__":
    unittest.main()
