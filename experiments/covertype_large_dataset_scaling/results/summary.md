# CoverType large-data scaling Forest CoverType 大型資料集 scaling 摘要

## 資料與設定

- Forest CoverType：581,012 筆、54 特徵、7 類別。
- 固定 20% test split；訓練子集大小：10000, 100000, 464809。
- Seeds：[42, 52, 62]；clients=3；rounds=5；local epochs=1。
- clip_norm=1.0；noise_multiplier=0.08。
- 同一 train size/seed 的 FL、clipping-only 與 DP-update 共用 split、子集、client partition、初始化與 batch shuffle。
- Client partition 為 stratified IID，用來隔離資料量效應；不是 non-IID robustness 測試。
- Peak RSS 由獨立 worker process 以 20 ms polling 量測。

## 結果

| Train samples | FL final | Clip-only final | DP final | Clip/FL | DP/FL | FL/Clip/DP train sec | Peak RSS range |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10000 | 0.627299±0.013913 | 0.627299±0.013913 | 0.569942±0.011624 | 1.000000 | 0.908566 | 12.8/12.6/12.8 | 599.3--606.8 MiB |
| 100000 | 0.712285±0.001126 | 0.701078±0.001588 | 0.667886±0.004700 | 0.984266 | 0.937666 | 20.8/20.4/20.0 | 597.8--626.9 MiB |
| 464809 | 0.719890±0.001210 | 0.700633±0.002038 | 0.636799±0.005917 | 0.973251 | 0.884579 | 51.1/50.7/52.0 | 715.2--716.1 MiB |

## 解讀

- 訓練樣本由 10000 增至 464809 時，FL 平均訓練時間成長為 4.00 倍。
- 最大訓練分割的 FL/DP final accuracy 分別為 0.719890 / 0.636799，retention=0.884579。
- 最大分割的 clipping-only final accuracy 為 0.700633；這個 control 用來區分 clipping 與 noise 的效應。
- 最大分割的總 accuracy gap 為 0.083091：clipping-only gap=0.019257，加入 noise 後的額外 gap=0.063834。這是 control-based 差距分解，不宣稱一般性的因果比例。
- 線性 7 類模型共有 385 個參數，因此 constraint-only VDP 的完整更新向量為 385 維；樣本數本身不會直接增加該 proof 的輸入維度。
- 本結果補強樣本規模可行性，但仍不代表深度模型、大量 clients 或 non-IID federation 的可行性。
- DP-update 的有限 epsilon 限制與 Gaussian privacy accounting 相同：public deterministic seed 現況仍為 epsilon infinity。