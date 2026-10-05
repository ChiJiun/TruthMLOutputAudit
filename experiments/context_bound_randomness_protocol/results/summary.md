# context-bound randomness protocol Context-Bound Hidden-Randomness Reference 摘要

## 結果

| Case | Expected | Accepted | Failed checks |
|---|---:|---:|---|
| honest | true | true | - |
| replay | false | false | freshness_ok, replay_ok |
| round_swap | false | false | context_ok, noise_generation_ok |
| model_swap | false | false | context_ok, noise_generation_ok |
| challenge_swap | false | false | context_ok, noise_generation_ok |
| zero_noise | false | false | noise_generation_ok |
| secret_swap | false | false | secret_commitment_ok, noise_generation_ok |
| clip_bypass | false | false | clip_ok |
| noisy_tamper | false | false | relation_ok |
| challenge_reissue | false | false | one_challenge_per_commitment |

## 判定

- Cases matching expectation：10/10。
- Public statement 不含 client secret、derived seed 或 q_noise；verifier 只能看到 DP noisy update 與 commitments/context。
- Commit-before-challenge、單一 challenge、context binding、challenge consumption 與 replay cache 共同阻止 host-level replay/context swap/adaptive retry。
- Zero-noise 必須同時維持 relation，但仍因 seed-derived noise check 失敗而被拒絕。

## 嚴格邊界

- 這是 intended circuit relation 的 host-side reference evaluator，不是 actual ZK proof。
- HMAC-SHA256/SHAKE256 與 centered-binomial sampler 尚未映射到 circuit，也尚未完成 sampler-specific DP theorem/accountant。
- 因此它修復 multi-round threat matrix policy contract 的規格缺口，但尚不能宣稱已完成 finite-epsilon verifiable DP。