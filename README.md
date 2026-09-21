# TruthMLOutputAudit

本專案研究如何將聯邦學習中的差分隱私更新轉換為可由零知識證明審計的介面，並讓驗證結果實際控制聚合。Repository 依研究功能與實驗里程碑組織，不再使用週次編號。

## 研究主線

| 研究單元 | 內容 | 主要目錄 |
|---|---|---|
| 基礎模型與證明流程 | PyTorch／ONNX／EZKL、Adult Income、量化尺度、FedAvg 與 DP baseline | `zk_ezkl_demo/`、`adult_income_model/`、`quantization_scale_sweep/`、`fedavg_baseline/`、`dp_fedavg_baseline/` |
| DP update 約束工程 | Clipping、noise relation、canonical quantized witness、constraint profile 與 artifact | `clipping_verification/`、`noise_relation_verification/`、`quantized_constraint_analysis/`、`canonical_witness/`、`constraint_profile/`、`constraint_artifacts/` |
| Proof-gated aggregation | Backend bundle、actual EZKL integration、驗證後聚合與端到端 round | `zk_backend_bundle/`、`ezkl_constraint_integration/`、`proof_gated_round/`、`end_to_end_proof_gated_round/` |
| 泛化與成本評估 | Binary／multiclass repeatability、完整 update proof、ZK cost 與 CoverType scaling | `breast_cancer_repeatability/`、`binary_dataset_repeatability/`、`multiclass_repeatability/`、`multiclass_vdp_zk/`、`zk_cost_scaling/`、`covertype_large_dataset_scaling/` |
| Privacy 與威脅分析 | Gaussian accountant、non-IID clients、多輪攻擊矩陣及統計稽核 | `gaussian_privacy_accounting/`、`noniid_client_scaling/`、`multiround_threat_matrix/`、`experimental_rigor_audit/` |
| 可驗證隨機性 | Commit-before-challenge、hidden randomness、Poseidon PRG、離散 sampler 與正式 accountant | `context_bound_randomness_protocol/`、`halo2_verifiable_randomness/`、`discrete_noise_accounting/` |
| 投稿強化 | Cross-backend／硬體重現、較大型 federation 與 bounded-poisoning defense | `cross_backend_reproducibility/`、`production_scaling/`、`robust_aggregation/` |

## 核心成果

- 建立 S0 FedAvg、S1 DP update、S2 proof-gated aggregation 的完整實驗鏈。
- 以 canonical quantized witness 解決浮點到整數 constraint 的 rounding 不一致。
- 在 EZKL 中實際證明完整 update-vector clipping 與 additive-noise relation。
- 在 Zcash Halo2 中實作 context-bound Poseidon PRG、canonical field decomposition 與 centered-binomial sampler。
- 對固定四維、`k=16`、十輪 profile 建立 replacement client-level PLD accountant：`epsilon <= 28.840669` at `delta=1e-5`。
- 完成 10-seed Halo2 reproducibility、Windows/Linux CI 與 EZKL/Halo2 backend coverage。
- CoverType 實驗擴至 50 clients、20 rounds、1,991 維 constraint profile。
- 以 10-seed paired experiment 評估 coordinate median 與 trimmed mean 對 20% bounded poisoning 的緩解效果。

## 目錄說明

### 基礎模型與 FL／DP baselines

- `zk_ezkl_demo/`：最小 EZKL train/export/prove/verify pipeline。
- `adult_income_model/`：Adult Income preprocessing、模型訓練與 EZKL artifacts。
- `quantization_scale_sweep/`：量化 scale 對 accuracy 與 proving cost 的影響。
- `baseline_charts/`：基礎實驗視覺化。
- `fedavg_baseline/`、`fedavg_round_charts/`：FedAvg 與 round-accuracy baseline。
- `dp_fedavg_baseline/`、`privacy_utility_sweep/`：clipping/noise updater 與早期 privacy-utility sweep。

### 約束、proof 與聚合

- `clipping_verification/`、`noise_relation_verification/`：DP update 原始條件驗證。
- `quantized_constraint_analysis/`、`canonical_witness/`、`constraint_profile/`：fixed-point constraint、canonical witness 與 slack policy。
- `constraint_artifacts/`、`zk_backend_bundle/`：可重現 statement/witness bundles。
- `ezkl_constraint_integration/`：actual EZKL constraint proof。
- `proof_gated_round/`、`end_to_end_proof_gated_round/`：accepted-only aggregation 與模型回寫。

### 泛化、成本與隱私分析

- `breast_cancer_repeatability/`、`binary_dataset_repeatability/`、`multiclass_repeatability/`：跨資料集 paired experiments。
- `multiclass_vdp_zk/`、`zk_cost_scaling/`：完整 update proof 與 rows/time/RSS/payload scaling。
- `gaussian_privacy_accounting/`：public-seed limitation、Gaussian RDP 與 privacy-utility frontier。
- `covertype_large_dataset_scaling/`、`noniid_client_scaling/`：581,012-row CoverType、IID/Dirichlet 與 client-count scaling。
- `multiround_threat_matrix/`：relation tamper、clip bypass、replay、zero noise 與 bounded sign flip。
- `experimental_rigor_audit/`：矩陣完整性、paired statistics、Holm correction、環境與 SHA-256 稽核。

### 可驗證隨機性與投稿強化

- `context_bound_randomness_protocol/`：setup commitment、commit-before-challenge、freshness 與 replay semantics。
- `halo2_verifiable_randomness/`：actual Halo2/Poseidon hidden-randomness sampler circuit。
- `discrete_noise_accounting/`：exact centered-binomial PLD theorem/accountant。
- `cross_backend_reproducibility/`：10-seed proofs、硬體 manifest 與跨 OS CI。
- `production_scaling/`：385–1,991 維 actual EZKL，以及 K=10–50、R=3–20 FL scaling。
- `robust_aggregation/`：mean、coordinate median、trimmed mean 的 bounded-poisoning evaluation。

## 主要執行方式

新增逐更新 Halo2 多輪實驗：[actual_multiround_halo2/README.md](actual_multiround_halo2/README.md)。
以四參數合成資料訓練，逐份產生／驗證 proof、重用 circuit keys，並從磁碟重建
model chain；這是固定範圍的整合證據，不代表高維 production 或完整 transcript DP。

各模組可以從 repository root 執行，也可以進入模組目錄執行其主程式。投稿強化流程例如：

```powershell
cd halo2_verifiable_randomness
cargo test --release
cargo run --release -- results/halo2_context_noise_proof.json 42

cd ..
python discrete_noise_accounting/centered_binomial_accountant.py
python cross_backend_reproducibility/run_halo2_seed_benchmark.py
python production_scaling/run_production_scaling.py
python robust_aggregation/run_robust_aggregation.py
```

正式結論、限制與可使用主張見 `docs/publication_strengthening_report.md`；研究規劃見 `docs/VDP-FL-research-plan.md`。
