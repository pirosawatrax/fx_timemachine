"""Virtual broker: orders, positions, margin and stop-out.

Execution rules (all deterministic, so the same input always gives the same result)
----------------------------------------------------------------------------------
* Buys fill at the Ask, sells at the Bid. Closing a long uses the Bid, a short the Ask.
* ``slippage`` (price units) is added against the trader on market fills, buy/sell
  stop fills, stop-loss fills and stop-out closes. Gaps need no extra rule: a stop or
  stop-loss fills at the first quote beyond its level, which is worse than the level.
* Limit orders and take-profits fill at their own price once the market touches it
  (no price improvement). A limit that is already marketable when placed fills at
  the current quote.
* ``latency`` delays market orders: they fill at the first tick at or after
  ``order time + latency``. Closes are immediate.
* Positions are independent (hedging); every fill opens its own position.
* Margin = units * mid price * (quote currency -> account currency) / leverage.
  Equity = balance + unrealized P&L. When equity / used margin falls below
  ``stop_out_level``, the worst losing position is closed, repeatedly.
* Swap/rollover and commissions are not modelled; the spread is the only cost.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

import pandas as pd

from fxtm.ticks import FxtmError, normalize_symbol

_UNSET = object()


class BrokerError(FxtmError):
    """The broker cannot do what was asked (missing rate, no quote, ...)."""


class OrderError(BrokerError):
    """An order or modification was rejected."""


def split_symbol(symbol: str) -> tuple[str, str]:
    sym = normalize_symbol(symbol)
    if len(sym) != 6:
        raise OrderError(f"expected a 6-letter currency pair, got {symbol!r}")
    return sym[:3], sym[3:]


def fixed_rates(account_currency: str, rates: dict[str, float]) -> Callable[[str], float]:
    """Constant conversion rates: ``rates[ccy]`` = account currency per 1 ccy."""
    account = account_currency.upper()

    def rate(currency: str) -> float:
        if currency == account:
            return 1.0
        try:
            return float(rates[currency])
        except KeyError:
            raise BrokerError(f"no conversion rate {currency}->{account}") from None

    return rate


def replay_rates(account_currency: str, replays: dict) -> Callable[[str], float]:
    """Conversion from the mid price of other replays, e.g. {"CHFJPY": replay}.

    The replays must be advanced together with the traded one by the caller.
    Both CCYACC and ACCCCY pairs are understood.
    """
    account = account_currency.upper()
    by_symbol = {normalize_symbol(k): v for k, v in replays.items()}

    def mid(symbol: str):
        replay = by_symbol.get(symbol)
        quote = replay.quote() if replay is not None else None
        return None if quote is None else (quote[0] + quote[1]) / 2

    def rate(currency: str) -> float:
        if currency == account:
            return 1.0
        direct = mid(f"{currency}{account}")
        if direct is not None:
            return direct
        inverse = mid(f"{account}{currency}")
        if inverse is not None:
            return 1.0 / inverse
        raise BrokerError(f"no quote available to convert {currency}->{account}")

    return rate


@dataclass
class AccountConfig:
    currency: str = "JPY"
    initial_balance: float = 1_000_000.0
    leverage: float = 25.0
    stop_out_level: float = 1.0  # equity / used margin, 1.0 = 100%
    slippage: float = 0.0
    latency: timedelta = timedelta(0)


@dataclass
class Order:
    id: int
    symbol: str
    side: str
    units: float
    kind: str  # market | limit | stop
    price: float | None
    sl: float | None
    tp: float | None
    created: pd.Timestamp
    activate_at: pd.Timestamp
    status: str = "pending"  # pending | filled | cancelled | rejected
    position_id: int | None = None
    note: str = ""


@dataclass
class Position:
    id: int
    symbol: str
    side: str
    units: float
    open_price: float
    open_time: pd.Timestamp
    sl: float | None
    tp: float | None


@dataclass
class Trade:
    id: int  # id of the position it belongs to (partial closes share it)
    symbol: str
    side: str
    units: float
    open_price: float
    open_time: pd.Timestamp
    close_price: float
    close_time: pd.Timestamp
    reason: str  # manual | sl | tp | stopout
    pnl: float  # account currency


@dataclass
class Event:
    time: pd.Timestamp
    kind: str  # open | close | pending | cancel | rejected | modify
    symbol: str
    price: float | None
    units: float
    ref: int
    note: str = ""


class Broker:
    def __init__(self, config: AccountConfig | None = None, rates: Callable[[str], float] | None = None):
        self.config = config or AccountConfig()
        self._rates = rates or fixed_rates(self.config.currency, {})
        self.balance = float(self.config.initial_balance)
        self.positions: dict[int, Position] = {}
        self.all_orders: list[Order] = []
        self.trades: list[Trade] = []
        self.events: list[Event] = []
        self._quotes: dict[str, tuple[float, float, pd.Timestamp]] = {}
        self._next_id = 1

    # ---- account state -------------------------------------------------
    @property
    def pending_orders(self) -> list[Order]:
        return [o for o in self.all_orders if o.status == "pending"]

    def _quote(self, symbol: str) -> tuple[float, float, pd.Timestamp]:
        quote = self._quotes.get(symbol)
        if quote is None:
            raise OrderError(f"no quote yet for {symbol}")
        return quote

    def _rate(self, symbol: str) -> float:
        return self._rates(split_symbol(symbol)[1])

    def unrealized(self, pos: Position) -> float:
        bid, ask, _ = self._quote(pos.symbol)
        per_unit = bid - pos.open_price if pos.side == "buy" else pos.open_price - ask
        return per_unit * pos.units * self._rate(pos.symbol)

    def _margin_for(self, symbol: str, units: float) -> float:
        bid, ask, _ = self._quote(symbol)
        return units * (bid + ask) / 2 * self._rate(symbol) / self.config.leverage

    def margin_required(self, symbol: str, units: float) -> float:
        """Margin (account currency) a position of ``units`` would need at the current price."""
        return self._margin_for(normalize_symbol(symbol), units)

    def used_margin(self) -> float:
        return sum(self._margin_for(p.symbol, p.units) for p in self.positions.values())

    def equity(self) -> float:
        return self.balance + sum(self.unrealized(p) for p in self.positions.values())

    def free_margin(self) -> float:
        return self.equity() - self.used_margin()

    def margin_level(self) -> float:
        used = self.used_margin()
        return float("inf") if used == 0 else self.equity() / used

    def summary(self) -> dict:
        return {
            "balance": self.balance,
            "equity": self.equity(),
            "used_margin": self.used_margin(),
            "free_margin": self.free_margin(),
            "margin_level": self.margin_level(),
        }

    # ---- internals -------------------------------------------------------
    def _new_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    def _log(self, t, kind, symbol, price, units, ref, note="") -> Event:
        event = Event(t, kind, symbol, price, units, ref, note)
        self.events.append(event)
        return event

    def _slip(self, side_of_trader: str) -> float:
        """Signed price adjustment against the trader (+ for buys, - for sells)."""
        s = self.config.slippage
        return s if side_of_trader == "buy" else -s

    def _open(self, order: Order, price: float, t: pd.Timestamp) -> Position:
        required = self._margin_for(order.symbol, order.units)
        if self.free_margin() < required:
            raise OrderError(
                f"insufficient margin: need {required:,.2f}, free {self.free_margin():,.2f}"
            )
        pos = Position(self._new_id(), order.symbol, order.side, order.units, price, t, order.sl, order.tp)
        self.positions[pos.id] = pos
        order.status, order.position_id = "filled", pos.id
        self._log(t, "open", pos.symbol, price, pos.units, pos.id, f"order {order.id} {order.kind}")
        return pos

    def _fill(self, order: Order, price: float, t: pd.Timestamp) -> None:
        try:
            self._open(order, price, t)
        except OrderError as exc:
            order.status, order.note = "rejected", str(exc)
            self._log(t, "rejected", order.symbol, price, order.units, order.id, str(exc))

    def _close(self, pos: Position, units: float, price: float, t: pd.Timestamp, reason: str) -> Trade:
        per_unit = price - pos.open_price if pos.side == "buy" else pos.open_price - price
        pnl = per_unit * units * self._rate(pos.symbol)
        self.balance += pnl
        trade = Trade(pos.id, pos.symbol, pos.side, units, pos.open_price, pos.open_time, price, t, reason, pnl)
        self.trades.append(trade)
        if units >= pos.units:
            del self.positions[pos.id]
        else:
            pos.units -= units
        self._log(t, "close", pos.symbol, price, units, pos.id, reason)
        return trade

    def _exit_price(self, pos: Position, slipped: bool = True) -> float:
        bid, ask, _ = self._quote(pos.symbol)
        if pos.side == "buy":  # a long closes by selling
            return bid + (self._slip("sell") if slipped else 0.0)
        return ask + (self._slip("buy") if slipped else 0.0)

    # ---- commands --------------------------------------------------------
    def place_order(self, symbol: str, side: str, units: float, kind: str = "market",
                    price: float | None = None, sl: float | None = None, tp: float | None = None) -> Order:
        sym = normalize_symbol(symbol)
        split_symbol(sym)
        if side not in ("buy", "sell"):
            raise OrderError("side must be 'buy' or 'sell'")
        if units <= 0:
            raise OrderError("units must be positive")
        if kind not in ("market", "limit", "stop"):
            raise OrderError("kind must be market, limit or stop")
        if kind != "market" and price is None:
            raise OrderError(f"a {kind} order needs a price")
        bid, ask, now = self._quote(sym)
        buy = side == "buy"
        marketable = False
        if kind == "limit":
            marketable = price >= ask if buy else price <= bid
        elif kind == "stop":
            if (buy and price <= ask) or (not buy and price >= bid):
                raise OrderError(f"{side} stop must be {'above the ask' if buy else 'below the bid'}")
        ref = price if kind != "market" and not marketable else (ask if buy else bid)
        if sl is not None and (sl >= ref if buy else sl <= ref):
            raise OrderError("stop-loss is on the wrong side of the entry price")
        if tp is not None and (tp <= ref if buy else tp >= ref):
            raise OrderError("take-profit is on the wrong side of the entry price")

        order = Order(self._new_id(), sym, side, units, kind, price, sl, tp, now, now)
        self.all_orders.append(order)
        immediate = marketable or (kind == "market" and self.config.latency <= timedelta(0))
        if immediate:
            fill_price = (ask if buy else bid)
            if kind == "market":
                fill_price += self._slip(side)
            try:
                self._open(order, fill_price, now)
            except OrderError:
                self.all_orders.remove(order)
                raise
        else:
            if kind == "market":
                order.activate_at = now + self.config.latency
            self._log(now, "pending", sym, price, units, order.id, f"{side} {kind}")
        return order

    def market(self, symbol, side, units, sl=None, tp=None) -> Order:
        return self.place_order(symbol, side, units, "market", None, sl, tp)

    def limit(self, symbol, side, units, price, sl=None, tp=None) -> Order:
        return self.place_order(symbol, side, units, "limit", price, sl, tp)

    def stop(self, symbol, side, units, price, sl=None, tp=None) -> Order:
        return self.place_order(symbol, side, units, "stop", price, sl, tp)

    def cancel(self, order_id: int) -> None:
        for order in self.pending_orders:
            if order.id == order_id:
                order.status = "cancelled"
                self._log(self._quote(order.symbol)[2], "cancel", order.symbol, order.price, order.units, order.id)
                return
        raise OrderError(f"no pending order with id {order_id}")

    def close(self, position_id: int, units: float | None = None) -> Trade:
        pos = self.positions.get(position_id)
        if pos is None:
            raise OrderError(f"no open position with id {position_id}")
        units = pos.units if units is None else units
        if not 0 < units <= pos.units:
            raise OrderError("units must be between 0 and the position size")
        t = self._quote(pos.symbol)[2]
        return self._close(pos, units, self._exit_price(pos), t, "manual")

    def modify(self, position_id: int, sl=_UNSET, tp=_UNSET) -> Position:
        """Change stop-loss / take-profit. Pass None to remove one."""
        pos = self.positions.get(position_id)
        if pos is None:
            raise OrderError(f"no open position with id {position_id}")
        bid, ask, t = self._quote(pos.symbol)
        long = pos.side == "buy"
        new_sl = pos.sl if sl is _UNSET else sl
        new_tp = pos.tp if tp is _UNSET else tp
        if new_sl is not None and (new_sl >= bid if long else new_sl <= ask):
            raise OrderError("stop-loss is on the wrong side of the market")
        if new_tp is not None and (new_tp <= bid if long else new_tp >= ask):
            raise OrderError("take-profit is on the wrong side of the market")
        pos.sl, pos.tp = new_sl, new_tp
        self._log(t, "modify", pos.symbol, None, pos.units, pos.id, f"sl={new_sl} tp={new_tp}")
        return pos

    # ---- market data -----------------------------------------------------
    def on_tick(self, symbol: str, time, bid: float, ask: float) -> list[Event]:
        """Feed one tick (in time order). Returns the events it caused."""
        sym = normalize_symbol(symbol)
        t = pd.Timestamp(time)
        self._quotes[sym] = (bid, ask, t)
        first = len(self.events)
        for order in self.pending_orders:
            if order.symbol == sym and t >= order.activate_at:
                self._try_fill(order, bid, ask, t)
        for pos in list(self.positions.values()):
            if pos.symbol == sym:
                self._check_exit(pos, bid, ask, t)
        self._check_stop_out(t)
        return self.events[first:]

    def _try_fill(self, order: Order, bid: float, ask: float, t: pd.Timestamp) -> None:
        buy = order.side == "buy"
        if order.kind == "market":
            self._fill(order, (ask if buy else bid) + self._slip(order.side), t)
        elif order.kind == "limit":
            if (buy and ask <= order.price) or (not buy and bid >= order.price):
                self._fill(order, order.price, t)
        else:  # stop
            if buy and ask >= order.price:
                self._fill(order, ask + self._slip("buy"), t)
            elif not buy and bid <= order.price:
                self._fill(order, bid + self._slip("sell"), t)

    def _check_exit(self, pos: Position, bid: float, ask: float, t: pd.Timestamp) -> None:
        if pos.side == "buy":
            if pos.sl is not None and bid <= pos.sl:
                self._close(pos, pos.units, bid + self._slip("sell"), t, "sl")
            elif pos.tp is not None and bid >= pos.tp:
                self._close(pos, pos.units, pos.tp, t, "tp")
        else:
            if pos.sl is not None and ask >= pos.sl:
                self._close(pos, pos.units, ask + self._slip("buy"), t, "sl")
            elif pos.tp is not None and ask <= pos.tp:
                self._close(pos, pos.units, pos.tp, t, "tp")

    def _check_stop_out(self, t: pd.Timestamp) -> None:
        while self.positions and self.margin_level() < self.config.stop_out_level:
            worst = min(self.positions.values(), key=self.unrealized)
            self._close(worst, worst.units, self._exit_price(worst), t, "stopout")
