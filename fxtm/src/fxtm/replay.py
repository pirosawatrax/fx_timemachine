"""Market replay that can never show the future.

``Replay`` owns a clock. Everything it returns (ticks, quote, candles) is derived
only from ticks with ``time <= now``. The candle that is still forming is built
from those ticks alone, so its high and low never include later prices.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from fxtm.candles import CandleSeries
from fxtm.ticks import time_ns, to_utc


def _to_ns(value) -> int:
    return int(pd.Timestamp(to_utc(value)).value)


class Replay:
    def __init__(self, ticks: pd.DataFrame, start=None, price: str = "bid"):
        if ticks.empty:
            raise ValueError("no ticks to replay")
        self._ticks = ticks.sort_values("time", kind="stable").reset_index(drop=True)
        self._times = time_ns(self._ticks)
        self._price = price
        self._series: dict[str, CandleSeries] = {}
        self._now_ns = int(self._times[0]) if start is None else _to_ns(start)
        self._pos = self._count_until(self._now_ns)

    def _count_until(self, ns: int) -> int:
        return int(np.searchsorted(self._times, ns, side="right"))

    @property
    def now(self) -> pd.Timestamp:
        return pd.Timestamp(self._now_ns, unit="ns", tz="UTC")

    @property
    def start(self) -> pd.Timestamp:
        return pd.Timestamp(int(self._times[0]), unit="ns", tz="UTC")

    @property
    def end(self) -> pd.Timestamp:
        return pd.Timestamp(int(self._times[-1]), unit="ns", tz="UTC")

    @property
    def at_end(self) -> bool:
        return self._pos >= len(self._ticks)

    def seek(self, when) -> None:
        """Jump to any time, forwards or backwards."""
        self._now_ns = _to_ns(when)
        self._pos = self._count_until(self._now_ns)

    def advance(self, delta) -> pd.DataFrame:
        """Move the clock forward; returns the ticks that just became visible."""
        ns = int(pd.Timedelta(delta if isinstance(delta, timedelta) else timedelta(seconds=delta)).value)
        if ns < 0:
            raise ValueError("advance() only moves forward; use seek() to go back")
        old = self._pos
        self._now_ns += ns
        self._pos = self._count_until(self._now_ns)
        return self._ticks.iloc[old : self._pos]

    def advance_wall(self, wall_seconds: float, speed: float = 1.0) -> pd.DataFrame:
        """Advance by real elapsed time multiplied by the replay speed."""
        return self.advance(timedelta(seconds=wall_seconds * speed))

    def next_tick(self) -> pd.Series | None:
        """Move the clock to the next tick and return it (None at the end)."""
        if self.at_end:
            return None
        self._now_ns = int(self._times[self._pos])
        self._pos = self._count_until(self._now_ns)
        return self._ticks.iloc[self._pos - 1]

    def visible_ticks(self) -> pd.DataFrame:
        return self._ticks.iloc[: self._pos]

    def quote(self) -> tuple[float, float] | None:
        """Latest (bid, ask), or None before the first tick."""
        if self._pos == 0:
            return None
        row = self._ticks.iloc[self._pos - 1]
        return float(row["bid"]), float(row["ask"])

    def candles(self, timeframe: str = "1m") -> pd.DataFrame:
        """Candles up to the replay clock; the last one may still be forming."""
        series = self._series.get(timeframe)
        if series is None:
            series = self._series[timeframe] = CandleSeries(timeframe, self._price)
        if series.consumed > self._pos:  # the clock moved backwards: rebuild
            series.reset()
        if series.consumed < self._pos:
            series.update(self._ticks.iloc[series.consumed : self._pos])
            series.consumed = self._pos
        return series.frame()
