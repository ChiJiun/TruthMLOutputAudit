# 以 ZKML 實現可驗證差分隱私聯邦學習之原型研究

> 2026-08-06 更新：the publication-strengthening modules 已完成 actual Halo2 hidden-randomness/sampler circuit、finite-profile client-level accountant、10-seed/CI reproducibility、K=50/R=20與1,991維scaling，以及bounded-poisoning robust aggregation。最新投稿強化結果與主張邊界請見 `docs/publication_strengthening_report.md`；本文件其餘內容保留原結案版本脈絡。

## 一、研究背景與目的

本研究的核心目標，是建立一套結合聯邦學習（Federated Learning, FL）、差分隱私（Differential Privacy, DP）與零知識機器學習（Zero-Knowledge Machine Learning, ZKML）的可驗證隱私學習原型。研究並非只關注模型能否訓練完成，而是希望進一步回答以下問題：

1. 聯邦學習在目前資料與模型設定下是否能穩定收斂。
2. 在聯邦學習中加入差分隱私後，模型效能會受到多大影響。
3. 差分隱私中的關鍵步驟是否能被轉換成 ZKML 可驗證的 constraint。
4. 這些可驗證條件是否能進一步影響聯邦學習的聚合決策，形成 proof-gated 的可信聚合流程。

本研究最終欲建立的不是單純的 FL baseline，也不是單純的 ZK proof demo，而是一條從模型訓練、DP 更新、到 ZK 驗證與聚合決策的完整研究路線，並證明未來可將 VDP 視為一種可被 ZKML 審計的隱私保護架構。

## 二、研究方法與整體流程

本研究依照專案規劃，將實驗分成三個層級進行：

- `S0`：FL baseline
- `S1`：FL + Differential Privacy
- `S2`：FL + Differential Privacy + Zero-Knowledge Verification

整體流程如下：

1. 使用 UCI Adult Income 資料集完成資料前處理與 client partition。
2. 建立 ZKML baseline，確認 `PyTorch -> ONNX -> EZKL -> prove -> verify` 可行。
3. 建立小規模聯邦學習 baseline，觀察多輪聚合下的 accuracy 變化。
4. 將 clipping 與 noise 加入聯邦學習，形成 DP baseline。
5. 將 clipping 與 noise relation 拆解成可驗證的約束條件。
6. 解決量化與 rounding 導致的驗證問題，收斂為 canonical witness 與固定 slack policy。
7. 將推薦的 constraint profile 匯出為 circuit-facing artifact，並進一步接入 EZKL backend。
8. 建立 proof-gated aggregation 原型，使 server 僅接受通過驗證的 client update。

在系統層面上，本研究並不是將完整 FL training 全部塞入單一大型 ZK 電路，而是先將 DP 的核心正確性步驟轉換成可審計條件，再逐步接回聯邦學習的 round 流程中。這樣的設計更貼近實際可行的研究原型，也更符合「可驗證差分隱私」的核心精神。

## 三、資料集、模型與實驗設定

本研究使用 UCI Adult Income 資料集進行實驗，並將訓練資料切分為 `K=3` 個 clients，以模擬小規模聯邦學習情境。模型以較輕量、ZKML 相容性較高的線性或小型模型為主，避免過於複雜的架構導致 proving 成本快速膨脹。

聯邦學習主要實驗設定如下：

- client 數：`3`
- 聯邦學習輪數：`5`
- local epochs：`1`
- clipping norm：`1.0`
- noise multiplier：`0.08`

在 ZKML 方面，研究以 EZKL 作為主要 proof backend，先完成最小化 prove/verify pipeline，再將後續的 VDP constraint 映射為小型 ONNX check model 與 circuit-facing artifact。

## 四、ZKML baseline：minimal EZKL demo 到 baseline visualization

### 4.1 minimal EZKL demo：最小 EZKL pipeline 驗證

minimal EZKL demo 的目標是建立最小可行的 ZKML pipeline，確認從模型匯出到 proof/verify 的流程是可行的。實作上完成了：

- PyTorch 模型建立
- ONNX 匯出
- EZKL settings / compile / setup
- proof 生成與 verify

此階段的意義在於確認技術鏈可用，為後續所有「可驗證」主張建立工具基礎。若 minimal EZKL demo 無法跑通，後續所有與 ZKML 有關的實驗都無法成立。

### 4.2 Adult Income model：真實資料導入與 client split

Adult Income model 將實驗從 demo 轉移到真實資料，完成：

- UCI Adult Income 前處理
- 類別特徵編碼與標準化
- train/test split
- `K=3` client partition

這一步的研究意義，是使後續 FL、DP 與 ZK 驗證都建立在同一組真實資料條件下，而不是只停留在 toy example。

### 4.3 quantization scale sweep：Scale sweep

quantization scale sweep 測試不同 quantization `scale` 對模型 accuracy 與 ZK 成本的影響。結果顯示：

- `scale = 8` 時 quantized accuracy 最佳：`0.841540`
- `scale = 8` 時 proving time 最快：約 `0.1391 sec`

