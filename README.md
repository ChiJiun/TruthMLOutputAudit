# TruthMLOutputAudit

專案現在改成以「每週進度一個資料夾」的方式整理。

## 專案結構

- `week1_demo/`：Week 1 的 EZKL demo 與產物
- `week2_uci_model/`：Week 2 的 UCI Adult Income 模型實驗
- `week3_scale_sweep/`：Week 3 的 scale sweep 實驗
- `week4_baseline_charts/`：Week 4 的 baseline 圖表整理
- `docs/`：研究規劃與筆記
- `requirements.txt`：目前專案使用的 Python 套件清單

## 每週內容

### `week1_demo/`

簡化版的 EZKL demo 流程，包含：

- `1_train_and_export.py` 到 `4_verify.py`
- `ezkl_pipeline.py`
- `common.py`
- demo 相關產物，例如 `demo_model.onnx`、`settings.json`、`proof.json`

### `week2_uci_model/`

正式的 UCI Adult Income 實驗，包含：

- `data_preprocessing.py`
- `train_model.py`
- `train_model_simple.py`
- `ezkl_pipeline.py`
- `data/`、`models/`、`src/`、`results/`

### `week3_scale_sweep/`

Week 3 的 scale sweep，包含：

- `run_scale_sweep.py`
- `results/scale_sweep_results.csv`
- `artifacts/` 中各 scale 的 EZKL 產物

### `week4_baseline_charts/`

Week 4 的 baseline 圖表，包含：

- `generate_charts.py`
- `results/scale_vs_accuracy.png`
- `results/scale_vs_proving_time.png`
- `results/summary.md`

## 備註

- 目前 Week 1 與 Week 2 都各自維持獨立可執行
- 各週腳本支援兩種執行方式：從專案根目錄執行 `python weekX_xxx/script.py`，或先進入該週資料夾再執行 `python script.py`
- 之後若新增 Week 5、Week 6，建議直接沿用同樣命名方式新增資料夾
