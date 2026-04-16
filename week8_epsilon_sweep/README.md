# Week 8 - Epsilon Sweep

Week 8 的目標是測試不同 `epsilon` 對 S1 baseline 的影響，並整理成圖表。

## 本週任務

- 測試 `epsilon = 0.5 / 1 / 2`
- 比較 accuracy 與 round time
- 輸出 `epsilon vs accuracy`

## 執行方式

從專案根目錄：

```bash
python week8_epsilon_sweep/run_epsilon_sweep.py
python week8_epsilon_sweep/generate_epsilon_chart.py
```

或先進入資料夾：

```bash
cd week8_epsilon_sweep
python run_epsilon_sweep.py
python generate_epsilon_chart.py
```

## 輸出

- `results/epsilon_sweep_results.csv`
- `results/epsilon_vs_accuracy.png`
- `results/summary.md`

## 重要說明

- 目前這版使用簡化的 `epsilon -> noise_multiplier` baseline 對應
- 可用於比較趨勢，但不能直接視為正式 DP accountant 結果
