# OTH4：VDP-FL（ZKML + DP + FL）研究里程碑計畫

## 計畫目標

本計畫的核心目標是建立一個可驗證的聯邦學習原型，逐步完成以下三個系統層級：

- `S0`: FL baseline
- `S1`: FL + Differential Privacy
- `S2`: FL + Differential Privacy + Zero-Knowledge Verification

最終希望能回答三個問題：

1. 聯邦學習在目前資料與模型設定下是否能穩定收斂
2. 加入 DP 後，隱私保護與模型效能之間的權衡是什麼
3. 加入 ZK 驗證後，是否能在可接受成本下提升系統可信度

## 主要量化指標

- Accuracy
- Proving time
- Verification time
- Proof size
- Peak memory
- Round time
- Communication overhead

## 計畫甘特圖

```mermaid
gantt
  title OTH4：VDP-FL（ZKML+DP+FL）研究甘特圖
  dateFormat  YYYY-MM-DD
  axisFormat  %m/%d

  section 環境與資料
  環境建置（PyTorch/ONNX/EZKL）           :a1, 2026-02-24, 7d
  UCI資料處理＋切成K=3 clients            :a2, after a1, 7d

  section ZKML Baseline
  小MLP訓練＋ONNX匯出                      :b1, after a2, 7d
  EZKL setup（settings→compile→pk/vk）     :b2, after b1, 7d
  ZK prove/verify跑通＋量測腳本            :b3, after b2, 7d
  Quantization sweep（scale/bits）         :b4, after b3, 14d

  section FL/DP Baseline
  FL模擬器（FedAvg, K=3,R=5,E=1）          :c1, after b3, 7d
  S0實驗：Round vs Accuracy                 :c2, after c1, 7d
  DP更新器（clipping+noise）               :d1, after c2, 7d
  S1實驗：epsilon sweep（0.5/1/2）          :d2, after d1, 7d

  section VDP-FL（S2）
  ZK：clipping驗證（||Δw||^2 ≤ C^2）        :e1, after d2, 14d
  ZK：noise可驗證（seed→noise，Δw~ = Δw+noise） :e2, after e1, 14d
  S2整合測試＋成本彙整                      :e3, after e2, 7d

  section 收尾與展示
  惡意Client對比（S1 vs S2）               :f1, after e3, 7d
  圖表/報告/簡報/DEMO                       :f2, after f1, 7d
```

## 當前進度對齊

截至 2026-08-06，repo 已完成計劃書的三個核心系統層級與後續擴展：

- the foundational ZKML and FL modules：完成 EZKL、UCI Adult、量化、FedAvg 與 S0 baseline
- the DP-update verification modules：完成 DP updater、epsilon sweep、clipping 與 noise verification prototype
- the quantized-constraint through proof-gated aggregation modules：完成 canonical quantized constraints、actual EZKL proof/verify、proof-gated aggregation 與 end-to-end S2 round
- the repeatability and multiclass proof evaluations：完成多個二元／多類別資料集的重複實驗，以及 Wine/Digits 完整更新向量的 VDP/ZK 成本驗證
- ZK cost scaling：以 Iris/Wine/Digits、3 個 seeds 補上 proving/verification time、peak RSS 與 application-layer communication overhead benchmark；9/9 honest runs 通過
- Gaussian privacy accounting：完成 client-level Gaussian RDP accountant 與 45 組 privacy-utility paired runs；確認 public deterministic seed 現況為 `epsilon = infinity`，秘密 Gaussian 條件下 `noise_multiplier=0.08` 仍為 `epsilon = 3504.357`（10 rounds、replace-one、`delta=1e-5`）
- CoverType large-data scaling：新增 Forest CoverType（581,012 筆、54 特徵、7 類別）大型資料 scaling；以 10,000、100,000、464,809 筆 training split、3 seeds 比較 FL／clipping-only／DP-update 共 27 runs，並完成 385 維 CoverType update 的 honest/tampered actual EZKL 檢查
- non-IID client scaling：以 CoverType 100,000 筆 training subset 完成 K=3/10、IID/Dirichlet alpha=0.5/0.1、5 seeds 的 90-run client/partition scaling；六個條件均完成，DP/FL retention 為 0.762431–0.962019
- multi-round threat matrix：以 K=10、Dirichlet alpha=0.1、3 rounds 完成 48 條 threat trajectories 與 1,440 次 client 決策；current gate 對 relation/clip 違規接受率為 0%，但對 replay/zero-noise 為 100%，strengthened policy 可將後兩者降為 0%
- experimental-rigor audit：完成 the large-data, non-IID, and threat-matrix evaluations raw results 的完整性、唯一鍵、paired effect/CI、exact permutation、Holm correction、環境版本與 SHA-256 稽核；33 組比較均保留，並確認小 seed 數不支持「統計顯著」措辭
- context-bound randomness protocol：完成 context-bound hidden-randomness reference protocol；commit-before-challenge、單一 challenge、hidden seed derivation、exact reference sampler、freshness/replay checks 與 10/10 threat cases 均通過，但仍明列為 circuit 前規格而非 actual proof

