# VDP-FL 進度彙報（Week 1 - Week 16）

## 一、目前完成進度

目前已完成 Week 1 到 Week 16 的 repo-level 實作，對應到三個主要階段：

- ZKML baseline 建立
- FL baseline 建立
- DP baseline 與 epsilon sweep

目前已完成的資料夾如下：

- `week1_demo/`
- `week2_uci_model/`
- `week3_scale_sweep/`
- `week4_baseline_charts/`
- `week5_fedavg_simulator/`
- `week6_s0_charts/`
- `week7_dp_updater/`
- `week8_epsilon_sweep/`
- `week9_clipping_verification/`
- `week10_noise_verification/`
- `week11_quantized_constraints/`
- `week12_canonical_witness/`
- `week13_recommended_constraints/`
- `week14_constraint_artifacts/`
- `week15_zk_backend_stub/`
- `week16_s2_integration/`

---

## 二、各週完成內容

### Week 1：ZKML 最小流程跑通

目標是驗證 `PyTorch -> ONNX -> EZKL -> prove -> verify` 是否可行。

已完成：

- 建立 demo 模型
- 匯出 ONNX
- 跑通 EZKL pipeline
- 完成 proof 與 verify

意義：

- 確認 ZKML 基本工具鏈可用
- 建立後續真實資料實驗的技術基礎

### Week 2：真實資料與 client split

目標是將 demo 換成真實資料，並準備 FL 所需資料。

已完成：

- 使用 UCI Adult Income 資料集
- 完成資料前處理與標準化
- 訓練模型並匯出 ONNX
- 跑通 EZKL pipeline
- 將訓練資料切成 `K=3` clients

目前 client split：

- client 0：13025 筆
- client 1：13024 筆
- client 2：13024 筆

意義：

- 完成真實資料上的 ZKML baseline
- 為後續聯邦學習建立資料基礎

### Week 3：Scale sweep

目標是測試不同量化 `scale` 對 accuracy 與 ZK 成本的影響。

已完成：

- 測試 `scale = 8 / 12 / 16`
- 記錄 accuracy、proving time、verify time、proof size
- 輸出 CSV

結果：

- scale 8：accuracy `0.841540`，prove `0.1391s`，verify `0.0762s`，proof `11.8428 KB`
- scale 12：accuracy `0.841335`，prove `0.1780s`，verify `0.0883s`，proof `11.8457 KB`
- scale 16：accuracy `0.841335`，prove `0.1499s`，verify `0.0863s`，proof `11.7734 KB`

目前觀察：

- `scale = 8` 是目前較佳的 baseline 設定

### Week 4：Baseline 圖表整理

目標是將 Week 3 的結果轉為可視化圖表。

已完成：

- `scale vs accuracy`
- `scale vs proving time`

意義：

- 能更直觀地說明量化參數對 accuracy 與證明成本的影響

### Week 5：FedAvg 聯邦學習 baseline

目標是建立 S0，也就是不含 DP 與 ZK 驗證的 FL baseline。

已完成：

- 使用 `K=3` client split
- 建立 `FedAvg` 模擬器
- 設定 `R=5, E=1`
- 輸出每輪 accuracy 與 round time

結果：

- round 0：`0.694851`
- round 1：`0.840823`
- round 2：`0.845122`
- round 3：`0.843382`
- round 4：`0.840823`
- round 5：`0.842051`

目前觀察：

- 模型在第 1 輪後快速收斂
- 第 2 輪達到最佳 accuracy

### Week 6：S0 Round vs Accuracy

目標是將 Week 5 的結果轉成 `Round vs Accuracy` 圖。

已完成：

- 輸出 `round_vs_accuracy.png`
- 輸出摘要檔

意義：

- 可觀察 FL baseline 的收斂趨勢
- 作為後續 S1、S2 的比較基準

### Week 7：DP updater baseline

目標是在 FedAvg 上加入 `clipping + Gaussian noise`，建立 S1 的第一版 baseline。

已完成：

- 計算 client update `Δw`
- 對 update 做 L2 clipping
- 對 clipped update 加入 Gaussian noise
- 記錄 round-level accuracy 與 update 統計量

結果：

- initial accuracy：`0.694851`
- final accuracy：`0.843075`
- best accuracy：`0.845020`

目前觀察：

- 在目前這組 baseline 設定下，加入簡化版 DP update 後，模型沒有明顯崩潰

### Week 8：Epsilon sweep

目標是測試不同 `epsilon` 設定對 S1 baseline 的影響。

已完成：

- 測試 `epsilon = 0.5 / 1 / 2`
- 比較 accuracy 與 round time
- 產出 `epsilon vs accuracy` 圖

結果：

- epsilon 0.5：best accuracy `0.844815`
- epsilon 1.0：best accuracy `0.845020`
- epsilon 2.0：best accuracy `0.844611`

目前觀察：

- 在目前 baseline 中，`epsilon = 1.0` 的 accuracy 最佳

---

### Week 11：Quantized Constraint Mapping

目標是先觀察 clipping 與 noise relation 在 fixed-point / integer constraint 下會出現哪些 rounding 問題。

已完成：

- 建立整數 constraint 檢查腳本
- 比較 `q(a+b)` 與 `q(a) + q(b)` 的差異
- 檢查 clipping bound 是否會因量化而跨界

重要觀察：

- `q(a+b)` 與 `q(a) + q(b)` 在 honest case 下不會自然精確相等
- clipping bound 在邊界案例下可能因 rounding 輕微超界

意義：

- 提前定位未來電路設計的 rounding 問題
- 證明後續必須選擇 canonical witness 與明確 slack policy

### Week 12：Canonical Witness + Slack Sweep

