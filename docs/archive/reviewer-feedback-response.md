# 審查意見回應與研究修正對照

本文件將兩位審查人的意見對照至目前實作、實驗證據、尚存限制與論文修改。回應原則是：已有數據者以數據回答；只有部分證據者明確限制主張；尚未完成者列為後續工作，不以推測代替結果。

## 審查人 1

審查人肯定研究背景、方法組織、三項研究任務的技術合理性與整體品質。目前成果維持原三階段主線：

- S0：FedAvg 聯邦學習基準。
- S1：加入 clipping 與 Gaussian noise 的 DP 更新。
- S2：將量化後 clipping bound 與 additive noise relation 映射為 EZKL 可驗證條件，並接回 proof-gated aggregation。

最終文件會保留此清楚的三階段結構，同時補上審查人 2 指出的可行性、貢獻邊界與評估協議。

## 審查人 2：逐項回應

| 審查疑慮 | 狀態 | 已完成的回應證據 | 仍需保留的限制 |
|---|---|---|---|
| Halo2/EZKL 成本被低估，缺少量化基準與風險分析 | 已大幅補強 | 除15/42/650維外，production-oriented scaling 再以385/999/1,991維各3 seeds完成9/9 actual EZKL proofs；prove mean為0.530/1.524/1.658秒、peak RSS為419.1/439.4/471.3 MiB。Halo2 verifiable-randomness circuit/32另完成actual Halo2 sampler circuit與10/10 seed proofs。 | 高維 proof仍是update constraint，不含forward/backward；K=50/R=20逐更新全量proof成本為外推。 |
| 研究較像系統整合，缺少新演算法 | 接受並重新定位 | 不宣稱提出新的 DP optimizer、ZKP protocol 或 proof system。貢獻定位為：canonical quantized witness、由 honest/tampered gap 導出的 fixed-slack policy、proof-gated aggregation contract，以及可重現的 VDP/ZK 審計評估流程。 | 這是方法工程與實證型系統研究，不應宣稱一般性的密碼學或最佳化演算法 novelty。 |
| 僅使用 MNIST / Heart Disease 等小型資料，實驗薄弱 | 已大幅補強 | 最終涵蓋16個資料集與581,012-row CoverType；production-oriented scaling再加入MLP-16 training、MLP-32 constraint dimension、K=10/25/50、R=3/10/20與40條5-seed trajectories。 | 仍非natural-client benchmark；MLP training provenance未進circuit。 |
| 未明確定義 baseline 與 evaluation protocol | 已補強 | 明確定義 S0、S1、S2；paired modes 共用 split、partition、初始化與 shuffle。定義 accuracy、retention、CI、label TV、acceptance、proof cost、RSS 與 payload。multi-round threat matrix 加入 5 attacks × 3 policies；experimental-rigor audit 再驗證完整矩陣、paired effects、exact permutation、Holm correction、環境版本與 SHA-256。 | n=3/n=5 的 exact test resolution 不足以支持「統計顯著」；結果定位為描述性、effect-size 與可行性證據。 |
| DP privacy budget 未被正式驗證 | 已完成 exact sampler accountant | discrete-noise accounting 對centered-binomial finite-support mechanism做conservative PLD composition；固定d=4、k=16、10 rounds、replacement-client adjacency得到epsilon≤28.840669 at delta=1e-5。 | Actual Poseidon為PRF assumption下的computational DP；不外推至385–1,991維、add/remove participation或record-level DP。 |
| Replay/context/randomness 缺口只有未來工作 | 已進actual circuit | context-bound randomness protocol state machine加上the Halo2 verifiable-randomness circuit Halo2 secret/update commitments、context-bound Poseidon PRG、canonical discrete sampler；tamper/context swap/zero-noise tests皆拒絕。 | Single-use challenge/replay cache仍需server state；selective abort、collusion與PRF security仍需更完整分析。 |
| 合法bounded poisoning仍可通過gate | 已加入robust aggregation | robust aggregation以10 seeds、20% attackers完成60 trajectories/3,000 decisions；median/trimmed mean相對mean retention gain為0.1988/0.1541，exact p=0.001953。 | 300/300 malicious updates仍通過gate，robust方法只顯著緩解所測攻擊，未取代local-training proof。 |

## 研究貢獻的適當表述

建議論文與答辯使用以下表述：

