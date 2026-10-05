# 實驗索引

本目錄集中 35 個可重現研究單元。各單元維持同一層，是為了保留既有的跨實驗 Python import 與資料路徑；不要再把新實驗放到 repository 根目錄。

閱讀順序以「目前核心」為先。早期 baseline 與中間約束實驗保留作為研究歷程與可追溯證據，不應和最新 Halo2 結果混成同一項保證。

## 目前核心

| 目錄 | 用途 | 主要入口／結果 |
|---|---|---|
| `halo2_verifiable_randomness` | Actual Halo2：context-bound secret、Poseidon PRG、canonical sampler、clipping/noise relation | `cargo test --release --manifest-path experiments/halo2_verifiable_randomness/Cargo.toml` |
| `discrete_noise_accounting` | 固定 `d=4, k=16` profile 的 exact PLD accountant | `centered_binomial_accountant.py`、`results/accounting_results.json` |
| `actual_multiround_halo2` | 3 clients × 10 rounds × 5 seeds 的逐更新 proof 與磁碟模型鏈重驗 | `run_experiment.py`、`results_roundtrip/summary.json` |
| `cross_backend_reproducibility` | 多 seed、硬體 manifest、跨 OS CI | `run_halo2_seed_benchmark.py` |
| `production_scaling` | 385–1,991 維 constraint cost 與 K/R scaling | `run_production_scaling.py` |
| `robust_aggregation` | 合法範圍內 poisoning 與 median／trimmed mean | `run_robust_aggregation.py` |
| `context_bound_randomness_protocol` | circuit 前身的 protocol/state-machine 參考實作 | `protocol_spec.md` |

## 約束與 proof-gated aggregation

| 目錄 | 用途 |
|---|---|
| `clipping_verification` | clipping 條件原型與 fail cases |
| `noise_relation_verification` | additive-noise relation 原型 |
| `quantized_constraint_analysis` | fixed-point／rounding 條件 |
| `canonical_witness` | canonical quantized witness 與 slack sweep |
| `constraint_profile` | 推薦 constraint profile |
| `constraint_artifacts` | statement/witness artifact export |
| `zk_backend_bundle` | backend-ready bundle |
| `ezkl_constraint_integration` | actual EZKL constraint proof |
| `proof_gated_round` | 驗證後才聚合的單輪流程 |
| `end_to_end_proof_gated_round` | proof gate 到模型回寫的端到端流程 |

## Baseline 與早期流程

| 目錄 | 用途 |
|---|---|
| `zk_ezkl_demo` | 最小 EZKL prove/verify pipeline |
| `adult_income_model` | UCI Adult 下載、前處理、模型與 client split |
| `quantization_scale_sweep` | 量化尺度與 proving cost |
| `baseline_charts` | 基礎圖表 |
| `fedavg_baseline` | FedAvg baseline |
| `fedavg_round_charts` | round–accuracy 圖 |
| `dp_fedavg_baseline` | clipping/noise updater baseline |
| `privacy_utility_sweep` | 早期 noise／utility sweep；不是正式 accountant |

## 泛化、成本與威脅評估

| 目錄 | 用途 |
|---|---|
| `breast_cancer_repeatability` | 二元資料重複實驗 |
| `binary_dataset_repeatability` | 多個二元資料集的 paired runs |
| `multiclass_repeatability` | Iris／Wine／Digits 重複實驗 |
| `multiclass_vdp_zk` | 多類別完整 update constraint proof |
| `zk_cost_scaling` | rows、time、RSS、payload scaling |
| `gaussian_privacy_accounting` | public-seed `epsilon = infinity` 與條件式 Gaussian RDP |
| `covertype_large_dataset_scaling` | 581,012 筆 CoverType 與 385 維 proof |
| `noniid_client_scaling` | K=3/10、IID／Dirichlet、5 seeds |
| `multiround_threat_matrix` | relation、clip、replay、zero-noise、bounded sign-flip |
| `experimental_rigor_audit` | 完整性、paired statistics、環境與 SHA-256 稽核 |

## 產物政策

- CSV、JSON、圖表與摘要若直接支撐報告主張，可以提交。
- `*.key`、`*.srs`、Rust `target/`、下載資料、衍生 NumPy arrays、smoke/CI output 不提交；它們都能由腳本重建。
- 新增主張時，同步更新 [`docs/research/claim-evidence-map.md`](../docs/research/claim-evidence-map.md)。
