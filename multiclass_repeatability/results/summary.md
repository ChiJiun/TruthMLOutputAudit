# multiclass repeatability 多類別資料集重複實驗摘要

目標：
- 將 FL/DP 重複實驗從二元分類擴展到非二元的多類別資料集。
- 檢查模型輸出層與損失函數改為多類別設定後，DP 更新是否仍接近 FL 基準。

設定：
- 隨機種子：[42, 52, 62]
- 客戶端數量：3
- 訓練輪數：10
- 裁剪上限 clip_norm：1.0
- 雜訊倍率 noise_multiplier：0.08

資料集：
- digits：10-class handwritten digit classification，樣本數=1797，類別數=10，特徵數=64
- iris：3-class flower classification，樣本數=150，類別數=3，特徵數=4
- wine：3-class wine cultivar classification，樣本數=178，類別數=3，特徵數=13

結果：
| 資料集 | 類別數 | FL 最終平均 | DP 最終平均 | 差距 | DP/FL 保留率 | 是否達標 |
|---|---:|---:|---:|---:|---:|---|
| digits | 10 | 0.961111 | 0.946296 | 0.014815 | 0.984586 | True |
| iris | 3 | 0.866667 | 0.866666 | 0.000000 | 1.000000 | True |
| wine | 3 | 0.972222 | 0.981481 | -0.009259 | 1.009524 | True |

解讀：
- DP 在 3/3 個多類別資料集上維持 FL 最終準確率基準的 90% 以上。
- 這是基準層級的多類別擴展：目前檢查 FL/DP 在多類別輸出上的行為，尚未對這些新資料集產生完整 EZKL 證明。
- 若未來有資料集低於門檻，下一步應針對訓練輪數、clip_norm 與 noise_multiplier 進行參數掃描。