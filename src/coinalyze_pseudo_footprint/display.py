from __future__ import annotations

import pandas as pd


def select_recent_display_window(
    candles: pd.DataFrame,
    footprint: pd.DataFrame,
    *,
    max_candles: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Return a continuous, recent display window and matching footprint rows.

    This module owns only chart-window selection. It does not aggregate OHLCV,
    allocate footprint volume, or render images.

    Why a continuous recent window instead of sampling every Nth candle?
    - Skipping candles breaks price-action continuity.
    - A pseudo-footprint is dense; readability improves more by reducing the
      visible window than by thinning within a 6h range.
    """

    if candles.empty:
        return candles.copy(), footprint.copy(), 0
    if max_candles is None or len(candles) <= max_candles:
        return candles.copy(), footprint.copy(), len(candles)

    selected = candles.sort_values("timestamp").tail(max_candles).copy()
    keep_ts = set(pd.to_datetime(selected["timestamp"]))

    if footprint.empty:
        selected_fp = footprint.copy()
    else:
        fp = footprint.copy()
        fp["timestamp"] = pd.to_datetime(fp["timestamp"])
        selected_fp = fp[fp["timestamp"].isin(keep_ts)].copy()

    return selected.reset_index(drop=True), selected_fp.reset_index(drop=True), len(candles)