因此，原計劃的 S0、S1、S2、聲明範圍內的惡意更新拒絕、主要成本量測、大型樣本、non-IID/client scaling 與條件式 privacy accountant 均已有可重現證據。Gaussian privacy accounting 與 multi-round threat matrix 同時界定主張邊界：public seed 不能形成正式 DP，現有 gate 也不能阻止 bounded model poisoning；仍需 secret verifiable randomness、circuit-level context binding、local-training proof 或 robust aggregation。完整假設判定見 `docs/hypothesis_evidence_matrix.md`。

## 審查意見後的範圍修正

本研究依審查意見做出五項明確修正：

1. **技術可行性由抽象預期改為量化判定。** ZK cost scaling 實測 15、42、650 維更新的 proving time、verification time、proof size、peak RSS、key size 與 application payload，並在 `docs/reviewer_feedback_response.md` 明訂綠／黃／紅工程門檻。
2. **貢獻不再宣稱新 DP/ZKP 演算法。** 本研究定位為 VDP constraint formulation、canonical quantized witness、fixed-slack policy、proof-gated aggregation contract 與可重現系統評估。
3. **資料集由少數案例擴充至 16 個，並加入大型/non-IID client scaling。** Adult Income 為主線，另有 11 個二元表格資料集、Iris/Wine/Digits 三個小型多類別資料集，以及 581,012 筆的 Forest CoverType；non-IID client scaling 進一步涵蓋 K=3/10 與 IID/Dirichlet partition，但仍誠實限制於線性模型與最多 10 clients。
4. **固定 baseline 與 evaluation protocol。** S0/S1 採相同 seed、split、client partition 與初始化進行 paired comparison；S2 加入 honest/tampered acceptance、proof cost、RSS 與 payload 指標。
5. **正式區分 DP utility prototype 與 privacy guarantee。** Gaussian privacy accounting 完成 RDP accounting，明確揭露 public deterministic seed 使 verifier 可扣除 noise；有限 epsilon 僅在 secret independent Gaussian noise 的條件下成立。

完整逐項回應與可直接使用的答辯文字見 `docs/reviewer_feedback_response.md`。

因此，下面的週計畫同時兼具兩個用途：

- 作為正式研究時程
- 作為目前 repo 的實作對照表

---

## minimal EZKL demo：環境建置（PyTorch / ONNX / EZKL）

**期間：** 2026-02-24 至 2026-03-02

**目標**

- 建立 ZKML 開發環境
- 跑通最小可行 pipeline：`PyTorch -> ONNX -> EZKL -> prove -> verify`
- 確認工具鏈版本與 API 相容性

**主要工作**

- 建立 Python / conda 環境
- 安裝 `torch`、`onnx`、`ezkl`
- 測試模型匯出為 ONNX
- 產生 settings、compile 電路、setup keys
- 完成 proof 生成與 verify

**預期產出**

- `zk_ezkl_demo/` 中可執行的 demo pipeline
- 一份成功通過的 proof
- 可重現的執行步驟

**驗收標準**

- `verify` 成功通過
- demo pipeline 可從頭執行
- 關鍵版本與 API 用法已記錄

**風險**

- EZKL API 變動
- ONNX opset 或 operator 不相容

---

## Adult Income model：UCI 資料處理＋切成 K=3 clients

**期間：** 2026-03-03 至 2026-03-09

**目標**

- 以真實資料集建立後續實驗基礎
- 完成 FL baseline 所需的 client 資料切分
- 保留與 ZKML 相容的特徵與模型設計空間

**主要工作**

- 下載 UCI Adult Income 資料
- 移除缺失值並完成類別編碼
- 進行標準化與 train/test split
- 將訓練集切為 `K=3` clients
- 輸出 `processed` 與 `clients` 兩類資料

**預期產出**

- `adult_income_model/data/processed/`
- `adult_income_model/data/clients/`
- `metadata.json` 記錄每個 client 的樣本數與 label 比例

**驗收標準**

- 資料前處理腳本可重跑
- `K=3` client split 成功輸出
- 每個 client 樣本分布合理且無空集合

**目前狀態**

- 已完成並已在 repo 實作

**風險**

- client label 分布過度失衡
- 前處理方式若後續改動，需重新生成所有輸出

---

## quantization scale sweep：小 MLP 訓練＋ONNX 匯出

**期間：** 2026-03-10 至 2026-03-16

**目標**

