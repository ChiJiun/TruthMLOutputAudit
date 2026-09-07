# multiclass VDP/ZK evaluation Wine 多類別 VDP/ZK 成本摘要

目標：
- 將實際 EZKL-backed VDP 約束檢查擴展到 Adult Income 以外的資料集。
- 使用 Wine 多類別資料集，驗證完整 42 維 DP 更新向量。
- 量測誠實與篡改 DP 更新案例的證明相關成本。

設定：
- 資料集：wine
- 任務：3 類多類別分類
- client_id：0
- 向量維度：42
- 隨機種子：42
- 量化尺度 scale：10000
- 裁剪上限 clip_norm：1.0
- 雜訊倍率 noise_multiplier：0.08
- 容差 slack_ppm：4201

結果：
| 案例 | 證明驗證 | 裁剪通過 | 關係通過 | 接受 | 證明秒數 | 驗證秒數 | 證明大小 bytes |
|---|---|---|---|---|---:|---:|---:|
| honest_profile | True | True | True | True | 0.140052 | 0.044162 | 11910 |
| tampered_noisy_profile | True | True | False | False | 0.144741 | 0.052252 | 11925 |

解讀：
- 接受案例：1/2。
- 拒絕案例：1/2。
- Wine 的誠實更新同時通過 EZKL proof verification 與 VDP 關係檢查。
- 篡改 noisy update 仍可對其算術輸出產生有效 proof，但因公開關係檢查失敗而被拒絕。
- 此結果補強論文主張：實際 VDP/ZK 檢查並不限於 Adult Income 二元分類流程。