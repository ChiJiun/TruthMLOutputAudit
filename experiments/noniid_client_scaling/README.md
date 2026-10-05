# non-IID client scaling CoverType Non-IID × Client Scaling

本實驗檢查架構是否只在 `K=3`、IID client partition 下成立。

正式矩陣：

- Forest CoverType training subset：100,000 筆
- Clients：3、10
- Partitions：stratified IID、Dirichlet alpha=0.5、Dirichlet alpha=0.1
- Seeds：42、52、62、72、82
- Modes：FL、clipping-only、DP-update
- Training rounds：3（保留多輪行為，同時使 90-run 矩陣可在單機重現）
- 共 6 conditions、30 paired workers、90 mode runs

執行：

```powershell
python experiments/noniid_client_scaling/run_noniid_client_scaling.py
```

續跑：

```powershell
python experiments/noniid_client_scaling/run_noniid_client_scaling.py --resume
```

輸出包含原始 runs、condition summary、95% seed-level t interval、label heterogeneity 指標與圖表。

此實驗仍使用 public deterministic noise seed，因此 finite epsilon 限制不變；它驗證的是 client/partition robustness，不是正式 DP randomness。
