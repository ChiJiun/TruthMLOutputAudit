# Week 17 - Proof-Gated Round

Week 17 的目標是讓每個 client update 先通過 actual EZKL-backed constraint check，再由 server 聚合通過者。

## 執行方式

```bash
python week17_proof_gated_round/run_actual_proof_gated_round.py
```

## 輸出

- `results/proof_gated_round.csv`
- `results/accepted_aggregate.json`
- `results/summary.md`

## 重要說明

- 這一輪會對 3 個 client 分別跑實際的 EZKL constraint proof/check
- 預設會把其中 1 個 client 換成 tampered case
- server 只聚合驗證通過且 constraint 成立的 `q_noisy` 更新
