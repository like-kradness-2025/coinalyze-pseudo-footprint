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
UP = "#4ade80"
DOWN = "#f43f5e"
PRICE_LINE = "#38bdf8"
TITLE_LEFT = 0.02


def _setup_axes_single(fig_width: float, fig_height: float) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=155)
    fig.patch.set_facecolor(NAVY)
    return fig, ax


def _style_axes(ax: plt.Axes, *, font_scale: float = 1.0) -> None:
    """Apply dark theme to any axes (single or subplot)."""
    ax.set_facecolor(NAVY)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.35)
    labelsize = max(6, round(9 * font_scale))
    ax.tick_params(colors=MUTED, labelsize=labelsize, length=3, width=0.8)
    for spine in ax.spines.values():
        spine.set_color(GRID)
        spine.set_alpha(0.80)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:,.0f}"))
    nbins = max(4, round(7 * font_scale))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=nbins, prune=None))


def _draw_candle(ax: plt.Axes, x: float, row: pd.Series, *, candle_width: float, wick_width: float = 1.3) -> None:
    o, h, l, c = (float(row[k]) for k in ["open", "high", "low", "close"])
    color = UP if c >= o else DOWN
    lower = min(o, c)
    height = max(abs(c - o), max((h - l) * 0.010, 1e-9))

    ax.vlines(x, l, h, color=color, linewidth=wick_width, alpha=0.92, zorder=7)
    rect = Rectangle(
        (x - candle_width / 2, lower),
        candle_width,
        height,
        facecolor=color,
        edgecolor=color,
        linewidth=1.15,
        alpha=0.72,
        zorder=8,
    )
    ax.add_patch(rect)


def _draw_volume_areas(
    ax: plt.Axes,
    x: float,
    fp: pd.DataFrame,
    *,
    price_bin_size: float,
    max_area_width: float,
    candle_width: float,
    bar_spacing: float,
    global_max_delta: float,
) -> None:
    if fp.empty or global_max_delta <= 0:
        return

    slot_half = bar_spacing / 2.0
    gap = max(0.025, min(0.08, (bar_spacing - candle_width) * 0.08))
    profile_cap = max(0.08, slot_half * 1.8 - candle_width / 2 - gap)
    usable_area_width = min(max_area_width, profile_cap)
    right_origin = x + candle_width / 2 + gap
    left_origin = x - candle_width / 2 - gap
    bar_h0 = price_bin_size * 0.12

    for _, row in fp.iterrows():
        y0 = float(row["price_bin"]) + bar_h0
        y1 = float(row["price_bin"]) + price_bin_size - bar_h0
        if y1 <= y0:
            y0 = float(row["price_bin"])
            y1 = y0 + price_bin_size

        d = float(row.get("delta", row["buy_volume"] - row["sell_volume"]))
        if abs(d) < 1e-12:
            continue

        if d > 0:
            w = usable_area_width * np.sqrt(d / global_max_delta)
            ax.fill_betweenx(
                [y0, y1], [right_origin, right_origin],
                [right_origin + w, right_origin + w],
                color=BUY, alpha=0.62, linewidth=0, zorder=3,
            )
        else:
            w = usable_area_width * np.sqrt(-d / global_max_delta)
            ax.fill_betweenx(
                [y0, y1], [left_origin - w, left_origin - w],
                [left_origin, left_origin],
                color=SELL, alpha=0.62, linewidth=0, zorder=3,
            )


def _format_x_labels(candles: pd.DataFrame, x_positions: np.ndarray) -> tuple[np.ndarray, list[str]]:
    ts_labels = pd.to_datetime(candles["timestamp"])
    n = len(candles)
    # Keep labels sparse enough to preserve the footprint itself.
    target_ticks = 5 if n <= 14 else 6
    step = max(1, int(np.ceil(n / target_ticks)))
    ticks = x_positions[::step]
    labels = [ts.strftime("%m-%d\n%H:%M") for ts in ts_labels.iloc[::step]]
    if ticks[-1] != x_positions[-1]:
        ticks = np.append(ticks, x_positions[-1])
        labels.append(ts_labels.iloc[-1].strftime("%m-%d\n%H:%M"))
    return ticks, labels


