"""What-if comparison: run the same manual trades under different conditions.

Orders are scripted by time (they are what the user did or planned by hand);
nothing here decides to trade by itself. Each scenario changes leverage, spread
or slippage and everything else stays identical, so the differences are caused
by the conditions alone.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from fxtm.analytics import EquityRecorder, performance
from fxtm.broker import AccountConfig, Broker, OrderError, fixed_rates
from fxtm.replay import Replay
from fxtm.session import Session
from fxtm.ticks import to_utc


@dataclass
class ScriptedOrder:
    time: object  # anything to_utc accepts
    side: str
    units: float
    kind: str = "market"
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    close_at: object | None = None  # close the resulting position at this time


@dataclass
class RunResult:
    broker: Broker
    recorder: EquityRecorder
    rejections: list[str] = field(default_factory=list)

    def performance(self) -> dict:
        return performance(self.broker, self.recorder)


def widen_spread(ticks: pd.DataFrame, extra: float) -> pd.DataFrame:
    """Add ``extra`` (price units) to the spread, half on each side of the mid."""
    if extra == 0:
        return ticks
    widened = ticks.copy()
    widened["bid"] = widened["bid"] - extra / 2
    widened["ask"] = widened["ask"] + extra / 2
    return widened


def run_scenario(ticks: pd.DataFrame, symbol: str, orders: list[ScriptedOrder], config: AccountConfig,
                 rates: Callable[[str], float] | None = None, extra_spread: float = 0.0,
                 interval=None) -> RunResult:
    ticks = widen_spread(ticks, extra_spread)
    broker = Broker(config, rates or fixed_rates(config.currency, {}))
    recorder = EquityRecorder(interval) if interval is not None else EquityRecorder()
    replay = Replay(ticks)
    session = Session(replay, broker, symbol, recorder)

    actions = []  # (time, sequence, kind, payload)
    for n, order in enumerate(orders):
        actions.append((pd.Timestamp(to_utc(order.time)), 2 * n, "open", order))
        if order.close_at is not None:
            close_time = pd.Timestamp(to_utc(order.close_at))
            actions.append((close_time, 2 * n + 1, "close", order))
    actions.sort(key=lambda a: (a[0], a[1]))

    placed: dict[int, object] = {}
    rejections: list[str] = []
    for when, seq, kind, order in actions:
        if when > replay.now:
            session.run_until(when)
        if kind == "open":
            try:
                placed[id(order)] = broker.place_order(
                    symbol, order.side, order.units, order.kind, order.price, order.sl, order.tp)
            except OrderError as exc:
                rejections.append(f"{when}: {exc}")
        else:
            placed_order = placed.get(id(order))
            if placed_order is not None and placed_order.position_id in broker.positions:
                broker.close(placed_order.position_id)
    session.run_until(replay.end)
    recorder.observe(broker, replay.now, force=True)
    return RunResult(broker, recorder, rejections)


def compare_scenarios(ticks: pd.DataFrame, symbol: str, orders: list[ScriptedOrder],
                      base_config: AccountConfig, scenarios: dict[str, dict],
                      rates: Callable[[str], float] | None = None) -> pd.DataFrame:
    """Run every scenario and tabulate the results.

    ``scenarios`` maps a name to overrides: any AccountConfig field
    (``leverage``, ``slippage``, ``latency``, ``stop_out_level``...) and/or
    ``extra_spread`` (added to the data's spread, in price units).
    """
    rows = {}
    for name, overrides in scenarios.items():
        overrides = dict(overrides)
        extra_spread = overrides.pop("extra_spread", 0.0)
        config = dataclasses.replace(base_config, **overrides)
        result = run_scenario(ticks, symbol, orders, config, rates, extra_spread)
        perf = result.performance()
        rows[name] = {
            "final_equity": perf["final_equity"],
            "return_pct": perf["return_pct"],
            "total_pnl": perf["stats"]["total_pnl"],
            "max_dd_pct": perf["max_drawdown"]["pct"],
            "max_dd_abs": perf["max_drawdown"]["abs"],
            "trades": perf["stats"]["trades"],
            "stop_outs": perf["stop_outs"],
            "rejected": perf["rejected_orders"] + len(result.rejections),
        }
    return pd.DataFrame.from_dict(rows, orient="index")