目標是找到更穩定的 witness 形式與 clipping slack 規則。

已完成：

- 建立 canonical witness 原型
- 確認 honest noise relation 可達到 `9/9` 精確成立
- 建立 slack policy sweep
- 找出 honest / tampered 之間的 slack 可行區間

重要觀察：

- honest 最大 clipping excess 為 `4200 ppm`
- tampered 最小 clipping excess 為 `73300 ppm`
- 已出現足夠大的安全區間可供固定 slack 使用

意義：

- 將 noise relation 從 prototype 推進到穩定可映射 constraint
- 將 clipping 驗證推進到可設定固定 slack 的設計階段

### Week 13：Recommended Constraint Profile

目標是把目前最穩定的 witness 與 slack 組合成單一推薦版本。

已完成：

- 建立推薦 constraint profile 腳本
- 固定 canonical witness
- 固定推薦 slack 候選值
- 同時檢查 clipping 與 noisy-update relation

意義：

- 為後續 S2 電路設計提供更接近規格的候選版本
- 將「探索問題」進一步收斂成「可採用設計」

### Week 14：Constraint Artifact Export

目標是把推薦 constraint profile 轉成更接近電路輸入的固定 artifact。

已完成：

- 匯出 `public_inputs`
- 匯出 `witness`
- 匯出 `checks`
- 建立 honest / tampered artifact corpus

意義：

- 固定後續 circuit-facing 的資料格式
- 降低之後接 ZK backend 時的格式不確定性

### Week 15：ZK Backend Stub

目標是把 Week 14 artifact 再整理成 backend-ready bundle。

已完成：

- 匯出 `io_bundle.json`
- 匯出 `verification_hint.json`
- 匯出 backend note

意義：

- 讓未來接 EZKL 或其他 backend 時有明確 handoff 格式
- 在沒有安裝 `ezkl` 的環境下，先完成 repo 內可交付的 stub 整合

### Week 16：S2 Integration Demo

目標是做一個可重跑的 S2 整合原型，展示 tampered client 會被過濾。

已完成：

- 建立 S2 round decision demo
- 模擬 1 個 tampered client + 2 個 honest clients
- 根據推薦 profile 做接受 / 拒絕決策

意義：

- 完成 repo-level 的 S2 整合示範
- 讓整個 16 週計畫在目前環境下具備端到端敘事與可執行產物

---

## 三、目前累積的研究意義

### Week 9：Clipping 驗證原型

目標是先把 `||Δw||^2 <= C^2` 的驗證邏輯整理成可重跑的原型。

已完成：

- 建立 clipping verification 腳本
- 對每個 client 的 update 檢查 clipping bound
- 建立 honest case 與 tampered case
- 區分「超出 bound」與「雖在 bound 內但不符合 clipping 關係」兩種 fail case

意義：

- 先把後續 ZK 要驗證的數學條件定義清楚
- 為之後的 circuit constraint 設計建立測試基準

### Week 10：Noise 驗證原型

目標是先把 `seed -> noise -> noisy update` 的驗證邏輯整理成可重跑的原型。

已完成：

- 建立 noise verification 腳本
- 用固定 seed 生成可重現的 noise
- 檢查 noise 是否真的對應指定 seed
- 檢查 noisy update 是否真的等於 clipped update 加上 noise
- 建立 honest case 與 tampered case

意義：

- 先把後續 ZK 要驗證的 noise 流程定義清楚
- 為之後的 verifiable DP 整合建立第二個核心測試基準

---

## 三、目前累積的研究意義

目前這 16 週的進度，已經建立出以下基礎：

1. 已完成真實資料上的 ZKML baseline
2. 已完成 FL baseline（S0）
3. 已完成 DP baseline（S1）的第一版流程
4. 已建立量化參數與隱私參數的基礎比較機制
5. 已建立 clipping 條件的前置驗證原型
6. 已建立 noise 生成與套用流程的前置驗證原型
7. 已定位 quantized constraint 的 rounding 問題
8. 已找到 canonical witness 與 clipping slack 的可行設計方向
9. 已收斂出推薦 constraint profile
10. 已固定 circuit-facing artifact 格式
11. 已建立 backend-ready handoff bundle
12. 已完成 repo-level S2 integration demo

這代表後續可以開始進到：

- clipping 可驗證
- noise 可驗證
- constraint profile 固定化
- circuit-facing artifact 固定化
- S2（FL + DP + ZK）repo-level 整合

---

## 四、目前已知限制

目前仍有幾個限制需要在報告中說清楚：

1. Week 7 與 Week 8 的 DP 部分，目前是 baseline 實驗版  
   `epsilon` 與 `noise_multiplier` 的關係，尚未接上正式 privacy accountant。

2. 目前模型仍以簡化線性模型為主  
   這是為了先確認 ZKML 與 FL/DP 流程可行，尚未進入更大模型。

3. 目前 client 數量為 `K=3`  
   主要目的在於先建立小規模聯邦學習 baseline，後續可再擴大測試。

---

## 五、下一步規劃

接下來若要再往下延伸，重點會是：

- 將推薦 constraint profile 實際映射到真實 ZK backend
- 實作至少一輪真正的 proof / verify
- 測量 proving time、verification time、proof size、memory

---

## 六、簡短結論

目前已完成從 ZKML baseline、FL baseline、DP baseline，到 S2 constraint profile、artifact、backend stub 與 integration demo 的 repo-level 串接。  
整體流程已從 demo 推進到真實資料、client split、多輪聚合、DP update、constraint 固定化與 S2 接受/拒絕決策示範。  
若要進一步完成研究型成果，下一步將是把目前已固定的 profile 真正接入可執行的 ZK backend。
