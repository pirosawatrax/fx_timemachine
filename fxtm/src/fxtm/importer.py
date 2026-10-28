"""Use tick files you downloaded yourself (for example in a browser) instead of the online feed.

A CSV needs a time, a bid and an ask column. Headers are recognised by name
("Gmt time,Ask,Bid,AskVolume,BidVolume" and "timestamp,askPrice,bidPrice,..." both work).
Without a header the order time, ask, bid, ask volume, bid volume is assumed (Dukascopy's order).
Times may be ISO strings, day.month.year strings, or epoch seconds/milliseconds; strings are read
in the time zone you give (UTC by default) and stored as UTC.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from fxtm.store import has_pyarrow, read_ticks, write_ticks
from fxtm.ticks import FxtmError, empty_ticks, make_ticks, normalize_symbol, time_ns, to_utc

_ALIASES = {
    "time": {"time", "gmttime", "timestamp", "datetime", "date", "utc", "utctime", "localtime"},
    "ask": {"ask", "askprice"},
    "bid": {"bid", "bidprice"},
    "ask_vol": {"askvolume", "askvol", "askvolumn"},
    "bid_vol": {"bidvolume", "bidvol", "bidvolumn"},
}
_POSITIONAL = ["time", "ask", "bid", "ask_vol", "bid_vol"]
_TIME_FORMATS = [
    "%d.%m.%Y %H:%M:%S.%f", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
    "%Y.%m.%d %H:%M:%S.%f", "%Y.%m.%d %H:%M:%S", "ISO8601",
]
_DATASET = re.compile(r"^(\d{8}T\d{6})_(\d{8}T\d{6})_(\d+)\.(parquet|csv\.gz)$")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _parse_times(values: pd.Series, timezone: str) -> pd.Series:
    text = values.astype(str).str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    if numeric.notna().mean() > 0.99:
        top = float(numeric.abs().max())
        unit = "ns" if top > 1e17 else "us" if top > 1e14 else "ms" if top > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, utc=True)
    best, best_count = None, 0
    for fmt in _TIME_FORMATS:  # keep the format that reads the most rows
        try:
            candidate = pd.to_datetime(text, format=fmt, errors="coerce")
        except (ValueError, TypeError):
            continue
        count = int(candidate.notna().sum())
        if count > best_count:
            best, best_count = candidate, count
    if best is None or best_count * 2 < len(text):
        raise FxtmError(f"Cannot read the time column (first value: {text.iloc[0]!r}).")
    parsed = best
    if parsed.dt.tz is not None:
        return parsed.dt.tz_convert("UTC")
    return parsed.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")


def read_tick_csv(path, timezone: str = "UTC") -> pd.DataFrame:
    """Read a tick CSV into a tick table (UTC, sorted)."""
    path = Path(path)
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()
    if not first_line.strip():
        raise FxtmError(f"{path.name} is empty.")
    delimiter = max((",", ";", "\t"), key=first_line.count)
    if first_line.count(delimiter) == 0:
        raise FxtmError(f"{path.name}: no comma, semicolon or tab separated columns found.")
    names = [_norm(n) for n in first_line.strip().split(delimiter)]
    has_header = any(n in alias for n in names for alias in _ALIASES.values())
    raw = pd.read_csv(path, sep=delimiter, header=0 if has_header else None, dtype=str,
                      encoding="utf-8-sig", encoding_errors="replace")
    if has_header:
        columns = {}
        for original in raw.columns:
            for key, alias in _ALIASES.items():
                if _norm(original) in alias and key not in columns:
                    columns[key] = original
    else:
        columns = {key: raw.columns[i] for i, key in enumerate(_POSITIONAL) if i < len(raw.columns)}
    missing = [k for k in ("time", "ask", "bid") if k not in columns]
    if missing:
        raise FxtmError(f"{path.name}: no {'/'.join(missing)} column found (columns: {', '.join(map(str, raw.columns))}).")

    times = _parse_times(raw[columns["time"]], timezone)
    frame = pd.DataFrame({
        "time": times,
        "bid": pd.to_numeric(raw[columns["bid"]], errors="coerce"),
        "ask": pd.to_numeric(raw[columns["ask"]], errors="coerce"),
        "bid_vol": pd.to_numeric(raw[columns["bid_vol"]], errors="coerce") if "bid_vol" in columns else 0.0,
        "ask_vol": pd.to_numeric(raw[columns["ask_vol"]], errors="coerce") if "ask_vol" in columns else 0.0,
    })
    frame = frame.dropna(subset=["time", "bid", "ask"])
    if frame.empty:
        raise FxtmError(f"{path.name}: no usable rows (check the time zone and the column order).")
    if float((frame["ask"] - frame["bid"]).median()) < 0:
        raise FxtmError("The Ask is lower than the Bid in most rows: the Bid and Ask columns may be swapped.")
    frame = frame.sort_values("time", kind="stable").reset_index(drop=True)
    frame[["bid_vol", "ask_vol"]] = frame[["bid_vol", "ask_vol"]].fillna(0.0)
    return make_ticks(time_ns(frame), frame["bid"], frame["ask"], frame["bid_vol"], frame["ask_vol"])


def _dataset_dir(data_dir, symbol: str) -> Path:
    return Path(data_dir) / "imports" / normalize_symbol(symbol)


def import_file(data_dir, symbol: str, path, timezone: str = "UTC") -> dict:
    """Read a CSV and keep it as a dataset of this pair. Returns its description."""
    sym = normalize_symbol(symbol)
    ticks = read_tick_csv(path, timezone)
    first, last = ticks["time"].iloc[0], ticks["time"].iloc[-1]
    fmt = "parquet" if has_pyarrow() else "csv.gz"
    target = _dataset_dir(data_dir, sym) / f"{first:%Y%m%dT%H%M%S}_{last:%Y%m%dT%H%M%S}_{len(ticks)}.{fmt}"
    write_ticks(target, ticks, fmt)
    return {"symbol": sym, "first": first, "last": last, "ticks": len(ticks), "path": str(target)}


def list_datasets(data_dir, symbol: str | None = None) -> list[dict]:
    root = Path(data_dir) / "imports"
    folders = [root / normalize_symbol(symbol)] if symbol else sorted(root.glob("*")) if root.exists() else []
    found = []
    for folder in folders:
        for file in sorted(folder.glob("*")) if folder.exists() else []:
            match = _DATASET.match(file.name)
            if match:
                found.append({
                    "symbol": folder.name,
                    "first": pd.Timestamp(match.group(1), tz="UTC"),
                    "last": pd.Timestamp(match.group(2), tz="UTC"),
                    "ticks": int(match.group(3)),
                    "path": str(file),
                })
    return found


class ImportedProvider:
    """Serves ticks from the datasets you imported. Nothing is downloaded or cached again."""

    name = "imported"
    cacheable = False  # a dataset can cover part of a day, so a day must never be remembered as complete

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def fetch_ticks(self, symbol: str, start, end) -> pd.DataFrame:
        start_ts, end_ts = pd.Timestamp(to_utc(start)), pd.Timestamp(to_utc(end))
        frames = []
        for dataset in list_datasets(self.data_dir, symbol):
            if dataset["last"] >= start_ts and dataset["first"] < end_ts:
                frames.append(read_ticks(Path(dataset["path"])))
        if not frames:
            return empty_ticks()
        ticks = pd.concat(frames, ignore_index=True)
        ticks = ticks[(ticks["time"] >= start_ts) & (ticks["time"] < end_ts)]
        ticks = ticks.drop_duplicates(subset=["time", "bid", "ask"])
        return ticks.sort_values("time", kind="stable").reset_index(drop=True)