- 建立可在 EZKL 中處理的模型
- 驗證真實資料上的基本準確率
- 產生穩定可重用的 ONNX 模型檔

**主要工作**

- 設計 EZKL 可相容的小型模型
- 測試 MLP 與純線性模型的可行性
- 使用 `BCEWithLogitsLoss` 訓練
- 匯出 ONNX 並驗證格式

**預期產出**

- `adult_income_model.onnx`
- 測試集 accuracy baseline
- 模型架構與限制說明

**驗收標準**

- ONNX 可被正常載入
- 模型在測試集有可接受準確率
- 匯出後能銜接 EZKL pipeline

**目前狀態**

- 已完成；目前採用純線性模型作為 ZKML 相容版本

**風險**

- 含激活函數的模型可能無法被 EZKL 支援
- 模型複雜度提高會顯著增加 proving 成本

---

## baseline visualization：EZKL setup（settings → compile → pk/vk）

**期間：** 2026-03-17 至 2026-03-23

**目標**

- 完成 ONNX 到電路的轉換流程
- 產出 setup 所需檔案與 proving / verifying keys

**主要工作**

- `gen_settings`
- `calibrate_settings`
- `compile_circuit`
- `setup`
- 檢查 `settings.json`、`network.ezkl`、`pk.key`、`vk.key`

**預期產出**

- `src/settings.json`
- `src/network.ezkl`
- `results/pk.key`
- `results/vk.key`

**驗收標準**

- setup 成功完成
- 所有關鍵檔案產出完整
- pipeline 可以銜接到 prove / verify 階段

**目前狀態**

- 已完成基本版本

**風險**

- 量化參數設定不佳會影響後續 prove 或 accuracy
- SRS 管理與檔案大小可能影響可攜性

---

## FedAvg baseline：ZK prove / verify 跑通＋量測腳本

**期間：** 2026-03-24 至 2026-03-30

**目標**

- 在真實資料模型上完成 prove / verify
- 建立量測 proving time、verify time、proof size 的腳本

**主要工作**

- `gen_witness`
- `prove`
- `verify`
- 寫入量測腳本與結果紀錄格式
- 建立後續比較用的 baseline 數據

**預期產出**

- `proof.json`
- 成本量測表
- 一份可重複執行的 ZK pipeline

**驗收標準**

- verify 成功
- 至少能記錄 prove time、verify time、proof size
- 結果可寫入 CSV 或 JSON

**目前狀態**

- 基本 pipeline 已完成；完整量測腳本已部分實作

**風險**

- proving 成本可能高於預期
- 環境未裝 `ezkl` 時無法在所有機器上重跑

---

## the FL-to-DP transition modules：Quantization sweep（scale / bits）

**期間：** 2026-03-31 至 2026-04-13

**目標**

- 評估不同量化設定對模型 accuracy 與 ZK 成本的影響
- 為後續圖表與模型選型建立依據

**主要工作**

- 測試 `scale = 8 / 12 / 16`
- 若可行，再補 `bits` 或其他量化參數
- 比較 quantized accuracy
- 比較 prove / verify 成本
- 輸出 CSV

**預期產出**

- `quantization_scale_sweep/results/scale_sweep_results.csv`
- scale / bits 與 accuracy / cost 對照表

**驗收標準**

- 至少完成 3 組 scale 比較
- 每組結果有 accuracy 與成本欄位
- 結果可直接供 privacy-utility sweep 繪圖

**目前狀態**

- scale sweep 腳本已建立並可輸出 accuracy CSV
- 完整 prove / verify 成本量測待 `ezkl` 環境補跑

**風險**

- scale 調整後 accuracy 變化不明顯
- bits 參數可能受限於 EZKL 設定格式

---

## privacy-utility sweep：FL 模擬器（FedAvg, K=3, R=5, E=1）

**期間：** 2026-04-14 至 2026-04-20

**目標**

- 建立聯邦學習 baseline 訓練流程
- 使用 Adult Income model 的 client split 執行多輪聚合

**主要工作**

- 建立 `K=3` client local training
- 實作 `FedAvg`
- 設定 `R=5, E=1`
- 在每輪後評估 global model

**預期產出**

- FL simulator 腳本
- 每輪 accuracy 紀錄
- 初版 global / local training 日誌

**驗收標準**

- 可完整跑完 5 輪訓練
- 聚合後模型有可追蹤 accuracy 變化
- 結果可輸出成表格

**風險**

- 本地訓練與 global aggregation 介面設計不當
- client data 分布造成收斂不穩

---

## clipping verification：S0 實驗：Round vs Accuracy

**期間：** 2026-04-21 至 2026-04-27

**目標**

- 建立 FL baseline（S0）的基準曲線

**主要工作**

