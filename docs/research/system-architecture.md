# 方法與系統架構說明

本文件用於說明海報中的「方法與系統架構圖」，內容涵蓋整體研究流程、各模組功能，以及圖中每個節點的意義。此架構對應本研究最終希望完成的 **基於 ZKML 的聯邦學習可驗證差分隱私架構**，並同時兼顧目前已完成的 ZKML baseline、FL baseline 與 DP baseline。

---

## 一、整體架構概念

本研究的整體系統由六個主要模組組成：

1. `Dataset & Preprocessing`
2. `Federated Learning Module`
3. `Differential Privacy Module`
4. `Verifiable Proof Module`
5. `Server / Aggregation Module`
6. `Evaluation`

整體流程為：

- 先將原始資料進行前處理，並切分為可供聯邦學習使用的多個 client 資料集
- 由 server 初始化 global model，並發送給各 client 進行本地訓練
- client 計算本地模型更新 `Δw`
- 對 `Δw` 執行 clipping 與加入 Gaussian noise，產生 noisy update
- 將更新流程轉換為可驗證的 ZK 電路，並生成 proof
- server 或 verifier 驗證 proof 是否通過
- 僅接受通過驗證的更新，進行 FedAvg 或 secure aggregation
- 最後量測 accuracy、proving time、verification time 與 proof size 等指標

此系統最終目標是使聯邦學習中的差分隱私流程，不再只依賴參與者自行宣稱，而能由第三方在不接觸私有資料的前提下進行驗證。

---

## 二、各模組說明

### 1. Dataset & Preprocessing

此模組負責完成原始資料的準備與切分，建立後續模型訓練與聯邦學習的基礎。

#### 節點說明

`Raw Data`
- 表示原始資料來源。
- 目前實作中使用的是 UCI Adult Income 資料集。
- 未來也可替換為 MNIST、Heart Disease 或其他資料集。

`Data Preprocessing`
- 表示資料前處理步驟。
- 包含資料清理、缺失值處理、類別特徵編碼、標準化等。
- 目的是將原始資料轉換為可直接輸入模型訓練的數值格式。

`Train/Test Split`
- 將資料分成訓練集與測試集。
- 訓練集用於模型訓練與聯邦學習，測試集用於統一評估 global model 的表現。

`Client Partition`
- 將訓練集切分為多個 client 子資料集。
- 在目前實作中，資料被切成 `K=3` 個 clients。
- 這一步對應聯邦學習中「資料分散持有」的情境。

---

### 2. Federated Learning Module

此模組負責聯邦學習的核心訓練流程，亦即 server 與 client 間的模型交換與本地訓練。

#### 節點說明

`Global Model`
- 表示由 server 維護的全域模型。
- 在目前 baseline 中，使用的是簡化的線性模型。
- 所有 client 都會從同一個 global model 開始進行本地訓練。

`Broadcast to Clients`
- 表示 server 將當前的 global model 發送給所有參與該輪訓練的 clients。
- 這是聯邦學習每一輪的起點。

`Local Training`
- 表示 client 使用自己的本地資料對模型進行訓練。
- 在此過程中，client 不需將原始資料上傳給 server。
- 這是聯邦學習保護資料不出門的核心設計。

`Compute Update Δw`
- 表示計算 client 本地模型相對於 global model 的更新量。
- 形式上可表示為：
  `Δw = w_local - w_global`
- 在本研究中，後續的 clipping、noise addition 與 aggregation 都是作用在這個 update 上，因此使用 `Δw` 比單純使用 gradient 更符合目前的系統流程。

---

### 3. Differential Privacy Module

此模組負責在聯邦學習更新量上加入差分隱私保護。

#### 節點說明

`Clip Update`
- 表示對 client update `Δw` 做 norm clipping。
- 目的是限制單一 client update 的敏感度，避免某一筆資料或某一個 client 對 global model 造成過大影響。
- 這是差分隱私訓練中的標準步驟之一。

`Add Gaussian Noise`
- 表示對 clipped update 加入 Gaussian noise。
- 加噪後的更新可降低從模型更新反推出個體資料的風險。
- 本研究目前以 baseline 方式建立此流程，未來將進一步驗證 noise 流程本身。

`Generate Noisy Update Δŵ`
- 表示產生最終用於上傳的 noisy update。
- 此 update 會被提交給 server 進行聚合。

`Set Privacy Parameters`
- 表示差分隱私機制的參數設定，例如 `epsilon`、`delta`、clip norm 或 noise scale。
- 此節點在圖中更接近「設定 / 控制條件」，不是主要計算流程中的運算步驟。
- 它影響 clipping 與 noise 的具體行為。

