# CoverType large-data scaling CoverType actual EZKL VDP 摘要

- 資料集：Forest CoverType，581,012 筆、54 特徵、7 類別。
- Seed=42；clients=3；client_id=0。
- 完整線性模型更新向量：385 維。
- scale=10000；clip_norm=1.0；noise_multiplier=0.08；slack_ppm=4201。

| Case | Proof verified | Clip OK | Relation OK | Accepted | Prove sec | Verify sec | Proof bytes | Peak RSS MiB |
|---|---|---|---|---|---:|---:|---:|---:|
| honest_profile | True | True | True | True | 0.305527 | 0.039568 | 12293 | 430.2 |
| tampered_noisy_profile | True | True | False | False | 0.364999 | 0.045118 | 12263 | 434.0 |

解讀：
- Honest update 必須同時通過 proof、clipping 與 additive relation。
- Tampered update 對 q_noisy 偏移 1 個量化單位；其 proof 可驗證算術輸出，但 relation policy 失敗，因此 aggregation gate 拒絕。
- 這證明 S2 constraint/check 可套用至由完整大型資料集產生的 385 維 client update。
- Proof 電路仍只驗證 update constraint，不會因訓練樣本數增加而包含整個 local training trace。
- EZKL calibration 曾輸出大型 lookup input 警告；兩個案例仍完成 compile/prove/verify，但此警告應列為量化與工具鏈風險。
- Public noise seed 的 epsilon infinity 限制不變。
