# 威脅模型與保證邊界

## 系統角色

- **Client／prover**：持有本地資料、原始更新、長期 randomness secret 與 commitment salt；輸出 noisy update 與 ZK proof。
- **Server／aggregator**：在收到 update commitment 後發 challenge，驗證 proof、context 與 replay state，只聚合通過者。
- **Verifier／auditor**：可與 server 為同一實體，也可為外部稽核者；只看到 public statement、proof 與聚合紀錄。
- **資料主體／聯盟成員**：其隱私與協定合規性是 DP policy 要保護的對象，不一定等同於執行 prover 的 client 軟體擁有者。

## 為什麼要驗證 client 自己加入的噪聲

若 DP 完全只是 client 自己的隱私選擇，server 確實沒有必要強迫 client 加噪。本研究採用的是較窄但不同的部署目的：server 或聯盟承諾「只接受符合共同 DP-update policy 的更新」，並需要在看不到原始更新與秘密 randomness 的情況下稽核該承諾。驗證因此保護的是資料主體、聯盟合規規則及聚合流程，而不是替一個可自由退出的 client 強迫自我保護。

這項設計仍不能阻止惡意 client 放棄自己的隱私、在合法 clipping 範圍內投毒，或用任意資料產生更新。若應用沒有共同合規需求，proof gate 的必要性必須重新論證。

## 已驗證的 relation

固定 Halo2 profile 驗證：

1. setup 時註冊的 secret commitment 與 private witness 一致；
2. update commitment 在 server challenge 前固定；
3. client、round、model、nonce、update commitment 與 challenge 被綁入 context；
4. Poseidon-derived bits 經 canonical field decomposition 形成 `k=16` centered-binomial noise；
5. clipped update 在公開 bound 內，且 `q_noisy = q_clipped + q_noise`；
6. proof 通過後，server-side replay cache／challenge state 決定是否接受。

## 對手與目前結論

| 對手／失敗模式 | 目前處理 | 尚未成立的保證 |
|---|---|---|
| 偽造 clipping 或 additive relation | Halo2／EZKL constraint 拒絕 | 不證明更新由指定 optimizer 或資料產生 |
| Public seed、zero noise、context swap | Halo2 hidden randomness 與 context binding | 完整 transcript 的 computational DP 仍依賴 PRF、ZK 與 composition 假設 |
| Replay／challenge grinding | commit-before-challenge、single-use challenge、server replay state | selective abort／dropout leakage 尚未形式化 |
| 合法範圍內 bounded poisoning | 實測 median／trimmed mean 緩解 | 300/300 惡意更新仍通過 gate；不是任意 Byzantine 防禦 |
| Server 與 client 勾結 | 未建立完整模型 | collusion threshold、分散式 randomness、malicious verifier security 待證明 |
| 惡意或自適應 server | 只以 protocol ordering 與 ZK 隱藏 witness 限制 | adaptive composition、challenge bias、timing／side channels 待證明 |

## 隱私主張

- **可主張**：固定 `d=4, k=16`、10 rounds、replacement-client、固定 participation profile 下，exact accountant 給出 `epsilon <= 28.840669` at `delta = 1e-5`。
- **條件**：Poseidon 輸出需可視為適當 PRF／pseudorandom source，secret 不洩漏，context 唯一，commit-before-challenge，且 proof system 的 soundness／zero-knowledge 假設成立。
- **不可外推**：385–1,991 維的 EZKL/scaling 實驗沒有隱藏 randomness theorem，也不繼承上述 epsilon。`epsilon = 28.84` 亦不代表實務上有強隱私。

## 兩條實驗線必須分開呈現

| 實驗線 | 強項 | 限制 |
|---|---|---|
| 固定四維 Halo2 + exact accountant | 真正隱藏 randomness、逐更新 proof、有限 profile epsilon | 合成資料、維度小、epsilon 大、形式化安全仍不完整 |
| 385–1,991 維 EZKL／FL scaling | 較高維、較多 clients/rounds、成本與 utility 壓力測試 | constraint-only；沒有同等的 hidden-randomness／有限-epsilon 保證 |

任何摘要、表格或圖說都不應把兩條線合併成「高維且具 `epsilon <= 28.84` 的完整系統」。

## Full-paper 前仍需完成

1. proof system relation 的 soundness 與 zero-knowledge reduction；
2. PRF-to-DP hybrid、有限域取樣偏差與自適應 composition；
3. selective abort、dropout、client–server collusion 與 malicious verifier；
4. local-training provenance 或明確的 robust-learning security model；
5. 高維 hidden-randomness circuit 與對應 accountant。
