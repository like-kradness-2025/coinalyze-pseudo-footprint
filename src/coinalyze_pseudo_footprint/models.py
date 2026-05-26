from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FootprintConfig:
    """Aggregation and rendering knobs kept in one small immutable object."""

    source_interval_minutes: int = 1
    target_interval_minutes: int = 15
    price_bin_size: float = 10.0

    # VolumeDelta is the single supported visual mode:
    # faint total volume by price bin + stronger delta overlay.
    mode: str = "volume_delta"
    max_display_candles: int | None = 14
    max_area_width: float = 1.05
    candle_width: float = 0.42
    bar_spacing: float = 2.00
    lookback_hours: float | None = 6.0
    exclude_unfinished: bool = True

    def validate(self) -> None:
        if self.source_interval_minutes <= 0:
            raise ValueError("source_interval_minutes must be positive")
        if self.target_interval_minutes <= 0:
            raise ValueError("target_interval_minutes must be positive")
        if self.target_interval_minutes % self.source_interval_minutes != 0:
            raise ValueError("target interval must be a multiple of source interval")
        if self.price_bin_size <= 0:
            raise ValueError("price_bin_size must be positive")
        if self.mode != "volume_delta":
            raise ValueError("mode must be volume_delta")
        if self.max_display_candles is not None and self.max_display_candles < 1:
            raise ValueError("max_display_candles must be positive or None")
        if not 0 < self.max_area_width <= 2.0:
            raise ValueError("max_area_width must be in (0, 2.0]")
        if not 0 < self.candle_width <= 1:
            raise ValueError("candle_width must be in (0, 1]")
        if not 1.0 <= self.bar_spacing <= 2.4:
            raise ValueError("bar_spacing must be in [1.0, 2.4]")