這說明在目前小型模型與資料條件下，較低 scale 已足以保留模型精度，並能降低 proving 成本。此結果也為後續 ZKML 可行性分析提供量化依據。

### 4.4 baseline visualization：Baseline 圖表整理

baseline visualization 將 scale sweep 結果視覺化，產出：

- `scale_vs_accuracy.png`
- `scale_vs_proving_time.png`

圖表呈現後，可以更清楚說明量化參數對 accuracy 與證明成本的影響，也讓 ZKML baseline 不只是流程驗證，而具有可比較的性能結果。

### 4.5 本階段分析與結論

ZKML baseline 階段證明兩件事：

1. 在目前設定下，EZKL 已可在小型模型上完成真正的 prove/verify。
2. 量化設定會同時影響 accuracy 與 proving 成本，因此後續若要將 DP 條件搬入 ZK，必須兼顧數值穩定性與電路成本。

因此，minimal EZKL demo 到 baseline visualization 成功建立了 ZKML 作為可驗證機制的技術基礎。

## 五、FL baseline：FedAvg baseline 到 FedAvg round analysis

### 5.1 FedAvg baseline：FedAvg baseline

FedAvg baseline 建立 S0，也就是不含 DP 與 ZK 驗證的聯邦學習 baseline。結果如下：

- 初始 accuracy：`0.694851`
- 最佳 accuracy：第 2 輪 `0.845122`
- 第 5 輪 accuracy：`0.842051`
- 平均 round time：`1.0171 sec`

此結果顯示模型在小規模聯邦學習下能快速收斂，且第 1 至第 2 輪就已接近穩定。這使得後續 S1 與 S2 都有一條可參照的 baseline 曲線。

### 5.2 FedAvg round analysis：S0 Round vs Accuracy

FedAvg round analysis 將 FedAvg baseline 的結果轉為 `Round vs Accuracy` 圖，幫助觀察聯邦學習的收斂趨勢。圖中可見 accuracy 在初始到第一輪有大幅提升，後續輪次則在高點附近小幅波動。

### 5.3 本階段分析與結論

S0 的建立很重要，因為它證明在目前模型、資料與 client split 設定下，聯邦學習本身是穩定的。若沒有這條基準線，就很難判斷後續 DP 或 ZK 驗證對系統造成的影響究竟來自保護機制本身，還是來自 FL 流程不穩定。

因此，本階段可合理得出結論：本研究的 FL baseline 已足以作為 S1 與 S2 的比較基準。

## 六、DP baseline：DP updater baseline 到 privacy-utility sweep

### 6.1 DP updater baseline：DP updater baseline

DP updater baseline 將 `clipping + Gaussian noise` 加入聯邦學習流程，建立 S1。結果如下：

- 初始 accuracy：`0.694851`
- 最佳 accuracy：`0.844201`
- 最終 accuracy：`0.838776`
- 平均 round time：`1.2266 sec`
- `noise_mode = seeded_deterministic`

此結果顯示，在目前設定下加入 DP updater 並未使模型表現崩潰，accuracy 仍能維持在與 S0 相近的水準。更重要的是，這裡引入了 `seeded_deterministic noise`，為後續可驗證 noise 提供了必要條件。

### 6.2 privacy-utility sweep：Epsilon sweep

privacy-utility sweep 測試不同 epsilon 設定對 accuracy 的影響，結果顯示：

- 最佳 epsilon：`2.0`
- 對應 best accuracy：`0.844303`

需注意的是，此階段的 epsilon-to-noise mapping 主要是 baseline 比較用途，並非正式 privacy accountant 結果，因此較適合用來觀察相對趨勢，而非作為最終嚴格隱私保證。

### 6.3 本階段分析與結論

DP baseline 階段的主要結論有三點：

1. 在目前任務與模型下，加入 clipping 與 noise 後，模型仍能維持可接受 accuracy。
2. noise 並未造成明顯訓練崩潰，表示目前 DP baseline 是穩定的。
3. deterministic noise 的引入使得「DP 可被重播與驗證」成為可能，這是後續 VDP 設計的核心前提。

因此，本階段成功將研究從單純 FL 推進到「可被驗證的 DP」方向。

## 七、VDP 核心條件驗證：clipping verification 到 noise-relation verification

### 7.1 clipping verification：Clipping verification

clipping verification 的目標是先將 clipping 條件整理成可重跑的驗證原型。結果如下：

- honest cases accepted：`3/3`
- tampered cases rejected：`6/6`

這表示 clipping 的 norm bound 與 clipping relation 在 Python 層已能穩定區分合法與篡改更新。

### 7.2 noise-relation verification：Noise verification

noise-relation verification 進一步驗證 seed-based noise 與 noisy-update relation。結果如下：

- honest cases accepted：`3/3`
- tampered cases rejected：`6/6`

