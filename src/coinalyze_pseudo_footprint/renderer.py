from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

from .models import FootprintConfig


NAVY = "#07111f"
GRID = "#2d4a6a"
TEXT = "#ecf3fe"
MUTED = "#96a8bf"
BUY = "#22d3ee"
SELL = "#ff5f78"
TOTAL = "#6b7f99"
UP = "#4ade80"
DOWN = "#f43f5e"
PRICE_LINE = "#38bdf8"
TITLE_LEFT = 0.02


def _setup_axes_single(fig_width: float, fig_height: float) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=155)
    fig.patch.set_facecolor(NAVY)
    return fig, ax


def _style_axes(ax: plt.Axes, *, font_scale: float = 1.0) -> None:
    ax.set_facecolor(NAVY)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.18)
    labelsize = max(6, round(9 * font_scale))
    ax.tick_params(colors=MUTED, labelsize=labelsize, length=3, width=0.8)
    for spine in ax.spines.values():
        spine.set_color(GRID)
        spine.set_alpha(0.70)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:,.0f}"))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=max(4, round(7 * font_scale)), prune=None))


def _draw_candle(ax: plt.Axes, x: float, row: pd.Series, *, candle_width: float, wick_width: float = 1.3) -> None:
    o, h, l, c = (float(row[k]) for k in ["open", "high", "low", "close"])
    color = UP if c >= o else DOWN
    lower = min(o, c)
    height = max(abs(c - o), max((h - l) * 0.010, 1e-9))

    ax.vlines(x, l, h, color=color, linewidth=wick_width, alpha=0.92, zorder=8)
    ax.add_patch(
        Rectangle(
            (x - candle_width / 2, lower),
            candle_width,
            height,
            facecolor=color,
            edgecolor=color,
            linewidth=1.15,
            alpha=0.78,
            zorder=9,
        )
    )


def _draw_volume_delta_profile(
    ax: plt.Axes,
    x: float,
    fp: pd.DataFrame,
    *,
    price_bin_size: float,
    max_area_width: float,
    candle_width: float,
    bar_spacing: float,
    global_max_total: float,
    global_max_delta: float,
) -> None:
    """Draw stacked bar: gray=common volume, colored=delta.

    Shows what proportion of total volume at each price level is directional
    imbalance (delta). Bars are placed to the right of the candle body.
    """
    if fp.empty or global_max_total <= 0:
        return

    gap = 0.04
    overlap_into_next = candle_width * 1.25
    profile_cap = max(0.08, bar_spacing - candle_width - gap + overlap_into_next)
    usable_width = min(max_area_width, profile_cap)
    right_origin = x + candle_width / 2 + gap
    bar_pad = 0.0  # full bar height

    y_min = float("inf")
    y_max = float("-inf")
    rows: list[tuple[float, float, float, float, float]] = []

    for _, row in fp.iterrows():
        y0 = float(row["price_bin"]) + bar_pad
        y1 = float(row["price_bin"]) + price_bin_size - bar_pad
        if y1 <= y0:
            y0 = float(row["price_bin"])
            y1 = y0 + price_bin_size

        buy = max(float(row.get("buy_volume", 0.0)), 0.0)
        sell = max(float(row.get("sell_volume", 0.0)), 0.0)
        total = buy + sell
        delta = abs(buy - sell)
        common = min(buy, sell)

        if total <= 0:
            continue

        rows.append((y0, y1, buy, sell, total))
        y_min = min(y_min, y0)
        y_max = max(y_max, y1)

    if not rows:
        return

    for y0, y1, buy, sell, total in rows:
        delta = abs(buy - sell)
        common = min(buy, sell)
        bar_w = usable_width * (total / global_max_total)

        # Common (overlap) portion — gray base
        if common > 0:
            common_w = bar_w * (common / total)
            ax.fill_betweenx(
                [y0, y1],
                [right_origin, right_origin],
                [right_origin + common_w, right_origin + common_w],
                color=TOTAL,
                alpha=0.45,
                linewidth=0,
                zorder=3,
            )
            delta_x0 = right_origin + common_w
        else:
            delta_x0 = right_origin

        # Delta portion — colored
        if delta > 0:
            delta_w = bar_w * (delta / total)
            color = BUY if buy > sell else SELL
            ax.fill_betweenx(
                [y0, y1],
                [delta_x0, delta_x0],
                [delta_x0 + delta_w, delta_x0 + delta_w],
                color=color,
                alpha=0.82,
                linewidth=0,
                zorder=4,
            )


