from __future__ import annotations

from coinalyze_pseudo_footprint.allocator import build_pseudo_footprint
from coinalyze_pseudo_footprint.display import select_recent_display_window
from coinalyze_pseudo_footprint.models import FootprintConfig
from tests.test_allocator import sample_df


def test_select_recent_display_window_keeps_continuous_latest_candles() -> None:
    cfg = FootprintConfig(target_interval_minutes=15, price_bin_size=10, exclude_unfinished=False)
    out = build_pseudo_footprint(sample_df(75), cfg)

    candles, fp, total = select_recent_display_window(out.candles, out.footprint, max_candles=3)

    assert total == 5
    assert len(candles) == 3
    assert list(candles["timestamp"]) == list(out.candles["timestamp"].tail(3))
    assert set(fp["timestamp"]).issubset(set(candles["timestamp"]))


def test_select_recent_display_window_zero_limit_equivalent_none() -> None:
    cfg = FootprintConfig(target_interval_minutes=15, price_bin_size=10, exclude_unfinished=False)
    out = build_pseudo_footprint(sample_df(45), cfg)

    candles, fp, total = select_recent_display_window(out.candles, out.footprint, max_candles=None)

    assert total == len(out.candles)
    assert len(candles) == len(out.candles)
    assert len(fp) == len(out.footprint)