這證明只要使用可重現的 seed-based noise，noise generation 與 add-noise relation 都可以被驗證。這一步是 VDP 架構最關鍵的前置條件之一，因為若 noise 完全不可重現，就無法進一步做 ZK 審計。

### 7.3 本階段分析與結論

clipping verification 與 noise-relation verification 的真正價值，不只是把 honest 與 tampered case 分出來，而是把差分隱私中的兩個核心步驟明確定義成「可檢查、可拒絕、可形成 fail case」的驗證問題。

合理結論是：`VDP` 並非天生不可驗證，只要把 clipping 與 noise relation 拆解成具體條件，就能為後續 ZK constraint 設計提供明確標的。

## 八、整數化與 rounding 問題：quantized-constraint analysis

quantized-constraint analysis 將 clipping 與 noise relation 搬到 fixed-point / integer constraint 下檢查，觀察量化後是否仍能精確成立。結果如下：

- honest integer clipping bounds exact：`5/9`
- honest quantized noise relations exact：`0/9`
- tampered quantized relations rejected：`9/9`
- max float-vs-quantized relation gap：`1`
- max clipping-bound excess after quantization：`4200 ppm`

這個結果非常關鍵，因為它說明若直接將浮點空間中的 DP 等式原封不動搬進整數 constraint，honest case 也可能失敗。換言之，未來電路設計最大的問題不是能否抓到惡意案例，而是如何避免把合法案例誤判為不合法。

### 本階段分析與結論

quantized-constraint analysis 的主要研究意義在於揭露了 quantization 與 rounding 的根本問題：

- `q(a+b)` 不會自然等於 `q(a)+q(b)`
- clipping 的邊界案例可能因 rounding 而略微超界

因此，後續若要讓 DP 條件真正進入 ZK 電路，不能直接驗證浮點定義，而必須重新定義 witness 形式與容錯策略。

## 九、Canonical witness 與 slack policy：canonical-witness analysis 到 constraint-profile selection

### 9.1 canonical-witness analysis：Canonical witness

為了解決 noise relation 的 rounding 問題，canonical-witness analysis 引入 canonical witness，直接定義：

- `q_clipped = round(scale * clipped_update)`
- `q_noise = round(scale * noise)`
- `q_noisy = q_clipped + q_noise`

結果如下：

- honest canonical relations exact：`9/9`
- tampered canonical relations rejected：`9/9`
- honest clipping checks exact without slack：`5/9`
- honest clipping checks covered with observed slack：`9/9`

這表示 additive relation 的量化問題已被 canonical witness 結構性解決。

### 9.2 canonical-witness analysis：Slack policy sweep

canonical-witness analysis 同時做了 clipping slack sweep，結果觀察到：

- max honest excess：`4200 ppm`
- min tampered excess：`73300 ppm`
- feasible slack interval：`(4200, 73300) ppm`
- simple candidate slack：`4201 ppm`

這顯示存在一個非常清楚的安全區間，使系統可以固定一個 slack，同時接受 honest case 並拒絕 tampered case。

### 9.3 constraint-profile selection：Recommended constraint profile

constraint-profile selection 將 canonical witness 與固定 slack 組合成單一推薦版本。結果如下：

- recommended slack：`4201 ppm`
- honest profiles accepted：`9/9`
- tampered profiles rejected：`18/18`

### 9.4 本階段分析與結論

canonical-witness analysis 到 constraint-profile selection 是整個研究最核心的方法學貢獻。它證明：

1. 不能直接用浮點等式做 ZK 驗證。
2. 必須改用 `canonical quantized witness`。
3. clipping 邊界誤差需要明確的 `slack policy`。
4. 這套設計在 honest 與 tampered case 之間具有足夠大的安全區間。

因此，本研究成功將「DP 可被驗證」從概念推進到穩定可行的 constraint 設計。

## 十、Artifact 與 backend-ready 格式：constraint-artifact export 到 backend-bundle preparation

### 10.1 constraint-artifact export：Constraint artifact export

constraint-artifact export 將推薦的 constraint profile 匯出成固定格式 JSON artifact，包含：

- `meta`
- `public_inputs`
- `witness`
- `checks`

結果如下：

- honest artifacts passing checks：`3/3`
- tampered artifacts rejected：`6/6`

這代表推薦 profile 不只是理論規則，而已具備固定的 circuit-facing 輸入格式。

### 10.2 backend-bundle preparation：ZK backend stub

backend-bundle preparation 再進一步將 artifact 轉成 backend-ready bundle，拆分為：

- `io_bundle.json`
- `verification_hint.json`
- backend note

結果如下：

- bundles exported：`9`
- honest bundles：`3`
- tampered bundles：`6`

這一步的重點是工程介面收斂。即使當時尚未實際生成 proof，研究已經把未來接入 ZK backend 的資料格式整理完整。

### 10.3 本階段分析與結論

constraint-artifact export 到 backend-bundle preparation 的意義在於把研究從「找到正確 constraint」推進到「固定後續實作介面」。這降低了未來 backend 整合的不確定性，也讓整個 VDP-ZKML 架構更接近真正可落地的系統設計。

