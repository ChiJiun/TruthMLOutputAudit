# ZK cost scaling ZK 成本、記憶體與通訊 scaling

本實驗延續 multiclass VDP/ZK evaluation 的 Iris、Wine、Digits 多類別 VDP/ZK constraint，補齊計劃書原訂的 peak memory 與 communication overhead 指標，並以多個 seed 重跑 proving/verification cost。

## 實驗設計

- 資料集與完整模型更新維度：Iris（15）、Wine（42）、Digits（650）
- 預設 seeds：`42, 52, 62`
- 每個 dataset/seed 都在獨立 Python process 執行，避免 EZKL/native allocator 保留記憶體影響下一次量測
- Peak memory 使用 5 ms polling 量測 process RSS
- S1 payload 定義為 compact JSON 的 `client_id + q_noisy`
- S2 payload 定義為 S1 payload 加上 `proof.json` 與 audit policy metadata

通訊量是 application-layer 序列化大小估計，不包含 TCP、TLS 或 HTTP framing。

## 執行方式

完整 3×3 benchmark：

```powershell
python experiments/zk_cost_scaling/run_zk_cost_scaling.py
```

快速 smoke test：

```powershell
python experiments/zk_cost_scaling/run_zk_cost_scaling.py --datasets iris --seeds 42
```

## 輸出

- `results/zk_cost_scaling_runs.csv`：每個 dataset/seed 的原始量測
- `results/zk_cost_scaling_summary.csv`：依 dataset 彙整的 mean、sample SD 與 scaling ratio
- `results/zk_cost_scaling.png`：proving time、peak RSS 與 S1/S2 payload 圖
- `results/summary.md`：實驗設定、結果與限制
- `results/config.json`：完整參數與量測定義

大型 EZKL proving artifacts 會重用已忽略的 `multiclass_vdp_zk/results/ezkl_cases/dimension_scaling/` 路徑。
