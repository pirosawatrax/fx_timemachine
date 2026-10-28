"""Local tick cache: one file per symbol and UTC day.

Parquet is used when pyarrow is installed, gzip CSV otherwise. A day that was
fully fetched is stored even when it has no ticks (weekends), so it is never
downloaded twice. The current, unfinished UTC day is never cached.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from fxtm.ticks import TICK_COLUMNS, empty_ticks, normalize_symbol, to_utc

_FORMATS = ("parquet", "csv.gz")


def default_data_dir() -> Path:
    """Where ticks and saved runs live: $FXTM_DATA_DIR, else the platform's usual data folder."""
    env = os.environ.get("FXTM_DATA_DIR")
    if env:
        return Path(env)
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "fxtm"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "fxtm"
    return Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / "fxtm"


class TickStore:
    def __init__(self, root, provider, now=None):
        self.root = Path(root)
        self.provider = provider
        self._now = now or (lambda: datetime.now(timezone.utc))
        has_pyarrow = importlib.util.find_spec("pyarrow") is not None
        self.fmt = "parquet" if has_pyarrow else "csv.gz"

    def _path(self, symbol: str, day, fmt: str) -> Path:
        return (
            self.root / "ticks" / self.provider.name / normalize_symbol(symbol)
            / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.{fmt}"
        )

    def _existing(self, symbol: str, day) -> Path | None:
        for fmt in _FORMATS:
            path = self._path(symbol, day, fmt)
            if path.exists():
                return path
        return None

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        if path.name.endswith(".parquet"):
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        if df.empty:
            return empty_ticks()
        df = df[TICK_COLUMNS].copy()
        df["time"] = pd.to_datetime(df["time"], utc=True, format="ISO8601").dt.as_unit("ns")
        return df.reset_index(drop=True)

    def _write(self, symbol: str, day, ticks: pd.DataFrame) -> None:
        path = self._path(symbol, day, self.fmt)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        if self.fmt == "parquet":
            ticks.to_parquet(tmp, index=False)
        else:
            ticks.to_csv(tmp, index=False, compression="gzip")
        os.replace(tmp, path)  # atomic: a half-written file is never visible

    def load_day(self, symbol: str, day, refresh: bool = False) -> pd.DataFrame:
        """All ticks of one UTC day, from the cache or from the provider."""
        if not refresh:
            cached = self._existing(symbol, day)
            if cached is not None:
                return self._read(cached)
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        ticks = self.provider.fetch_ticks(symbol, day_start, day_end)
        if day_end <= self._now():
            self._write(symbol, day, ticks)
        return ticks

    def load(self, symbol: str, start, end, refresh: bool = False, progress=None) -> pd.DataFrame:
        """Ticks in the UTC interval [start, end), downloading what is missing."""
        start, end = to_utc(start), to_utc(end)
        if end <= start:
            raise ValueError("end must be after start")
        day = start.date()
        last_day = (end - timedelta(microseconds=1)).date()
        frames = []
        while day <= last_day:
            frame = self.load_day(symbol, day, refresh=refresh)
            if progress:
                progress(day, len(frame))
            if not frame.empty:
                frames.append(frame)
            day += timedelta(days=1)
        if not frames:
            return empty_ticks()
        ticks = pd.concat(frames, ignore_index=True)
        mask = (ticks["time"] >= pd.Timestamp(start)) & (ticks["time"] < pd.Timestamp(end))
        return ticks[mask].sort_values("time", kind="stable").reset_index(drop=True)
