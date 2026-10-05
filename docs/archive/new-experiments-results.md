# 新增實驗設計與結果整理

本文整理近期新增的兩組實驗：第一組為非二元多類別資料集上的 FL/DP 可遷移性實驗；第二組為 Wine 與 Digits 多類別資料集上的實際 EZKL-backed VDP/ZK 約束驗證與成本量測。這兩組實驗用於補強期刊論文中「方法不只適用於 Adult Income 二元分類」以及「模型維度增加時 ZK 成本如何變化」兩個問題。

## 實驗一：非二元多類別資料集 FL/DP 重複實驗

### 實驗目的

原先多資料集實驗主要集中於表格型二元分類資料集，因此仍可能被質疑方法是否只適用於 binary classification。為了檢查 FL+DP pipeline 是否能延伸至非二元分類，本實驗選用三個多類別資料集進行重複實驗，觀察加入 DP 更新後的模型表現是否仍接近 FL baseline。

### 實驗設計

本實驗將二元分類模型的輸出層改為多類別 logits，並將 loss function 從 `BCEWithLogitsLoss` 改為 `CrossEntropyLoss`。為避免小型資料集在客戶端切分後出現類別分布不均，client partition 採用分層切分策略。

主要設定如下：

| 設定項目 | 數值 |
|---|---|
| 客戶端數量 | 3 |
| 隨機種子 | 42, 52, 62 |
| 聯邦學習輪數 | 10 |
| local epoch | 2 |
| `clip_norm` | 1.0 |
| `noise_multiplier` | 0.08 |
| 評估指標 | FL final accuracy、DP final accuracy、DP/FL retention |
| 達標門檻 | DP/FL retention >= 0.9 |

### 使用資料集

| 資料集 | 任務 | 樣本數 | 特徵數 | 類別數 |
|---|---|---:|---:|---:|
| Iris | 花朵品種分類 | 150 | 4 | 3 |
| Wine | 葡萄酒品種分類 | 178 | 13 | 3 |
| Digits | 手寫數字分類 | 1797 | 64 | 10 |

### 實驗結果

| 資料集 | 類別數 | FL 最終平均 | DP 最終平均 | 差距 | DP/FL 保留率 | 是否達標 |
|---|---:|---:|---:|---:|---:|---|
| Digits | 10 | 0.961111 | 0.946296 | 0.014815 | 0.984586 | True |
| Iris | 3 | 0.866667 | 0.866666 | 0.000000 | 1.000000 | True |
| Wine | 3 | 0.972222 | 0.981481 | -0.009259 | 1.009524 | True |

### 結果解讀

三個多類別資料集皆達到 90% DP/FL retention 門檻，表示目前的 DP update prototype 不只適用於二元分類，也能延伸到多類別輸出設定。Digits 為 10 類分類，且特徵維度高於 Iris 與 Wine，仍能維持 0.984586 的 retention，說明 DP noise 對模型準確率的影響在此設定下仍屬可接受。

需要注意的是，本實驗屬於 FL/DP baseline-level extension，主要證明多類別任務上的效能可遷移性；它尚未直接證明這些資料集皆完成 ZK proof-gated aggregation。因此後續進一步選擇 Wine 與 Digits 進行 VDP/ZK 成本驗證。

## 實驗二：Wine 多類別 VDP/ZK 約束驗證與成本量測

### 實驗目的

Adult Income 主線實驗已完成實際 EZKL-backed VDP 檢查與 proof-gated aggregation，但期刊審稿時可能會質疑：ZK 驗證是否只在 Adult Income 這個二元分類資料集上成立。因此本實驗選用 Wine 多類別資料集，驗證完整 DP update vector 是否也能被轉換成 ZKML 可審計約束條件。

### 實驗設計

Wine 資料集為 3 類分類，線性模型包含 42 個參數，因此本實驗驗證完整 42 維 DP 更新向量，而非只抽取部分向量。實驗建立 honest profile 與 tampered noisy profile 兩種案例：

