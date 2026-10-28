"""Replay + broker glued together.

Every tick the replay reveals is fed to the broker in order, so stop-losses,
limits and stop-outs trigger exactly when they would have. The session only
moves forward: the broker cannot undo trades, so there is no seek backwards.
An optional ``EquityRecorder`` samples the account while the replay runs.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from fxtm.broker import Broker, Event
from fxtm.replay import Replay
from fxtm.ticks import normalize_symbol, to_utc


class Session:
    def __init__(self, replay: Replay, broker: Broker, symbol: str, recorder=None, aux=()):
        """``aux`` are extra replays (e.g. a conversion pair) kept on the main clock."""
        self.replay = replay
        self.broker = broker
        self.symbol = normalize_symbol(symbol)
        self.recorder = recorder
        self.aux = list(aux)
        visible = replay.visible_ticks()
        if not visible.empty:
            last = visible.iloc[-1]
            self._on_tick(last["time"], last["bid"], last["ask"])

    def _on_tick(self, t, bid, ask) -> list[Event]:
        for other in self.aux:
            other.seek(t)
        events = self.broker.on_tick(self.symbol, t, bid, ask)
        if self.recorder is not None:
            self.recorder.observe(self.broker, pd.Timestamp(t), force=bool(events))
        return events

    def _feed(self, ticks: pd.DataFrame) -> list[Event]:
        events: list[Event] = []
        for t, bid, ask in zip(ticks["time"].tolist(), ticks["bid"].tolist(), ticks["ask"].tolist()):
            events.extend(self._on_tick(t, bid, ask))
        return events

    def advance(self, delta) -> list[Event]:
        return self._feed(self.replay.advance(delta))

    def advance_wall(self, wall_seconds: float, speed: float = 1.0) -> list[Event]:
        return self._feed(self.replay.advance_wall(wall_seconds, speed))

    def run_until(self, when) -> list[Event]:
        delta = pd.Timestamp(to_utc(when)) - self.replay.now
        if delta < timedelta(0):
            raise ValueError("a session cannot go back in time")
        return self.advance(delta)

    def next_tick(self) -> list[Event]:
        row = self.replay.next_tick()
        if row is None:
            return []
        return self._on_tick(row["time"], row["bid"], row["ask"])
