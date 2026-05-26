"""CLI entry point for coinalyze-pseudo-footprint."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .allocator import build_pseudo_footprint
from .display import select_recent_display_window
from .loader import load_ohlcv, load_open_interest
from .models import FootprintConfig
from .renderer import render_pseudo_footprint


# Coinalyze exchange code → display name mapping
# Source: https://note.com/1minami/n/n6d976b35ffc0
_EXCHANGE_CODES: dict[str, str] = {
    "A": "Binance",
    "6": "Bybit",
    "0": "BitMEX",
    "2": "Deribit",
    "3": "OKX",
    "4": "Huobi",
    "7": "Phemex",
    "8": "dYdX",
    "C": "Coinbase",
    "F": "Bitfinex",
    "K": "Kraken",
    "W": "WOO X",
    "Y": "Gate.io",
    "B": "Bitstamp",
    "D": "Bitforex",
    "E": "MercadoBitcoin",
    "G": "Gemini",
    "I": "Bit2c",
    "J": "Luno",
    "L": "BitFlyer",
    "M": "BtcMarkets",
    "N": "IndependentReserve",
    "P": "Poloniex",
    "U": "Bithumb",
    "V": "Vertex",
    "H": "BTC",
}


def _format_pair_label(symbol: str, market_key: str | None = None) -> str:
    """Build a human-readable label like 'Bybit BTCUSDT Spot' or 'Binance BTCUSDT-PERP'.

    Prefers market_key for exchange name if available, otherwise parses the
    Coinalyze symbol suffix.
    """
    if market_key:
        # market_key format: "binance:btcusdt_perp.a"
        parts = market_key.split(":", 1)
        if len(parts) == 2:
            exchange = parts[0].strip().capitalize()
            raw = parts[1].strip()
            pair = raw.split(".")[0] if "." in raw else raw
            # Clean up perpetual marker
            mkt_type = "Perpetual" if "_perp" in pair.lower() or "-perpetual" in pair.lower() else "Spot"
            pair_clean = re.sub(r"_(perp|PERP)", "-PERP", pair, flags=re.IGNORECASE)
            return f"{exchange} {pair_clean} {mkt_type}"

    # Fallback: parse symbol like "BTCUSDT.6", "BTCUSDT_PERP.A", "BTC-PERPETUAL.2"
    exchange_code = symbol.split(".")[-1] if "." in symbol else ""
    exchange_name = _EXCHANGE_CODES.get(exchange_code, f"?{exchange_code}")
    base = symbol.split(".")[0] if "." in symbol else symbol

    is_perpetual = bool(re.search(r"PERP|PERPETUAL", base, re.IGNORECASE))
    mkt_type = "Perpetual" if is_perpetual else "Spot"
    pair_clean = re.sub(r"[_-](perp|PERP|PERPETUAL)", "-PERP", base, flags=re.IGNORECASE)

    return f"{exchange_name} {pair_clean} {mkt_type}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coinalyze-pseudo-footprint",
        description="Render VolumeDelta pseudo footprint from Coinalyze Receiver SQLite/CSV data.",
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
    parser.add_argument("--bar-spacing", type=float, default=2.00, help="Horizontal spacing between target candles. Default 2.00")
    parser.add_argument("--candle-width", type=float, default=0.42, help="Candle body width. Default 0.42")
    parser.add_argument("--max-area-width", type=float, default=2.0, help="Max VolumeDelta profile width. Default 2.0")
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

    # Only load OI for perpetual/futures pairs — spot has no OI
    _base_symbol = (args.symbol or "").split(".")[0] if args.symbol else ""
    _is_perpetual = bool(re.search(r"PERP|PERPETUAL", _base_symbol, re.IGNORECASE))
    oi_data = load_open_interest(args.input, symbol=args.symbol) if _is_perpetual else pd.DataFrame()
    if not oi_data.empty:
        freq = f"{args.target_minutes}min"
        oi_data["target_ts"] = oi_data["timestamp"].dt.floor(freq)
        oi_data = oi_data.groupby("target_ts", sort=True)["oi"].last().reset_index()
        oi_data = oi_data.rename(columns={"target_ts": "timestamp"})
        ts_min = display_candles["timestamp"].min()
        ts_max = display_candles["timestamp"].max()
        if oi_data["timestamp"].dt.tz is not None:
            oi_data["timestamp"] = oi_data["timestamp"].dt.tz_localize(None)
        oi_data = oi_data[(oi_data["timestamp"] >= ts_min) & (oi_data["timestamp"] <= ts_max)].reset_index(drop=True)

    label = _format_pair_label(args.symbol or "", args.market_key)
    window_note = (
        f" | display=last {len(display_candles)}/{total_candles} candles"
        if len(display_candles) != total_candles
        else ""
    )
    subtitle = (
        f"{label} | {args.source_interval} -> {args.target_minutes}min "
        f"| VolumeDelta | bin={args.price_bin:g}{window_note}"
    )
    output = render_pseudo_footprint(
        display_candles,
        display_footprint,
        args.output,
        config=config,
        title=args.title,
        subtitle=subtitle,
        pair_label=label,
        oi_data=oi_data if not oi_data.empty else None,
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