| 案例 | 設計方式 | 預期結果 |
|---|---|---|
| honest_profile | 使用正確的 clipped update、noise 與 noisy update | 通過 |
| tampered_noisy_profile | 對 noisy update 人為偏移 1 個量化單位 | 被拒絕 |

驗證條件包含：

| 約束條件 | 說明 |
|---|---|
| clipping bound | 檢查 `q_clipped` 的平方和是否不超過裁剪上限與容差 |
| additive relation | 檢查 `q_noisy = q_clipped + q_noise` |
| EZKL proof verification | 檢查 ONNX arithmetic check model 的 proof 是否通過 |
| proof-gated decision | 同時滿足 proof verified、clip OK、relation OK 才接受 |

主要設定如下：

| 設定項目 | 數值 |
|---|---|
| 資料集 | Wine |
| 任務 | 3 類多類別分類 |
| 更新向量維度 | 42 |
| client_id | 0 |
| 隨機種子 | 42 |
| `scale` | 10000 |
| `clip_norm` | 1.0 |
| `noise_multiplier` | 0.08 |
| `slack_ppm` | 4201 |

### 實驗結果

| 案例 | 證明驗證 | 裁剪通過 | 關係通過 | 接受 | 證明秒數 | 驗證秒數 | 證明大小 |
|---|---|---|---|---|---:|---:|---:|
| honest_profile | True | True | True | True | 0.140052 | 0.044162 | 11910 bytes |
| tampered_noisy_profile | True | True | False | False | 0.144741 | 0.052252 | 11925 bytes |

### 結果解讀

Wine 的 honest update 同時通過 EZKL proof verification、clipping check 與 relation check，因此被接受。tampered noisy update 雖然仍能對其 arithmetic output 產生有效 proof，但因 `q_noisy = q_clipped + q_noise` 關係檢查失敗，因此在 proof-gated decision 中被拒絕。

這個結果很重要，因為它說明 ZK proof 本身只是證明「檢查模型的算術輸出正確」，真正的接受或拒絕仍取決於公開檢查結果是否符合 VDP 規則。換句話說，ZK proof 與 VDP constraints 必須共同構成完整的審計機制。

## 實驗三：Digits 高維多類別 VDP/ZK 成本量測

### 實驗目的

Wine 的更新向量只有 42 維，雖然能證明非 Adult、多類別資料集也可接上 VDP/ZK，但仍不足以說明模型維度增加時的成本變化。因此本實驗選用 Digits 資料集，其線性模型包含 650 個參數，用於觀察 ZK cost scaling。

### 實驗設計

Digits 為 10 類手寫數字分類資料集，輸入特徵數為 64，線性分類器輸出 10 類，因此完整模型更新向量維度為 650。本實驗沿用 Wine 的 VDP/ZK 設計，同樣建立 honest profile 與 tampered noisy profile，並驗證完整 650 維 DP 更新向量。

主要設定如下：

| 設定項目 | 數值 |
|---|---|
| 資料集 | Digits |
| 任務 | 10 類多類別分類 |
| 更新向量維度 | 650 |
| client_id | 0 |
| 隨機種子 | 42 |
| `scale` | 10000 |
| `clip_norm` | 1.0 |
| `noise_multiplier` | 0.08 |
| `slack_ppm` | 4201 |

### 實驗結果

| 案例 | 證明驗證 | 裁剪通過 | 關係通過 | 接受 | 證明秒數 | 驗證秒數 | 證明大小 |
|---|---|---|---|---|---:|---:|---:|
| honest_profile | True | True | True | True | 0.622663 | 0.034368 | 11952 bytes |
| tampered_noisy_profile | True | True | False | False | 0.589810 | 0.040578 | 11995 bytes |

額外成本指標如下：

| 資料集 | 更新維度 | Circuit rows | Total assignments | Proving key 大小 | SRS 大小 |
|---|---:|---:|---:|---:|---:|
| Wine | 42 | 379 | 758 | 1,574,867 bytes | 65,796 bytes |
| Digits | 650 | 5851 | 11702 | 25,181,267 bytes | 1,048,836 bytes |

