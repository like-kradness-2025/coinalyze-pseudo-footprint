from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from .time_utils import normalize_timestamp_series

CANONICAL_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "buy_volume",
    "sell_volume",
    "market_key",
    "interval",
]

ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "time", "t", "ts", "open_time", "start_time", "datetime", "date"),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
    "volume": ("volume", "vol", "v"),
    "buy_volume": (
        "buy_volume",
        "buy_vol",
        "buyvol",
        "buyvolume",
        "taker_buy_volume",
        "taker_buy_vol",
        "long_volume",
        "buy",
    ),
    "sell_volume": (
        "sell_volume",
        "sell_vol",
        "sellvol",
        "taker_sell_volume",
        "taker_sell_vol",
        "short_volume",
        "sell",
    ),
    "delta": ("delta", "cvd_delta", "volume_delta", "buy_sell_delta"),
    "market_key": ("market_key", "market", "symbol_key"),
    "symbol": ("symbol", "coinalyze_symbol", "symbol_on_exchange"),
    "interval": ("interval", "timeframe", "tf"),
}


def _find_column(columns: Iterable[str], canonical: str) -> str | None:
    lower_to_original = {c.lower(): c for c in columns}
    for candidate in ALIASES[canonical]:
        if candidate.lower() in lower_to_original:
            return lower_to_original[candidate.lower()]
    return None


def _normalize_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for canonical in ALIASES:
        found = _find_column(raw.columns, canonical)
        if found:
            mapping[found] = canonical

    df = raw.rename(columns=mapping).copy()

    required = ["timestamp", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing required OHLCV columns: {missing}; columns={list(raw.columns)}")

    df["timestamp"] = normalize_timestamp_series(df["timestamp"])
    df = df.dropna(subset=["timestamp"])

    for col in ["open", "high", "low", "close", "volume", "buy_volume", "sell_volume", "delta"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "buy_volume" not in df.columns or "sell_volume" not in df.columns:
        if "volume" in df.columns and "delta" in df.columns:
            # volume = buy + sell, delta = buy - sell
            df["buy_volume"] = (df["volume"] + df["delta"]) / 2
            df["sell_volume"] = (df["volume"] - df["delta"]) / 2
        elif "volume" in df.columns and "buy_volume" in df.columns:
            # Only buy_volume available: sell = volume - buy
            df["sell_volume"] = df["volume"] - df["buy_volume"]
        elif "volume" in df.columns and "sell_volume" in df.columns:
            # Only sell_volume available: buy = volume - sell
            df["buy_volume"] = df["volume"] - df["sell_volume"]
        else:
            raise ValueError("buy/sell volume is required, or volume+delta must be present")

    keep = [c for c in CANONICAL_COLUMNS if c in df.columns]
    out = df[keep].dropna(subset=["open", "high", "low", "close", "buy_volume", "sell_volume"])
    out = out.sort_values("timestamp").reset_index(drop=True)
    return out


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _choose_table(conn: sqlite3.Connection, preferred: str | None) -> str:
    if preferred:
        return preferred

    tables = _sqlite_tables(conn)
    for candidate in ["ohlcv_raw", "ohlcv", "candles", "raw_ohlcv"]:
        if candidate in tables:
            return candidate

    for table in tables:
        columns = _table_columns(conn, table)
        if all(_find_column(columns, c) for c in ["timestamp", "open", "high", "low", "close"]):
            return table

    raise ValueError(f"no OHLCV-like table found; tables={tables}")


def load_sqlite_ohlcv(
    db_path: str | Path,
    *,
    market_key: str | None = None,
    symbol: str | None = None,
    interval: str | None = "1min",
    table: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load Receiver OHLCV rows from SQLite with light schema introspection."""

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with sqlite3.connect(db_path) as conn:
        selected_table = _choose_table(conn, table)
        columns = _table_columns(conn, selected_table)

        where: list[str] = []
        params: list[object] = []

        market_col = _find_column(columns, "market_key")
        symbol_col = _find_column(columns, "symbol")
        interval_col = _find_column(columns, "interval")

        if market_key and market_col:
            where.append(f'LOWER("{market_col}") = LOWER(?)')
            params.append(market_key)
        elif symbol and symbol_col:
            where.append(f'LOWER("{symbol_col}") = LOWER(?)')
            params.append(symbol)

        if interval and interval_col:
            where.append(f'"{interval_col}" = ?')
            params.append(interval)

        sql = f'SELECT * FROM "{selected_table}"'
        if where:
            sql += " WHERE " + " AND ".join(where)

        ts_col = _find_column(columns, "timestamp")
        if ts_col:
            sql += f' ORDER BY "{ts_col}"'
        if limit:
            sql += f" LIMIT {int(limit)}"

        raw = pd.read_sql_query(sql, conn, params=params)

    return _normalize_ohlcv(raw)


def load_csv_ohlcv(path: str | Path) -> pd.DataFrame:
    return _normalize_ohlcv(pd.read_csv(path))


def load_ohlcv(
    input_path: str | Path,
    *,
    market_key: str | None = None,
    symbol: str | None = None,
    interval: str | None = "1min",
    table: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load OHLCV from SQLite or CSV.

    This is the only public data-loading entrypoint. Downstream modules receive a
    normalized DataFrame and do not know about SQLite/CSV/schema aliases.
    """

    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return load_sqlite_ohlcv(
            input_path,
            market_key=market_key,
            symbol=symbol,
            interval=interval,
            table=table,
            limit=limit,
        )
    if suffix in {".csv", ".txt"}:
        return load_csv_ohlcv(input_path)
    raise ValueError(f"unsupported input type: {input_path}")
