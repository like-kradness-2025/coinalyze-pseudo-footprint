from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .models import FootprintConfig
from .time_utils import drop_unfinished_candles


@dataclass(frozen=True)
class PseudoFootprintResult:
    candles: pd.DataFrame
    footprint: pd.DataFrame


def _bucket_floor(price: float, bin_size: float) -> float:
    return math.floor(price / bin_size) * bin_size


def _alloc_one_row(row: pd.Series, *, price_bin_size: float) -> list[tuple[float, float, float]]:
    """Return [(price_bin_low, buy_part, sell_part), ...] for one source candle.

    Allocation is by overlap length with each price bucket, not by plain bucket
    count. This keeps the rule deterministic and slightly less crude around bin
    boundaries while staying OHLCV-only.
    """

    low = float(min(row["low"], row["high"]))
    high = float(max(row["low"], row["high"]))
    buy = max(float(row["buy_volume"]), 0.0)
    sell = max(float(row["sell_volume"]), 0.0)

    if not np.isfinite([low, high, buy, sell]).all():
        return []

    if high <= low:
        bucket = _bucket_floor(float(row["close"]), price_bin_size)
        return [(bucket, buy, sell)]

    start = _bucket_floor(low, price_bin_size)
    end = _bucket_floor(high, price_bin_size)

    buckets: list[float] = []
    weights: list[float] = []
    b = start
    # Small epsilon avoids skipping the high bucket due float representation.
    while b <= end + price_bin_size * 1e-9:
        overlap = max(0.0, min(high, b + price_bin_size) - max(low, b))
        if overlap > 0:
            buckets.append(b)
            weights.append(overlap)
        b += price_bin_size

    if not weights:
        bucket = _bucket_floor(float(row["close"]), price_bin_size)
        return [(bucket, buy, sell)]

    total_weight = sum(weights)
    return [(bucket, buy * w / total_weight, sell * w / total_weight) for bucket, w in zip(buckets, weights)]


def build_pseudo_footprint(df: pd.DataFrame, config: FootprintConfig) -> PseudoFootprintResult:
    """Convert 1m OHLCV into target-interval candle + price-bin footprint.

    Output semantics:
    - candles: one row per target candle with OHLC
    - footprint: one row per target candle x price_bin with buy/sell/delta
    """

    config.validate()
    if df.empty:
        raise ValueError("no OHLCV rows")

    work = df.copy()
    if config.exclude_unfinished:
        work = drop_unfinished_candles(
            work,
            timestamp_col="timestamp",
            interval_minutes=config.source_interval_minutes,
        )
    if work.empty:
        raise ValueError("no completed OHLCV rows after unfinished-candle exclusion")

    work = work.sort_values("timestamp").reset_index(drop=True)
    freq = f"{config.target_interval_minutes}min"
    work["target_ts"] = work["timestamp"].dt.floor(freq)

    candle_rows: list[dict[str, object]] = []
    footprint_rows: list[dict[str, object]] = []

    for target_ts, group in work.groupby("target_ts", sort=True):
        group = group.sort_values("timestamp")
        candle_rows.append(
            {
                "timestamp": target_ts,
                "open": float(group.iloc[0]["open"]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group.iloc[-1]["close"]),
                "buy_volume": float(group["buy_volume"].sum()),
                "sell_volume": float(group["sell_volume"].sum()),
                "delta": float(group["buy_volume"].sum() - group["sell_volume"].sum()),
                "source_rows": int(len(group)),
            }
        )

        acc: dict[float, list[float]] = {}
        for _, row in group.iterrows():
            for price_bin, buy_part, sell_part in _alloc_one_row(row, price_bin_size=config.price_bin_size):
                slot = acc.setdefault(price_bin, [0.0, 0.0])
                slot[0] += buy_part
                slot[1] += sell_part

        for price_bin, (buy, sell) in sorted(acc.items()):
            footprint_rows.append(
                {
                    "timestamp": target_ts,
                    "price_bin": float(price_bin),
                    "buy_volume": float(buy),
                    "sell_volume": float(sell),
                    "delta": float(buy - sell),
                }
            )

    candles = pd.DataFrame(candle_rows)
    footprint = pd.DataFrame(footprint_rows)
    return PseudoFootprintResult(candles=candles, footprint=footprint)
