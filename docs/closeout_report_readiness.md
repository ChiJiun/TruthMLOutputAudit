# 結案報告準備度與寫作清單

截至 robust aggregation，本專題已具備撰寫結案報告所需的完整實驗鏈、actual context-bound Halo2 sampler、finite-profile client-level accountant、兩種proof backend、大型/non-IID/scaling資料、多輪威脅矩陣、10-seed robust aggregation及統計/硬體可重現性證據。最新完整判定見 `docs/publication_strengthening_report.md`。

## 建議最終題目定位

**基於 ZKML 的聯邦學習 DP-update 可審計原型：量化約束、Proof-gated Aggregation、成本與 Privacy Budget 邊界**

可以對the Halo2 sampler and discrete-accounting modules固定的四維、`k=16`、replacement-client profile宣稱條件式finite-epsilon verifiable DP；不可將此主張外推成任意高維、任意participation或完整local-training的production VDP系統。

## 已完成的核心證據

| 結案問題 | 實驗證據 | 可寫入的結論 |
|---|---|---|
| FL 是否收斂 | the federated-learning baseline modules S0 | 小型 K=3 設定下 FedAvg 可穩定收斂 |
| 低強度 noise 對 utility 的影響 | the DP baseline and privacy-utility modules、19-21 | 預設設定在多數資料集維持高 retention，但不等於正式 DP |
| Clipping/noise relation 能否被審計 | the constraint-engineering modules | Canonical quantized witness + fixed slack 可接受 honest 並拒絕 tampered cases |
| 驗證能否影響 FL | the proof-gated aggregation modules | Proof-gated aggregation 可排除篡改 client 並形成 round outcome |
| 是否只適用 Adult/binary | the repeatability and multiclass proof evaluations | 15 個小型資料集的 utility 實驗，Wine/Digits 完整更新 actual EZKL proof |
| 小型資料能否代表規模效果 | CoverType large-data scaling | CoverType 581,012 筆、27 組 scaling runs、clipping-only control 與 385 維 actual EZKL |
| 是否只在 K=3/IID 成立 | non-IID client scaling | CoverType K=3/10、IID/Dirichlet、5 seeds、90 mode runs；DP/FL retention 0.762431–0.962019 |
| 多輪 gate 能阻止哪些攻擊 | multi-round threat matrix | 48 trajectories、1,440 decisions；relation/clip 接受率 0%，replay/zero-noise 缺口與 strengthened policy 對照 |
| 是否能阻止任意 poisoning | multi-round threat matrix | Bounded sign-flip 在 current/strengthened gate 皆 100% 通過，明確否定過度主張 |
| Raw results 是否完整、配對且可驗證 | experimental-rigor audit | 27/27、90/90、48/48、1,440/1,440 全部齊全；33 paired effects、exact permutation、Holm、環境版本與 SHA-256 |
| Randomness/context 缺口是否有可執行修正規格 | context-bound randomness protocol | Commit-before-challenge、hidden seed、single-use challenge、10/10 reference threats；仍非 actual circuit |
| ZK 成本是否可量化 | the multiclass proof and cost-scaling modules | 15/42/650 維的 time、rows、keys、RSS 與 payload |
| 是否具有正式 privacy budget | Gaussian privacy accounting | Public seed 現況 epsilon infinity；秘密 Gaussian 條件下原設定 epsilon 3504.357 |
| Privacy 與 utility 如何取捨 | Gaussian privacy accounting | epsilon 128/32/8 所需 noise 使三個資料集 retention 明顯下降 |

## 結案報告必放的圖表

1. S0 round vs accuracy。
2. S0/S1 accuracy 或 epsilon/noise baseline comparison。
3. Honest/tampered constraint acceptance table。
4. Proof-gated round：accepted 2/3、rejected 1/3。
5. ZK cost scaling proving time、peak RSS、S1/S2 payload scaling 圖。
6. Gaussian privacy accounting privacy-utility frontier 圖。
7. CoverType large-data scaling CoverType large-dataset scaling 圖。
8. non-IID client scaling non-IID × client scaling 圖。
9. multi-round threat matrix multi-round threat matrix 圖。

主要檔案：

- `zk_cost_scaling/results/zk_cost_scaling.png`
- `gaussian_privacy_accounting/results/privacy_utility_frontier.png`
- `covertype_large_dataset_scaling/results/covertype_scaling.png`
- `covertype_large_dataset_scaling/results/covertype_vdp_zk_summary.md`
- `noniid_client_scaling/results/noniid_client_scaling.png`
- `multiround_threat_matrix/results/threat_matrix.png`
- `docs/hypothesis_evidence_matrix.md`
- `experimental_rigor_audit/results/summary.md`
- `experimental_rigor_audit/results/paired_effects.csv`
- `experimental_rigor_audit/results/sha256_manifest.csv`
- `gaussian_privacy_accounting/results/summary.md`

## 建議章節結構

1. 研究背景與可信缺口
2. 問題定義與主張邊界
3. S0/S1/S2 方法
4. Canonical quantized witness 與 fixed-slack policy
5. Baseline 與 paired evaluation protocol
6. Proof-gated aggregation
7. 跨資料集、大型/non-IID 與 client scaling
8. 多輪 threat matrix 與安全/availability trade-off
9. Privacy accountant 與負面結果
10. 審查意見回應
11. 限制、未來工作與結論

## 必須誠實寫出的限制

- 現行 `noise_seed` 是 public input，privacy budget 為 infinity。
- Actual EZKL 驗證 additive relation 與 clipping output，未驗證 secret PRG/Gaussian distribution。
- Accountant 是 client-level、q=1，不是 record-level DP-SGD。
- 模型仍是線性分類器，最多 10 clients；多數實驗只有 3–5 seeds。
- Strengthened context/randomness policy 尚未全部進入 actual ZK circuit。
- Update gate 無法驗證 local-training provenance；bounded poisoning 仍可通過。
- RSS 與 payload 是工程估計，不代表 production network。

## 最終可支持的核心主張

> 本研究證明聯邦學習 DP update 中的 clipping 與 noise additive relation 可被轉換為 ZKML 可審計約束，且驗證結果可控制聚合。16 個資料集、581,012 筆 CoverType、K=3/10 non-IID scaling 與多輪 threat matrix 支持此原型在線性模型上的可重現性。Privacy accountant 與攻擊實驗同時顯示，auditability 不等於 formal DP 或完整 poisoning defense：現行 public deterministic seed 無有限 privacy budget，replay/randomness 需額外 binding，而 local-training provenance 仍待解決。

## 寫作前最後檢查

- [x] 所有主要結果有 CSV/JSON 原始資料
- [x] Actual proof/verify 有成功與 fail cases
- [x] ZK 成本包含 time、size、rows、keys、RSS、payload
- [x] Baseline 與 evaluation protocol 已明確定義
- [x] Reviewer concerns 已逐項回應
- [x] Privacy accountant 與 utility frontier 已完成
- [x] 大型資料、K=10 與 Dirichlet non-IID scaling 已完成
- [x] 多輪 threat matrix 與 hypothesis evidence matrix 已完成
- [x] 統計、矩陣完整性、環境版本與結果雜湊稽核已完成
- [ ] 將最終圖表嵌入學校指定格式的結案報告模板
- [ ] 依頁數限制濃縮方法與附錄
- [ ] 最後校對引用、圖表編號與術語一致性