## 十一、S2 整合與 actual EZKL proof：EZKL constraint integration

### 11.1 EZKL constraint integration：S2 integration demo

EZKL constraint integration 先完成 repo-level 的 S2 整合示範。結果如下：

- scale：`10000`
- tampered client：`1`
- accepted updates under S2 profile：`2/3`
- rejected updates under S2 profile：`1/3`
- tampered client accepted：`False`

這表示推薦 profile 已能在系統層級做出接受或拒絕決策。

### 11.2 EZKL constraint integration：Actual EZKL constraint demo

EZKL constraint integration 更進一步將推薦 profile 映射成小型 ONNX check model，並以 EZKL Python API 做實際 proof/verify。結果如下：

- `honest_profile`: `verified=True`, `clip_ok=True`, `relation_ok=True`
- `tampered_noisy_profile`: `verified=True`, `clip_ok=True`, `relation_ok=False`

這是本研究的重要里程碑，因為它證明 VDP 的關鍵檢查條件不只是在 Python 內被檢查，而是真的被送進 ZKML backend 做了 proof/verify。

### 11.3 本階段分析與結論

EZKL constraint integration 的主要意義是把研究從「artifact / stub」推進到「實際 ZK backend 驗證」。雖然這還不是完整的 FL training circuit，但已足以支撐一個非常重要的研究結論：

`VDP` 的核心審計條件可以被轉換成 `ZKML/EZKL` 可驗證模型。

## 十二、Proof-gated aggregation 與 end-to-end round：proof-gated aggregation 到 end-to-end proof-gated round

### 12.1 proof-gated aggregation：Proof-gated round

proof-gated aggregation 建立 proof-gated aggregation 原型，讓每個 client 在提交 update 前先經過 actual EZKL-backed check。結果如下：

- accepted proofs：`2/3`
- rejected proofs：`1/3`
- tampered client accepted：`False`
- accepted clients：client 0、client 2
- rejected client：client 1（tampered）

這意味著 server 不再只是被動接收 update，而是能先根據 proof/check 結果過濾不合法更新，再進行聚合。

### 12.2 end-to-end proof-gated round：End-to-end S2 round outcome

end-to-end proof-gated round 將 proof-gated aggregate 實際回寫到 global model，量測下一輪 accuracy。結果如下：

- initial accuracy：`0.694851`
- proof-gated next-round accuracy：`0.839697`
- ungated next-round accuracy：`0.836831`
- accepted clients：`2/3`

這說明 proof-gated 流程不只是邏輯上可行，也能形成實際 round-level outcome，且在本次實驗中略優於 ungated 聚合。

### 12.3 本階段分析與結論

proof-gated aggregation 與 end-to-end proof-gated round 將本研究推到最接近完整系統原型的狀態。其核心價值在於：

1. client update 已能先經過實際 ZK-backed check。
2. tampered update 可在聚合前被排除。
3. 被接受的 aggregate 可實際更新 global model 並得到可量測的 accuracy。

因此，本研究已不只是證明某組 constraint 可以被驗證，而是證明「驗證結果能真正影響聯邦學習的聚合決策」。

## 十三、整體研究討論

綜合所有實驗結果，本研究形成了一條清楚的技術路線：

1. 先確認 ZKML 工具鏈可行。
2. 再建立 FL baseline，確定聯邦學習本身穩定。
3. 接著加入 DP updater，確認 accuracy 仍可接受。
4. 再將 clipping 與 noise 拆成可審計問題。
5. 在整數 constraint 下發現 rounding 問題。
6. 透過 canonical witness 與 fixed slack 解決 honest case 誤判。
7. 將推薦 profile 匯出為 artifact 與 bundle。
8. 使用 actual EZKL proof/verify 驗證關鍵 constraint。
9. 最終接回 proof-gated aggregation 與 end-to-end round。

從研究觀點來看，本研究最重要的發現有三點：

第一，`VDP` 不應直接被當成浮點空間的數學條件搬入電路，而必須重構為量化後可穩定驗證的 witness 與 constraint。

第二，若將 DP 的核心步驟拆解成 clipping 與 additive relation 兩類條件，則它們確實可以被整理成 `ZKML` 可驗證形式。

第三，這些可驗證條件不只是理論上的檢查規則，而已能接入 FL 聚合決策，形成 proof-gated 的可信 round 流程。

## 十四、審查意見後的實驗補強：breast-cancer repeatability 到 multi-round threat matrix

針對審查意見中「技術成本缺少量化基準、資料集過少、baseline 與 evaluation protocol 不明確、研究貢獻偏系統整合」四項疑慮，breast-cancer repeatability 到 multi-round threat matrix 進行以下補強。

### 14.1 跨資料集與多類別重複實驗

主線 Adult Income 之外，實驗新增 11 個表格型二元分類資料集、Iris/Wine/Digits 三個小型多類別資料集，以及 Forest CoverType 大型多類別資料集，共涵蓋 16 個資料集。FL/DP 比較使用 seeds `42/52/62`；同一 seed 的比較模式共用相同 train/test split、client partition、模型初始化與本地訓練 shuffle。

