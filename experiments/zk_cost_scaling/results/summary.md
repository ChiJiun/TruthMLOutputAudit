# ZK cost scaling ZK 成本、記憶體與通訊 scaling 摘要

本實驗補齊計劃書原訂但先前尚未系統量測的 peak memory 與 communication overhead，
並以獨立 Python process 重跑每個 dataset/seed，避免前一次 EZKL 配置保留的記憶體干擾 RSS 比較。

## 設定

- 重跑 seeds：42, 52, 62
- 案例：honest profile（所有 run 均須通過 proof、clipping 與 additive relation）
- Peak memory：5 ms polling 的 process RSS 峰值；同時保留相對 pipeline baseline 的增量
- S1 payload：compact JSON 的 `client_id + q_noisy`
- S2 payload：S1 payload + `proof.json` + compact JSON audit policy metadata
- 通訊量不含 TCP/TLS/HTTP framing，因此是可重現的 application-layer wire-size 估計

## 結果

| Dataset | 維度 | 通過 | Prove 秒 mean±SD | Verify 秒 mean±SD | Peak RSS MiB mean±SD | S1 bytes | S2 bytes | S2 額外倍率 | Circuit rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iris | 15 | 3/3 | 0.100064±0.006598 | 0.032662±0.001165 | 410.018±0.391 | 99 | 12519 | 125.626x | 138 |
| wine | 42 | 3/3 | 0.153746±0.011348 | 0.040995±0.006190 | 412.462±0.085 | 222 | 12331 | 54.632x | 379 |
| digits | 650 | 3/3 | 0.586401±0.008719 | 0.034425±0.001359 | 425.966±0.653 | 3056 | 15198 | 3.973x | 5851 |

## 解讀

- 更新維度由 15 增至 650 時，平均 proving time 為最小模型的 5.860 倍。
- 同一範圍內，pipeline peak RSS 為最小模型的 1.039 倍，S2 application payload 為 1.214 倍。
- Proof JSON 大小介於 11961 到 12272 bytes；成本成長主要應搭配 circuit rows、proving key、RSS 與 proving time 一起解讀。
- S2 額外倍率在小更新向量上較高，因固定大小的 proof 與 metadata 佔比更大；向量變大後，原始更新 payload 的占比上升。
- 本實驗只比較三個線性多類別模型，不能據此宣稱對深度模型呈線性 scaling。