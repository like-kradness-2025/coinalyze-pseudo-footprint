# Coinalyze OHLCV Pseudo Footprint

Coinalyze Receiver の 1分OHLCV + buy/sell volume から、15分足内の **推定価格帯別 buy/sell 分布** を描画する小型実装です。

## 役割分担

- `loader.py`: SQLite/CSVを読む。列名ゆれを吸収する。
- `allocator.py`: 1分足のbuy/sellを価格ビンへ配分し、15分足へ集約する。
- `display.py`: 表示する最新ウィンドウだけを選ぶ。
- `renderer.py`: ローソク足 + 左sell area / 右buy area をPNG化する。
- `cli.py`: 入出力だけを束ねる薄い入口。

## 使い方

```bash
python -m coinalyze_pseudo_footprint \
  --input path/to/receiver.db \
  --table ohlcv_raw \
  --market-key binance:btcusdt_perp.a \
  --source-interval 1min \
  --target-minutes 15 \
  --price-bin 10 \
  --max-display-candles 14 \
  --bar-spacing 1.42 \
  --output out/btc_pseudo_footprint.png
```

CSVでも可:

```bash
python -m coinalyze_pseudo_footprint \
  --input examples/sample_ohlcv.csv \
  --price-bin 10 \
  --max-display-candles 14 \
  --output out/sample_pseudo_footprint.png
```

## 入力列

必須:

- `timestamp`
- `open/high/low/close` または `o/h/l/c`
- `buy_volume` と `sell_volume`

代替:

- `volume + delta` があれば `buy/sell` を復元します。

任意:

- `market_key`
- `interval`
- `symbol`

## 注意

これは約定tick由来の本物フットプリントではありません。1分足OHLCVのレンジ内にbuy/sell volumeを配分する **OHLCV-based pseudo footprint** です。


## 表示本数の調整

疑似フットプリントは、1本のローソクに buy/sell profile が付くため、6時間分をすべて表示すると情報密度が上がりすぎます。
そのためデフォルトでは **最新14本の15分足** に絞って描画します。

```bash
# 見やすさ優先: 最新14本だけ表示 デフォルト
--max-display-candles 14

# 全部表示
--max-display-candles 0

# さらに絞る 例: 最新12本
--max-display-candles 12
```

実装上は `display.py` が表示窓の選択だけを担当します。OHLCV集約は `allocator.py`、描画は `renderer.py` のまま分離しています。


## 横方向の見やすさ調整

ローソク同士の詰まりを避けるため、v3ではローソク/footprintの1セットを「スロット」として扱い、スロット間隔を広げています。

```bash
# デフォルト。ローソク間に余白を作る
--bar-spacing 1.42

# さらに余白を広げる
--bar-spacing 1.60

# profileを細める
--max-area-width 0.22

# ローソクを少し細める
--candle-width 0.48
```

`renderer.py` は表示座標だけを扱い、データの配分や表示窓選択には触れません。
