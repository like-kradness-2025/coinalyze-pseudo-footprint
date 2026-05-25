from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "sample_receiver.db"
CSV = ROOT / "examples" / "sample_ohlcv.csv"

rng = np.random.default_rng(42)
start = datetime(2026, 5, 24, 0, 0, 0)
price = 108_000.0
rows = []
for i in range(6 * 60):
    drift = 8 * np.sin(i / 28) + rng.normal(0, 18)
    open_ = price
    close = price + drift
    high = max(open_, close) + abs(rng.normal(22, 10))
    low = min(open_, close) - abs(rng.normal(22, 10))
    volume = max(20, rng.normal(280, 80))
    # create alternating pressure pockets so the footprint is visually testable
    delta_bias = 0.35 * np.sin(i / 11) + (0.25 if 130 < i < 170 else 0) - (0.30 if 230 < i < 265 else 0)
    delta = np.clip(volume * delta_bias + rng.normal(0, volume * 0.12), -volume * 0.8, volume * 0.8)
    buy = (volume + delta) / 2
    sell = (volume - delta) / 2
    rows.append(
        {
            "market_key": "binance:btcusdt_perp.a",
            "interval": "1min",
            "timestamp": int(start.timestamp()) + i * 60,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "buy_volume": buy,
            "sell_volume": sell,
        }
    )
    price = close

DF = pd.DataFrame(rows)
DF.to_csv(CSV, index=False)
if OUT.exists():
    OUT.unlink()
with sqlite3.connect(OUT) as conn:
    DF.to_sql("ohlcv_raw", conn, index=False)

print(f"wrote {OUT}")
print(f"wrote {CSV}")
