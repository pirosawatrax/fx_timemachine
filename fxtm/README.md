# FX Time Machine (fxtm)  "FX Warrior Milk-chan"

Replay the forex market of any past moment and practice trading it with virtual money. Free, MIT licensed,
no accounts, runs on your own computer and works offline once the data is downloaded.

[日本語のREADME](README.ja.md)

![The chart with an open position, replaying generated demo data](docs/images/screenshot.png)

*Screenshot with generated demo data, not real prices.*

## What you can do

- Pick a currency pair and a period (for example EUR/CHF on 15 Jan 2015) and watch it unfold tick by tick.
- Trade it with market, limit and stop orders, stop-loss and take-profit, leverage and stop-out.
- See profit and loss in your account currency, the equity curve, maximum drawdown and win rate.
- Change the spread, slippage or leverage and compare how the same trades would have ended.
- Replay never shows the future: the candle being formed only contains ticks up to the replay clock.

fxtm is for learning and research. It cannot place real orders.

## Install

You need Python 3.10 or newer.

```bash
git clone <this repository>
cd fxtm
pip install .
```

## Start

```bash
fxtm serve
```

This opens http://127.0.0.1:8765/ in your browser. Choose a pair and a UTC period, press
"Load data and start", then press Play. The first load downloads ticks from Dukascopy's public historical feed
to your computer; after that the same days load from disk.

Controls: mouse wheel zooms, dragging pans, double click returns to the latest candle, Space plays or pauses.
Times are UTC in the data; the header switches the display time zone (UTC, Tokyo, London, New York) and the
language (English, Japanese).

Other commands:

```bash
fxtm serve --port 9000 --no-browser     # another port, do not open a tab
fxtm fetch EUR/CHF 2015-01-15           # download and cache one UTC day
fxtm candles EUR/CHF 2015-01-15 --tf 5m # print candles (or --out file.csv)
fxtm import export.csv EUR/CHF          # use a tick CSV you downloaded yourself
fxtm imports                            # list imported datasets
python -m fxtm --version
```

Downloaded data and saved runs live in your user data folder (`~/.local/share/fxtm` on Linux,
`~/Library/Application Support/fxtm` on macOS, `%LOCALAPPDATA%\fxtm` on Windows). Set `FXTM_DATA_DIR` or use
`--data-dir` to put them elsewhere.

## If the download does not work

Dukascopy's free historical feed has been unreliable since July 2026: independent projects report timeouts,
HTTP 503 and, more recently, a bot-protection challenge (HTTP 202) that blocks scripts while a normal browser
can still get through. The data format itself has not changed. fxtm retries, tells you which of these
happened, and never stores an empty weekday as if the market had been quiet. Each hour that downloads
correctly is kept (in the `raw` folder of the data directory) and hours that fail are retried in further
rounds, so if a few hours still fail, pressing start again continues from there instead of starting over. When the feed is down, use your
own data files.

### Your own data files

1. Export ticks to a CSV file yourself, for example in your browser from Dukascopy's historical data page, or
   with the `dukascopy-node` tool. Any CSV with a time, a bid and an ask column works. Headers such as
   `Gmt time,Ask,Bid,AskVolume,BidVolume` and `timestamp,askPrice,bidPrice` are recognised; without a header
   the order time, ask, bid, ask volume, bid volume is assumed. Times can be ISO, `15.01.2015 09:30:00.123`
   or epoch seconds/milliseconds.
2. In the browser app open "Your own data files", choose the file, say which time zone its times are in
   (UTC unless the export used another), and press "Import for the pair above". Or use the command line:

   ```bash
   fxtm import export.csv EUR/CHF --timezone UTC
   fxtm imports                      # list what you imported
   ```
3. Tick "Use my imported data" (clicking an imported dataset fills the pair and period for you) and start.

Imported files stay on your computer, are never uploaded anywhere, and are kept apart from downloaded data.
If your account currency differs from the pair's quote currency, either import the conversion pair too
(for example CHF/JPY) or enter a fixed conversion rate under "Trading conditions".

