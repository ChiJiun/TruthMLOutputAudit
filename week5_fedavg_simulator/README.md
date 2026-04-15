# Week 5 - FedAvg Simulator

Week 5 的目標是建立聯邦學習 baseline，使用 `K=3` clients 跑 `FedAvg`。

## 本週任務

- 使用 Week 2 的 client split
- 執行 `FedAvg`
- 設定 `K=3, R=5, E=1`
- 輸出每一輪 accuracy 與 round time

## 執行方式

從專案根目錄：

```bash
python week5_fedavg_simulator/run_fedavg.py
```

或先進入資料夾：

```bash
cd week5_fedavg_simulator
python run_fedavg.py
```

## 輸出

- `results/round_metrics.csv`
- `results/summary.md`
- `models/fedavg_global_model.pt`

## 備註

- 目前 baseline 使用與 Week 2 相同的純線性模型
- 後續 Week 6 會直接讀取 `round_metrics.csv` 繪製 `Round vs Accuracy`
