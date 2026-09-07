# multiclass VDP/ZK evaluation 多類別 VDP/ZK 成本實驗

本實驗將實際 EZKL-backed VDP 約束檢查擴展到 Adult Income 以外的多類別資料集。預設使用 `wine` 三類分類資料集驗證完整 42 維 DP 更新向量，也可指定 `digits` 驗證 650 維更新向量，以觀察模型維度增加時的 proof cost。

## 實驗目的

- 檢查多類別資料集的 DP 更新是否也能轉換為 ZKML 可審計約束條件。
- 比較誠實更新與篡改 noisy update 的驗證結果。
- 量測 EZKL proof 相關成本，例如 proving time、verification time、proof size、key size 與 circuit rows。

## 執行方式

```powershell
python multiclass_vdp_zk\run_wine_vdp_zk_cost.py
```

執行 `digits` scaling/cost 實驗：

```powershell
python multiclass_vdp_zk\run_wine_vdp_zk_cost.py --dataset digits
```

## 輸出檔案

- `results/wine_vdp_zk_cost.csv`
- `results/digits_vdp_zk_cost.csv`
- `results/wine_summary.md`
- `results/digits_summary.md`
- `results/config.json`

大型 EZKL 生成物會放在 `results/ezkl_cases/`，並已由 `.gitignore` 排除。

## 實驗範圍

這一步驗證的是多類別資料集上的 VDP 約束與 proof cost，尚未把 Wine 的 proof-gated aggregation 完整接回多輪 FL 訓練流程。
