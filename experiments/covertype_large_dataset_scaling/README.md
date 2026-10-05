# CoverType large-data scaling Forest CoverType 大型資料集 Scaling

本實驗回應審查意見中「資料集過小，難以支撐實務可行性」的疑慮，使用 Forest CoverType：

- 581,012 筆樣本
- 54 個特徵
- 7 類別分類
- 線性模型完整更新向量 385 維

實驗使用固定 20% test split，依序比較 10,000、100,000 與完整 training split。每個規模使用 seeds 42、52、62，並以相同 split、client partition、模型初始化及 batch shuffle 執行 paired FL／clipping-only／DP-update 比較。Clipping-only control 用來區分效用下降來自 clipping 或 noise。

## 執行

```powershell
python experiments/covertype_large_dataset_scaling/run_covertype_scaling.py --modes fl clip dp
```

完整資料產生的 385 維 update 之 actual EZKL honest/tampered 檢查：

```powershell
python experiments/covertype_large_dataset_scaling/run_covertype_vdp_zk.py
```

中斷後續跑：

```powershell
python experiments/covertype_large_dataset_scaling/run_covertype_scaling.py --modes fl clip dp --resume
```

快速 smoke test：

```powershell
python experiments/covertype_large_dataset_scaling/run_covertype_scaling.py --train-sizes 10000 --seeds 42 --rounds 1 --results-dir experiments/covertype_large_dataset_scaling/smoke_results
```

## 輸出

- `results/covertype_scaling_runs.csv`
- `results/covertype_scaling_summary.csv`
- `results/covertype_scaling.png`
- `results/summary.md`
- `results/config.json`
- `results/worker_rows/*.json`
- `results/covertype_vdp_zk_cost.csv`
- `results/covertype_vdp_zk_summary.md`

## 解讀邊界

- 此實驗隔離「訓練樣本量」對 FL/DP utility、時間與記憶體的影響。
- 目前使用 stratified IID client partition，不代表 non-IID robustness。
- Constraint-only ZK 成本主要受模型更新維度影響；資料集由小變大不會直接增加 385 維 update proof 的輸入維度。
- Public deterministic noise seed 的正式 DP 限制不變，現行 verifier view 仍為 `epsilon = infinity`。