### 結果解讀

Digits 的 honest update 被接受，tampered noisy update 被拒絕，表示完整 650 維 DP 更新向量仍能套用相同的 VDP/ZK 約束設計。與 Wine 相比，Digits 的向量維度從 42 增至 650，circuit rows 從 379 增至 5851，proving time 從約 0.14 秒增加至約 0.62 秒。這說明模型維度增加會推升 ZK 證明成本，但在本實驗規模下仍能完成實際 proof/verify。

另一方面，proof size 仍維持在約 11.9 KB，沒有隨向量維度大幅增加；真正明顯增加的是 proving key、SRS、circuit rows 與 proving time。這個觀察可作為期刊論文中討論 ZKML 實用性與成本瓶頸的重要依據。

## 實驗四：ZK peak memory 與通訊成本 scaling benchmark

### 實驗目的

原計劃的主要量化指標除了 accuracy、proving time、verification time 與 proof size，也包含 peak memory 與 communication overhead。multiclass VDP/ZK evaluation 雖已比較 Wine 與 Digits 的 proof cost，但尚未重複量測記憶體與 application-layer payload。因此本實驗加入 Iris 15 維更新，並對 Iris、Wine、Digits 各使用 3 個 seed 重跑 honest profile。

### 實驗設計

- seeds：42、52、62
- 每個 dataset/seed 皆在獨立 Python process 執行，避免前一次 EZKL/native allocator 保留的記憶體影響下一次量測
- peak memory：每 5 ms polling process RSS，報告 pipeline 絕對峰值與相對 baseline 增量
- S1 payload：compact JSON 序列化的 `client_id + q_noisy`
- S2 payload：S1 payload + `proof.json` + compact JSON audit policy metadata
- 通訊量不包含 TCP、TLS 或 HTTP framing，因此屬可重現的 application-layer wire-size 估計

### 實驗結果

| Dataset | 更新維度 | 通過 | Prove 秒 mean±SD | Verify 秒 mean±SD | Peak RSS MiB mean±SD | S1 payload | S2 payload | S2 額外倍率 | Circuit rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Iris | 15 | 3/3 | 0.100064±0.006598 | 0.032662±0.001165 | 410.018±0.391 | 99 bytes | 12,519 bytes | 125.626x | 138 |
| Wine | 42 | 3/3 | 0.153746±0.011348 | 0.040995±0.006190 | 412.462±0.085 | 222 bytes | 12,331 bytes | 54.632x | 379 |
| Digits | 650 | 3/3 | 0.586401±0.008719 | 0.034425±0.001359 | 425.966±0.653 | 3,056 bytes | 15,198 bytes | 3.973x | 5,851 |

### 結果解讀

9/9 honest runs 均通過 proof verification、clipping 與 additive relation。更新維度從 15 增至 650 時，平均 proving time 增至 5.860 倍，pipeline peak RSS 增至 1.039 倍，而 S2 application payload 增至 1.214 倍。Proof JSON 平均大小仍約 11.9-12.3 KB，因此小模型的固定 proof 成本占比特別高；更新向量變大後，S1 更新本身的占比上升，使相對通訊額外倍率下降。

EZKL calibration 會對量化後的大型 lookup input 輸出警告；所有 run 仍完成 compile/prove/verify，Digits fidelity report 的 mean absolute percent error 約為 0.0000018%。此結果可支持「目前設定下 proof 可完成」的主張，但不應被延伸解讀為深度模型或任意量化尺度皆無數值風險。

## 實驗五：正式 Privacy Accounting 與 Utility Frontier

### 實驗目的

前述 DP 實驗主要以 `noise_multiplier` 與 accuracy retention 比較效用，尚未確認機制是否符合 finite privacy budget 的前提。Gaussian privacy accounting 因此加入 client-level Gaussian RDP accountant，並重新檢查 verifier 實際可觀察的資訊。