- 11 個二元資料集中，9 個在預設 DP 參數下維持 90% 以上 DP/FL retention。
- Banknote 與 Blood Transfusion 的預設結果未達門檻，經獨立參數 sweep 後恢復；報告仍保留原始未達標結果。
- Iris、Wine、Digits 三個多類別資料集皆維持 90% 以上 retention。

這些結果改善了跨資料集可遷移性的證據；CoverType large-data scaling 另以 581,012 筆 CoverType 補強樣本規模，但模型與 client 規模仍不足以代表 production-scale FL。

### 14.2 ZKML 量化成本與風險

multiclass VDP/ZK evaluation 到 ZK cost scaling 對完整 15、42、650 維更新進行 actual EZKL benchmark。每個 dataset/seed 在獨立 Python process 執行，peak memory 使用 5 ms process RSS polling；communication payload 定義為 compact JSON update、proof JSON 與 audit metadata，不含實際網路 framing。

| Dataset | 維度 | 通過 | Prove mean | Verify mean | Peak RSS | Proving key | S2 payload |
|---|---:|---:|---:|---:|---:|---:|---:|
| Iris | 15 | 3/3 | 0.100 s | 0.033 s | 410.0 MiB | 0.89 MB | 12,519 B |
| Wine | 42 | 3/3 | 0.154 s | 0.041 s | 412.5 MiB | 1.57 MB | 12,331 B |
| Digits | 650 | 3/3 | 0.586 s | 0.034 s | 426.0 MiB | 25.18 MB | 15,198 B |

更新維度由 15 增至 650 時，circuit rows 從 138 增至 5851，proving key 約增至 28.4 倍。雖然目前設定可執行，這個成長已確認審查人指出的 scaling 風險成立。因此，本研究只主張 constraint-only、小型線性模型範圍內的技術可行性，不將結果外推到完整 local training circuit 或深度模型。

### 14.3 Baseline 與 evaluation protocol

- `S0`：FedAvg，不含 clipping、noise 與 proof。
- `S1`：相同 FedAvg 加入 clipping 與 seeded Gaussian noise，不含 proof gate。
- `S2`：S1 更新加上 EZKL proof、clipping/relation decision，且只聚合通過驗證的更新。
- 二元多資料集使用 3 clients、5 rounds、1 local epoch；多類別使用 3 clients、10 rounds、2 local epochs。
- DP/FL retention 定義為兩模式 final accuracy 平均值之比，90% 為固定門檻。
- S2 只有 proof verified、clip OK、relation OK 同時成立時接受；tampered fail case 偏移 1 個量化單位。

### 14.4 研究貢獻定位

本研究不宣稱提出新的 DP optimizer、ZKP protocol 或 proof system。較準確的貢獻是：

1. 將浮點 DP 更新重構為 `canonical quantized witness`，避免誠實更新因分別捨入而被誤拒。
2. 由 honest/tampered gap 收斂出 fixed-slack policy。
3. 建立 proof-gated aggregation contract，使 ZK/constraint 結果直接控制 FL 聚合。
4. 提供跨資料集、篡改案例與 ZK 成本的可重現實證流程。

### 14.5 Gaussian privacy accounting：正式 Privacy Accounting 與 Utility Frontier

Gaussian privacy accounting 補上 client-level Gaussian RDP accountant，並首先重新檢查目前機制是否符合 accountant 前提。結果發現，現行 artifact 將 deterministic `noise_seed` 放在 `public_inputs`；verifier/server 可由 seed 重建 `q_noise`，再由 `q_noisy - q_noise` 還原 `q_clipped`。因此，從 verifier view 不能宣稱 Gaussian DP，privacy budget 應記為 `epsilon = infinity`。

為量化「若改用 verifier 不知道的秘密、獨立 Gaussian randomness」時的條件式 trade-off，本實驗使用 client-level full participation（`q=1`）、replace-one sensitivity `2C`、`delta=1e-5` 與 10 次 sequential releases。Gaussian RDP 在 order `alpha` 的組合成本為：

```text
RDP(alpha) = T * alpha / (2 * sigma_effective^2)
epsilon = min_alpha [RDP(alpha) + log(1/delta)/(alpha-1)]
sigma_effective = noise_multiplier / 2
```

目前 `noise_multiplier=0.08` 即使在秘密 Gaussian 條件下，epsilon 仍為 `3504.357`。目標 epsilon 128、32、8 分別需要 raw noise multiplier `0.531228`、`1.396075`、`4.366154`。

| Dataset | 現行 0.08 retention / epsilon | epsilon=128 retention | epsilon=32 retention | epsilon=8 retention |
|---|---:|---:|---:|---:|
| Digits | 0.984586 / 3504.357 | 0.536609 | 0.252409 | 0.171483 |
| Iris | 1.000000 / 3504.357 | 0.782051 | 0.500000 | 0.384615 |
| Wine | 1.009524 / 3504.357 | 0.876190 | 0.609524 | 0.457143 |