> 本研究不主張提出新的差分隱私演算法或零知識證明系統；研究貢獻在於把聯邦學習 DP 更新中的 clipping 與 noise relation 轉換為可穩定量化、可由 EZKL 證明、且能直接控制聚合決策的審計介面。其方法學重點是 canonical quantized witness 與 fixed-slack policy，系統重點則是 proof-gated aggregation 與跨資料集的成本／篡改評估。

避免使用以下過度主張：

- 「提出全新的 DP 演算法」
- 「解決大規模 ZK-FL」
- 「證明所有深度模型皆可在可接受成本下運行」
- 「目前 epsilon sweep 已提供正式 $(\epsilon,\delta)$ 隱私保證」

## Baseline 與 evaluation protocol

### Baselines

| 系統 | 組成 | 對照目的 | 主要指標 |
|---|---|---|---|
| S0 | FedAvg，不含 clipping/noise/proof | 確認 FL 收斂與效能上限 | round accuracy、final/best accuracy、round time |
| S1 | FedAvg + clipping + seeded Gaussian noise，不含 proof gate | 量測 DP update 對效能的影響；顯示未驗證聚合會接受任意上傳 | final accuracy、DP/FL retention |
| S2 | S1 + EZKL proof + clipping/relation public decision + accepted-only aggregation | 量測可信度增益與 ZK 成本 | honest acceptance、tampered rejection、prove/verify、proof size、RSS、payload |

### Paired protocol

- Train/test 採 80/20 stratified split。
- 所有 preprocessing transformer 只在 train split 上 fit，再套用到 test split。
- S0 與 S1 對每個 seed 重設相同 RNG，因此共用相同 split、client partition、模型初始化與本地訓練 shuffle；DP noise 使用額外的 deterministic generator。
- 二元多資料集：3 clients、5 rounds、1 local epoch、seeds 42/52/62。
- 多類別資料集：3 clients、10 rounds、2 local epochs、seeds 42/52/62，並採分層 client partition。
- `clip_norm=1.0`、`noise_multiplier=0.08` 為預設值；參數敏感資料集另行報告 sweep，不以調參後結果取代預設結果。
- DP/FL retention 定義為各模式 final accuracy 平均值之比，90% 為事先固定的 baseline-level 門檻。
- ZK fail case 對 `q_noisy` 偏移 1 個量化單位；只有 proof verified、clip OK 與 relation OK 同時成立時才接受。
- Large/non-IID protocol：CoverType 100,000 筆、K=3/10、IID/Dirichlet alpha=0.5/0.1、3 rounds、5 seeds，報告 label-TV 與 seed-level 95% t interval。
- Threat protocol：CoverType K=10、Dirichlet alpha=0.1、3 rounds、20% attackers；惡意接受率只計實際 attack submission，不把 replay 的第一輪 honest warm-up 納入分母。
- multi-round threat matrix 的 1,440 次 decision 是重用 actual-EZKL artifact/check contract 的 policy simulation，不宣稱產生了 1,440 份 proof；actual proof 成本由 EZKL constraint integration、22、23、25 獨立量測。

### experimental-rigor audit 統計與完整性稽核

- the large-data, non-IID, and threat-matrix evaluations expected/actual rows 為 27/27、90/90、48/48 trajectories、1,440/1,440 decisions；primary keys 無重複，seed sets 完整配對。
- 33 組 accuracy comparisons 以 seed 為單位報告 paired difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip p 與 family-level Holm-adjusted p。
- n=3 的最小 two-sided exact p 為 0.25，n=5 為 0.0625；Holm-adjusted p<0.05 為 0 組。因此本文不使用「統計顯著」，而以 effect、方向、範圍、原始 rows 與工程可重現性回答。
- 精確 Python/OS/package versions 與核心 scripts/results SHA-256 已保存，避免只保留無法追溯的圖表。

## 技術可行性與風險控制

### 已量測基準

| Dataset | 維度 | Circuit rows | Prove mean | Verify mean | Peak RSS | Proof | Proving key | S2 payload |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Iris | 15 | 138 | 0.100 s | 0.033 s | 410.0 MiB | 12.27 KB | 0.89 MB | 12,519 B |
| Wine | 42 | 379 | 0.154 s | 0.041 s | 412.5 MiB | 11.96 KB | 1.57 MB | 12,331 B |
| Digits | 650 | 5,851 | 0.586 s | 0.034 s | 426.0 MiB | 11.99 KB | 25.18 MB | 15,198 B |

