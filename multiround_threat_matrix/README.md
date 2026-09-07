# multi-round threat matrix 多輪 Proof-Gated Threat Matrix

本實驗把 the proof-gated aggregation modules 的單輪 proof-gated outcome 擴展為 3 輪、K=10、高度 non-IID CoverType 壓力測試。

這 1,440 次決策使用與前期 actual EZKL 相同的 verified-artifact/check contract 進行系統層 gate 模擬，並未為每次 client update 重新產生 1,440 份 actual EZKL proof；actual proof 可行性由 EZKL constraint integration、22、23、25 的獨立實驗支撐。

攻擊：

- `relation_tamper`：修改 noisy update，使 additive relation 失敗
- `clip_bypass`：提交超出 clipping bound 的向量
- `replay`：重播前一輪合法 artifact
- `zero_noise`：提交零 noise，但維持 additive relation
- `bounded_sign_flip`：提交 clipping bound 內、noise relation 合法的反向更新

Policies：

- `ungated`
- `current_vdp_gate`：proof + clip + relation
- `strengthened_vdp_gate`：current gate + client/round/model binding + replay protection + noise-generation policy

本實驗刻意保留 bounded sign flip：若沒有完整 local-training proof，目前 VDP update gate 無法判斷更新是否真的源於指定訓練流程。這是架構範圍，而不是漏報的測試失敗。

```powershell
python multiround_threat_matrix\run_multiround_threat_matrix.py
```

正式結果使用 seeds 42/52/62，共完成 48 條 trajectories 與 1,440 次 client 決策。Relation tamper 與 clip bypass 在 current/strengthened gate 的惡意接受率皆為 0%；replay 與 zero-noise 在 current gate 為 100%、strengthened gate 為 0%；bounded sign flip 在兩者皆為 100%。

拒絕兩個最大 non-IID clients 時，relation/clip/zero-noise strengthened trajectory 的 clean retention 為 0.585848，顯示安全拒絕同時帶來可用資料減少的 availability/utility 代價。完整結果見 `results/threat_summary.csv` 與 `results/threat_matrix.png`。

測試：

```powershell
python -m unittest multiround_threat_matrix.test_threat_matrix -v
```
