# experimental-rigor audit 實驗嚴謹性稽核

## 結案判定

**可用於結案，但核心主張必須限定為線性模型上的 constraint-only DP-update audit 與 proof/check-gated aggregation feasibility。**

不能把結果寫成已完成 finite-epsilon verifiable DP、1,440 次 actual proof、完整 local-training correctness 或任意 poisoning defense。

## 完整性與設計控制

- CoverType large-data scaling：27/27 mode runs。
- non-IID client scaling：90/90 mode runs。
- multi-round threat matrix：48/48 trajectories、1,440/1,440 decisions。
- Primary keys 無重複，所有 baseline/comparison seed sets 完整配對。
- 程式碼確認先切 train/test，StandardScaler 只在 train fit；同一 paired condition 共用 split、partition、初始化與 shuffle。
- multi-round threat matrix 是多輪 policy simulation；actual EZKL 證據與成本由 EZKL constraint integration、multiclass VDP-ZK、ZK cost scaling 與 CoverType scaling 獨立支撐。

## 統計判讀

- 所有 accuracy 比較以 seed 為獨立分析單位，報告 paired mean difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation p 與 family-level Holm correction。
- CoverType large-data scaling 的 27 組 mode runs 只有 3 seeds，two-sided exact test 的最小可能 p=0.25；non-IID client scaling 有 5 seeds，最小可能 p=0.0625。因此這些實驗是描述性、effect-size 與可行性證據，不應使用「統計顯著」措辭。
- 分析 families：large_data_scaling, noniid_scaling, threat_utility；Holm-adjusted p<0.05 的比較數=0。
- 小樣本 t interval 與 Cohen dz 可能不穩定，應與原始 seed rows、方向一致性和工程效果共同解讀。

## 可重現性產物

- `paired_effects.csv`：全部成對 effect 與檢定。
- `completeness.json`：矩陣筆數、唯一鍵、pairing 與 proof scope 稽核。
- `environment.json`：Python、作業系統與核心套件精確版本。
- `sha256_manifest.csv`：核心 scripts 與 raw/summary CSV 的 SHA-256。

## 結案前必須遵守

1. 使用『支持／顯示／在本實驗範圍內』，不要寫『證明所有情境』或『統計顯著』。
2. Public deterministic seed 的 verifier-view epsilon 明列為 infinity；有限 epsilon 只列為 secret-noise 條件式分析。
3. multi-round threat matrix 的 1,440 decisions 明列為 policy simulation，不宣稱 1,440 actual proofs。
4. Bounded sign-flip 的 100% acceptance 與 availability/utility 損失必須保留，不能只呈現成功拒絕的攻擊。
5. Actual EZKL 只主張 constraint-only 線性 update；完整 training circuit、secret noise generation 與 production-scale federation 列為未來工作。