### 關鍵機制檢查

目前 artifact 將 deterministic `noise_seed` 放在 `public_inputs`。由於 noise generator 與 seed 都可得，verifier 能重建 `q_noise`，再由 `q_noisy - q_noise` 還原 `q_clipped`。因此現行 verifier view 不能套用秘密 Gaussian mechanism 的有限 epsilon，應記為：

```text
current public deterministic seed: epsilon = infinity
```

後續有限 epsilon 都是假設部署改成 secret independent Gaussian noise 的條件式分析。Accountant 的範圍為 client-level、full participation `q=1`、replace-one sensitivity `2C`、10 rounds、`delta=1e-5`，不是 record-level DP-SGD。

### Accounting 結果

| Raw noise multiplier | 條件式 replace-one epsilon |
|---:|---:|
| 0.080000 | 3504.357 |
| 0.531228 | 128 |
| 1.396075 | 32 |
| 4.366154 | 8 |

### Privacy-utility 結果

| Dataset | epsilon=3504 retention | epsilon=128 | epsilon=32 | epsilon=8 |
|---|---:|---:|---:|---:|
| Digits | 0.984586 | 0.536609 | 0.252409 | 0.171483 |
| Iris | 1.000000 | 0.782051 | 0.500000 | 0.384615 |
| Wine | 1.009524 | 0.876190 | 0.609524 | 0.457143 |

45 組 paired runs 顯示，`noise_multiplier=0.08` 的高 utility 對應極大的條件式 epsilon；當 noise 提升到較強 privacy 所需程度時，三個資料集皆跌破 90% retention。更重要的是，現行 public-seed 機制本身仍為 infinity。這個結果把「可驗證 noise addition」與「可驗證且不可預測的 DP randomness」清楚區分。

### 結案定位

本研究已完成 ZKML 可審計 DP-update 原型、篡改拒絕、proof-gated aggregation 與成本量測；尚未完成的是 secret seed 到指定 noise distribution 的 circuit-level verification。正式版本需要 PRG/discrete-Gaussian circuit 與 commitment、VRF/commit-reveal 或 distributed noise generation。只隱藏 JSON 中的 seed 並不足夠。

## 實驗六：Forest CoverType 大型資料 Scaling 與 Actual EZKL

### 實驗目的

前五項補強仍以小型或中型分類資料集為主。為直接檢查樣本規模，本實驗加入 Forest CoverType（581,012 筆、54 特徵、7 類別），並區分「訓練資料量」與「ZK update 維度」兩種 scaling。

### 實驗設計

- 固定 20% test split（116,203 筆）
- training sizes：10,000、100,000、464,809
- seeds：42、52、62
- 3 clients、5 rounds、1 local epoch、batch size 1024
- 三種 paired modes：FL、clipping-only、clipping + seeded noise
- worker process 獨立量測 wall time、training time 與 20 ms polling peak RSS
- 對完整資料產生的 385 維 client update 另執行 honest/tampered actual EZKL

### 實驗結果

| Training samples | FL final | Clip-only final | DP final | Clip/FL | DP/FL | Peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.627299 | 0.627299 | 0.569942 | 1.000000 | 0.908566 | 599--607 MiB |
| 100,000 | 0.712285 | 0.701078 | 0.667886 | 0.984266 | 0.937666 | 598--627 MiB |
| 464,809 | 0.719890 | 0.700633 | 0.636799 | 0.973251 | 0.884579 | 715--716 MiB |

完整分割 FL／clipping-only／DP-update 的平均 training time 為 51.1／50.7／52.0 秒。總 accuracy gap 為 0.083091，其中 clipping-only gap 為 0.019257，加入 noise 後額外 gap 為 0.063834。效用不隨資料量單調改善，因此資料量不能取代 clipping/noise 的參數校準。

