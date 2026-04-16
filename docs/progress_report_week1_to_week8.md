# VDP-FL 進度彙報（Week 1 - Week 8）

## 一、目前完成進度

目前已完成 Week 1 到 Week 8 的基礎實作，對應到三個主要階段：

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

## 三、目前累積的研究意義

目前這 8 週的進度，已經建立出以下基礎：

1. 已完成真實資料上的 ZKML baseline
2. 已完成 FL baseline（S0）
3. 已完成 DP baseline（S1）的第一版流程
4. 已建立量化參數與隱私參數的基礎比較機制

這代表後續可以開始進到：

- clipping 可驗證
- noise 可驗證
- S2（FL + DP + ZK）整合

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

接下來的重點會進入 S2，也就是：

- 驗證 clipping 條件是否可被零知識證明
- 驗證 noise 生成與加噪流程是否可被驗證
- 整合 FL + DP + ZK 的完整流程

下一個主要目標是：

- Week 9：`||Δw||^2 ≤ C^2` 的 clipping 驗證原型

---

## 六、簡短結論

目前已完成從 ZKML baseline、FL baseline，到 DP baseline 的初步整合。  
整體流程已從 demo 推進到真實資料、client split、多輪聚合、DP update 與 epsilon sweep。  
後續研究將聚焦於「可驗證差分隱私（VDP）」的核心，也就是如何讓 clipping 與 noise 流程本身能被第三方驗證。
