# Contributing

Thanks for helping. This is a learning and research tool, so correctness and clarity matter more than features.

## Setup

```bash
git clone <your fork>
cd fxtm
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -v
node --check src/fxtm/web/app.js                  # optional: syntax check of the browser code
```

## Rules the code must keep

1. **No look-ahead.** Nothing shown to the user may depend on ticks after the replay clock. Add a test when
   you touch `replay.py`, `candles.py` or `session.py`.
2. **Deterministic.** The same ticks and the same orders must give the same result.
3. **UTC inside.** Convert time zones at the edges (providers, display) only.
4. **Real data and assumptions stay apart.** Anything the simulator assumes (spread, slippage, fill rules)
   must be visible in the settings and stored with a saved run.
5. **Data providers are replaceable.** Keep provider-specific code in `providers.py`; the rest takes tick tables.
6. **Never bundle market data** and never commit downloaded files (see `.gitignore`).

## Style

- Code, comments and commit messages in English. UI text goes through the `I18N` table in `web/app.js`
  (English and Japanese).
- Standard library first; think twice before adding a dependency, because users install this on their own PCs.
- Tests use `unittest`; fake providers and synthetic ticks keep them fast and offline.

## Reporting data problems

If a download or a price looks wrong, include the pair, the UTC period, your OS and Python version, and the
error message. Please do not attach raw data from a provider.
