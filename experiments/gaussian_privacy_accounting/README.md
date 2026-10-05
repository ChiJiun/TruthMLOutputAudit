# Gaussian privacy accounting 正式 Privacy Accounting 與 Utility Frontier

本實驗補上結案報告最重要的方法限制：目前 VDP artifact 將 deterministic `noise_seed` 列為 public input，因此 verifier/server 可以重建並扣除 noise。現行機制不能直接套用 Gaussian privacy accountant，從 verifier view 應記為 `epsilon = infinity`。

實驗同時提供條件式分析：如果 deployment 改用 verifier 不知道的秘密、獨立 Gaussian randomness，則可用 RDP accountant 計算 client-level `(epsilon, delta)`，並觀察達到不同 epsilon 所需 noise 對 accuracy 的影響。

## Accounting 範圍

- Client-level DP，不是 record-level DP-SGD。
- 每個 client 每輪上傳一個 clipping 後更新，client participation `q=1`。
- Add/remove adjacency sensitivity 為 `C`；保守 replace-one sensitivity 為 `2C`。
- 使用 Gaussian RDP 的 sequential composition 與 classic conservative `(epsilon, delta)` conversion。
- 有限 epsilon 僅在 noise seed 對 verifier 保密且 noise 確實為獨立 Gaussian 時成立。

## 執行

```powershell
python -m unittest discover -s experiments/gaussian_privacy_accounting -p "test*.py" -v
python experiments/gaussian_privacy_accounting/run_privacy_accounting_experiment.py
```

只產生 accounting tables、不跑模型：

```powershell
python experiments/gaussian_privacy_accounting/run_privacy_accounting_experiment.py --skip-training
```

## 輸出

- `results/privacy_accounting_scenarios.csv`
- `results/target_noise_requirements.csv`
- `results/privacy_utility_runs.csv`
- `results/privacy_utility_summary.csv`
- `results/privacy_utility_frontier.png`
- `results/summary.md`
- `results/config.json`

## 不能省略的限制

只把 seed 從 JSON 移除並不足以形成 verifiable DP。正式版本還需在電路內驗證 `secret seed -> PRG -> Gaussian/discrete-Gaussian noise`，並使用 commitment、VRF/commit-reveal 或 distributed noise generation 避免 client 與 verifier 任意選擇 randomness。
