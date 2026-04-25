# Week 12 - Canonical Witness Experiment

Week 12 的目標是測試：如果未來 ZK 電路不直接驗證 `q(a+b)`，而是固定用 `q(a)` 與 `q(noise)` 先量化、再組出 `q_noisy = q(a) + q(noise)` 的 canonical witness，是否能讓 noise relation 穩定成立。

## 本週任務

- 延續 Week 11 的 fixed-point / integer 檢查
- 將 `q_noisy` 改成用 `q_clipped + q_noise` 建構
- 觀察 honest case 是否可得到精確的整數 relation
- 量測 clipping bound 還需要多少 slack
- 建立 tampered canonical witness case

## 執行方式

從專案根目錄：

```bash
python week12_canonical_witness/run_canonical_witness_experiment.py
```

## 輸出

- `results/canonical_witness_cases.csv`
- `results/summary.md`
- `results/slack_policy_sweep.csv`
- `results/slack_policy_summary.md`

## 重要說明

- 這仍然是 `pre-circuit design experiment`
- 重點不是直接宣稱已完成 ZK 電路，而是先確認哪種 witness 形式最穩定
- 如果這個 canonical 版本成立，就代表未來 constraint 設計應優先驗證整數 witness 的一致性，而不是回頭混用浮點空間
- 另外也會搭配 `slack policy sweep`，觀察 clipping bound 需要多大的容忍範圍才適合實際電路
