from datetime import datetime, timezone

import pandas as pd

from fxtm.ticks import make_ticks


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def ns(dt: datetime) -> int:
    return int(pd.Timestamp(dt).value)


def ticks_from(rows):
    """rows: list of (datetime, bid, ask)."""
    return make_ticks(
        [ns(t) for t, _, _ in rows],
        [b for _, b, _ in rows],
        [a for _, _, a in rows],
        [1.0] * len(rows),
        [1.0] * len(rows),
    )


class FakeProvider:
    name = "fake"

    def __init__(self, ticks):
        self.ticks = ticks
        self.calls = 0

    def fetch_ticks(self, symbol, start, end):
        self.calls += 1
        t = self.ticks
        mask = (t["time"] >= pd.Timestamp(start)) & (t["time"] < pd.Timestamp(end))
        return t[mask].reset_index(drop=True)
