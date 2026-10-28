import lzma
import struct
import tempfile
import unittest
from pathlib import Path

from fxtm.providers import DukascopyProvider, decode_bi5, hour_url, price_divisor
from fxtm.ticks import ProviderError

from helpers import ns, utc


def bi5(records):
    """records: (ms, ask_int, bid_int, ask_vol, bid_vol)."""
    raw = b"".join(struct.pack(">IIIff", *r) for r in records)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


class ProviderTests(unittest.TestCase):
    def test_url_months_start_at_zero(self):
        url = hour_url("EUR/CHF", utc(2015, 1, 15, 9))
        self.assertTrue(url.endswith("/EURCHF/2015/00/15/09h_ticks.bi5"))

    def test_price_divisor(self):
        self.assertEqual(price_divisor("USD/JPY"), 1_000)
        self.assertEqual(price_divisor("EUR/USD"), 100_000)

    def test_decode(self):
        raw = bi5([(0, 107125, 107123, 1.5, 2.5), (1500, 107130, 107128, 1.0, 1.0)])
        df = decode_bi5(raw, utc(2024, 3, 4, 10), 100_000)
        self.assertEqual(len(df), 2)
        self.assertAlmostEqual(df.loc[0, "bid"], 1.07123)
        self.assertAlmostEqual(df.loc[0, "ask"], 1.07125)
        self.assertEqual(df.loc[0, "bid_vol"], 2.5)
        self.assertEqual(int(df["time"].iloc[1].value) - int(df["time"].iloc[0].value), 1_500_000_000)
        self.assertEqual(int(df["time"].iloc[0].value), ns(utc(2024, 3, 4, 10)))

    def test_decode_empty_and_corrupt(self):
        self.assertTrue(decode_bi5(b"", utc(2024, 3, 4, 10), 100_000).empty)
        with self.assertRaises(ProviderError):
            decode_bi5(b"not lzma", utc(2024, 3, 4, 10), 100_000)

    def test_fetch_filters_range_and_skips_missing_hours(self):
        urls = []

        def fake_get(url):
            urls.append(url)
            if "10h_ticks" in url:
                return bi5([(0, 107125, 107123, 1, 1), (1_800_000, 107130, 107128, 1, 1)])
            return None  # 404: no data

        provider = DukascopyProvider(get=fake_get, now=lambda: utc(2024, 3, 5))
        df = provider.fetch_ticks("EUR/USD", utc(2024, 3, 4, 9), utc(2024, 3, 4, 11))
        self.assertEqual(len(urls), 2)  # hours 09 and 10
        self.assertEqual(len(df), 2)
        df = provider.fetch_ticks("EUR/USD", utc(2024, 3, 4, 10, 15), utc(2024, 3, 4, 11))
        self.assertEqual(len(df), 1)  # the tick at 10:30 only

    def test_unfinished_hours_are_not_requested(self):
        provider = DukascopyProvider(get=lambda url: self.fail("must not download"),
                                     now=lambda: utc(2024, 3, 4, 10, 30))
        self.assertTrue(provider.fetch_ticks("EURUSD", utc(2024, 3, 4, 10), utc(2024, 3, 4, 11)).empty)


class ResilienceTests(unittest.TestCase):
    NOW = utc(2024, 3, 5)
    START, END = utc(2024, 3, 4, 9), utc(2024, 3, 4, 12)  # hours 09, 10, 11

    @staticmethod
    def good(hour_label):
        return bi5([(1000, 107125, 107123, 1, 1)])

    def make(self, get, **kw):
        return DukascopyProvider(get=get, now=lambda: self.NOW, sleep=lambda s: None, **kw)

    def test_a_failing_hour_is_retried_in_later_rounds(self):
        calls = {"10h": 0}

        def get(url):
            if "10h_ticks" in url:
                calls["10h"] += 1
                if calls["10h"] <= 2:
                    raise ProviderError("HTTP 503")
            return self.good(url)

        ticks = self.make(get).fetch_ticks("EURUSD", self.START, self.END)
        self.assertEqual(len(ticks), 3)  # one tick in each of the three hours
        self.assertEqual(calls["10h"], 3)

    def test_permanent_failure_reports_how_many_hours_and_keeps_the_good_ones(self):
        with tempfile.TemporaryDirectory() as cache:
            def get(url):
                if "11h_ticks" in url:
                    raise ProviderError("HTTP 503")
                return self.good(url)

            with self.assertRaises(ProviderError) as ctx:
                self.make(get, cache_dir=cache).fetch_ticks("EURUSD", self.START, self.END)
            self.assertIn("1 of 3 hours", str(ctx.exception))
            self.assertIn("11h", str(ctx.exception))
            saved = sorted(p.name for p in Path(cache).rglob("*.bi5"))
            self.assertEqual(saved, ["09h_ticks.bi5", "10h_ticks.bi5"])

    def test_second_attempt_continues_from_the_saved_hours(self):
        with tempfile.TemporaryDirectory() as cache:
            def broken(url):
                if "11h_ticks" in url:
                    raise ProviderError("HTTP 503")
                return self.good(url)

            with self.assertRaises(ProviderError):
                self.make(broken, cache_dir=cache).fetch_ticks("EURUSD", self.START, self.END)

            requested = []

            def recovered(url):
                requested.append(url)
                return self.good(url)

            ticks = self.make(recovered, cache_dir=cache).fetch_ticks("EURUSD", self.START, self.END)
            self.assertEqual(len(ticks), 3)
            self.assertEqual(len(requested), 1)  # only the missing hour was downloaded
            self.assertIn("11h_ticks", requested[0])

    def test_damaged_cached_hour_is_downloaded_again(self):
        with tempfile.TemporaryDirectory() as cache:
            path = Path(cache, "EURUSD", "2024", "03", "04", "09h_ticks.bi5")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"garbage")
            ticks = self.make(self.good_get, cache_dir=cache).fetch_ticks("EURUSD", self.START, utc(2024, 3, 4, 10))
            self.assertEqual(len(ticks), 1)
            self.assertNotEqual(path.read_bytes(), b"garbage")

    def good_get(self, url):
        return self.good(url)

    def test_progress_is_reported(self):
        seen = []
        provider = self.make(self.good_get, progress=lambda done, total, hour: seen.append((done, total)))
        provider.fetch_ticks("EURUSD", self.START, self.END)
        self.assertEqual(sorted(seen), [(1, 3), (2, 3), (3, 3)])


if __name__ == "__main__":
    unittest.main()
