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
- 因為 quantized-constraint analysis 已觀察到 `q(a+b)` 與 `q(a)+q(b)` 會有固定 1 單位等級的 rounding gap
- 因此推薦用 canonical witness，直接把 `q_noisy` 定義成 `q_clipped + q_noise`

## 4. Public Inputs

目前建議固定下列 public inputs：

- `clip_rhs_bound_sq`
- `slack_abs`
- `scale`
- `noise_commitment` 或不可反推出 secret seed 的 public randomness reference（尚未實作）

Gaussian privacy accounting privacy accounting 已證明 `noise_seed` 不應公開：若 verifier 同時取得 deterministic seed 與 `q_noisy`，便可重建 `q_noise` 並還原 `q_clipped`，此時 privacy budget 為 `epsilon = infinity`。因此 `noise_seed` 必須改為 private witness，且 circuit 必須驗證其 commitment 與 noise generation。

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

目前 noise-relation verification / constraint-artifact export 原型使用 `seed-based deterministic noise`，但 seed 是 public input；這只支援可重現測試，不構成正式 DP。

正式版本至少需要同時完成：

1. seed 對 verifier 保密，並以 commitment 或 VRF/commit-reveal reference 綁定
2. 在 circuit 內驗證 `secret seed -> PRG -> Gaussian/discrete-Gaussian q_noise`
3. 防止 client 在看到 update 後任意挑選有利 seed

目前 repo 已固定 additive relation artifact 與 actual EZKL proof，但尚未實作 secret PRG/distribution 電路。

## 6. 目前實驗支持

來自 canonical-witness analysis / constraint-profile selection 的觀察：

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

constraint-artifact export 已輸出 circuit-facing JSON artifact，格式包含：

- `meta`
- `public_inputs`
- `witness`
- `checks`

參考路徑：

- `experiments/constraint_artifacts/results/artifacts/scale_10000/client_0_honest_profile.json`

這些檔案可作為後續：

- EZKL witness / input 轉換
- 其他 ZK constraint system 的測試輸入
- 單元測試與 fail-case regression corpus

## 8. 尚未完成部分

這份 spec 的 additive relation 與 proof-gated aggregation 已完成；要升級成具有 finite privacy budget 的正式 VDP，還差：

1. 將 `noise_seed` 從 public input 改成 private witness，並加入不可洩漏 seed 的 public commitment
2. 把 PRG 與 Gaussian/discrete-Gaussian sampling 正式映射到 circuit
3. 定義不可被 client 操控的 randomness protocol，例如 VRF、commit-reveal 或 distributed noise
4. 將 verified noise mechanism 的參數直接連接 Gaussian privacy accounting RDP accountant

## 9. context-bound randomness protocol Context-Bound Randomness Contract

context-bound randomness protocol 已將上述第 1 與第 3 項轉成可執行 reference semantics：

- Client randomness commitment 必須在 rounds 前註冊且不可替換。
- Client 先提交 `q_clipped` commitment，server 才發出唯一 challenge。
- Hidden seed 綁定 client、round、model hash、nonce、update commitment 與 server challenge。
- Failed proof attempt 同樣消耗 challenge，避免 adaptive retry/grinding。
- Public statement 不包含 client secret、derived seed 或 `q_noise`。
- Replay、round/model/challenge swap、zero-noise、secret swap、clip bypass、noisy tamper 與 challenge reissue 均被 reference evaluator 拒絕。

目前 HMAC-SHA256、SHAKE256 與 centered-binomial sampler 僅定義 host reference behavior。下一階段仍須選擇 circuit-friendly primitives、產生 actual proof，並對 exact integer sampler 建立正式 DP theorem/accountant。