表中有限 epsilon 都是假設 seed/noise 對 verifier 保密的條件式結果；public-seed 現況仍為 infinity。45 組 paired runs 顯示，原始設定能維持 utility，但沒有有意義的 privacy budget；當 noise 增加到較小 epsilon 所需程度時，三個資料集均跌破 90% retention。這是重要的負面結果，表示「可驗證 noise addition」與「可驗證、不可預測的 DP randomness」是不同問題。

正式 VDP 尚需在電路內驗證 `secret seed -> PRG -> Gaussian/discrete-Gaussian noise`，並透過 commitment、VRF/commit-reveal 或 distributed noise generation 防止 client 與 verifier 任意選擇 randomness。只把 seed 從 JSON 移除並不足以完成此修正。

### 14.6 CoverType large-data scaling：Forest CoverType 大型資料 Scaling 與 Actual EZKL

為直接回應小型資料集不足的疑慮，本研究加入 Forest CoverType：共 `581,012` 筆、54 特徵、7 類別。固定 20% test split（116,203 筆），比較 10,000、100,000 與完整 464,809 筆 training split。每個規模使用 seeds `42/52/62`，並加入 clipping-only control，使 FL、clipping-only、DP-update 共完成 27 組 paired runs。

| Training samples | FL final mean | Clip-only final mean | DP final mean | Clip/FL retention | DP/FL retention | FL/Clip/DP train sec |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.627299 | 0.627299 | 0.569942 | 1.000000 | 0.908566 | 12.8 / 12.6 / 12.8 |
| 100,000 | 0.712285 | 0.701078 | 0.667886 | 0.984266 | 0.937666 | 20.8 / 20.4 / 20.0 |
| 464,809 | 0.719890 | 0.700633 | 0.636799 | 0.973251 | 0.884579 | 51.1 / 50.7 / 52.0 |

完整 training split 的 peak process RSS 約為 715--716 MiB，單次平均訓練約 51--52 秒，證明 58 萬筆資料可由目前線性 FL/DP 原型實際處理。效用結果並非隨資料量單調改善：完整分割的總 accuracy gap 為 `0.083091`，其中 clipping-only gap 為 `0.019257`，加入 noise 後額外 gap 為 `0.063834`。這是由 control 得到的差距分解，不應被外推為一般性因果比例。

CoverType 線性 7 類模型共有 385 個參數。本研究進一步把完整資料訓練所產生的 385 維 client update 送入 actual EZKL：honest case 為 `verified=True, clip_ok=True, relation_ok=True, accepted=True`；將 `q_noisy` 偏移 1 個量化單位後，tampered case 為 `verified=True, relation_ok=False, accepted=False`。Honest prove/verify 分別為 0.306/0.040 秒，proof 為 12,293 bytes，peak RSS 約 430 MiB。這支持 S2 constraint/check 可銜接大型資料所產生的更新，但 proof 電路仍未包含完整 local training trace；EZKL calibration 的大型 lookup input 警告亦保留為量化與工具鏈風險。

### 14.7 non-IID client scaling：Non-IID 與 Client Scaling

為移除 CoverType large-data scaling 僅 K=3、stratified IID 的限制，non-IID client scaling 固定 CoverType 100,000 筆 training subset，比較 K=3/10 與 stratified IID、Dirichlet alpha=0.5、Dirichlet alpha=0.1。每個條件使用 seeds `42/52/62/72/82`，並以完全相同 split、partition、初始化與 shuffle 比較 FL、clipping-only、DP-update，共完成 6 conditions、30 paired workers、90 mode runs。表中的 95% CI 為 seed-level t interval。

| Clients | Partition | Label TV | FL final mean | DP final mean | DP/FL retention | DP 95% CI |
|---:|---|---:|---:|---:|---:|---:|
| 3 | IID | 0.000050 | 0.689464 | 0.612738 | 0.888716 | 0.012088 |
| 3 | alpha=0.5 | 0.282212 | 0.679766 | 0.576464 | 0.848033 | 0.029448 |
| 3 | alpha=0.1 | 0.512622 | 0.677091 | 0.516235 | 0.762431 | 0.068056 |
| 10 | IID | 0.000134 | 0.607950 | 0.584859 | 0.962019 | 0.026942 |
| 10 | alpha=0.5 | 0.368662 | 0.630750 | 0.581477 | 0.921883 | 0.015131 |
| 10 | alpha=0.1 | 0.634526 | 0.620605 | 0.518181 | 0.834961 | 0.058654 |

六個條件全部可執行，支持原型不只在 K=3/IID partition 上成立；但高度 non-IID 條件的 retention 與 CI 明顯惡化，因此不能宣稱所有 partition 都維持 90% utility。此處的結論是 client/partition robustness 的範圍量測，不是正式 DP randomness 保證。

### 14.8 multi-round threat matrix：多輪 Proof-Gated Threat Matrix

