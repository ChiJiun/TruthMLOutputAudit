# Week 1 Demo

這個資料夾保存 Week 1 的 EZKL demo 流程與對應產物。

## 主要檔案

- `1_train_and_export.py`：建立簡單模型並匯出 ONNX
- `2_compile_and_setup.py`：產生 settings、compile 電路、setup
- `3_prove.py`：生成 witness 與 proof
- `4_verify.py`：驗證 proof
- `ezkl_pipeline.py`：串接完整流程
- `common.py`：共用路徑常數

## 執行方式

從專案根目錄：

```bash
python week1_demo/ezkl_pipeline.py
```

或先進入資料夾：

```bash
cd week1_demo
python ezkl_pipeline.py
```

## 產物

此資料夾中的 `demo_model.onnx`、`settings.json`、`network.ezkl`、`proof.json`、`pk.key`、`vk.key`、`witness.json` 等檔案皆屬於 Week 1 demo 產物。