def _render_single_subplot(
    ax: plt.Axes,
    candles: pd.DataFrame,
    footprint: pd.DataFrame,
    config: FootprintConfig,
    global_max_delta: float,
    *,
    font_scale: float = 1.0,
    title_text: str | None = None,
) -> None:
    """Render one set of candles + footprint onto a given Axes.

    Shared by the single-chart and grid-chart entry points so all drawing
    logic lives in one place and stays consistent.
    """
    _style_axes(ax, font_scale=font_scale)
    n = len(candles)
    x_positions = np.arange(n, dtype=float) * config.bar_spacing
    candle_by_ts = candles.set_index("timestamp")
    fp_groups = {ts: g for ts, g in footprint.groupby("timestamp")} if not footprint.empty else {}

    # Wick thickness from candle volume (range: 0.3 low vol ~ 1.2 high vol)
    if "buy_volume" in candles.columns and "sell_volume" in candles.columns:
        vols = candles["buy_volume"] + candles["sell_volume"]
        max_vol = max(float(vols.max()), 1.0) if len(vols) > 0 else 1.0
        wick_widths = {ts: 0.3 + 0.9 * (v / max_vol) for ts, v in vols.items()}
    else:
        wick_widths = {ts: 1.3 for ts in candle_by_ts.index}

    for x, (ts, candle) in zip(x_positions, candle_by_ts.iterrows()):
        _draw_volume_areas(
            ax,
            float(x),
            fp_groups.get(ts, pd.DataFrame()),
            price_bin_size=config.price_bin_size,
            max_area_width=config.max_area_width,
            candle_width=config.candle_width,
            bar_spacing=config.bar_spacing,
            global_max_delta=global_max_delta,
        )
        _draw_candle(
            ax, float(x), candle,
            candle_width=config.candle_width,
            wick_width=wick_widths.get(ts, 1.3),
        )

    low = float(candles["low"].min())
    high = float(candles["high"].max())
    pad = max((high - low) * 0.14, config.price_bin_size * 6)
    ax.set_ylim(low - pad, high + pad)
    # Dynamic x-padding based on actual volume bar extension
    ext_gap = max(0.025, min(0.08, (config.bar_spacing - config.candle_width) * 0.08))
    max_ext = config.candle_width / 2 + ext_gap + config.max_area_width
    left_pad = max_ext + config.bar_spacing * 0.15
    right_pad = max_ext + config.bar_spacing * 0.15
    ax.set_xlim(x_positions[0] - left_pad, x_positions[-1] + right_pad)

    ticks, labels = _format_x_labels(candles, x_positions)
    fs = 9.5 * font_scale
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color=MUTED, fontsize=fs)

    # last price badge
    last = candles.iloc[-1]
    last_close = float(last["close"])
    ax.axhline(last_close, color=PRICE_LINE, linewidth=0.8 * font_scale, alpha=0.55, linestyle=(0, (4, 4)), zorder=1)
    ax.text(
        x_positions[-1] + config.bar_spacing * 0.38 + config.max_area_width,
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


def render_pseudo_footprint(
    candles: pd.DataFrame,
    footprint: pd.DataFrame,
    output_path: str | Path,
    *,
    config: FootprintConfig,
    title: str = "OHLCV Pseudo Footprint",
    subtitle: str | None = None,
    global_max_delta: float | None = None,
) -> Path:
    """Render candle + left sell/right buy pseudo footprint PNG.

    Renderer owns only visual mapping. It does not query data, select display
    windows, or allocate volume.
    """

    if candles.empty:
        raise ValueError("candles is empty")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n = len(candles)
    fig_width = max(14.0, min(24.0, n * config.bar_spacing * 0.90))
    fig_height = 13.0
    fig, ax = _setup_axes_single(fig_width, fig_height)

    # Global delta max across ALL candles (shared axis width)
    if global_max_delta is not None:
        pass  # caller-provided global scale
    elif footprint.empty:
        global_max_delta = 1.0
    else:
        deltas = footprint["delta"].values if "delta" in footprint.columns else footprint["buy_volume"].values - footprint["sell_volume"].values
        global_max_delta = float(max(np.abs(deltas).max(), 1e-9))

    _render_single_subplot(ax, candles, footprint, config, global_max_delta, font_scale=1.0)

    header = title if subtitle is None else f"{title}\n{subtitle}"
    ax.set_title(header, color=TEXT, loc="left", fontsize=14, pad=16, weight="semibold")
    ax.text(
        0.99,
        1.012,
        "left=sell · right=buy  |  delta  |  OHLCV-estimated",
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
    """Render up to 4 markets in a 2×2 grid with globally-shared delta bar-width scale.

    Parameters
    ----------
    markets:
        {market_key: (candles_df, footprint_df)}. At most 4 entries; extras are ignored.
    output_path:
        Output PNG path.
    config:
        Shared FootprintConfig for visual knobs.
    title:
        Figure-level title.
    """
    if not markets:
        raise ValueError("markets is empty")

    items = list(markets.items())[:4]
    n_markets = len(items)

    # Pre-compute global max |delta| across ALL markets
    global_max_delta = 1.0
    for _, (_, fp) in items:
        if fp is not None and not fp.empty:
            deltas = (
                fp["delta"].values
                if "delta" in fp.columns
                else fp["buy_volume"].values - fp["sell_volume"].values
            )
            gd = float(np.abs(deltas).max())
            if gd > global_max_delta:
                global_max_delta = gd

    rows = 2
    cols = 2
    fig, axes = plt.subplots(
        rows, cols,
        figsize=(24, 16),
        dpi=155,
        constrained_layout=True,
    )
    fig.patch.set_facecolor(NAVY)
    fig.suptitle(
        title,
        color=TEXT,
        fontsize=16,
        weight="semibold",
        x=TITLE_LEFT,
        ha="left",
        y=0.985,
    )

    # Render each market into its subplot
    for idx, (market_key, (candles, footprint)) in enumerate(items):
        row = idx // cols
        col = idx % cols
        ax = axes[row][col]

        if candles.empty:
            _style_axes(ax, font_scale=0.85)
            ax.text(0.5, 0.5, "no data", color=MUTED, ha="center", va="center", transform=ax.transAxes)
            ax.set_title(market_key, color=TEXT, fontsize=11, loc="left", pad=8, weight="semibold")
            continue

        _render_single_subplot(
            ax, candles, footprint if footprint is not None else pd.DataFrame(), config, global_max_delta,
            font_scale=0.85,
            title_text=market_key,
        )

    # Hide unused subplots
    for idx in range(n_markets, rows * cols):
        row = idx // cols
        col = idx % cols
        axes[row][col].set_visible(False)

    # Shared footer annotation
    fig.text(
        0.5, 0.005,
        "left=sell · right=buy  |  delta  |  OHLCV-estimated  |  global delta scale shared across all markets",
        ha="center", va="bottom",
        color=MUTED, fontsize=9,
    )

    fig.savefig(output_path, facecolor=fig.get_facecolor(), dpi=155, bbox_inches="tight")
    plt.close(fig)
    return Path(output_path)
