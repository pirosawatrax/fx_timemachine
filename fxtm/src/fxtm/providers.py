"""Data providers.

A provider is any object with a ``name`` and a ``fetch_ticks(symbol, start, end)``
method returning a tick table for the half-open UTC interval [start, end).
Providers are the only code that knows where data comes from, so a provider can
be replaced without touching candles, replay or trading.
"""
from __future__ import annotations

import lzma
import os
import threading
import time as _time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
        raise ProviderError(
            f"not a valid bi5 data file for {hour_start:%Y-%m-%d %H}h (it may be a block page): {exc}") from exc
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


HINT = (
    "Dukascopy's free feed has been unreliable since July 2026 and may block scripts. "
    "Try again later, or import tick files you downloaded yourself (see the README, 'Your own data files')."
)


def _describe_status(status: int) -> str:
    if status == 202:
        return "Dukascopy answered with a bot-protection challenge (HTTP 202) instead of data"
    if status in (401, 403, 429):
        return f"Dukascopy refused the request (HTTP {status})"
    if status >= 500:
        return f"Dukascopy's server is in trouble (HTTP {status})"
    return f"unexpected answer from Dukascopy (HTTP {status})"


def http_get(url: str, timeout: float = 30.0, retries: int = 4, sleep=_time.sleep) -> bytes | None:
    """GET a URL.

    Returns the body for HTTP 200 (an empty body means an hour without ticks) and
    None for 404 (no such file). Anything else is a failure and is retried: an empty
    "202" challenge must never be mistaken for a quiet market.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "fxtm/0.1 (open-source FX replay tool)"}
    )
    problem = "no answer"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, body = response.status, response.read()
            if status == 200:
                return body
            problem = _describe_status(status)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            problem = _describe_status(exc.code)
        except OSError as exc:  # URLError, timeouts, connection resets
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                problem = "Dukascopy did not answer in time (timeout)"
            else:
                problem = f"connection problem ({reason})"
        if attempt + 1 < retries:
            sleep(min(1.0 * 2**attempt, 8.0))
    raise ProviderError(f"{problem}: {url}. {HINT}")


class DukascopyProvider:
    """Tick data from Dukascopy's public historical feed (no account needed).

    Every finished hour that downloads correctly is kept in ``cache_dir`` (if given), so a
    failed hour never costs the hours that worked: hours that fail are retried in further
    rounds, and pressing "start" again continues where the last attempt stopped.
    """

    name = "dukascopy"

    def __init__(self, get=http_get, max_workers: int = 2, now=None, cache_dir=None,
                 rounds: int = 3, pauses=(5.0, 15.0), sleep=_time.sleep, progress=None):
        self._get = get
        self._max_workers = max_workers
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._cache_dir = None if cache_dir is None else Path(cache_dir)
        self._rounds = max(1, rounds)
        self._pauses = tuple(pauses) or (0.0,)
        self._sleep = sleep
        self.progress = progress  # optional callable(done, total, hour)

    def _raw_path(self, symbol: str, hour: datetime) -> Path | None:
        if self._cache_dir is None:
            return None
        return (self._cache_dir / symbol / f"{hour:%Y}" / f"{hour:%m}" / f"{hour:%d}"
                / f"{hour:%H}h_ticks.bi5")

    def _fetch_hour(self, symbol: str, hour: datetime, divisor: int) -> pd.DataFrame:
        path = self._raw_path(symbol, hour)
        raw = path.read_bytes() if path is not None and path.exists() else None
        from_cache = raw is not None
        if raw is None:
            raw = self._get(hour_url(symbol, hour))
            if raw is None:  # 404: the feed has no file for this hour
                return empty_ticks()
        try:
            ticks = decode_bi5(raw, hour, divisor)
        except ProviderError:
            if from_cache:
                path.unlink(missing_ok=True)  # a damaged cached file: download it again next round
            raise
        if path is not None and not from_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, path)
        return ticks

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
        frames: dict[datetime, pd.DataFrame] = {}
        errors: dict[datetime, ProviderError] = {}
        lock = threading.Lock()

        def task(h: datetime) -> None:
            try:
                frame = self._fetch_hour(sym, h, divisor)
            except ProviderError as exc:
                with lock:
                    errors[h] = exc
                return
            with lock:
                frames[h] = frame
                errors.pop(h, None)
                done = len(frames)
            if self.progress is not None:
                self.progress(done, len(hours), h)

        pending = hours
        for round_no in range(self._rounds):
            if not pending:
                break
            if round_no:
                self._sleep(self._pauses[min(round_no - 1, len(self._pauses) - 1)])
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                list(pool.map(task, pending))
            pending = [h for h in hours if h not in frames]
        if pending:
            first = pending[0]
            raise ProviderError(
                f"{len(pending)} of {len(hours)} hours could not be downloaded "
                f"(first: {first:%Y-%m-%d %H}h). {errors[first]} "
                "Hours that worked are kept: press start again to continue from there.")
        parts = [frames[h] for h in hours if not frames[h].empty]
        if not parts:
            return empty_ticks()
        ticks = pd.concat(parts, ignore_index=True)
        ticks = ticks[(ticks["time"] >= pd.Timestamp(start)) & (ticks["time"] < pd.Timestamp(end))]
        return ticks.sort_values("time", kind="stable").reset_index(drop=True)
