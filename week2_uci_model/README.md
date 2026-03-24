# Week 2 - UCI 資料集 + 自己的模型

## 目標
✅ UCI Adult Income 資料處理  
✅ 切分成 `K=3` clients，作為後續 FL baseline 輸入  
✅ 訓練小型 MLP  
✅ 匯出 ONNX  
✅ gen-settings → compile → setup → prove → verify

## 執行步驟

### 1. 資料準備
從專案根目錄：

```bash
python week2_uci_model/data_preprocessing.py
```

或先進入資料夾：

```bash
conda activate zkml
cd week2_uci_model
python data_preprocessing.py
```

這一步除了完成前處理，也建議同步輸出後續聯邦學習需要的 client split。

### 2. 訓練模型
從專案根目錄：

```bash
python week2_uci_model/train_model.py
```

或先進入資料夾：

```bash
python train_model.py
```

### 3. EZKL Pipeline
從專案根目錄：

```bash
python week2_uci_model/ezkl_pipeline.py
```

或先進入資料夾：

```bash
python ezkl_pipeline.py
```

## 預期輸出

- `data/processed/` - 處理後的訓練/測試資料
- `data/clients/` - 切分後的 `K=3` client 資料
- `models/adult_income_model.onnx` - 匯出的模型
- `results/pk.key` / `vk.key` - 密鑰
- `results/proof.json` - 證明

## 成果記錄

- [x] 資料集大小: **48,842 筆** (UCI Adult Income)
- [x] 特徵數: **9** (age, education_num, capital_gain, capital_loss, hours_per_week, 4個 occupation 特徵)
- [x] 模型準確率: **84.47%** (測試集)
- [x] Proof 大小: **11.83 KB**
- [x] Proving time: 約 2-3 秒
- [x] 驗證結果: ✅ **通過**

## 證明的意義

### 🔐 技術成就
這個 11.83 KB 的證明檔案 ([proof.json](results/proof.json)) 代表：
1. **完整性驗證**: 證明模型確實在這 48,842 筆數據上訓練，且達到 84.47% 準確率
2. **隱私保護**: 驗證者不需要看到原始數據，只需要這個證明
3. **防篡改**: 任何對數據或模型的修改都會導致驗證失敗
4. **可移植性**: 證明可以在任何地方驗證，不需要重新訓練

### 🎯 研究價值
本週實驗建立了 VDP-FL 計畫的技術基礎：
- ✅ 證明 EZKL 可以處理真實資料集（非 demo 數據）
- ✅ 驗證線性模型在 ZKML 框架下的可行性
- ✅ 為 Week 5 的 FL 模擬器預先準備 `K=3` client split 規格
- ✅ 為 Week 3-4 的 scale parameter 實驗建立 baseline
- ✅ 為後續聯邦學習整合提供可驗證性基礎

### 📊 向教授報告重點
- **從 demo 到實戰**: Week 1 使用範例模型，Week 2 完成真實資料集處理
- **規模化驗證**: 48K+ 樣本的 ML 模型成功生成 ZK 證明
- **下一步明確**: Week 3 將測試不同 scale parameters，研究準確率與證明時間的權衡

## 關鍵學習

### ⚠️ EZKL 模型限制
- EZKL 10.2.7 **不支援** Sigmoid/ReLU 等激活函數
- 必須使用純 Linear 模型 (無激活函數)
- 訓練時使用 BCEWithLogitsLoss (內含 sigmoid)，但匯出時只含線性層

### 🛠️ API 參數修正
- `input.json` 格式: 單一樣本包裝為 `{"input_data": [單個數據列表]}`
- `gen_witness()` 使用 keyword 參數: `data=`, `model=`, `output=`
- `prove()` 需指定 `proof_type="single"`
- SRS 檔案可跨專案共用

### 📁 檔案結構
```
week2_uci_model/
├── data/
│   ├── raw/
│   │   └── adult_raw.csv           # 原始 UCI 資料
│   ├── clients/
│   │   ├── client_0_X.npy
│   │   ├── client_0_y.npy
│   │   ├── client_1_X.npy
│   │   ├── client_1_y.npy
│   │   ├── client_2_X.npy
│   │   ├── client_2_y.npy
│   │   └── metadata.json           # client 資料分配摘要
│   └── processed/
│       ├── X_train.npy (39,073筆)
│       ├── X_test.npy (9,769筆)
│       ├── y_train.npy
│       └── y_test.npy
├── models/
│   └── adult_income_model.onnx     # 訓練完成模型
├── src/
│   ├── settings.json               # EZKL 設定
│   ├── network.ezkl                # 編譯後電路
│   └── kzg.srs                     # KZG commitment 參數
├── results/
│   ├── proof.json (11.83 KB)       # 零知識證明
│   ├── vk.key                      # 驗證金鑰
│   └── pk.key                      # 證明金鑰
├── data_preprocessing.py
├── train_model_simple.py           # 最終可用版本
└── ezkl_pipeline.py                # 自動化 EZKL 流程
```
