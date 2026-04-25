# Recommended Constraint Profile Spec

這份文件整理目前 VDP-FL S2 前置實驗所收斂出的推薦 constraint profile，作為後續 ZK / EZKL 映射的規格草案。

## 1. 目標

希望固定一組在目前實驗中表現穩定的條件：

- `canonical quantized witness`
- `fixed clipping slack`
- `seed-based deterministic noise`

並同時滿足：

1. honest case 可穩定通過
2. tampered clipping witness 會被拒絕
3. tampered noisy update 會被拒絕

## 2. 目前推薦設定

- `scale = 10000`
- `clip_norm = 1.0`
- `noise_multiplier = 0.08`
- `slack_ppm = 4201`

對應整數 clipping bound：

- `clip_rhs_bound_sq = (clip_norm * scale)^2 = 100000000`
- `slack_abs = round(clip_rhs_bound_sq * slack_ppm / 1_000_000) = 420100`

因此可接受的 clipping 條件為：

```text
sum(q_clipped[i]^2) <= clip_rhs_bound_sq + slack_abs
```

## 3. Witness 形式

推薦 witness 分成三組整數向量：

- `q_clipped`
- `q_noise`
- `q_noisy`

其中：

- `q_clipped = round(scale * clipped_update)`
- `q_noise = round(scale * noise)`
- `q_noisy = q_clipped + q_noise`

注意：

- 不直接要求 `q_noisy = round(scale * (clipped_update + noise))`
- 因為 Week 11 已觀察到 `q(a+b)` 與 `q(a)+q(b)` 會有固定 1 單位等級的 rounding gap
- 因此推薦用 canonical witness，直接把 `q_noisy` 定義成 `q_clipped + q_noise`

## 4. Public Inputs

目前建議固定下列 public inputs：

- `clip_rhs_bound_sq`
- `slack_abs`
- `noise_seed`
- `scale`

若未來需要，也可再加入：

- `client_id`
- `round_idx`
- `noise_multiplier`

## 5. Constraint Checks

### A. Clipping Bound

```text
clip_lhs_sum_sq = sum(q_clipped[i]^2)
clip_ok = (clip_lhs_sum_sq <= clip_rhs_bound_sq + slack_abs)
```

### B. Additive Noise Relation

```text
for all i:
    q_noisy[i] = q_clipped[i] + q_noise[i]
```

### C. Noise Determinism

目前 Week 10 / Week 14 原型已固定使用 `seed-based deterministic noise`。

後續若映射到 ZK，需要再決定以下其中一條路：

1. 在 circuit 內重建 noise 生成流程
2. 在 circuit 外先固定 `q_noise`，並只證明其與某個可驗證 PRG / seed 展開規則一致

目前 repo 已先固定 artifact 格式，但尚未實作正式 PRG 電路。

## 6. 目前實驗支持

來自 Week 12 / Week 13 的觀察：

- honest 最大 clipping excess：`4200 ppm`
- tampered 最小 clipping excess：`73300 ppm`
- 使用 `slack_ppm = 4201` 時：
  - honest `9/9` 通過
  - tampered `18/18` 被拒絕

因此目前存在明顯安全區間：

```text
4200 ppm < slack_ppm < 73300 ppm
```

`4201 ppm` 是目前最保守且可行的候選值。

## 7. Artifact 對應

Week 14 已輸出 circuit-facing JSON artifact，格式包含：

- `meta`
- `public_inputs`
- `witness`
- `checks`

參考路徑：

- `week14_constraint_artifacts/results/artifacts/scale_10000/client_0_honest_profile.json`

這些檔案可作為後續：

- EZKL witness / input 轉換
- 其他 ZK constraint system 的測試輸入
- 單元測試與 fail-case regression corpus

## 8. 尚未完成部分

這份 spec 仍不是正式電路，還差：

1. 把 `q_noise` 的 seed 展開規則正式映射到可驗證形式
2. 決定 clipping slack 在電路中是硬編碼常數還是 public input
3. 選擇實際的 circuit backend 與欄位表示方式
4. 做至少一輪端到端 S2 proof / verify 測試
