# Gaussian privacy accounting 正式 privacy accounting 與 utility frontier

## 核心結論

1. **目前 public deterministic seed 原型不具可宣稱的 Gaussian DP 保證。** noise seed 是 public input，verifier 可重建並扣除 noise，因此從 verifier/server view 應記為 epsilon = infinity。
2. 下列有限 epsilon 僅是條件式反事實：noise 必須由 verifier 不知道的秘密、獨立 Gaussian randomness 產生。
3. 目前 clipping 是整個 client update 的 L2 clipping，因此 accountant 是 client-level，而不是 record-level DP-SGD accountant。

## Accounting 假設

- delta：1e-05
- rounds / sequential releases：10
- client participation：q=1，沒有 subsampling amplification
- replace-one sensitivity：2C；raw noise standard deviation：noise_multiplier * C
- 轉換：Gaussian RDP 的 classic conservative (epsilon, delta) conversion
- 現行 noise_multiplier=0.08 在秘密 Gaussian 假設下仍只有 epsilon=3504.357；public-seed 現況則為 infinity。

## Privacy-utility 結果

| Dataset | Profile | Noise multiplier | 條件式 replace-one epsilon | FL final | DP final | Retention |
|---|---|---:|---:|---:|---:|---:|
| digits | current_utility_setting | 0.080000 | 3504.357 | 0.961111 | 0.946296 | 0.984586 |
| digits | conditional_target_eps_128 | 0.531228 | 128.000 | 0.961111 | 0.515741 | 0.536609 |
| digits | conditional_target_eps_32 | 1.396075 | 32.000 | 0.961111 | 0.242593 | 0.252409 |
| digits | conditional_target_eps_8 | 4.366154 | 8.000 | 0.961111 | 0.164815 | 0.171483 |
| iris | current_utility_setting | 0.080000 | 3504.357 | 0.866667 | 0.866666 | 1.000000 |
| iris | conditional_target_eps_128 | 0.531228 | 128.000 | 0.866667 | 0.677778 | 0.782051 |
| iris | conditional_target_eps_32 | 1.396075 | 32.000 | 0.866667 | 0.433333 | 0.500000 |
| iris | conditional_target_eps_8 | 4.366154 | 8.000 | 0.866667 | 0.333333 | 0.384615 |
| wine | current_utility_setting | 0.080000 | 3504.357 | 0.972222 | 0.981481 | 1.009524 |
| wine | conditional_target_eps_128 | 0.531228 | 128.000 | 0.972222 | 0.851852 | 0.876190 |
| wine | conditional_target_eps_32 | 1.396075 | 32.000 | 0.972222 | 0.592593 | 0.609524 |
| wine | conditional_target_eps_8 | 4.366154 | 8.000 | 0.972222 | 0.444444 | 0.457143 |

## 結案報告應採用的主張

- 已完成：FL、DP-update prototype、quantized VDP constraints、actual EZKL proof、tampered rejection、proof-gated aggregation 與成本 benchmark。
- 條件式完成：若使用秘密且獨立的 Gaussian noise，可用本實驗 RDP accountant 報告 client-level epsilon。
- 尚未完成：目前 public-seed artifact 的正式 DP；seed-to-noise PRG/distribution 尚未在電路內驗證。
- 正確定位：本研究是『可審計 DP 更新的 ZKML 原型』，不是已完成嚴格 DP 保證的大規模部署系統。

## 後續密碼學修正方向

需要讓 seed 對 verifier 保密，並在電路內驗證 secret seed -> PRG -> Gaussian/discrete-Gaussian noise；可再搭配 public commitment、VRF/commit-reveal randomness 或 distributed noise generation。只把 seed 從 JSON 移除但不驗證 noise generation，仍不足以形成 verifiable DP。