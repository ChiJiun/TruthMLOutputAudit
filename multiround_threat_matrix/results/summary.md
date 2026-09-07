# multi-round threat matrix 多輪 Proof-Gated Threat Matrix 摘要

## 設定

- CoverType train_size=100000、K=10、partition=dirichlet_0.1。
- Seeds=[42, 52, 62]、rounds=3、attacker fraction=0.2。
- Current gate：proof + clipping bound + additive relation。
- Strengthened gate：current gate + client/round/model context + replay protection + noise-generation policy。
- Bounded sign flip 刻意保持 clipping/noise 關係合法，用來界定未證明 local training provenance 的剩餘風險。
- 1,440 次決策為重用前期 actual-EZKL artifact/check contract 的 policy simulation；本實驗未逐更新產生 1,440 份 actual proofs。

Clean DP final accuracy mean=0.495314。

| Attack | Policy | Final mean | Clean retention | Attacker acceptance | Accepted updates |
|---|---|---:|---:|---:|---:|
| bounded_sign_flip | current_vdp_gate | 0.090566 | 0.179797 | 1.000000 | 30.0 |
| bounded_sign_flip | strengthened_vdp_gate | 0.090566 | 0.179797 | 1.000000 | 30.0 |
| bounded_sign_flip | ungated | 0.090566 | 0.179797 | 1.000000 | 30.0 |
| clip_bypass | current_vdp_gate | 0.297167 | 0.585848 | 0.000000 | 24.0 |
| clip_bypass | strengthened_vdp_gate | 0.297167 | 0.585848 | 0.000000 | 24.0 |
| clip_bypass | ungated | 0.603920 | 1.227617 | 1.000000 | 30.0 |
| relation_tamper | current_vdp_gate | 0.297167 | 0.585848 | 0.000000 | 24.0 |
| relation_tamper | strengthened_vdp_gate | 0.297167 | 0.585848 | 0.000000 | 24.0 |
| relation_tamper | ungated | 0.557886 | 1.129527 | 1.000000 | 30.0 |
| replay | current_vdp_gate | 0.483748 | 0.975868 | 1.000000 | 30.0 |
| replay | strengthened_vdp_gate | 0.360719 | 0.718373 | 0.000000 | 26.0 |
| replay | ungated | 0.483748 | 0.975868 | 1.000000 | 30.0 |
| zero_noise | current_vdp_gate | 0.589173 | 1.197807 | 1.000000 | 30.0 |
| zero_noise | strengthened_vdp_gate | 0.297167 | 0.585848 | 0.000000 | 24.0 |
| zero_noise | ungated | 0.589173 | 1.197807 | 1.000000 | 30.0 |

## 假設判定

- Relation tamper 與 clip bypass 應由 current gate 拒絕。
- Replay 與 zero-noise 會暴露 current gate 的 context/randomness 缺口，應由 strengthened gate 拒絕。
- Bounded sign flip 即使在 strengthened VDP gate 下仍可通過，因為本研究沒有證明完整 local training provenance。
- 因此，多輪 gate 架構成立於『DP-update constraint audit』範圍；若要同時阻止任意 model poisoning，必須再加入 local-training proof 或其他 robust aggregation。
- Public deterministic seed 的 epsilon infinity 限制仍未由本實驗修復。
