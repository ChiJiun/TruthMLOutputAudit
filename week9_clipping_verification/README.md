# Week 9 - Clipping Verification Prototype

Week 9 的目標是先把 `||Δw|| <= C` 的驗證邏輯做成可重跑的原型，替後續真正的 ZK constraint 設計做準備。

## 本週任務

- 以 Week 7 的 DP-FedAvg update 流程為基礎
- 對每個 client 的原始 update `Δw` 計算 L2 norm
- 套用 clipping，得到 `Δw_clipped`
- 驗證 `Δw_clipped` 是否滿足 norm bound
- 驗證 `Δw_clipped` 是否真的對應到正確的 clipping 規則
- 建立 success / fail case，模擬誠實與篡改更新

## 執行方式

從專案根目錄：

```bash
python week9_clipping_verification/run_clipping_verification.py
```

或先進入資料夾：

```bash
cd week9_clipping_verification
python run_clipping_verification.py
```

## 輸出

- `results/clipping_verification_cases.csv`
- `results/summary.md`

## 重要說明

- 這一週做的是 `pre-ZK verification prototype`
- 目前是用 Python 直接檢查 clipping 條件，還不是正式的 zero-knowledge proof
- 這份結果的用途是先確認之後要放進 ZK circuit 的數學條件與 fail case 定義是否清楚
