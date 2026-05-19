# 以 ZKML 實現可驗證差分隱私聯邦學習之原型研究

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

## 四、ZKML baseline：Week 1 到 Week 4

### 4.1 Week 1：最小 EZKL pipeline 驗證

Week 1 的目標是建立最小可行的 ZKML pipeline，確認從模型匯出到 proof/verify 的流程是可行的。實作上完成了：

- PyTorch 模型建立
- ONNX 匯出
- EZKL settings / compile / setup
- proof 生成與 verify

此階段的意義在於確認技術鏈可用，為後續所有「可驗證」主張建立工具基礎。若 Week 1 無法跑通，後續所有與 ZKML 有關的實驗都無法成立。

### 4.2 Week 2：真實資料導入與 client split

Week 2 將實驗從 demo 轉移到真實資料，完成：

- UCI Adult Income 前處理
- 類別特徵編碼與標準化
- train/test split
- `K=3` client partition

這一步的研究意義，是使後續 FL、DP 與 ZK 驗證都建立在同一組真實資料條件下，而不是只停留在 toy example。

### 4.3 Week 3：Scale sweep

Week 3 測試不同 quantization `scale` 對模型 accuracy 與 ZK 成本的影響。結果顯示：

- `scale = 8` 時 quantized accuracy 最佳：`0.841540`
- `scale = 8` 時 proving time 最快：約 `0.1391 sec`

這說明在目前小型模型與資料條件下，較低 scale 已足以保留模型精度，並能降低 proving 成本。此結果也為後續 ZKML 可行性分析提供量化依據。

### 4.4 Week 4：Baseline 圖表整理

Week 4 將 scale sweep 結果視覺化，產出：

- `scale_vs_accuracy.png`
- `scale_vs_proving_time.png`

圖表呈現後，可以更清楚說明量化參數對 accuracy 與證明成本的影響，也讓 ZKML baseline 不只是流程驗證，而具有可比較的性能結果。

### 4.5 本階段分析與結論

ZKML baseline 階段證明兩件事：

1. 在目前設定下，EZKL 已可在小型模型上完成真正的 prove/verify。
2. 量化設定會同時影響 accuracy 與 proving 成本，因此後續若要將 DP 條件搬入 ZK，必須兼顧數值穩定性與電路成本。

因此，Week 1 到 Week 4 成功建立了 ZKML 作為可驗證機制的技術基礎。

## 五、FL baseline：Week 5 到 Week 6

### 5.1 Week 5：FedAvg baseline

Week 5 建立 S0，也就是不含 DP 與 ZK 驗證的聯邦學習 baseline。結果如下：

- 初始 accuracy：`0.694851`
- 最佳 accuracy：第 2 輪 `0.845122`
- 第 5 輪 accuracy：`0.842051`
- 平均 round time：`1.0171 sec`

此結果顯示模型在小規模聯邦學習下能快速收斂，且第 1 至第 2 輪就已接近穩定。這使得後續 S1 與 S2 都有一條可參照的 baseline 曲線。

### 5.2 Week 6：S0 Round vs Accuracy

Week 6 將 Week 5 的結果轉為 `Round vs Accuracy` 圖，幫助觀察聯邦學習的收斂趨勢。圖中可見 accuracy 在初始到第一輪有大幅提升，後續輪次則在高點附近小幅波動。

### 5.3 本階段分析與結論

S0 的建立很重要，因為它證明在目前模型、資料與 client split 設定下，聯邦學習本身是穩定的。若沒有這條基準線，就很難判斷後續 DP 或 ZK 驗證對系統造成的影響究竟來自保護機制本身，還是來自 FL 流程不穩定。

因此，本階段可合理得出結論：本研究的 FL baseline 已足以作為 S1 與 S2 的比較基準。

## 六、DP baseline：Week 7 到 Week 8

### 6.1 Week 7：DP updater baseline

