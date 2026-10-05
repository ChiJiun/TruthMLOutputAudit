# multiclass repeatability 多類別資料集重複實驗

本實驗將 binary-dataset repeatability 的 FL/DP 重複實驗從二元分類擴展到非二元的多類別資料集。

資料集：

- Iris (`sklearn`)：3 類
- Wine (`sklearn`)：3 類
- Digits (`sklearn`)：10 類

相較於二元分類實驗，主要改動如下：

- 模型輸出從單一 sigmoid logit 改為每個類別一個 logit。
- 損失函數從 `BCEWithLogitsLoss` 改為 `CrossEntropyLoss`。
- 客戶端切分改為分層分配，盡量讓每個客戶端保有類別平衡。
- DP 更新邏輯維持一致：裁剪客戶端模型更新、加入以種子產生的高斯雜訊，再進行聚合。

## 執行方式

```powershell
python experiments/multiclass_repeatability/run_multiclass_dataset_repeats.py
```

可選的參數調整範例：

```powershell
python experiments/multiclass_repeatability/run_multiclass_dataset_repeats.py --rounds 15 --noise-multiplier 0.04
```

## 輸出檔案

- `results/multiclass_runs.csv`
- `results/multiclass_summary.csv`
- `results/summary.md`
- `results/config.json`

## 範圍說明

這是基準層級的多類別擴展，用來檢查任務不是二元分類時，FL/DP 行為是否仍穩定。此階段尚未針對這些多類別資料集產生新的 EZKL 證明。