Actual EZKL 中，385 維 honest update 通過 proof、clipping 與 relation；tampered `q_noisy + 1` 具有有效算術 proof，但 relation 失敗而被 aggregation gate 拒絕。Honest prove/verify 為 0.305527／0.039568 秒，proof 12,293 bytes，peak RSS 約 430.2 MiB。

### 結果解讀

- 目前線性原型可實際處理 581,012 筆資料，補強小型資料集的規模疑慮。
- Clipping-only control 避免把 S0/S1 accuracy gap 全部誤歸因於 noise。
- Dataset size 影響本地訓練時間與記憶體；constraint-only proof 則主要受 385 維模型更新影響。
- 仍只涵蓋 `K=3`、stratified IID 與線性模型，不代表 non-IID 或深度模型可行性。
- Public deterministic seed 的正式 DP 限制不變。

## 實驗七：CoverType Non-IID × Client Scaling

### 實驗目的與設計

本實驗檢查 CoverType large-data scaling 的大型資料結果是否只在 K=3、stratified IID 成立。固定 CoverType 100,000 筆 training subset，比較 K=3/10 與 IID、Dirichlet alpha=0.5/0.1；每個條件使用 5 seeds，且 FL、clipping-only、DP-update 共用 split、partition、初始化與 shuffle，共完成 90 mode runs。以 label total variation 描述 client heterogeneity，並報告 seed-level 95% t interval。

### 實驗結果

| K | Partition | Label TV | FL | DP | DP/FL retention |
|---:|---|---:|---:|---:|---:|
| 3 | IID | 0.000050 | 0.689464 | 0.612738 | 0.888716 |
| 3 | alpha=0.5 | 0.282212 | 0.679766 | 0.576464 | 0.848033 |
| 3 | alpha=0.1 | 0.512622 | 0.677091 | 0.516235 | 0.762431 |
| 10 | IID | 0.000134 | 0.607950 | 0.584859 | 0.962019 |
| 10 | alpha=0.5 | 0.368662 | 0.630750 | 0.581477 | 0.921883 |
| 10 | alpha=0.1 | 0.634526 | 0.620605 | 0.518181 | 0.834961 |

六個條件全部成功完成，支持架構可在 K=10 與 non-IID partition 執行；但高度異質條件不維持固定 90% retention，故結果同時構成 utility robustness 的負面邊界。

## 實驗八：多輪 Proof-Gated Threat Matrix

### 實驗目的與設計

在 CoverType 100,000 筆、K=10、Dirichlet alpha=0.1、3 rounds、20% attackers 下，對 relation tamper、clip bypass、replay、zero-noise 與 bounded sign-flip 比較 ungated、current VDP gate 與 strengthened VDP gate。三個 seeds 共完成 48 條 trajectories 與 1,440 次 client 決策。Strengthened policy 在 proof+clip+relation 之外加入 client/round/model binding、replay protection 與 noise-generation policy。

Threat matrix 重用前期 actual EZKL 的 verified-artifact/check contract，1,440 次決策是多輪 policy simulation，並非 1,440 次 actual proof generation；實際 proof 可行性與成本仍由 EZKL constraint integration、22、23、25 的獨立實驗提供。

### 實驗結果與邊界

| Attack | Current acceptance | Strengthened acceptance | Strengthened clean retention |
|---|---:|---:|---:|
| Relation tamper | 0.000000 | 0.000000 | 0.585848 |
| Clip bypass | 0.000000 | 0.000000 | 0.585848 |
| Replay | 1.000000 | 0.000000 | 0.718373 |
| Zero noise | 1.000000 | 0.000000 | 0.585848 |
| Bounded sign flip | 1.000000 | 1.000000 | 0.179797 |

Current gate 的聲明範圍（clip/relation）在多輪壓力下成立；replay 與零噪聲則證明 context/randomness binding 不可省略。Bounded sign-flip 即使在 strengthened gate 仍通過，證明 update-level audit 不能被解讀為完整 local-training proof。拒絕大型 non-IID clients 亦使部分 trajectory retention 降至 0.585848，揭露安全與 availability/utility 的取捨。