Week 7 將 `clipping + Gaussian noise` 加入聯邦學習流程，建立 S1。結果如下：

- 初始 accuracy：`0.694851`
- 最佳 accuracy：`0.844201`
- 最終 accuracy：`0.838776`
- 平均 round time：`1.2266 sec`
- `noise_mode = seeded_deterministic`

此結果顯示，在目前設定下加入 DP updater 並未使模型表現崩潰，accuracy 仍能維持在與 S0 相近的水準。更重要的是，這裡引入了 `seeded_deterministic noise`，為後續可驗證 noise 提供了必要條件。

### 6.2 Week 8：Epsilon sweep

Week 8 測試不同 epsilon 設定對 accuracy 的影響，結果顯示：

- 最佳 epsilon：`2.0`
- 對應 best accuracy：`0.844303`

需注意的是，此階段的 epsilon-to-noise mapping 主要是 baseline 比較用途，並非正式 privacy accountant 結果，因此較適合用來觀察相對趨勢，而非作為最終嚴格隱私保證。

### 6.3 本階段分析與結論

DP baseline 階段的主要結論有三點：

1. 在目前任務與模型下，加入 clipping 與 noise 後，模型仍能維持可接受 accuracy。
2. noise 並未造成明顯訓練崩潰，表示目前 DP baseline 是穩定的。
3. deterministic noise 的引入使得「DP 可被重播與驗證」成為可能，這是後續 VDP 設計的核心前提。

因此，本階段成功將研究從單純 FL 推進到「可被驗證的 DP」方向。

## 七、VDP 核心條件驗證：Week 9 到 Week 10

### 7.1 Week 9：Clipping verification

Week 9 的目標是先將 clipping 條件整理成可重跑的驗證原型。結果如下：

- honest cases accepted：`3/3`
- tampered cases rejected：`6/6`

這表示 clipping 的 norm bound 與 clipping relation 在 Python 層已能穩定區分合法與篡改更新。

### 7.2 Week 10：Noise verification

Week 10 進一步驗證 seed-based noise 與 noisy-update relation。結果如下：

- honest cases accepted：`3/3`
- tampered cases rejected：`6/6`

這證明只要使用可重現的 seed-based noise，noise generation 與 add-noise relation 都可以被驗證。這一步是 VDP 架構最關鍵的前置條件之一，因為若 noise 完全不可重現，就無法進一步做 ZK 審計。

### 7.3 本階段分析與結論

Week 9 與 Week 10 的真正價值，不只是把 honest 與 tampered case 分出來，而是把差分隱私中的兩個核心步驟明確定義成「可檢查、可拒絕、可形成 fail case」的驗證問題。

合理結論是：`VDP` 並非天生不可驗證，只要把 clipping 與 noise relation 拆解成具體條件，就能為後續 ZK constraint 設計提供明確標的。

## 八、整數化與 rounding 問題：Week 11

Week 11 將 clipping 與 noise relation 搬到 fixed-point / integer constraint 下檢查，觀察量化後是否仍能精確成立。結果如下：

- honest integer clipping bounds exact：`5/9`
- honest quantized noise relations exact：`0/9`
- tampered quantized relations rejected：`9/9`
- max float-vs-quantized relation gap：`1`
- max clipping-bound excess after quantization：`4200 ppm`

這個結果非常關鍵，因為它說明若直接將浮點空間中的 DP 等式原封不動搬進整數 constraint，honest case 也可能失敗。換言之，未來電路設計最大的問題不是能否抓到惡意案例，而是如何避免把合法案例誤判為不合法。

### 本階段分析與結論

Week 11 的主要研究意義在於揭露了 quantization 與 rounding 的根本問題：

- `q(a+b)` 不會自然等於 `q(a)+q(b)`
- clipping 的邊界案例可能因 rounding 而略微超界

因此，後續若要讓 DP 條件真正進入 ZK 電路，不能直接驗證浮點定義，而必須重新定義 witness 形式與容錯策略。

