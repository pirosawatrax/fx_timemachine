"""Core tick helpers shared by every module.

Conventions
-----------
* All timestamps are UTC. Providers convert their own time zones on import.
* A tick table is a DataFrame with the columns in ``TICK_COLUMNS``; ``time`` is
  ``datetime64[ns, UTC]`` and rows are sorted by time.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

TICK_COLUMNS = ["time", "bid", "ask", "bid_vol", "ask_vol"]


class FxtmError(Exception):
    """Base class for expected, user-facing errors."""


class ProviderError(FxtmError):
    """A data provider could not deliver the requested data."""


def to_utc(value) -> datetime:
    """Convert a date, datetime or ISO string to an aware UTC datetime.

    Naive values are interpreted as UTC.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_symbol(symbol: str) -> str:
    """'eur/chf' -> 'EURCHF'."""
    cleaned = "".join(ch for ch in symbol.upper() if ch.isalnum())
    if not cleaned:
        raise ValueError(f"invalid currency pair: {symbol!r}")
    return cleaned


def make_ticks(time_ns, bid, ask, bid_vol, ask_vol) -> pd.DataFrame:
    """Build a tick table from epoch-nanosecond timestamps and price arrays."""
    times = pd.to_datetime(np.asarray(time_ns, dtype="int64"), unit="ns", utc=True)
    return pd.DataFrame(
        {
            "time": pd.Series(times.as_unit("ns")),
            "bid": np.asarray(bid, dtype="float64"),
            "ask": np.asarray(ask, dtype="float64"),
            "bid_vol": np.asarray(bid_vol, dtype="float64"),
            "ask_vol": np.asarray(ask_vol, dtype="float64"),
        }
    )


def empty_ticks() -> pd.DataFrame:
    return make_ticks([], [], [], [], [])


def time_ns(ticks: pd.DataFrame) -> np.ndarray:
    """Epoch nanoseconds (int64) of a tick table's ``time`` column."""
    naive = ticks["time"].dt.tz_convert("UTC").dt.tz_localize(None)
    return naive.to_numpy(dtype="datetime64[ns]").astype("int64")
