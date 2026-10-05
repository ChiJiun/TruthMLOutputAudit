# FedAvg baseline - FedAvg Simulator

FedAvg baseline 的目標是建立聯邦學習 baseline，使用 `K=3` clients 跑 `FedAvg`。

## 本週任務

- 使用 Adult Income model 的 client split
- 執行 `FedAvg`
- 設定 `K=3, R=5, E=1`
- 輸出每一輪 accuracy 與 round time

## 執行方式

從專案根目錄：

```bash
python experiments/fedavg_baseline/run_fedavg.py
```

或先進入資料夾：

```bash
cd experiments/fedavg_baseline
python run_fedavg.py
```

## 輸出

- `results/round_metrics.csv`
- `results/summary.md`
- `models/fedavg_global_model.pt`

## 備註

- 目前 baseline 使用與 Adult Income model 相同的純線性模型
- 後續 FedAvg round analysis 會直接讀取 `round_metrics.csv` 繪製 `Round vs Accuracy`