## 九、Canonical witness 與 slack policy：Week 12 到 Week 13

### 9.1 Week 12：Canonical witness

為了解決 noise relation 的 rounding 問題，Week 12 引入 canonical witness，直接定義：

- `q_clipped = round(scale * clipped_update)`
- `q_noise = round(scale * noise)`
- `q_noisy = q_clipped + q_noise`

結果如下：

- honest canonical relations exact：`9/9`
- tampered canonical relations rejected：`9/9`
- honest clipping checks exact without slack：`5/9`
- honest clipping checks covered with observed slack：`9/9`

這表示 additive relation 的量化問題已被 canonical witness 結構性解決。

### 9.2 Week 12：Slack policy sweep

Week 12 同時做了 clipping slack sweep，結果觀察到：

- max honest excess：`4200 ppm`
- min tampered excess：`73300 ppm`
- feasible slack interval：`(4200, 73300) ppm`
- simple candidate slack：`4201 ppm`

這顯示存在一個非常清楚的安全區間，使系統可以固定一個 slack，同時接受 honest case 並拒絕 tampered case。

### 9.3 Week 13：Recommended constraint profile

Week 13 將 canonical witness 與固定 slack 組合成單一推薦版本。結果如下：

- recommended slack：`4201 ppm`
- honest profiles accepted：`9/9`
- tampered profiles rejected：`18/18`

### 9.4 本階段分析與結論

Week 12 到 Week 13 是整個研究最核心的方法學貢獻。它證明：

1. 不能直接用浮點等式做 ZK 驗證。
2. 必須改用 `canonical quantized witness`。
3. clipping 邊界誤差需要明確的 `slack policy`。
4. 這套設計在 honest 與 tampered case 之間具有足夠大的安全區間。

因此，本研究成功將「DP 可被驗證」從概念推進到穩定可行的 constraint 設計。

## 十、Artifact 與 backend-ready 格式：Week 14 到 Week 15

### 10.1 Week 14：Constraint artifact export

Week 14 將推薦的 constraint profile 匯出成固定格式 JSON artifact，包含：

- `meta`
- `public_inputs`
- `witness`
- `checks`

結果如下：

- honest artifacts passing checks：`3/3`
- tampered artifacts rejected：`6/6`

這代表推薦 profile 不只是理論規則，而已具備固定的 circuit-facing 輸入格式。

### 10.2 Week 15：ZK backend stub

Week 15 再進一步將 artifact 轉成 backend-ready bundle，拆分為：

- `io_bundle.json`
- `verification_hint.json`
- backend note

結果如下：

- bundles exported：`9`
- honest bundles：`3`
- tampered bundles：`6`

這一步的重點是工程介面收斂。即使當時尚未實際生成 proof，研究已經把未來接入 ZK backend 的資料格式整理完整。

### 10.3 本階段分析與結論

Week 14 到 Week 15 的意義在於把研究從「找到正確 constraint」推進到「固定後續實作介面」。這降低了未來 backend 整合的不確定性，也讓整個 VDP-ZKML 架構更接近真正可落地的系統設計。

## 十一、S2 整合與 actual EZKL proof：Week 16

### 11.1 Week 16：S2 integration demo

Week 16 先完成 repo-level 的 S2 整合示範。結果如下：

- scale：`10000`
- tampered client：`1`
- accepted updates under S2 profile：`2/3`
- rejected updates under S2 profile：`1/3`
- tampered client accepted：`False`

這表示推薦 profile 已能在系統層級做出接受或拒絕決策。

### 11.2 Week 16：Actual EZKL constraint demo

Week 16 更進一步將推薦 profile 映射成小型 ONNX check model，並以 EZKL Python API 做實際 proof/verify。結果如下：

- `honest_profile`: `verified=True`, `clip_ok=True`, `relation_ok=True`
- `tampered_noisy_profile`: `verified=True`, `clip_ok=True`, `relation_ok=False`

