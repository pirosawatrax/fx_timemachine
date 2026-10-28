"""Command line interface: ``serve``, ``fetch``, ``candles``, ``import`` and ``imports``."""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from fxtm import __version__
from fxtm.candles import PRICE_SOURCES, TIMEFRAMES, build_candles
from fxtm.providers import DukascopyProvider
from fxtm.store import TickStore, default_data_dir
from fxtm.ticks import FxtmError, to_utc


def _range(args):
    start = to_utc(args.start)
    end = to_utc(args.end) if args.end else start + timedelta(days=1)
    return start, end


def _store(args) -> TickStore:
    root = args.data_dir or default_data_dir()
    return TickStore(root, DukascopyProvider(cache_dir=Path(root) / "raw" / "dukascopy"))


def _cmd_fetch(args) -> int:
    start, end = _range(args)
    ticks = _store(args).load(
        args.symbol, start, end, refresh=args.refresh,
        progress=lambda day, n: print(f"{day}: {n} ticks"),
    )
    print(f"total {len(ticks)} ticks ({start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC)")
    return 0


def _cmd_candles(args) -> int:
    start, end = _range(args)
    ticks = _store(args).load(args.symbol, start, end)
    if ticks.empty:
        print("no ticks in this period (weekend, holiday, or no data from the provider)")
        return 1
    candles = build_candles(ticks, args.tf, args.price)
    if args.out:
        candles.to_csv(args.out, index=False)
        print(f"wrote {len(candles)} candles to {args.out}")
    else:
        print(candles.head(args.head).to_string(index=False))
    return 0


def _cmd_import(args) -> int:
    from fxtm.importer import import_file

    info = import_file(args.data_dir or default_data_dir(), args.symbol, args.file, args.timezone)
    print(f"imported {info['ticks']:,} ticks of {info['symbol']}: "
          f"{info['first']:%Y-%m-%d %H:%M:%S} to {info['last']:%Y-%m-%d %H:%M:%S} UTC")
    print("In the browser app, tick 'Use my imported data' (or use the same pair and period).")
    return 0


def _cmd_imports(args) -> int:
    from fxtm.importer import list_datasets

    datasets = list_datasets(args.data_dir or default_data_dir())
    if not datasets:
        print("no imported data yet (see: fxtm import --help)")
    for d in datasets:
        print(f"{d['symbol']}  {d['first']:%Y-%m-%d %H:%M:%S} to {d['last']:%Y-%m-%d %H:%M:%S} UTC  {d['ticks']:,} ticks")
    return 0


def _cmd_serve(args) -> int:
    from fxtm.webapp import serve  # imported lazily: the CLI works without the web app

    serve(args.data_dir or default_data_dir(), port=args.port, open_browser=not args.no_browser)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fxtm", description="FX Time Machine")
    parser.add_argument("--version", action="version", version=f"fxtm {__version__}")
    parser.add_argument("--data-dir", help="cache directory (default: $FXTM_DATA_DIR or XDG data dir)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_range(p):
        p.add_argument("symbol", help="currency pair, e.g. EUR/CHF")
        p.add_argument("start", help="UTC date or datetime, e.g. 2015-01-15")
        p.add_argument("end", nargs="?", help="end (exclusive); default: start + 1 day")

    serve = sub.add_parser("serve", help="start the browser app on this computer")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    serve.set_defaults(func=_cmd_serve)

    imp = sub.add_parser("import", help="import a tick CSV file you downloaded yourself")
    imp.add_argument("file", help="CSV with time, bid and ask columns")
    imp.add_argument("symbol", help="currency pair of the file, e.g. EUR/CHF")
    imp.add_argument("--timezone", default="UTC", help="time zone of the times in the file (default: UTC)")
    imp.set_defaults(func=_cmd_import)

    listing = sub.add_parser("imports", help="list imported datasets")
    listing.set_defaults(func=_cmd_imports)

    fetch = sub.add_parser("fetch", help="download and cache ticks")
    add_range(fetch)
    fetch.add_argument("--refresh", action="store_true", help="download again even if cached")
    fetch.set_defaults(func=_cmd_fetch)

    candles = sub.add_parser("candles", help="show or export candles")
    add_range(candles)
    candles.add_argument("--tf", choices=list(TIMEFRAMES), default="1m")
    candles.add_argument("--price", choices=PRICE_SOURCES, default="bid")
    candles.add_argument("--head", type=int, default=20)
    candles.add_argument("--out", help="write all candles to this CSV file")
    candles.set_defaults(func=_cmd_candles)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FxtmError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