multi-round threat matrix 在 CoverType 100,000 筆、K=10、Dirichlet alpha=0.1、3 rounds、20% attackers 下，對 relation tamper、clip bypass、replay、zero-noise 與 bounded sign-flip 比較 ungated、current gate 與 strengthened gate。三個 seeds 共完成 48 條完整訓練軌跡與 1,440 次 client 決策。Current gate 為 proof+clip+relation；strengthened policy 另加入 client/round/model binding、replay protection 與 noise-generation policy。

這 1,440 次決策重用前期 actual EZKL 所建立的 verified-artifact/check contract，屬於系統層 policy simulation，並未逐 client update 重新產生 1,440 份 actual proofs。Actual proof 可行性由 EZKL constraint integration、22、23、25 的獨立 proof 實驗支撐；因此 multi-round threat matrix 的結論是多輪 aggregation policy 與威脅範圍，不是額外的 1,440-proof 成本 benchmark。

| Attack | Current malicious acceptance | Strengthened acceptance | Current clean retention | Strengthened clean retention |
|---|---:|---:|---:|---:|
| Relation tamper | 0.000000 | 0.000000 | 0.585848 | 0.585848 |
| Clip bypass | 0.000000 | 0.000000 | 0.585848 | 0.585848 |
| Replay | 1.000000 | 0.000000 | 0.975868 | 0.718373 |
| Zero noise | 1.000000 | 0.000000 | 1.197807 | 0.585848 |
| Bounded sign flip | 1.000000 | 1.000000 | 0.179797 | 0.179797 |

結果支持三個精確結論。第一，現有 gate 對其聲明的 clipping/relation 違規確實能在多輪情境拒絕。第二，只驗證 additive relation 不足以阻止舊 proof replay 或零噪聲；context 與 noise-generation policy 是必要條件。第三，即使加上上述 policy，合法界限內的反向更新仍會通過，表示 update-level VDP gate 不能被誇大為完整 local-training correctness 或任意 poisoning defense。

拒絕兩個最大 non-IID clients 後，部分 strengthened trajectories 的 clean retention 只有 0.585848，亦揭露安全拒絕與可用資料/availability 的代價。這是壓力測試的重要負面結果，而不是以選擇性指標隱藏的失敗。完整假設判定整理於 `docs/hypothesis_evidence_matrix.md`。

### 14.9 experimental-rigor audit：實驗完整性、統計與可重現性稽核

為避免只憑平均值宣稱架構成立，experimental-rigor audit 直接讀取 the large-data, non-IID, and threat-matrix evaluations raw CSV，檢查 expected rows、primary-key uniqueness 與 baseline/comparison seed pairing。結果為 27/27 large-scaling mode runs、90/90 non-IID mode runs、48/48 threat trajectories 與 1,440/1,440 client decisions，沒有重複 primary key；程式碼審查亦確認先切 train/test、scaler 只在 train fit，且 paired modes 共用 split、partition、初始化與 shuffle。

33 組 accuracy comparisons 皆以 seed 為獨立單位，報告 paired mean difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation p 與 family-level Holm correction。CoverType large-data scaling/27 的 n=3 使 two-sided exact p 最低只能為 0.25；non-IID client scaling 的 n=5 最低為 0.0625，所有 Holm-adjusted p 均未低於 0.05。因此，本研究的 accuracy 結果定位為描述性 effect、方向、區間與工程可行性證據，不使用「統計顯著」措辭。

可重現性方面，另輸出 Python/OS/ezkl/torch/numpy/scikit-learn/scipy 等精確版本，以及核心 scripts、raw CSV、summary CSV 的 SHA-256 manifest。這些產物使結案結果可被完整性驗證，但不把小樣本描述統計誇大為一般性母體推論。

### 14.10 context-bound randomness protocol：Context-Bound Hidden-Randomness Reference Protocol

為把 public seed、replay 與 zero-noise 從「已知限制」推進成可實作規格，context-bound randomness protocol 定義 setup-time client randomness commitment、commit-before-challenge、單一 server challenge、context-bound hidden seed、integer centered-binomial reference sampler、challenge consumption 與 replay cache。Hidden seed 綁定 client、round、model hash、nonce、update commitment 及 challenge；public statement 不包含 client secret、derived seed 或 `q_noise`。

Reference evaluator 完成 honest、replay、round swap、model swap、challenge swap、zero-noise、secret swap、clip bypass、noisy tamper 與 challenge reissue 共 10 cases，10/10 符合預期。尤其 zero-noise 即使維持 additive relation，仍因 seed-derived noise check 失敗而被拒絕；失敗提交也消耗 challenge，避免同一 commitment 反覆嘗試有利 noise。

context-bound randomness protocol 仍是 intended circuit relation 的 host-side evaluator。HMAC/SHAKE 與 sampler 尚未映射 actual ZK circuit，也沒有 exact sampler 的 finite-epsilon theorem/accountant。因此它是投稿版方法設計的第一個可執行 contract，不取代 actual proof 或正式 DP security proof。

