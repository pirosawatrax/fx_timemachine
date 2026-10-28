"""Tick -> candle aggregation (UTC bins)."""
from __future__ import annotations

import pandas as pd

TIMEFRAMES = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "1d": "1D"}
CANDLE_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
PRICE_SOURCES = ("bid", "ask", "mid")


def _price_series(ticks: pd.DataFrame, price: str) -> pd.Series:
    if price not in PRICE_SOURCES:
        raise ValueError(f"price must be one of {PRICE_SOURCES}")
    values = (ticks["bid"] + ticks["ask"]) / 2 if price == "mid" else ticks[price]
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(ticks["time"]), name=price)


def build_candles(ticks: pd.DataFrame, timeframe: str = "1m", price: str = "bid") -> pd.DataFrame:
    """Aggregate ticks into OHLC candles. ``volume`` is the tick count.

    ``time`` is the start of each bin. Bins without ticks are omitted.
    Daily candles roll at 00:00 UTC.
    """
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"timeframe must be one of {list(TIMEFRAMES)}")
    if ticks.empty:
        return pd.DataFrame({name: [] for name in CANDLE_COLUMNS})
    series = _price_series(ticks, price)
    resampler = series.resample(TIMEFRAMES[timeframe])
    candles = resampler.ohlc()
    candles["volume"] = resampler.count()
    candles = candles[candles["volume"] > 0]
    candles.index.name = "time"
    return candles.reset_index()[CANDLE_COLUMNS]


class CandleSeries:
    """Candles built incrementally from consecutive tick batches.

    The last candle may still be forming: it only reflects ticks fed so far.
    """

    def __init__(self, timeframe: str, price: str = "bid"):
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {list(TIMEFRAMES)}")
        self.timeframe = timeframe
        self.price = price
        self.consumed = 0  # how many ticks of the source table were fed
        self._rows: list[list] = []

    def reset(self) -> None:
        self.consumed = 0
        self._rows = []

    def update(self, ticks: pd.DataFrame) -> None:
        for row in build_candles(ticks, self.timeframe, self.price).itertuples(index=False):
            if self._rows and self._rows[-1][0] == row.time:
                last = self._rows[-1]
                last[2] = max(last[2], row.high)
                last[3] = min(last[3], row.low)
                last[4] = row.close
                last[5] += int(row.volume)
            else:
                self._rows.append(
                    [row.time, row.open, row.high, row.low, row.close, int(row.volume)]
                )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows, columns=CANDLE_COLUMNS)
