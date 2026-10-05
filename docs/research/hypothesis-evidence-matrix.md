# 研究假設與證據矩陣

本矩陣把「架構是否成立」拆成可被實驗判定的子假設。判定原則為：只有實際執行、保留原始結果且通過一致性檢查者列為支持；條件式分析與尚未進入 ZK circuit 的 policy 不視為已完成的密碼學保證。

| ID | 可檢驗假設 | 主要證據 | 判定 | 可支持的主張邊界 |
|---|---|---|---|---|
| H1 | FL 與 DP-update pipeline 可在不同資料、樣本量與 client partition 下執行 | FL／DP baselines；CoverType 581,012 筆；K=3/10、IID／Dirichlet、90 runs | 支持 | 支持線性分類與本實驗規模的可執行性，不外推至深度模型或 production federation |
| H2 | Clipping bound 與 additive noise relation 可轉成穩定的量化審計條件 | Canonical witness／fixed slack；多類別 actual EZKL 9/9；CoverType 385 維 honest／tampered proof | 支持 | 支持 constraint-only update audit，不代表完整 local training circuit |
| H3 | 驗證結果可控制多輪 FL aggregation | Proof-gated 單輪鏈結；四維 150/150 actual Halo2 proofs 與模型鏈重驗；另有 1,440 simulated policy decisions | 支持固定 profile | 支持逐更新 proof-gated aggregation；1,440 decisions 並非 1,440 份 actual proofs |
| H4 | 現有 proof+clip+relation gate 能拒絕其聲明範圍內的違規更新 | multi-round threat matrix relation tamper、clip bypass：current gate 惡意接受率皆 0% | 支持 | 只涵蓋 proof、裁切界限與 additive relation |
| H5 | 多輪部署需要 client/round/model binding、replay protection 與 noise-generation policy | Threat matrix、reference state machine、actual context-bound Halo2 circuit | 支持 | Circuit 已綁定 context／randomness；single-use challenge 與 replay cache仍由 server state 執行 |
| H6 | 舊 public deterministic seed 機制能提供有限 client-level DP | Gaussian privacy accounting 的 verifier-view audit 與 RDP accountant | 否定 | Verifier 可重建並扣除 noise，故該舊機制的 epsilon 為 infinity |
| H7 | Update-level VDP gate 可阻止任意 model poisoning | multi-round threat matrix bounded sign-flip：current/strengthened gate 接受率皆 100%，clean retention 僅 0.179797 | 否定 | 需 local-training provenance proof 或 robust aggregation，不能用目前架構宣稱完整 poisoning defense |
| H8 | Replay／context／zero-noise 缺口可被轉成 actual ZK relation | Secret/update commitments、context-bound Poseidon PRG、canonical sampler 的 actual Halo2 circuit，8/8 tests | 支持固定 profile | Server freshness／replay cache 仍是 host state；Poseidon PRF security 為明示假設 |
| H9 | Exact 離散 sampler 可取得有限 client-level epsilon | Exact PLD accountant：`d=4, k=16`、10 rounds、`delta=1e-5` 時 `epsilon <= 28.840669` | 支持 replacement-client fixed-participation profile | 實際 PRG 為 conditional computational DP；不外推至高維、add/remove 或 record-level |
| H10 | 架構可擴至較複雜模型、50 clients 與20 rounds | production-oriented scaling：9/9 EZKL proofs、40 FL trajectories、385–1,991 維、最大 1,000 updates | 支持 production-oriented stress test | Local training 不在 circuit；全量 proof latency為實測單證明外推 |
| H11 | Robust aggregation 可緩解合法範圍內的 bounded poisoning | robust aggregation：10 seeds、60 trajectories、3,000 decisions；median/trimmed mean retention gain 0.1988/0.1541，exact p=0.001953 | 支持所測20%攻擊的顯著緩解 | 300/300 malicious updates仍通過 gate；未完全恢復 utility或證明任意 Byzantine robustness |

## 大型與 non-IID 壓力測試

CoverType large-data scaling 的 CoverType 完整資料實驗使用 581,012 筆資料、464,809 筆 training split；FL、clipping-only、DP-update 共 27 個 paired runs。完整 split 的 FL/DP final accuracy 為 0.719890/0.636799，DP/FL retention 為 0.884579，peak RSS 約 716 MiB。385 維 actual EZKL honest proof 的 prove/verify 為 0.306/0.040 秒，proof 12,293 bytes。

non-IID client scaling 固定 100,000 筆 CoverType training subset，以 5 seeds 比較 K=3/10 與 IID、Dirichlet alpha=0.5/0.1。六個條件全部完成；DP/FL retention 從 K=10 IID 的 0.962019 到 K=3、alpha=0.1 的 0.762431。這表示架構可在更異質 partition 下執行，但 utility 並非在所有 non-IID 條件都達到 90% 門檻。

## 核心假設的結案判定

補充實驗：`experiments/actual_multiround_halo2/` 將四參數合成資料訓練、逐更新 Halo2 proof、model context 與跨輪聚合接在同一程式中，保存後由獨立執行重驗 proof 與模型鏈。結果見 `experiments/actual_multiround_halo2/hackmd_update.md`。它補強 H3/H8 的固定-profile 整合證據；不把 H10 的高維 cost experiment 自動升格為逐更新全量證明，也不替代完整 transcript 的 DP 安全分析。

若核心假設定義為：

> 聯邦學習中的 DP update clipping 與 additive relation，可以被轉換成可由 ZKML/constraint 檢查、並能控制 aggregation 的可重現審計介面。

則 H1–H4 的跨資料、actual proof、大型資料、non-IID 與多輪攻擊證據已足以支持此假設在「線性模型、constraint-only DP-update audit」範圍內成立。

若核心假設定義為「已完成任意維度、任意 participation、完整 local-training correctness 與任意 poisoning defense 的 production VDP-FL 系統」，則 H7/H9–H11 的主張邊界顯示此較強結論仍不成立。結案報告可主張固定-profile finite-epsilon verifiable randomness與 bounded-poisoning mitigation，但須把高維 privacy composition、training provenance、selective abort/collusion 與全量 multi-round proofs列為後續工作。

## 統計證據強度

Experimental-rigor audit 對 large-data、non-IID 與 threat-matrix evaluations 共 33 組 accuracy comparisons 執行 paired mean difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation test 與 family-level Holm correction。核心矩陣 27/27、90/90、48/48 trajectories 與 1,440/1,440 decisions 均完整且無重複主鍵。

CoverType large-data scaling 每個條件只有 3 seeds，two-sided exact test 的最小 p 為 0.25；non-IID client scaling 每個條件有 5 seeds，最小 p 為 0.0625。Holm-adjusted `p < 0.05` 的比較為 0，因此本研究應使用「可行性證據、effect size、範圍與重現結果」，不使用「統計顯著」主張。這不否定 H1–H4 的工程／邏輯證據，但限制了將 accuracy 差異推廣為母體統計結論的能力。
