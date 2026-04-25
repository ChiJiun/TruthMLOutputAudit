# Week 13 - Recommended Constraint Profile

Week 13 的目標是把 Week 12 的觀察收斂成一個更接近實際電路設計的推薦版本：

- `canonical quantized witness`
- 固定 clipping slack
- 同時檢查 clipping 與 noisy update relation

## 執行方式

從專案根目錄：

```bash
python week13_recommended_constraints/run_recommended_constraint_profile.py
```

## 輸出

- `results/recommended_constraint_cases.csv`
- `results/summary.md`

## 重要說明

- 這仍然不是正式 ZK 電路，而是 `pre-circuit constraint profile`
- 目標是把目前已知最穩定的 witness 與 slack 規則固定下來
- 如果這個 profile 能穩定接受 honest、拒絕 tampered，就代表後續可以把它當成 S2 電路設計的候選規格
