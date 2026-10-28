"""Data providers.

A provider is any object with a ``name`` and a ``fetch_ticks(symbol, start, end)``
method returning a tick table for the half-open UTC interval [start, end).
Providers are the only code that knows where data comes from, so a provider can
be replaced without touching candles, replay or trading.
"""
from __future__ import annotations

import lzma
import time as _time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from fxtm.ticks import ProviderError, empty_ticks, make_ticks, normalize_symbol, to_utc

DUKASCOPY_BASE_URL = "https://datafeed.dukascopy.com/datafeed"

# One bi5 record is 20 bytes, big endian: ms offset from the hour start,
# ask and bid as integers (price * divisor), ask and bid volume as float32.
_BI5_RECORD = np.dtype(
    [("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("ask_vol", ">f4"), ("bid_vol", ">f4")]
)


def price_divisor(symbol: str) -> int:
    """Integer scale of Dukascopy prices: 1000 for JPY quotes, else 100000."""
    return 1_000 if normalize_symbol(symbol).endswith("JPY") else 100_000


def hour_url(symbol: str, hour_start: datetime) -> str:
    """URL of one hour of ticks. Dukascopy numbers months from 0."""
    h = hour_start
    return (
        f"{DUKASCOPY_BASE_URL}/{normalize_symbol(symbol)}/"
        f"{h.year:04d}/{h.month - 1:02d}/{h.day:02d}/{h.hour:02d}h_ticks.bi5"
    )


def decode_bi5(raw: bytes, hour_start: datetime, divisor: int) -> pd.DataFrame:
    """Decode one downloaded .bi5 file (LZMA-compressed records)."""
    if not raw:
        return empty_ticks()
    try:
        data = lzma.decompress(raw)
    except lzma.LZMAError as exc:
        raise ProviderError(f"corrupt bi5 data for {hour_start:%Y-%m-%d %H}h: {exc}") from exc
    if len(data) % _BI5_RECORD.itemsize:
        raise ProviderError(f"unexpected bi5 length for {hour_start:%Y-%m-%d %H}h")
    rec = np.frombuffer(data, dtype=_BI5_RECORD)
    base_ns = int(hour_start.timestamp()) * 1_000_000_000
    return make_ticks(
        base_ns + rec["ms"].astype("int64") * 1_000_000,
        rec["bid"].astype("float64") / divisor,
        rec["ask"].astype("float64") / divisor,
        rec["bid_vol"],
        rec["ask_vol"],
    )


def http_get(url: str, timeout: float = 30.0, retries: int = 3) -> bytes | None:
    """GET a URL. Returns None for 404 (no data for that hour)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "fxtm/0.1 (open-source FX replay tool)"}
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last_error = exc
        except OSError as exc:  # URLError, timeouts, connection resets
            last_error = exc
        _time.sleep(0.5 * 2**attempt)
    raise ProviderError(f"download failed: {url} ({last_error})")


class DukascopyProvider:
    """Tick data from Dukascopy's public historical feed (no account needed)."""

    name = "dukascopy"

    def __init__(self, get=http_get, max_workers: int = 4, now=None):
        self._get = get
        self._max_workers = max_workers
        self._now = now or (lambda: datetime.now(timezone.utc))

    def fetch_ticks(self, symbol: str, start, end) -> pd.DataFrame:
        sym = normalize_symbol(symbol)
        start, end = to_utc(start), to_utc(end)
        if end <= start:
            raise ValueError("end must be after start")
        now = self._now()
        hour = start.replace(minute=0, second=0, microsecond=0)
        hours = []
        while hour < end:
            if hour + timedelta(hours=1) <= now:  # skip hours not finished yet
                hours.append(hour)
            hour += timedelta(hours=1)
        divisor = price_divisor(sym)

        def fetch_hour(h: datetime) -> pd.DataFrame:
            raw = self._get(hour_url(sym, h))
            return decode_bi5(raw or b"", h, divisor)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            frames = [f for f in pool.map(fetch_hour, hours) if not f.empty]
        if not frames:
            return empty_ticks()
        ticks = pd.concat(frames, ignore_index=True)
        ticks = ticks[(ticks["time"] >= pd.Timestamp(start)) & (ticks["time"] < pd.Timestamp(end))]
        return ticks.sort_values("time", kind="stable").reset_index(drop=True)
