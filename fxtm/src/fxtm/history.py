"""SQLite store for finished runs: settings, trades, events and the equity curve.

Every run keeps the conditions it was made under (data source, pair, period,
spread/leverage settings), so real data and simulated assumptions stay apart.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fxtm.analytics import EquityRecorder, trades_frame
from fxtm.broker import Broker

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, meta TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trades (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    position_id INTEGER, symbol TEXT, side TEXT, units REAL,
    open_time TEXT, open_price REAL, close_time TEXT, close_price REAL,
    reason TEXT, pnl REAL);
CREATE TABLE IF NOT EXISTS events (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    time TEXT, kind TEXT, symbol TEXT, price REAL, units REAL, ref INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS equity (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    time TEXT, balance REAL, equity REAL, used_margin REAL);
CREATE INDEX IF NOT EXISTS idx_trades_run ON trades(run_id);
CREATE INDEX IF NOT EXISTS idx_equity_run ON equity(run_id);
"""


def config_meta(broker: Broker, **extra) -> dict:
    """Settings of a broker as plain data, plus any extra context (provider, pair, period...)."""
    cfg = dataclasses.asdict(broker.config)
    cfg["latency"] = broker.config.latency.total_seconds()
    return {"account": cfg, **extra}


def _connect(path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def _iso(value) -> str | None:
    return None if value is None else pd.Timestamp(value).isoformat()


def save_run(path, broker: Broker, recorder: EquityRecorder | None = None, meta: dict | None = None) -> int:
    """Store a run and return its id."""
    meta = meta if meta is not None else config_meta(broker)
    conn = _connect(path)
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (created, meta) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), json.dumps(meta, default=str)),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, t.id, t.symbol, t.side, t.units, _iso(t.open_time), t.open_price,
              _iso(t.close_time), t.close_price, t.reason, t.pnl) for t in broker.trades],
        )
        conn.executemany(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
            [(run_id, _iso(e.time), e.kind, e.symbol, e.price, e.units, e.ref, e.note)
             for e in broker.events],
        )
        if recorder is not None:
            conn.executemany(
                "INSERT INTO equity VALUES (?,?,?,?,?)",
                [(run_id, _iso(r.time), r.balance, r.equity, r.used_margin)
                 for r in recorder.frame().itertuples(index=False)],
            )
    conn.close()
    return run_id


def _query(path, sql: str, params=()) -> pd.DataFrame:
    conn = _connect(path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def list_runs(path) -> pd.DataFrame:
    runs = _query(path, "SELECT id, created, meta FROM runs ORDER BY id")
    runs["meta"] = runs["meta"].map(json.loads)
    return runs


def load_trades(path, run_id: int) -> pd.DataFrame:
    df = _query(path, "SELECT * FROM trades WHERE run_id = ? ORDER BY rowid", (run_id,))
    for col in ("open_time", "close_time"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df.drop(columns="run_id")


def load_equity(path, run_id: int) -> pd.DataFrame:
    df = _query(path, "SELECT time, balance, equity, used_margin FROM equity WHERE run_id = ? ORDER BY rowid", (run_id,))
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def delete_run(path, run_id: int) -> None:
    conn = _connect(path)
    with conn:
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.close()