## How the simulation works

| Topic | Rule |
| --- | --- |
| Fills | Buys fill at the Ask, sells at the Bid. Closing a long uses the Bid, a short the Ask. |
| Stop orders and stop-loss | Fill at the first quote beyond the level, so a price gap fills at the worse, gapped price. |
| Limit orders and take-profit | Fill at their own price once touched. A limit that is already marketable fills at the current quote. |
| Slippage and delay | Optional, set in "Trading conditions". Slippage works against you; delay postpones market orders. |
| Margin | units × mid price × conversion rate ÷ leverage. Equity = balance + floating profit. |
| Stop-out | When equity ÷ used margin drops below the stop-out level, the worst losing position is closed, repeatedly. |
| Currency conversion | Profit in the quote currency is converted with the live price of the conversion pair (for example CHF/JPY for an EUR/CHF trade on a yen account), or a fixed rate you enter. |
| Positions | Every fill is its own position (hedging); there is no netting. |
| Time | UTC everywhere inside. Daily candles roll at 00:00 UTC. |

The same ticks and the same orders always give the same result.

## Use it from Python

```python
from datetime import timedelta
from fxtm.analytics import EquityRecorder, format_report, performance
from fxtm.broker import AccountConfig, Broker, fixed_rates
from fxtm.providers import DukascopyProvider
from fxtm.replay import Replay
from fxtm.session import Session
from fxtm.store import TickStore, default_data_dir

store = TickStore(default_data_dir(), DukascopyProvider())
ticks = store.load("EUR/USD", "2024-03-04 08:00", "2024-03-04 12:00")

broker = Broker(AccountConfig(currency="USD", initial_balance=10_000, leverage=10), fixed_rates("USD", {}))
recorder = EquityRecorder(timedelta(seconds=60))
session = Session(Replay(ticks), broker, "EUR/USD", recorder)

broker.market("EURUSD", "buy", 10_000, sl=1.0800, tp=1.0900)
session.advance(3600)                       # one hour of market time
print(format_report(performance(broker, recorder)))
```

`fxtm.compare.compare_scenarios` runs the same scripted manual orders under different leverage, spread and
slippage; `fxtm.history.save_run` stores a run in SQLite together with the conditions it used.

## Data and legal

- The code is MIT licensed (see `LICENSE`). **Market data is not part of it.** It belongs to its provider and
  is subject to that provider's terms.
- fxtm never bundles or redistributes data. Your computer downloads it directly from Dukascopy's public
  historical feed and keeps it locally. Read Dukascopy's current terms of use before you use the data, and do
  not publish downloaded files.
- The feed is not an official API and may change or disappear. Data providers are replaceable
  (`fxtm/providers.py`).
- fxtm is not affiliated with or endorsed by Dukascopy.
- Simulated results are not real results. Spreads, fills, gaps and liquidity differ between brokers and data
  sources, especially in fast markets. Nothing here is investment advice.
- No telemetry: fxtm sends nothing anywhere except the downloads you start. The browser app listens on
  `127.0.0.1` only.

## Limitations

- No swap/rollover and no commission; the spread is the only cost.
- A session only moves forward. Use Restart to go back to the beginning (open trades are discarded; save the run first).
- A session covers at most 7 days of ticks.
- Prices have 5 decimals, or 3 for JPY quotes. Metals and other instruments are not supported yet.
- Dukascopy's data availability depends on the pair and the date. Weekends and holidays have no ticks.
- The online feed is currently unreliable (see "If the download does not work"); the project's tests use synthetic
  data, so the live feed is checked by hand before each release.

## Development

```bash
pip install -e .
python -m unittest discover -s tests -v
```

See `CONTRIBUTING.md`. Layout: `ticks.py` (time and tick tables), `providers.py` (download and decoding),
`store.py` (cache), `candles.py`, `replay.py`, `broker.py`, `session.py`, `analytics.py`, `history.py`,
`compare.py`, `webapp.py` and `web/` (the browser app, no external libraries).

## License

MIT. See `LICENSE`.