- 固定模型與資料設定
- 記錄每輪 accuracy
- 匯出繪圖用資料
- 分析是否有明顯震盪或過擬合

**預期產出**

- `Round vs Accuracy` 表格
- S0 baseline 圖

**驗收標準**

- 至少能重現一條穩定曲線
- 結果可供之後與 S1 / S2 比較

**風險**

- 只有 5 輪時曲線訊號不足
- local epoch 設定可能影響對比公平性

---

## noise-relation verification：DP 更新器（clipping + noise）

**期間：** 2026-04-28 至 2026-05-04

**目標**

- 將差分隱私更新器加入聯邦學習流程

**主要工作**

- 計算 client update `Δw`
- 實作 clipping
- 加入 Gaussian noise
- 定義 DP 相關超參數

**預期產出**

- DP updater 模組
- 可切換 S0 / S1 的實驗腳本

**驗收標準**

- clipping 與 noise 可正確套用
- pipeline 不因加入 DP 而中斷

**風險**

- noise 過大導致模型嚴重退化
- clipping threshold 難以選定

---

## quantized-constraint analysis：S1 實驗：epsilon sweep（0.5 / 1 / 2）

**期間：** 2026-05-05 至 2026-05-11

**目標**

- 量化隱私與效能的取捨

**主要工作**

- 測試 `epsilon = 0.5 / 1 / 2`
- 記錄 accuracy 與可能的訓練穩定性
- 匯出繪圖資料

**預期產出**

- `epsilon vs accuracy` 表格與圖
- S1 實驗摘要

**驗收標準**

- 至少完成 3 組 epsilon 設定
- 結果可與 S0 baseline 直接比較

**風險**

- ε 定義與實作方式需保持一致
- 實驗差異可能需要多次重跑才能看出趨勢

---

## the canonical-witness and constraint-profile modules：ZK：clipping 驗證（||Δw||^2 ≤ C^2）

**期間：** 2026-05-12 至 2026-05-25

**目標**

- 將 DP 的 clipping 條件轉成可驗證的 ZK constraint

**主要工作**

- 設計 clipping constraint
- 將 `||Δw||^2 ≤ C^2` 映射到可驗證形式
- 建立 success / fail case
- 量測 proof 生成與驗證成本

**預期產出**

- clipping verification prototype
- fail case 測試結果

**驗收標準**

- 正常更新可通過 proof
- 超出 clipping bound 的更新可觸發 fail case

**風險**

- 向量維度與電路大小使 proving 成本暴增
- constraint 設計可能需先做簡化版驗證

---

## the artifact and backend-bundle modules：ZK：noise 可驗證（seed → noise，Δw~ = Δw + noise）

**期間：** 2026-05-26 至 2026-06-08

**目標**

- 讓 DP noise 的生成與套用也能被驗證

**主要工作**

- 設計從 seed 生成 noise 的可驗證流程
- 驗證 `Δw~ = Δw + noise`
- 建立篡改 noise 的 fail case

**預期產出**

- noise verification prototype
- success / fail case 對照結果

**驗收標準**

- 正確 noise 可通過 proof
- 被修改的 noise 或 update 會驗證失敗

**風險**

- 可驗證 noise 生成可能需要額外簡化假設
- 隨機性與可重現性之間需明確定義

---

## EZKL constraint integration：S2 整合測試＋成本彙整

**期間：** 2026-06-09 至 2026-06-15

**目標**

- 完成 `S2 = FL + DP + ZK` 的整體串接
- 對照 S0 / S1 / S2 的成本與效能

**主要工作**

- 整合 FL、DP、ZK 三部分
- 記錄 accuracy、proof size、prove / verify time、memory
- 彙整對照表

**預期產出**

- S2 prototype
- S0 / S1 / S2 比較表

**驗收標準**

- S2 可至少完成一輪端到端流程
- 有可報告的成本與效能摘要

**風險**

- 系統整合點多，debug 成本高
- S2 執行時間可能需要分階段拆測

---

## 延伸收尾任務

雖然甘特圖將最後兩項列在 S2 之後，實務上建議保留緩衝時間：

### 惡意 Client 對比（S1 vs S2）

- 模擬惡意 client 上傳不合法 update
- 比較 S1 無法防擋與 S2 可驗證攔截的差異

### 圖表 / 報告 / 簡報 / Demo

- 整理所有圖表
- 完成論文或報告章節
- 準備教授報告或 demo 展示

---

## 建議交付節奏

為了讓每個里程碑都有可展示內容，建議每個研究單元至少固定產出一項：

- 一個可執行腳本
- 一份結果 CSV / JSON
- 一張圖
- 一段實驗記錄或 README 更新

這樣即使後續 ZK 與 DP 整合階段變複雜，仍能持續累積可報告成果。
