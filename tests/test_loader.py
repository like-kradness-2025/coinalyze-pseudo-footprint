from __future__ import annotations

import sqlite3
from pathlib import Path

from coinalyze_pseudo_footprint.loader import load_ohlcv


def test_sqlite_loader_accepts_receiver_like_aliases(tmp_path: Path) -> None:
    db = tmp_path / "receiver.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE ohlcv_raw (
                market_key TEXT,
                interval TEXT,
                timestamp INTEGER,
                o REAL,
                h REAL,
                l REAL,
                c REAL,
                buy_volume REAL,
                sell_volume REAL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ohlcv_raw VALUES
            ('binance:btcusdt_perp.a', '1min', 1770000000, 100, 105, 95, 102, 10, 8),
            ('coinbase:btcusd.c', '1min', 1770000000, 100, 105, 95, 102, 99, 88)
            """
        )

    df = load_ohlcv(db, market_key="binance:btcusdt_perp.a", interval="1min")

    assert len(df) == 1
    assert list(df.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "buy_volume",
        "sell_volume",
        "market_key",
        "interval",
    ]
    assert df.iloc[0]["buy_volume"] == 10
