# 主張—腳本—結果對照

本表是結案報告與 README 的主張入口。數字若與二手摘要衝突，以列出的原始結果檔及其產生腳本為準。

| ID | 可使用主張 | 產生／驗證腳本 | 主要結果檔 | 必須一起寫出的限制 |
|---|---|---|---|---|
| C1 | Hidden randomness、context binding、Poseidon PRG、canonical sampler、clipping 與 additive relation 已進 actual Halo2 circuit | `experiments/halo2_verifiable_randomness/src/`；`cargo test --release --manifest-path experiments/halo2_verifiable_randomness/Cargo.toml` | `experiments/halo2_verifiable_randomness/results/halo2_context_noise_proof.json` | Freshness/replay 是 server state；不證明 local training |
| C2 | 固定 `d=4, k=16`、10 rounds 的 replacement-client accountant 給出 `epsilon <= 28.840669` at `delta=1e-5` | `experiments/discrete_noise_accounting/centered_binomial_accountant.py` | `experiments/discrete_noise_accounting/results/accounting_results.json` | 只適用固定 profile；Poseidon 結論依賴 computational assumptions |
| C3 | 3 clients × 10 rounds × 5 seeds，共 150 份逐更新 Halo2 proofs 通過，且模型鏈可由磁碟重驗 | `experiments/actual_multiround_halo2/run_experiment.py`、`verify_artifacts.py` | `experiments/actual_multiround_halo2/results_roundtrip/summary.json`、`artifact_sha256.json` | 四維合成資料；不等於完整自適應 transcript DP |
| C4 | Public deterministic seed 可被 verifier 扣除，故舊機制 `epsilon = infinity` | `experiments/gaussian_privacy_accounting/run_privacy_accounting_experiment.py` | `experiments/gaussian_privacy_accounting/results/privacy_accounting_scenarios.csv` | 這是舊 public-seed 線的負面結果；不可拿來否定新的固定 Halo2 profile |
| C5 | 385–1,991 維 constraint proofs 與 K=10–50、R=3–20 FL scaling 已量測 | `experiments/production_scaling/run_production_scaling.py` | `experiments/production_scaling/results/actual_ezkl_proof_scaling.csv`、`scaling_summary.csv` | 高維 proof 不含 hidden randomness／local training；1,000-proof workload 是外推 |
| C6 | CoverType 581,012 筆、K=3/10、IID／Dirichlet 的壓力測試可重現 | `experiments/covertype_large_dataset_scaling/run_covertype_scaling.py`、`experiments/noniid_client_scaling/run_noniid_client_scaling.py` | 各自 `results/*_summary.csv` | 小型線性模型；3–5 seeds，多數比較不具統計顯著性 |
| C7 | Relation tamper／clip bypass 可拒絕；bounded sign-flip 在合法範圍內仍 100% 通過 | `experiments/multiround_threat_matrix/run_multiround_threat_matrix.py` | `experiments/multiround_threat_matrix/results/threat_summary.csv` | 1,440 decisions 是 policy simulation，不是 1,440 份 actual proofs |
| C8 | 20% bounded poisoning 下，median／trimmed mean 比 mean 有改善，但未恢復乾淨效用 | `experiments/robust_aggregation/run_robust_aggregation.py` | `experiments/robust_aggregation/results/aggregation_summary.csv`、`robustness_comparisons.csv` | 300/300 malicious updates 仍通過 gate；只涵蓋所測 attack |
| C9 | 核心矩陣的 row count、pairing、環境與 SHA-256 已稽核 | `experiments/experimental_rigor_audit/analyze_rigor.py` | `experiments/experimental_rigor_audit/results/completeness.json`、`sha256_manifest.csv` | SHA-256 證明檔案一致性，不證明論文主張本身正確 |

## 報告引用規則

1. 每個結果數字至少連到一個 raw CSV／JSON，不只連到 Markdown 摘要。
2. 對 C2、C3、C5 分開列 profile，不以同一列暗示高維享有四維 epsilon。
3. 負面結果 C4、C7、C8 保留在正文，不只放附錄。
4. 若重新跑實驗，更新結果檔、硬體 manifest、hash 與本表，不手動只改報告數字。
