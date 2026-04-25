# Week 14 - Constraint Artifact Export

Week 14 的目標是把 Week 13 的推薦 constraint profile 轉成更接近電路輸入的 artifact。

## 執行方式

```bash
python week14_constraint_artifacts/run_constraint_artifact_export.py
```

## 輸出

- `results/artifact_index.csv`
- `results/summary.md`
- `results/artifacts/*.json`

## 重要說明

- JSON 會固定 `public_inputs`、`witness` 與 `checks`
- 目前預設輸出 `scale=10000` 的 artifact
- 這些檔案的用途是幫下一步 ZK / EZKL 映射固定資料格式
