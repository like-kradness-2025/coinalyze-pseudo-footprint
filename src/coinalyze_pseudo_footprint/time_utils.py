from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def normalize_timestamp_series(series: pd.Series) -> pd.Series:
    """Normalize seconds/ms/ISO timestamps to UTC-naive pandas datetime.

    Receiver projects often move between integer epoch and ISO strings. Keeping
    this conversion isolated prevents timestamp handling from leaking into the
    allocator or renderer.
    """

    if pd.api.types.is_numeric_dtype(series):
        values = pd.to_numeric(series, errors="coerce")
        median = values.dropna().median()
        unit = "ms" if median > 10_000_000_000 else "s"
        out = pd.to_datetime(values, unit=unit, utc=True, errors="coerce")
    else:
        out = pd.to_datetime(series, utc=True, errors="coerce")

    return out.dt.tz_convert("UTC").dt.tz_localize(None)


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def drop_unfinished_candles(
    df: pd.DataFrame,
    *,
    timestamp_col: str = "timestamp",
    interval_minutes: int = 1,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Drop candles whose close time is after `now`.

    Coinalyze/Receiver rows are treated as candle-open timestamps. A row is
    complete only when timestamp + interval <= now.
    """

    if df.empty:
        return df.copy()

    current_time = now or utc_now_naive()
    close_time = df[timestamp_col] + pd.to_timedelta(interval_minutes, unit="m")
    return df.loc[close_time <= current_time].copy()
