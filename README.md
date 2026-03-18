---
title: kf-stock-watch
emoji: 🚀
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.44.1
app_file: app.py
pinned: false
---

# KF-StockWatch

> 飲食店の在庫を見える化して、在庫切れとロスを防ぐ。

## The Problem

飲食店の在庫管理が地獄。何がいつ切れるか把握できない。

## How It Works

1. 在庫CSV（品名・数量・単位・日付）をアップロード
2. DuckDBで集計し、現在の在庫状況を表示
3. 消費トレンドをグラフで可視化
4. 閾値以下の在庫にアラート表示
5. レポートCSVをダウンロード

## Libraries Used

- **DuckDB** — インメモリSQL実行による高速集計
- **Streamlit charts** — 消費トレンドのグラフ表示

## Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Hosted on [Hugging Face Spaces](https://huggingface.co/spaces/mitoi/kf-stock-watch).

---

Part of the [KaleidoFuture AI-Driven Development Research](https://kaleidofuture.com) — proving that everyday problems can be solved with existing libraries, no AI model required.
