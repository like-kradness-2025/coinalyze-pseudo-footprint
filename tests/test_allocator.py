from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from coinalyze_pseudo_footprint.allocator import build_pseudo_footprint
from coinalyze_pseudo_footprint.models import FootprintConfig


def sample_df(rows: int = 15) -> pd.DataFrame:
    start = datetime(2026, 5, 20, 0, 0, 0)
    data = []
    price = 100_000.0
    for i in range(rows):
        o = price + i * 10
        c = o + (-1) ** i * 6
        h = max(o, c) + 8
        l = min(o, c) - 7
        data.append(
            {
                "timestamp": start + timedelta(minutes=i),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "buy_volume": 100 + i,
                "sell_volume": 80 + i,
            }
        )
    return pd.DataFrame(data)


def test_allocator_preserves_buy_sell_volume() -> None:
    df = sample_df(15)
    cfg = FootprintConfig(price_bin_size=5, exclude_unfinished=False)
    out = build_pseudo_footprint(df, cfg)

    assert len(out.candles) == 1
    assert out.footprint["buy_volume"].sum() == pytest.approx(df["buy_volume"].sum())
    assert out.footprint["sell_volume"].sum() == pytest.approx(df["sell_volume"].sum())
    assert out.candles.iloc[0]["delta"] == pytest.approx(
        df["buy_volume"].sum() - df["sell_volume"].sum()
    )


def test_allocator_groups_to_15min() -> None:
    df = sample_df(31)
    cfg = FootprintConfig(target_interval_minutes=15, price_bin_size=10, exclude_unfinished=False)
    out = build_pseudo_footprint(df, cfg)

    assert len(out.candles) == 3
    assert list(out.candles["source_rows"]) == [15, 15, 1]
