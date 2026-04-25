# TruthMLOutputAudit

專案現在改成以「每週進度一個資料夾」的方式整理。

## 專案結構

- `week1_demo/`：Week 1 的 EZKL demo 與產物
- `week2_uci_model/`：Week 2 的 UCI Adult Income 模型實驗
- `week3_scale_sweep/`：Week 3 的 scale sweep 實驗
- `week4_baseline_charts/`：Week 4 的 baseline 圖表整理
- `week5_fedavg_simulator/`：Week 5 的 FedAvg 聯邦學習 baseline
- `week6_s0_charts/`：Week 6 的 S0 Round vs Accuracy 圖表
- `week7_dp_updater/`：Week 7 的 DP updater baseline
- `week8_epsilon_sweep/`：Week 8 的 epsilon sweep 與圖表
- `week9_clipping_verification/`：Week 9 的 clipping 驗證原型
- `week10_noise_verification/`：Week 10 的 noise 驗證原型
- `week11_quantized_constraints/`：Week 11 的整數 constraint 檢查原型
- `week12_canonical_witness/`：Week 12 的 canonical witness 實驗
- `week13_recommended_constraints/`：Week 13 的推薦 constraint profile
- `week14_constraint_artifacts/`：Week 14 的 constraint artifact 匯出
- `week15_zk_backend_stub/`：Week 15 的 backend-ready bundle
- `week16_s2_integration/`：Week 16 的 S2 整合 demo
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

### `week5_fedavg_simulator/`

Week 5 的 FedAvg baseline，包含：

- `run_fedavg.py`
- `results/round_metrics.csv`
- `results/summary.md`
- `models/fedavg_global_model.pt`

### `week6_s0_charts/`

Week 6 的 S0 圖表，包含：

- `generate_round_accuracy_chart.py`
- `results/round_vs_accuracy.png`
- `results/summary.md`

### `week7_dp_updater/`

Week 7 的 DP baseline，包含：

- `run_dp_fedavg.py`
- `dp_fedavg_core.py`
- `results/round_metrics_dp.csv`
- `results/summary.md`

### `week8_epsilon_sweep/`

Week 8 的 epsilon sweep，包含：

- `run_epsilon_sweep.py`
- `generate_epsilon_chart.py`
- `results/epsilon_sweep_results.csv`
- `results/epsilon_vs_accuracy.png`
- `results/summary.md`

### `week9_clipping_verification/`

Week 9 的 clipping 驗證原型，包含：

- `run_clipping_verification.py`
- `results/clipping_verification_cases.csv`
- `results/summary.md`

### `week10_noise_verification/`

Week 10 的 noise 驗證原型，包含：

- `run_noise_verification.py`
- `results/noise_verification_cases.csv`
- `results/summary.md`

### `week11_quantized_constraints/`

Week 11 的整數 constraint 檢查原型，包含：

- `run_quantized_constraint_checks.py`
- `results/quantized_constraint_cases.csv`
- `results/summary.md`

### `week12_canonical_witness/`

Week 12 的 canonical witness 實驗，包含：

- `run_canonical_witness_experiment.py`
- `results/canonical_witness_cases.csv`
- `results/summary.md`

### `week13_recommended_constraints/`

Week 13 的推薦 constraint profile，包含：

- `run_recommended_constraint_profile.py`
- `results/recommended_constraint_cases.csv`
- `results/summary.md`

### `week14_constraint_artifacts/`

Week 14 的 constraint artifact 匯出，包含：

- `run_constraint_artifact_export.py`
- `results/artifact_index.csv`
- `results/artifacts/*.json`
- `results/summary.md`

### `week15_zk_backend_stub/`

Week 15 的 backend-ready bundle，包含：

- `run_zk_backend_stub.py`
- `results/bundle_index.csv`
- `results/bundles/*/io_bundle.json`
- `results/bundles/*/verification_hint.json`
- `results/summary.md`

### `week16_s2_integration/`

Week 16 的 S2 整合 demo，包含：

- `run_s2_integration_demo.py`
- `run_actual_ezkl_constraint_demo.py`
- `results/s2_round_decisions.csv`
- `results/actual_ezkl_summary.md`
- `results/summary.md`

## 備註

- 目前 Week 1 與 Week 2 都各自維持獨立可執行
- 各週腳本支援兩種執行方式：從專案根目錄執行 `python weekX_xxx/script.py`，或先進入該週資料夾再執行 `python script.py`
- 若後續再延伸，建議直接沿用同樣命名方式新增資料夾