---

### 4. Verifiable Proof Module

此模組是本研究與一般 FL + DP 架構最關鍵的差異所在，目的是讓隱私保護流程變得可驗證。

#### 節點說明

`Encode into ZK Circuit`
- 表示將模型計算、clipping 與 noise 相關邏輯轉換為可由零知識證明系統處理的算術電路或約束表示。
- 這是從一般機器學習流程進入 ZKML / zk-proof 流程的重要步驟。

`Generate Proof`
- 表示 client 針對自己的計算流程產生 proof。
- proof 的目的不是揭露私有資料，而是向 verifier 證明：
  - 本地計算是依照協定執行的
  - 更新流程是合法的
  - 差分隱私相關步驟符合預期條件

`Encode Clipping Constraint`
- 表示將 clipping 條件形式化為可驗證的約束。
- 例如將 `||Δw|| ≤ C` 轉為 ZK 電路內可驗證的條件。
- 這是未來完整 VDP-FL 中的重要部分。

`Encode Noise Constraint`
- 表示將 noise generation 與 add-noise 流程轉為可驗證的約束。
- 這比單純驗證一般模型運算更困難，也是本研究未來的核心挑戰之一。

---

### 5. Server / Aggregation Module

此模組負責 proof 驗證、client update 篩選與聚合。

#### 節點說明

`Verify Proof`
- 表示 server 或外部 verifier 對 client 提交的 proof 進行驗證。
- 驗證通過才表示該 update 有資格被接受。

`Proof Valid?`
- 這是 decision node，用來判斷 proof 是否驗證通過。
- 若 proof 通過，update 才能進入 aggregation；若不通過，則 update 應被拒絕。

`Accept Update`
- 表示 proof 驗證通過後，該 client update 被視為合法更新。
- 合法更新才能進入下一步聚合流程。

`Reject Update`
- 表示 proof 驗證失敗時，拒絕該 update。
- 這能防止不合規更新或惡意更新參與 aggregation。

`FedAvg / Secure Aggregation`
- 表示對所有被接受的 client update 進行聚合。
- 在目前 baseline 中，使用的是 `FedAvg`。
- 未來若進一步延伸，也可結合 secure aggregation 機制。

`Update Global Model`
- 表示 server 使用聚合結果更新 global model。
- 更新後的 global model 將用於下一輪聯邦學習。

---

### 6. Evaluation

此模組負責量測模型表現與系統成本，是用來評估整體架構可行性的重要部分。

#### 節點說明

`Accuracy`
- 表示模型在測試集上的預測準確率。
- 用來觀察加入 ZKML、FL、DP 後對模型表現的影響。

`Proving Time`
- 表示生成 proof 所需的時間。
- 是衡量 ZK 機制實用性的核心指標之一。

`Verification Time`
- 表示驗證 proof 所需的時間。
- 反映 verifier / server 端的負擔。

`Proof Size / Memory`
- 表示 proof 檔案大小與系統記憶體消耗。
- 用來評估系統在實務部署中的可行性與成本。

---

## 三、目前已完成與未來工作的對應

從目前研究進度來看，各模組的完成情況如下：

### 已完成
- `Dataset & Preprocessing`
- `Federated Learning Module`
- `Differential Privacy Module` 的 baseline 版本
- `Verifiable Proof Module` 中 ZKML baseline 的 proof generation
- `Server / Aggregation Module` 中的 FedAvg baseline
- `Evaluation` 中 accuracy、proving time、verification time、proof size 等量測

### 尚待完成 / 未來工作
- clipping 條件的完整零知識驗證
- noise generation / add-noise 流程的完整零知識驗證
- proof-based update acceptance 的完整 S2 整合

也就是說，目前本研究已建立出：

- ZKML baseline
- FL baseline（S0）
- DP baseline（S1）

而最終要完成的是：

- 完整的 VDP-FL（S2）架構

---

## 四、此架構的研究意義

一般聯邦學習加上差分隱私後，server 往往只能「相信」client 有依照規範進行 clipping 與加噪，卻無法直接驗證。  
本研究所提出的架構，核心價值在於將這種「信任」轉變為「可驗證性」。

也就是說，未來在此架構下，外部不需要看到 client 的私有資料，也能驗證：

- client 是否正確完成本地訓練
- update 是否符合 clipping 條件
- noise 是否依規範生成與加入
- server 是否只聚合通過驗證的更新

因此，此系統架構不僅是一個技術流程圖，也代表本研究對未來可信聯邦學習系統的設計方向。
