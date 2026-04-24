# Week 11 - Quantized Constraint Checks

Week 11 的目標是把 clipping 與 seed-based noise 的驗證條件，進一步整理成更接近 ZK circuit 的整數 constraint 形式。

## 本週任務

- 將 `Δw_clipped`、`noise`、`Δw_tilde` 量化成 fixed-point integer
- 檢查 clipping bound 是否可轉成整數平方和比較
- 檢查 `q(Δw_tilde)` 是否能由 `q(Δw_clipped) + q(noise)` 精確構成
- 比較 float-space 相加後再量化，與各自量化後再相加的差異
- 建立 tampered case，確認 quantized relation 會失敗

## 執行方式

從專案根目錄：

```bash
python week11_quantized_constraints/run_quantized_constraint_checks.py
```

或先進入資料夾：

```bash
cd week11_quantized_constraints
python run_quantized_constraint_checks.py
```

## 輸出

- `results/quantized_constraint_cases.csv`
- `results/summary.md`

## 重要說明

- 這一週不是正式 ZK proof，而是 `pre-circuit mapping prototype`
- 如果 `q(a+b) != q(a) + q(b)`，就表示未來電路必須固定 witness 建構方式，不能混用浮點與量化後的等式
- 這個實驗的重點是提早暴露 rounding 與 constraint canonicalization 的問題