def _format_x_labels(candles: pd.DataFrame, x_positions: np.ndarray) -> tuple[np.ndarray, list[str]]:
    ts_labels = pd.to_datetime(candles["timestamp"])
    n = len(candles)
    target_ticks = 5 if n <= 14 else 6
    step = max(1, int(np.ceil(n / target_ticks)))
    ticks = x_positions[::step]
    labels = [ts.strftime("%m-%d\n%H:%M") for ts in ts_labels.iloc[::step]]
    if ticks[-1] != x_positions[-1]:
        ticks = np.append(ticks, x_positions[-1])
        labels.append(ts_labels.iloc[-1].strftime("%m-%d\n%H:%M"))
    return ticks, labels


def _scale_values(footprint: pd.DataFrame) -> tuple[float, float]:
    if footprint.empty:
        return 1.0, 1.0
    total = footprint["buy_volume"].clip(lower=0) + footprint["sell_volume"].clip(lower=0)
    delta = footprint["delta"] if "delta" in footprint.columns else footprint["buy_volume"] - footprint["sell_volume"]
    return float(max(total.max(), 1e-9)), float(max(np.abs(delta).max(), 1e-9))


def _render_single_subplot(
    ax: plt.Axes,
    candles: pd.DataFrame,
    footprint: pd.DataFrame,
    config: FootprintConfig,
    global_max_total: float,
    global_max_delta: float,
    *,
    font_scale: float = 1.0,
    title_text: str | None = None,
    pair_label: str | None = None,
) -> None:
    _style_axes(ax, font_scale=font_scale)
    x_positions = np.arange(len(candles), dtype=float) * config.bar_spacing
    candle_by_ts = candles.set_index("timestamp")
    fp_groups = {ts: g for ts, g in footprint.groupby("timestamp")} if not footprint.empty else {}

    if "buy_volume" in candles.columns and "sell_volume" in candles.columns:
        vols = (candles["buy_volume"] + candles["sell_volume"]).reset_index(drop=True)
        max_vol = max(float(vols.max()), 1.0)
        wick_widths = {ts: 0.45 + 0.85 * (float(vols.iloc[i]) / max_vol) for i, ts in enumerate(candle_by_ts.index)}
    else:
        wick_widths = {ts: 1.3 for ts in candle_by_ts.index}

    for x, (ts, candle) in zip(x_positions, candle_by_ts.iterrows()):
        _draw_volume_delta_profile(
            ax,
            float(x),
            fp_groups.get(ts, pd.DataFrame()),
            price_bin_size=config.price_bin_size,
            max_area_width=config.max_area_width,
            candle_width=config.candle_width,
            bar_spacing=config.bar_spacing,
            global_max_total=global_max_total,
            global_max_delta=global_max_delta,
        )
        _draw_candle(ax, float(x), candle, candle_width=config.candle_width, wick_width=wick_widths.get(ts, 1.3))

    low = float(candles["low"].min())
    high = float(candles["high"].max())
    pad = max((high - low) * 0.14, config.price_bin_size * 6)
    ax.set_ylim(low - pad, high + pad)

    # Calculate right-side bar extent for x_lim padding
    _gap = 0.04
    _overlap_into_next = config.candle_width * 1.25
    _profile_cap = max(0.08, config.bar_spacing - config.candle_width - _gap + _overlap_into_next)
    _usable_width = min(config.max_area_width, _profile_cap)
    right_ext = config.candle_width / 2 + _gap + _usable_width
    left_pad = right_ext * 0.25
    right_pad = right_ext + config.bar_spacing * 0.80
    ax.set_xlim(x_positions[0] - left_pad, x_positions[-1] + right_pad)

    # Bar width scale label (top-right corner of data area)
    scale_x = x_positions[-1] + right_pad * 0.55
    scale_y = float(candles["high"].max()) + pad * 0.85
    ax.text(
        scale_x, scale_y,
        f"max bar = {global_max_total:,.0f}",
        va="top", ha="right",
        color=MUTED, fontsize=8.5 * font_scale,
        alpha=0.85, zorder=1,
    )

    ticks, labels = _format_x_labels(candles, x_positions)
    fs = 9.5 * font_scale
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color=MUTED, fontsize=fs)

    last_close = float(candles.iloc[-1]["close"])
    ax.axhline(last_close, color=PRICE_LINE, linewidth=0.8 * font_scale, alpha=0.55, linestyle=(0, (4, 4)), zorder=1)
    ax.text(
        x_positions[-1] + right_ext * 0.15,
        last_close,
        f" {last_close:,.1f} ",
        va="center",
        ha="left",
        color=TEXT,
        fontsize=fs,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="#143752", edgecolor="none", alpha=0.92),
        zorder=10,
    )

    if title_text:
        ax.set_title(title_text, color=TEXT, fontsize=11 * font_scale, loc="left", pad=8, weight="semibold")

    if pair_label:
        ax.text(
            0.02, 0.97,
            pair_label,
            transform=ax.transAxes,
            va="top", ha="left",
            color="#ecf3fe", fontsize=45 * font_scale,
            alpha=1.0, zorder=1,
            weight="bold",
        )