## 實驗九：統計、完整性與可重現性稽核

experimental-rigor audit 不選擇性增加成功案例，而是讀取 the large-data, non-IID, and threat-matrix evaluations raw results，驗證 expected rows、unique primary keys、seed pairing 與 preprocessing/paired protocol。27/27、90/90、48/48 trajectories 與 1,440/1,440 decisions 全部齊全。

33 組 accuracy comparisons 使用 paired mean difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation 與 family-level Holm correction。由於 n=3 的最小 exact p=0.25、n=5 的最小 exact p=0.0625，Holm-adjusted p<0.05 為 0 組。因此 accuracy 結果不宣稱統計顯著，而定位為描述性 effect、範圍與工程可行性證據。另保存精確環境版本與核心 scripts/results SHA-256。

## 實驗十：Context-Bound Hidden-Randomness Reference Protocol

context-bound randomness protocol 將 Gaussian privacy accounting/27 的 public seed、replay 與 zero-noise 缺口轉成 executable protocol contract。Client 在 server challenge 前先承諾 clipped update，setup-time randomness commitment 不可替換；hidden seed 綁定 client、round、model、nonce、update commitment 與 single-use challenge。Public statement 不含 client secret、derived seed 或 `q_noise`。

Honest、replay、round/model/challenge swap、zero-noise、secret swap、clip bypass、noisy tamper 與 challenge reissue 共 10 cases 全部符合預期。此結果是 intended circuit semantics 與 regression oracle；HMAC/SHAKE、integer sampler、actual proof 與 sampler-specific DP theorem 仍待完成，因此不列為 finite-epsilon VDP 成果。

## 綜合結論

新增實驗補強了十個層面的論文主張：

1. FL+DP pipeline 不只適用於二元分類，也能延伸到多類別分類。
2. VDP/ZK 約束檢查不只適用於 Adult Income，也能套用到 Wine 與 Digits 等非 Adult 資料集。
3. 當模型更新維度從 42 增加到 650 時，ZK proving cost 上升，但 proof/verify 仍可完成，且 tampered noisy update 仍能被穩定拒絕。
4. 在 15、42、650 維更新的重複量測中，peak RSS 與 application-layer communication overhead 已能被明確定義與重現，補齊原計劃的主要成本指標。
5. Privacy accountant 量化了目前原型的保證邊界：public deterministic seed 為 epsilon infinity；秘密 Gaussian 條件下亦存在明顯 privacy-utility trade-off。
6. Forest CoverType 證明 58 萬筆資料可由目前 FL/DP 線性原型實際處理，並以 clipping-only control 與 385 維 actual EZKL 補上效用歸因及大型資料 S2 證據。
7. K=3/10 與 IID/Dirichlet 的 90-run 矩陣證明架構可在更異質的 client partition 執行，同時量出高度 non-IID 下的效用下降。
8. 多輪 threat matrix 證明 current gate 能拒絕其聲明範圍內的違規，並以 replay、zero-noise 與 bounded poisoning 精確界定尚缺的 context、randomness 與 training provenance。
9. 完整性與統計稽核證明所有核心 raw matrices 完整且配對，同時確認小 seed 數不支持顯著性措辭，避免過度推論。
10. Context-bound hidden-randomness contract 將 replay/zero-noise 修正從概念變成可測試規格，並明確留下 actual circuit 與 formal DP 的下一個研究門檻。

因此，這些新增實驗可支持以下論文敘述：

> 本研究不僅在 Adult Income 主線流程中完成 FL+DP+VDP/ZK 驗證，也進一步於 16 個資料集、581,012 筆 CoverType、K=3/10 IID/Dirichlet partition 與多輪攻擊矩陣量測 utility、資源、proof cost 與惡意接受率。結果支持 VDP-as-ZKML-constraint 作為聚合前 DP-update 審計機制的可行性；同時，public seed、replay/zero-noise 與 bounded poisoning 結果證明 formal DP、context binding 與 local-training provenance 仍需額外機制。
