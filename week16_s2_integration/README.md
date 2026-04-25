# Week 16 - S2 Integration Demo

Week 16 的目標是把目前的推薦 constraint profile 套進一個簡化的 S2 端到端整合流程。

## 執行方式

```bash
python week16_s2_integration/run_s2_integration_demo.py
```

## 輸出

- `results/s2_round_decisions.csv`
- `results/summary.md`

## 重要說明

- 這是 S2 的 repo-level integration prototype
- 接受 / 拒絕決策是依據 Week 14 artifact 中的 constraint checks
- 目前仍未接上真實 proof backend，因此屬於 pre-proof integration demo
