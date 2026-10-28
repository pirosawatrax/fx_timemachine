"""Trade history, equity curve and performance statistics."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from fxtm.broker import Broker

TRADE_COLUMNS = [
    "id", "symbol", "side", "units", "open_time", "open_price",
    "close_time", "close_price", "reason", "pnl", "holding",
]
EQUITY_COLUMNS = ["time", "balance", "equity", "used_margin"]


class EquityRecorder:
    """Samples balance / equity / margin at most once per ``interval``.

    A sample is also forced whenever the broker reports an event (fill, close,
    stop-out). Drawdown is measured on these samples, so a dip that starts and
    ends between two samples is missed; use ``interval=timedelta(0)`` to sample
    every tick (slower).
    """

    def __init__(self, interval: timedelta = timedelta(seconds=60)):
        self.interval = interval
        self._rows: list[tuple] = []
        self._last: pd.Timestamp | None = None

    def observe(self, broker: Broker, t: pd.Timestamp, force: bool = False) -> None:
        if not force and self._last is not None and t - self._last < self.interval:
            return
        self._rows.append((t, broker.balance, broker.equity(), broker.used_margin()))
        self._last = t

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows, columns=EQUITY_COLUMNS)


def trades_frame(broker: Broker) -> pd.DataFrame:
    """Closed trades (a partial close is its own row)."""
    rows = [
        (t.id, t.symbol, t.side, t.units, t.open_time, t.open_price,
         t.close_time, t.close_price, t.reason, t.pnl, t.close_time - t.open_time)
        for t in broker.trades
    ]
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


def max_drawdown(equity: pd.Series) -> dict:
    """Largest peak-to-trough fall of an equity series (index = time)."""
    if equity.empty:
        return {"abs": 0.0, "pct": 0.0, "peak": None, "trough": None,
                "peak_time": None, "trough_time": None}
    running_max = equity.cummax()
    drawdown = running_max - equity
    i = int(drawdown.to_numpy().argmax())
    peak = float(running_max.iloc[i])
    peak_time = equity.iloc[: i + 1].idxmax()
    return {
        "abs": float(drawdown.iloc[i]),
        "pct": float(drawdown.iloc[i] / peak * 100) if peak > 0 else 0.0,
        "peak": peak,
        "trough": float(equity.iloc[i]),
        "peak_time": peak_time,
        "trough_time": equity.index[i],
    }


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": None, "total_pnl": 0.0,
                "avg_win": None, "avg_loss": None, "profit_factor": None,
                "best": None, "worst": None, "avg_holding": None}
    pnl = trades["pnl"]
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    if losses.empty:
        profit_factor = float("inf") if not wins.empty else None
    else:
        profit_factor = float(wins.sum() / -losses.sum())
    return {
        "trades": int(len(trades)),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": float(len(wins) / len(trades)),
        "total_pnl": float(pnl.sum()),
        "avg_win": float(wins.mean()) if not wins.empty else None,
        "avg_loss": float(losses.mean()) if not losses.empty else None,
        "profit_factor": profit_factor,
        "best": float(pnl.max()),
        "worst": float(pnl.min()),
        "avg_holding": trades["holding"].mean(),
    }


def performance(broker: Broker, recorder: EquityRecorder | None = None) -> dict:
    """One dictionary with the headline numbers of a run."""
    start = broker.config.initial_balance
    equity = broker.equity() if broker._quotes else broker.balance
    curve = recorder.frame() if recorder is not None else pd.DataFrame(columns=EQUITY_COLUMNS)
    series = curve.set_index("time")["equity"] if not curve.empty else pd.Series(dtype="float64")
    return {
        "currency": broker.config.currency,
        "initial_balance": start,
        "final_balance": broker.balance,
        "final_equity": equity,
        "return_pct": (equity - start) / start * 100,
        "max_drawdown": max_drawdown(series),
        "stats": trade_stats(trades_frame(broker)),
        "stop_outs": sum(1 for t in broker.trades if t.reason == "stopout"),
        "rejected_orders": sum(1 for o in broker.all_orders if o.status == "rejected"),
    }


def format_report(perf: dict) -> str:
    cur, st, dd = perf["currency"], perf["stats"], perf["max_drawdown"]
    lines = [
        f"Balance: {perf['initial_balance']:,.2f} -> {perf['final_balance']:,.2f} {cur}",
        f"Equity: {perf['final_equity']:,.2f} {cur} ({perf['return_pct']:+.2f}%)",
        f"Max drawdown: {dd['abs']:,.2f} {cur} ({dd['pct']:.2f}%)",
        f"Trades: {st['trades']}  wins {st['wins']}  losses {st['losses']}"
        + (f"  win rate {st['win_rate']:.0%}" if st["win_rate"] is not None else ""),
        f"Total P&L: {st['total_pnl']:,.2f} {cur}",
    ]
    if st["profit_factor"] is not None:
        lines.append(f"Profit factor: {st['profit_factor']:.2f}")
    if st["avg_holding"] is not None:
        lines.append(f"Average holding time: {st['avg_holding']}")
    lines.append(f"Stop-outs: {perf['stop_outs']}  Rejected orders: {perf['rejected_orders']}")
    return "\n".join(lines)
