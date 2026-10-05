# baseline visualization - Baseline Charts

baseline visualization 的目標是把 quantization scale sweep 的 scale sweep 結果整理成可展示的圖表。

## 本週任務

- 讀取 quantization scale sweep 的 `scale_sweep_results.csv`
- 產出 `scale vs accuracy`
- 產出 `scale vs proving time`
- 彙整簡短圖表摘要

## 執行方式

從專案根目錄：

```bash
python experiments/baseline_charts/generate_charts.py
```

或先進入資料夾：

```bash
cd experiments/baseline_charts
python generate_charts.py
```

## 輸出

- `results/scale_vs_accuracy.png`
- `results/scale_vs_proving_time.png`
- `results/summary.md`

## 備註

- 如果 quantization scale sweep CSV 還沒有 `proving_time_sec`，腳本仍會產出 proving time 圖，但會明確標示資料待補
