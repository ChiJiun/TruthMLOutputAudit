# non-IID client scaling CoverType Non-IID 與 Client Scaling 摘要

## 預先固定的設計

- Training samples=100000；seeds=[42, 52, 62, 72, 82]。
- Clients=[3, 10]；partitions=['iid', 'dirichlet_0.5', 'dirichlet_0.1']。
- Rounds=3；local epochs=1；batch size=2048。
- 每個 condition/seed 共用資料、初始化與 shuffle，依序執行 FL、clipping-only、DP-update。
- 95% CI 使用 seed-level Student-t interval；這是小樣本描述性區間。
- Label TV 越大、normalized entropy 越低，代表 client label distribution 越異質。

## 結果

| K | Partition | Label TV | FL mean±CI | Clip mean±CI | DP mean±CI | Clip/FL | DP/FL | Train sec F/C/D |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | dirichlet_0.1 | 0.513 | 0.677091±0.027786 | 0.635283±0.016300 | 0.516235±0.068056 | 0.938254 | 0.762431 | 14.9/11.9/11.9 |
| 3 | dirichlet_0.5 | 0.282 | 0.679766±0.012848 | 0.645574±0.007827 | 0.576464±0.029448 | 0.949701 | 0.848033 | 14.9/11.9/11.9 |
| 3 | iid | 0.000 | 0.689464±0.002361 | 0.646100±0.008510 | 0.612738±0.012088 | 0.937105 | 0.888716 | 15.0/12.1/12.1 |
| 10 | dirichlet_0.1 | 0.635 | 0.620605±0.021727 | 0.604719±0.020370 | 0.518181±0.058654 | 0.974402 | 0.834961 | 14.7/12.0/12.0 |
| 10 | dirichlet_0.5 | 0.369 | 0.630750±0.007278 | 0.621714±0.002934 | 0.581477±0.015131 | 0.985675 | 0.921883 | 15.0/12.0/11.9 |
| 10 | iid | 0.000 | 0.607950±0.013959 | 0.607950±0.013959 | 0.584859±0.026942 | 1.000000 | 0.962019 | 14.7/11.8/11.9 |

## 假設判定

- 全部 6 個 condition 均完成：True。
- 最低 DP/FL retention 出現在 K=3、dirichlet_0.1：0.762431。
- 本實驗檢查執行可行性與 utility robustness；public seed 的 epsilon infinity 限制不變。
- 若 non-IID condition 低於 90%，應如實解讀為固定 clipping/noise profile 不具跨 partition 穩健性，而不是隱藏該結果。