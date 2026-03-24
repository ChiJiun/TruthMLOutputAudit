# Week 4 - Baseline Charts

Week 4 的目標是把 Week 3 的 scale sweep 結果整理成可展示的圖表。

## 本週任務

- 讀取 Week 3 的 `scale_sweep_results.csv`
- 產出 `scale vs accuracy`
- 產出 `scale vs proving time`
- 彙整簡短圖表摘要

## 執行方式

從專案根目錄：

```bash
python week4_baseline_charts/generate_charts.py
```

或先進入資料夾：

```bash
cd week4_baseline_charts
python generate_charts.py
```

## 輸出

- `results/scale_vs_accuracy.png`
- `results/scale_vs_proving_time.png`
- `results/summary.md`

## 備註

- 如果 Week 3 CSV 還沒有 `proving_time_sec`，腳本仍會產出 proving time 圖，但會明確標示資料待補
