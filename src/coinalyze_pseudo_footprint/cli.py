from __future__ import annotations

import argparse
from pathlib import Path

from .allocator import build_pseudo_footprint
from .display import select_recent_display_window
from .loader import load_ohlcv
from .models import FootprintConfig
from .renderer import render_pseudo_footprint


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coinalyze-pseudo-footprint",
        description="Render OHLCV-based pseudo footprint from Coinalyze Receiver SQLite/CSV data.",
    )
    parser.add_argument("--input", required=True, help="Receiver SQLite DB or normalized OHLCV CSV")
    parser.add_argument("--output", default="out/pseudo_footprint.png", help="Output PNG path")
    parser.add_argument("--table", default=None, help="SQLite table name; auto-detects ohlcv_raw when omitted")
    parser.add_argument("--market-key", default=None, help="Internal market_key, e.g. binance:btcusdt_perp.a")
    parser.add_argument("--symbol", default=None, help="Fallback symbol filter when market_key is not available")
    parser.add_argument("--source-interval", default="1min", help="Source interval label stored in DB, default: 1min")
    parser.add_argument("--source-minutes", type=int, default=1, help="Source candle minutes, default: 1")
    parser.add_argument("--target-minutes", type=int, default=15, help="Target candle minutes, default: 15")
    parser.add_argument("--price-bin", type=float, default=10.0, help="Price bucket size, e.g. BTC=10 or 1")
    parser.add_argument("--bar-spacing", type=float, default=1.85, help="Horizontal spacing between target candles. Default 1.85")
    parser.add_argument("--candle-width", type=float, default=0.52, help="Candle body width. Default 0.52")
    parser.add_argument("--max-area-width", type=float, default=0.26, help="Max width of each side profile inside a candle slot. Default 0.26")
    parser.add_argument("--lookback-hours", type=float, default=6.0, help="Reserved for caller-side DB filtering/reporting")
    parser.add_argument(
        "--max-display-candles",
        type=int,
        default=14,
        help="Max target candles to render. Default 14 for readability. Use 0 to render all.",
    )
    parser.add_argument("--include-unfinished", action="store_true", help="Do not drop in-progress source candles")
    parser.add_argument("--title", default="OHLCV Pseudo Footprint")
    parser.add_argument("--limit", type=int, default=None, help="Optional max DB rows for smoke testing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = FootprintConfig(
        source_interval_minutes=args.source_minutes,
        target_interval_minutes=args.target_minutes,
        price_bin_size=args.price_bin,
        lookback_hours=args.lookback_hours,
        exclude_unfinished=not args.include_unfinished,
        max_display_candles=None if args.max_display_candles == 0 else args.max_display_candles,
        bar_spacing=args.bar_spacing,
        candle_width=args.candle_width,
        max_area_width=args.max_area_width,
    )

    df = load_ohlcv(
        args.input,
        market_key=args.market_key,
        symbol=args.symbol,
        interval=args.source_interval,
        table=args.table,
        limit=args.limit,
    )
    result = build_pseudo_footprint(df, config)
    display_candles, display_footprint, total_candles = select_recent_display_window(
        result.candles,
        result.footprint,
        max_candles=config.max_display_candles,
    )

    label = args.market_key or args.symbol or Path(args.input).stem
    window_note = (
        f" | display=last {len(display_candles)}/{total_candles} candles"
        if len(display_candles) != total_candles
        else ""
    )
    subtitle = (
        f"{label} | {args.source_interval} -> {args.target_minutes}min "
        f"| delta | bin={args.price_bin:g}{window_note}"
    )
    output = render_pseudo_footprint(
        display_candles,
        display_footprint,
        args.output,
        config=config,
        title=args.title,
        subtitle=subtitle,
    )

    print(
        "rendered="
        f"{output} candles={len(display_candles)}/{len(result.candles)} "
        f"footprint_bins={len(display_footprint)}/{len(result.footprint)} "
        f"source_rows={len(df)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
