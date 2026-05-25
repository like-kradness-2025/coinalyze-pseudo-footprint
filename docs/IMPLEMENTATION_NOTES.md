# Implementation Notes

## Core rule

1分足の `buy_volume` / `sell_volume` を、その1分足の `low-high` レンジに重なる価格ビンへ按分する。
その後、15分単位で合算する。

## Why overlap allocation

単純な「ビン数で均等割り」より、価格ビン境界をまたぐ時に少しだけ自然になる。
ただしOHLCVしか使わないので、実約定価格の分布ではない。

## Visual rule

- candle center: 15m OHLC
- left area: sell volume
- right area: buy volume
- area width: sqrt(volume / candle-local max volume)
- no area line stroke
- dark navy base

## Integration note

既存 `cvd_monitor` 側に統合するなら、既存の `render` サブコマンドを書き換えず、別サブコマンドまたは別rendererとして差し込むのが安全。
例: `python -m cvd_monitor render-footprint ...`