完整審查回應、工程綠／黃／紅門檻與可直接使用的答辯文字，整理於 `docs/reviewer_feedback_response.md`。

## 十五、研究限制

雖然本研究已完成完整原型鏈，但仍有幾項限制必須誠實說明：

1. Gaussian privacy accounting 已完成條件式 client-level RDP accountant，但現行 public deterministic seed 使 noise 可被 verifier 扣除，因此實際機制不能宣稱有限 epsilon；正式 secret randomness 與 circuit-level noise-generation verification 尚未完成。
2. non-IID client scaling 已把 CoverType 擴展至 K=10 與 Dirichlet non-IID partition，但最多仍只有 10 clients、5 seeds，且不是 production-scale federation。
3. 目前模型仍以小型、ZKML 相容模型為主，尚未擴展到更複雜深度模型。
4. Actual EZKL proof 目前驗證的是 `VDP constraint-style check model`，而不是完整的 FL local training + aggregation 單一大型電路。
5. 後續 ZK cost scaling 已補上 Iris/Wine/Digits、3 個 seeds 的 proving time、verification time、proof size、peak RSS 與 application-layer communication payload；CoverType large-data scaling 另完成 CoverType 385 維 actual EZKL，但仍限於線性模型，且通訊量尚未包含實際網路 framing。
6. 多數跨資料集 FL/DP 實驗只有 3 個 seeds；non-IID client scaling 使用 5 seeds 與 95% t interval，但仍不足以形成一般性統計結論。
7. multi-round threat matrix 的 strengthened context/replay/noise-generation gate 是系統 policy 原型，尚未全部綁入 actual ZK circuit 或密碼學 commitment。
8. Bounded sign-flip 可通過 current 與 strengthened gate；目前系統不能宣稱驗證 local training provenance 或防禦任意 model poisoning。
9. context-bound randomness protocol 已完成 hidden-randomness/context contract，但 reference cryptographic primitives 與 integer sampler 尚未 circuit 化或取得正式 privacy theorem。

這些限制表示本研究目前最合適的定位是「可驗證差分隱私聯邦學習之研究原型」，而不是最終版的大規模部署系統。

## 十六、最終結論

本研究已完成從 ZKML baseline、FL baseline、DP baseline，到 VDP constraint 設計、artifact 匯出、actual EZKL proof/verify、proof-gated aggregation 與 end-to-end round outcome 的完整原型鏈。

實驗結果支持以下結論：

1. 聯邦學習在目前設定下可穩定收斂。
2. 差分隱私更新在目前 baseline 下可維持可接受效能。
3. 差分隱私中的 clipping 與 noise relation，不能直接以浮點形式搬入 ZK，但可透過 `canonical quantized witness + fixed slack policy` 轉換為穩定可驗證的 constraint。
4. 這些 constraint 已能被 EZKL 實際 proof/verify。
5. proof/check 結果已能影響聯邦學習聚合決策，並形成可量測的 end-to-end round outcome。
6. Privacy accountant 已把主張邊界量化：現行 public-seed 原型的 epsilon 為 infinity；秘密 Gaussian 條件下則存在明顯 privacy-utility trade-off。
7. CoverType 的 581,012 筆大型資料實驗顯示現有 FL/DP 原型可在約 716 MiB peak RSS 下完成；clipping-only control 亦顯示完整分割的效用下降主要來自加入 noise 後的額外 gap，而非單純資料載入失敗。
8. K=3/10 與 IID/Dirichlet 的 90-run 實驗顯示架構能在較大 client 數與 non-IID partition 下執行，但高度異質條件會使 DP/FL retention 降至 0.762431–0.834961。
9. 多輪威脅矩陣證實 current gate 可拒絕 relation/clip 違規；replay/zero-noise 必須增加 context/randomness policy，而 bounded poisoning 仍需 training provenance 或 robust aggregation。
10. experimental-rigor audit 稽核確認全部核心矩陣完整且成對，但 exact permutation 與 Holm correction 亦確認目前 seed 數只適合描述性/可行性主張，不支持統計顯著措辭。
11. context-bound randomness protocol 將 replay/context/randomness 缺口收斂成 10/10 reference checks，但 full-paper 等級仍需 actual verifiable-randomness circuit 與 sampler-specific DP proof。

因此，本研究已足以主張：

**聯邦學習中的 DP update 核心步驟可以被轉換成 ZKML 可審計的約束條件，並形成可在大型資料、K=10 non-IID 多輪情境運作的 proof-gated 原型；但要升級為具有有限 privacy budget 與完整訓練正確性的可驗證差分隱私，仍必須補上對 verifier 保密且可在電路內驗證的 noise generation、context binding，以及 local-training provenance 或 robust aggregation。**

若以未來應用來看，本研究最重要的貢獻，在於證明了：

**`VDP-as-auditable-ZKML-constraint` 是可行的，並可作為未來隱私審計架構與可信聯邦學習系統的重要參考。**
