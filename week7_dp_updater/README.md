# Week 7 - DP Updater

Week 7 的目標是把 `clipping + Gaussian noise` 加入聯邦學習流程，建立 `S1` 的第一版 baseline。

## 本週任務

- 以 Week 5 的 FedAvg 為基礎
- 對每個 client update 計算 `Δw`
- 對 `Δw` 做 L2 clipping
- 對 clipped update 加入 Gaussian noise
- 記錄 round-level accuracy 與 update 統計量

## 執行方式

從專案根目錄：

```bash
python week7_dp_updater/run_dp_fedavg.py
```

或先進入資料夾：

```bash
cd week7_dp_updater
python run_dp_fedavg.py
```

## 輸出

- `results/round_metrics_dp.csv`
- `results/summary.md`
- `models/dp_fedavg_global_model.pt`

## 重要說明

- 目前這版是 `DP baseline for experimentation`
- `noise_multiplier` 與 `epsilon` 的對應尚未使用正式 privacy accountant
- 因此這一版適合做趨勢比較與流程驗證，不應直接視為正式合規聲明
