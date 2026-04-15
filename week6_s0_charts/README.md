# Week 6 - S0 Round vs Accuracy

Week 6 的目標是把 Week 5 的 FedAvg baseline 整理成 `Round vs Accuracy` 圖。

## 本週任務

- 讀取 Week 5 的 `round_metrics.csv`
- 產出 `Round vs Accuracy` 圖
- 彙整簡短摘要

## 執行方式

從專案根目錄：

```bash
python week6_s0_charts/generate_round_accuracy_chart.py
```

或先進入資料夾：

```bash
cd week6_s0_charts
python generate_round_accuracy_chart.py
```

## 輸出

- `results/round_vs_accuracy.png`
- `results/summary.md`

## 備註

- 這個圖表對應到 S0 baseline，也就是尚未加入 DP 與 ZK 驗證的聯邦學習版本