### 本專題的工程門檻

下列門檻用於控制大專專題的執行風險，不是通用的 ZKML 效能標準：

| 狀態 | Proving time | Peak RSS | 單一 proving artifact | 處置 |
|---|---:|---:|---:|---|
| 綠色 | <= 10 s | <= 2 GiB | <= 256 MiB | 可納入重複實驗 |
| 黃色 | 10-60 s | 2-8 GiB | 256 MiB-1 GiB | 降低維度、減少 seeds 或拆分 constraint proof |
| 紅色 | > 60 s | > 8 GiB | > 1 GiB | 不納入本專題主張，改列 future work |

目前三個模型都在綠色範圍，但從 15 到 650 維時 circuit rows 增加約 42.4 倍、proving key 增加約 28.4 倍，已顯示擴展風險不能忽略。

### 風險邊界

- EZKL calibration 對大型量化 lookup input 會輸出警告；目前 runs 均通過，Digits mean absolute percent error 約為 $1.8\times10^{-6}\%$，但未來尺度改變時必須重新檢查 fidelity。
- Peak RSS 是 5 ms process polling，不是硬體層級 profiler。
- Communication payload 是 compact JSON update + proof + audit metadata，不含 TCP/TLS/HTTP framing。
- 先前 privacy accountant 尚未完成時，noise multiplier 實驗只能支撐相對 utility；Gaussian privacy accounting 已補做 accountant，並確認現行 public seed 仍不能形成有限 privacy budget。
- Gaussian privacy accounting 已完成條件式 RDP accountant，但 accountant 反而證明現行 public deterministic seed 不符合其隨機性前提，故不能宣稱有限 epsilon。
- 即使假設 seed 保密，10 rounds、replace-one、`delta=1e-5` 下的 `noise_multiplier=0.08` 仍只有 `epsilon=3504.357`；目標 epsilon 128/32/8 分別需要 multiplier 0.531/1.396/4.366，且三個資料集 retention 均隨隱私增強而明顯下降。
- multi-round threat matrix 顯示 current proof+clip+relation gate 對 replay 與 zero-noise 的惡意接受率都是 100%；加入 context/replay/noise-generation policy 後可降至 0%，但該 strengthened policy 尚未全部進入 actual ZK circuit。
- Bounded sign-flip 在 current 與 strengthened gate 的接受率都是 100%，因此本研究明確不宣稱完整 local-training correctness 或任意 poisoning defense。

## 可直接用於成果報告的回覆

> 感謝審查人指出技術可行性、研究貢獻定位、資料集規模與評估協議不足。執行階段已據此調整：首先，不再以抽象的「可接受成本」描述 ZKML，而是在 15、42、385、650 維完整更新上實際量測 proving/verification time、proof size、peak RSS、key 與 payload。其次，本研究不宣稱新的 DP 或 ZKP 演算法，而將貢獻界定為 canonical quantized witness、fixed-slack policy、proof-gated aggregation contract 與實證評估流程。第三，實驗擴充至 16 個資料集；Forest CoverType 有 581,012 筆，並進一步完成 K=3/10、IID/Dirichlet、5 seeds 共 90 runs。第四，論文明確定義 paired baselines、CI、heterogeneity、tampered fail case 與成本指標。第五，K=10 non-IID 多輪 threat matrix 完成 48 條 trajectories 與 1,440 次 client 決策，證明 current gate 能拒絕 relation/clip 違規，也揭露 replay、randomness 與 training provenance 缺口。最後，RDP accountant 顯示 public deterministic seed 讓 verifier 可重建 noise，現行原型不能宣稱有限 epsilon。故本研究支持 DP-update audit 架構的可行性，但不過度宣稱 formal DP、深度模型、production-scale federation 或任意 poisoning defense。

## Privacy accountant 依據

- Mironov, *Rényi Differential Privacy*, CSF 2017：Gaussian RDP、sequential composition 與轉換基礎，https://research.google/pubs/r%C3%A9nyi-differential-privacy/
- Opacus 官方 RDP accountant：以 noise multiplier、sample rate 與 steps 累積 privacy spending，https://opacus.ai/api/accounting/rdp.html
