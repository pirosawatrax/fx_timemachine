import tempfile
import unittest
from pathlib import Path

from fxtm.importer import ImportedProvider, import_file, list_datasets, read_tick_csv
from fxtm.store import TickStore
from fxtm.ticks import FxtmError

from helpers import utc


class Files:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()

    def write(self, name, text):
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return path


class ReadCsvTests(unittest.TestCase):
    def setUp(self):
        self.files = Files()
        self.addCleanup(self.files.tmp.cleanup)

    def test_dukascopy_website_style(self):
        path = self.files.write("a.csv", (
            "Gmt time,Ask,Bid,AskVolume,BidVolume\n"
            "15.01.2015 09:30:00.123,1.20050,1.20040,1.5,2.5\n"
            "15.01.2015 09:30:01.000,1.20060,1.20050,1.0,1.0\n"))
        ticks = read_tick_csv(path)
        self.assertEqual(len(ticks), 2)
        self.assertEqual(ticks["time"].iloc[0], utc(2015, 1, 15, 9, 30, 0, 123_000))
        self.assertAlmostEqual(ticks["bid"].iloc[0], 1.2004)
        self.assertAlmostEqual(ticks["ask"].iloc[0], 1.2005)
        self.assertEqual(ticks["bid_vol"].iloc[0], 2.5)

    def test_dukascopy_node_style_with_epoch_milliseconds(self):
        path = self.files.write("b.csv", (
            "timestamp,askPrice,bidPrice,askVolume,bidVolume\n"
            "1421314200123,1.2005,1.2004,1,1\n1421314201000,1.2006,1.2005,1,1\n"))
        ticks = read_tick_csv(path)
        self.assertEqual(ticks["time"].iloc[0], utc(2015, 1, 15, 9, 30, 0, 123_000))

    def test_no_header_semicolons_and_local_time_zone(self):
        path = self.files.write("c.csv", "2015-01-15 18:30:00;1.2005;1.2004\n2015-01-15 18:30:02;1.2006;1.2005\n")
        ticks = read_tick_csv(path, timezone="Asia/Tokyo")  # 18:30 JST = 09:30 UTC
        self.assertEqual(ticks["time"].iloc[0], utc(2015, 1, 15, 9, 30, 0))
        self.assertEqual(ticks["bid_vol"].iloc[0], 0.0)

    def test_rows_are_sorted_and_bad_rows_dropped(self):
        path = self.files.write("d.csv", (
            "time,bid,ask\n2024-03-04 10:00:02,1.1,1.2\nbroken,x,y\n2024-03-04 10:00:01,1.1,1.2\n"))
        ticks = read_tick_csv(path)
        self.assertEqual(len(ticks), 2)
        self.assertLess(ticks["time"].iloc[0], ticks["time"].iloc[1])

    def test_errors_are_explained(self):
        swapped = self.files.write("e.csv", "time,bid,ask\n2024-03-04 10:00:00,1.2,1.1\n2024-03-04 10:00:01,1.2,1.1\n")
        with self.assertRaisesRegex(FxtmError, "swapped"):
            read_tick_csv(swapped)
        nocol = self.files.write("f.csv", "time,price\n2024-03-04 10:00:00,1.2\n")
        with self.assertRaisesRegex(FxtmError, "no ask/bid column"):
            read_tick_csv(nocol)
        with self.assertRaisesRegex(FxtmError, "empty"):
            read_tick_csv(self.files.write("g.csv", ""))


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.files = Files()
        self.addCleanup(self.files.tmp.cleanup)
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        rows = "".join(f"2024-03-04 10:{m:02d}:00,1.1000,1.1002\n" for m in range(0, 60))
        self.csv = self.files.write("h.csv", "time,bid,ask\n" + rows)

    def test_import_list_and_serve(self):
        info = import_file(self.data.name, "EUR/USD", self.csv)
        self.assertEqual((info["symbol"], info["ticks"]), ("EURUSD", 60))
        listed = list_datasets(self.data.name)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["first"], utc(2024, 3, 4, 10, 0))
        self.assertEqual(list_datasets(self.data.name, "GBP/USD"), [])

        provider = ImportedProvider(self.data.name)
        self.assertEqual(len(provider.fetch_ticks("EURUSD", utc(2024, 3, 4, 10, 30), utc(2024, 3, 4, 11))), 30)
        self.assertTrue(provider.fetch_ticks("EURUSD", utc(2024, 3, 5), utc(2024, 3, 6)).empty)

    def test_overlapping_imports_do_not_duplicate_ticks(self):
        import_file(self.data.name, "EURUSD", self.csv)
        import_file(self.data.name, "EURUSD", self.csv)  # same file again
        ticks = ImportedProvider(self.data.name).fetch_ticks("EURUSD", utc(2024, 3, 4), utc(2024, 3, 5))
        self.assertEqual(len(ticks), 60)

    def test_store_never_remembers_partial_days_from_imports(self):
        import_file(self.data.name, "EURUSD", self.csv)
        store = TickStore(self.data.name, ImportedProvider(self.data.name), now=lambda: utc(2030, 1, 1))
        self.assertEqual(len(store.load("EURUSD", utc(2024, 3, 4), utc(2024, 3, 5))), 60)
        self.assertFalse(list(Path(self.data.name, "ticks").rglob("*.*")))  # nothing written under ticks/


if __name__ == "__main__":
    unittest.main()
