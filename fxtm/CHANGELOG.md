# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

First public version.

### Added
- Tick download from Dukascopy's public historical feed (no account), UTC time everywhere, local cache
  (Parquet, or gzip CSV when pyarrow is missing).
- Candles from ticks (1m, 5m, 15m, 1h, 1d) and a replay clock that never exposes future ticks.
- Virtual broker: market, limit and stop orders, stop-loss and take-profit, partial close, Bid/Ask fills,
  gap-aware stop fills, optional slippage and order delay, margin, stop-out, account currency conversion.
- Equity curve, maximum drawdown, trade statistics, SQLite history of runs with the conditions they used.
- What-if comparison of the same manual trades under different leverage, spread and slippage.
- Browser app (`fxtm serve`): chart, replay controls, order ticket, positions, history, report; English and Japanese.
- Command line tools: `fxtm serve`, `fxtm fetch`, `fxtm candles`.

### Known limitations
- No swap/rollover or commission. Daily candles roll at 00:00 UTC. Sessions only move forward.
- Not yet verified against live Dukascopy downloads by the project's own tests (they use synthetic data).