這是本研究的重要里程碑，因為它證明 VDP 的關鍵檢查條件不只是在 Python 內被檢查，而是真的被送進 ZKML backend 做了 proof/verify。

### 11.3 本階段分析與結論

Week 16 的主要意義是把研究從「artifact / stub」推進到「實際 ZK backend 驗證」。雖然這還不是完整的 FL training circuit，但已足以支撐一個非常重要的研究結論：

`VDP` 的核心審計條件可以被轉換成 `ZKML/EZKL` 可驗證模型。

## 十二、Proof-gated aggregation 與 end-to-end round：Week 17 到 Week 18

### 12.1 Week 17：Proof-gated round

Week 17 建立 proof-gated aggregation 原型，讓每個 client 在提交 update 前先經過 actual EZKL-backed check。結果如下：

- accepted proofs：`2/3`
- rejected proofs：`1/3`
- tampered client accepted：`False`
- accepted clients：client 0、client 2
- rejected client：client 1（tampered）

這意味著 server 不再只是被動接收 update，而是能先根據 proof/check 結果過濾不合法更新，再進行聚合。

### 12.2 Week 18：End-to-end S2 round outcome

Week 18 將 proof-gated aggregate 實際回寫到 global model，量測下一輪 accuracy。結果如下：

- initial accuracy：`0.694851`
- proof-gated next-round accuracy：`0.839697`
- ungated next-round accuracy：`0.836831`
- accepted clients：`2/3`

這說明 proof-gated 流程不只是邏輯上可行，也能形成實際 round-level outcome，且在本次實驗中略優於 ungated 聚合。

### 12.3 本階段分析與結論

Week 17 與 Week 18 將本研究推到最接近完整系統原型的狀態。其核心價值在於：

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

## 十四、研究限制

雖然本研究已完成完整原型鏈，但仍有幾項限制必須誠實說明：

1. 目前 `epsilon` 實驗主要作為 baseline 比較用途，尚未接上正式 privacy accountant。
2. 目前 client 數量為 `K=3`，屬於小規模聯邦學習原型。
3. 目前模型仍以小型、ZKML 相容模型為主，尚未擴展到更複雜深度模型。
4. Actual EZKL proof 目前驗證的是 `VDP constraint-style check model`，而不是完整的 FL local training + aggregation 單一大型電路。
5. 系統級 proving time、verification time、proof size、memory 與 communication overhead，仍可在未來進一步做更完整 benchmark。

這些限制表示本研究目前最合適的定位是「可驗證差分隱私聯邦學習之研究原型」，而不是最終版的大規模部署系統。

## 十五、最終結論

本研究已完成從 ZKML baseline、FL baseline、DP baseline，到 VDP constraint 設計、artifact 匯出、actual EZKL proof/verify、proof-gated aggregation 與 end-to-end round outcome 的完整原型鏈。

實驗結果支持以下結論：

1. 聯邦學習在目前設定下可穩定收斂。
2. 差分隱私更新在目前 baseline 下可維持可接受效能。
3. 差分隱私中的 clipping 與 noise relation，不能直接以浮點形式搬入 ZK，但可透過 `canonical quantized witness + fixed slack policy` 轉換為穩定可驗證的 constraint。
4. 這些 constraint 已能被 EZKL 實際 proof/verify。
5. proof/check 結果已能影響聯邦學習聚合決策，並形成可量測的 end-to-end round outcome。

因此，本研究已足以主張：

**聯邦學習中的差分隱私核心步驟可以被轉換成 ZKML 可審計的約束條件，並進一步形成 proof-gated 的可驗證差分隱私架構原型。**

若以未來應用來看，本研究最重要的貢獻，在於證明了：

**`VDP-as-auditable-ZKML-constraint` 是可行的，並可作為未來隱私審計架構與可信聯邦學習系統的重要參考。**
