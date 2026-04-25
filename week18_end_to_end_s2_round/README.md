# Week 18 - End-to-End S2 Round

Week 18 的目標是把 proof-gated aggregation 實際套回 global model，形成一輪更完整的 S2 round outcome。

## 執行方式

```bash
python week18_end_to_end_s2_round/run_end_to_end_s2_round.py
```

## 輸出

- `results/accepted_average_q_noisy.json`
- `results/ungated_average_q_noisy.json`
- `results/summary.md`

## 重要說明

- 這一步會使用 Week 17 的 proof-gated round 結果
- `proof-gated` 版本只聚合通過 proof/check 的 client
- `ungated` 版本會把所有 selected updates 一起聚合，作為對照
