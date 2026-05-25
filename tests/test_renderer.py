from __future__ import annotations

from pathlib import Path

from coinalyze_pseudo_footprint.allocator import build_pseudo_footprint
from coinalyze_pseudo_footprint.models import FootprintConfig
from coinalyze_pseudo_footprint.renderer import render_pseudo_footprint
from tests.test_allocator import sample_df


def test_renderer_writes_png(tmp_path: Path) -> None:
    cfg = FootprintConfig(price_bin_size=10, exclude_unfinished=False)
    out = build_pseudo_footprint(sample_df(45), cfg)
    png = render_pseudo_footprint(out.candles, out.footprint, tmp_path / "fp.png", config=cfg)

    assert png.exists()
    assert png.stat().st_size > 10_000
