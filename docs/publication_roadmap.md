# VDP-FL 投稿版研究路線圖

## 建議論文核心

暫定題目：

> Context-Bound Verifiable DP Updates for Federated Learning with Hidden Joint Randomness

目前 repo 已足以支撐結案與 preliminary/workshop artifact。the publication-strengthening modules 已把 context-bound randomness protocol contract 映射成 fixed-profile actual Halo2 circuit、完成exact sampler theorem/accountant，並加入reproducibility、scaling與robust aggregation；full paper的主要剩餘門檻是matched multi-round actual proofs、natural-client benchmark與更完整 security analysis。

## 2026-08-06 gate 狀態

| Gate | 狀態 | 最新證據 |
|---|---|---|
| P1 Actual verifiable-randomness circuit | 固定profile已完成 | Halo2 verifiable-randomness circuit actual Halo2；4/4 tests |
| P2 Formal privacy/security | DP accountant完成，security仍部分 | discrete-noise accounting ε≤28.840669 at δ=1e-5；PRF/unique-context條件式定理 |
| P3 Actual multi-round integration | 部分 | Actual single proofs＋多輪policy/FL；尚未逐更新產生全量proofs |
| P4 Publication-grade evaluation | 部分 | 10 seeds、K=50/R=20、MLP、robust attacks；缺natural-client/partial participation |
| P5 Artifact/manuscript | 部分 | Lockfile、raw results、hardware manifest、Windows/Linux CI、完整報告；尚缺container與venue package |

## 已有研究資產

- S0/S1/S2、canonical quantized witness、fixed slack 與 actual EZKL constraint proofs。
- 16 datasets、581,012-row CoverType、K=3/10 IID/Dirichlet、ZK cost scaling。
- Public-seed verifier-view `epsilon = infinity` 的負面結果與 privacy--utility frontier。
- Replay、zero-noise、context swap 與 bounded poisoning threat matrix。
- experimental-rigor audit 完整性、paired statistics、environment 與 SHA-256 audit。
- context-bound randomness protocol commit-before-challenge、hidden seed、context binding、freshness/replay reference semantics；10/10 threats 符合預期。

## 投稿前研究門檻

### Gate P1：Actual verifiable-randomness circuit

- 選定 circuit-friendly commitment/PRF/hash。
- 將 setup-time client secret commitment、server challenge、context derivation、integer sampler、clipping 與 additive relation放入同一 proof relation。
- Public statement 不得暴露 secret seed 或 `q_noise`。
- 產生 honest 與全部 tampered actual proofs，而不只是 host evaluator。

### Gate P2：Formal privacy and security

- 固定 adjacency：client-level 或 record-level，以一者為 primary claim。
- 對 exact quantized noise sampler證明 `(epsilon, delta)`，並讓 accountant 與 circuit parameters 同源。
- 定義 completeness、soundness、zero knowledge、freshness 與 randomizer-tampering resistance。
- 分析 malicious client/server、collusion、dropout、selective abort 與 randomness grinding。

### Gate P3：Actual multi-round integration

- 每個被聚合的 client update 提供 actual proof。
- Client/round/model/nonce 與 pre-challenge update commitment 綁入 statement。
- 量測 proof generation、verification、round latency、throughput、RSS、proof/key size與 network payload。
- 比較 ungated、public-seed、context-only、hidden-randomness 與 full gate。

### Gate P4：Publication-grade evaluation

- 至少一個 natural-client federated benchmark（例如 FEMNIST/FedScale split），而非全部人工 partition。
- Linear、MLP/small CNN 與多個 update dimensions。
- 10/50/100 clients、partial participation、dropout 與 non-IID。
- 事前指定 primary endpoints，使用 power analysis 決定 seeds。
- 報告 effect size、CI、raw rows 與 multiple-testing policy；不以事後增 seed 追求顯著。

### Gate P5：Artifact and manuscript

- Container/lockfile、一鍵重現、CI、raw proofs/results、hardware/environment manifest。
- Threat model、protocol pseudocode、formal statements、related-work comparison、ablations與 limitations。
- 依目標 venue 規格完成 anonymization、artifact instructions 和 ethical/reproducibility checklist。

## 必要 baselines 與 attacks

Baselines：FL、clip-only、DP、public-seed gate、context-only gate、hidden-randomness gate、完整 gate，以及可合理重現的 VDP/ZK-FL 方法。

Attacks：clip/relation tamper、replay、round/model/context swap、zero-noise、secret/commitment substitution、challenge reissue、seed grinding、selective abort、bounded poisoning。

Bounded poisoning 若不納入 local-training proof，必須明列為 threat-model 外；可另以 robust aggregation 對照，但不能把 update-level DP audit 說成完整 training correctness。

## 相關研究定位

- Biswas and Cormode, Verifiable Differential Privacy / interactive proofs for DP counting: https://arxiv.org/abs/2208.09011
- Bontekoe et al., Efficient Verifiable Differential Privacy with Input Authenticity, PoPETs 2025: https://doi.org/10.56553/popets-2025-0076
- Bell-Clark et al., Vεrity: Verifiable Local Differential Privacy, USENIX Security 2026 prepublication: https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_bell.pdf
- Jin et al., Zero-Knowledge Federated Learning framework: https://arxiv.org/abs/2503.15550
- Xing et al., Practical ZKP-FL: https://arxiv.org/abs/2304.05590
- Lai et al., FedScale, ICML 2022: https://proceedings.mlr.press/v162/lai22a.html

## 當前精確判定

Halo2 verifiable-randomness circuit/31 已通過固定profile的 P1 與 privacy-accounting部分：可以對 `d=4, k=16, 10 rounds` 宣稱conditional finite-epsilon verifiable DP。尚不能把該epsilon套到高維模型，也不能宣稱完整training correctness。下一個最高優先工作是讓每個multi-round client update真正附帶matched actual proof，並加入natural-client/partial-participation與selective-abort/collusion分析，而不是繼續擴充相似表格資料集。