def render_pseudo_footprint(
    candles: pd.DataFrame,
    footprint: pd.DataFrame,
    output_path: str | Path,
    *,
    config: FootprintConfig,
    title: str = "OHLCV Pseudo Footprint",
    subtitle: str | None = None,
    global_max_delta: float | None = None,
    pair_label: str | None = None,
) -> Path:
    """Render VolumeDelta pseudo footprint PNG.

    Renderer owns only visual mapping. It does not query data, select display
    windows, or allocate volume.
    """
    config.validate()
    if candles.empty:
        raise ValueError("candles is empty")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig_width = max(14.0, min(24.0, len(candles) * config.bar_spacing * 0.88))
    fig_height = 13.0
    fig, ax = _setup_axes_single(fig_width, fig_height)

    global_max_total, computed_delta = _scale_values(footprint)
    global_max_delta = computed_delta if global_max_delta is None else max(float(global_max_delta), 1e-9)

    _render_single_subplot(ax, candles, footprint, config, global_max_total, global_max_delta, font_scale=1.0, pair_label=pair_label)

    header = title if subtitle is None else f"{title}\n{subtitle}"
    ax.set_title(header, color=TEXT, loc="left", fontsize=14, pad=16, weight="semibold")
    ax.text(
        0.99,
        1.012,
        "faint=total vol · blue/red=delta (buy/sell)  |  OHLCV-estimated",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        color=TEXT,
        fontsize=10,
    )

    fig.tight_layout(pad=1.3)
    fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path


def render_pseudo_footprint_grid(
    markets: dict[str, tuple[pd.DataFrame, pd.DataFrame | None]],
    output_path: str | Path,
    *,
    config: FootprintConfig,
    title: str = "OHLCV Pseudo Footprint — 4 Markets",
) -> Path:
    if not markets:
        raise ValueError("markets is empty")

    config.validate()
    items = list(markets.items())[:4]

    global_max_total = global_max_delta = 1.0
    for _, (_, fp) in items:
        if fp is not None and not fp.empty:
            t, d = _scale_values(fp)
            global_max_total = max(global_max_total, t)
            global_max_delta = max(global_max_delta, d)

    fig, axes = plt.subplots(2, 2, figsize=(24, 16), dpi=155, constrained_layout=True)
    fig.patch.set_facecolor(NAVY)
    fig.suptitle(title, color=TEXT, fontsize=16, weight="semibold", x=TITLE_LEFT, ha="left", y=0.985)

    for idx, (market_key, (candles, footprint)) in enumerate(items):
        ax = axes[idx // 2][idx % 2]
        if candles.empty:
            _style_axes(ax, font_scale=0.85)
            ax.text(0.5, 0.5, "no data", color=MUTED, ha="center", va="center", transform=ax.transAxes)
            ax.set_title(market_key, color=TEXT, fontsize=11, loc="left", pad=8, weight="semibold")
            continue
        _render_single_subplot(
            ax,
            candles,
            footprint if footprint is not None else pd.DataFrame(),
            config,
            global_max_total,
            global_max_delta,
            font_scale=0.85,
            title_text=market_key,
            pair_label=market_key,
        )

    for idx in range(len(items), 4):
        axes[idx // 2][idx % 2].set_visible(False)

    fig.text(
        0.5,
        0.005,
        "faint=total vol · blue/red=delta (buy/sell)  |  OHLCV-estimated  |  global scale shared across markets",
        ha="center",
        va="bottom",
        color=MUTED,
        fontsize=9,
    )
    fig.savefig(output_path, facecolor=fig.get_facecolor(), dpi=155, bbox_inches="tight")
    plt.close(fig)
    return Path(output_path)
