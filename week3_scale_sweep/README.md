# Week 3 - Scale Sweep

Week 3 的目標是測試不同量化 scale 對模型表現與 ZK 成本的影響。

## 本週任務

- 測試 `scale = 8 / 12 / 16`
- 記錄 quantized accuracy
- 記錄 proving time / verify time / proof size
- 產出 CSV 結果表

## 檔案說明

- `run_scale_sweep.py`：執行 scale sweep
- `results/scale_sweep_results.csv`：輸出結果表
- `artifacts/`：每個 scale 的 EZKL 中間產物與 proof

## 執行方式

只先計算 accuracy：

從專案根目錄：

```bash
python week3_scale_sweep/run_scale_sweep.py --accuracy-only
```

或先進入資料夾：

```bash
cd week3_scale_sweep
python run_scale_sweep.py --accuracy-only
```

完整執行 EZKL sweep：

從專案根目錄：

```bash
python week3_scale_sweep/run_scale_sweep.py
```

或先進入資料夾：

```bash
cd week3_scale_sweep
python run_scale_sweep.py
```

## 依賴條件

- 必須先完成 Week 2，確保 `../week2_uci_model/models/adult_income_model.onnx` 與處理後資料存在
- 若要完整量測 prove/verify，環境中必須安裝 `ezkl`

## 備註

- 目前 accuracy 是根據 Week 2 的純線性 ONNX 模型做量化後推論得到
- 如果本機沒有 `ezkl`，腳本仍會輸出 accuracy CSV，但 prove/verify 欄位會標記為 skipped
