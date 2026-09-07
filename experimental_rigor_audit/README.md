# experimental-rigor audit Experimental Rigor Audit

本週不新增模型或選擇性重跑成功案例，而是稽核 the large-data, non-IID, and threat-matrix evaluations 的原始結果是否完整、配對、可重現且沒有過度統計解讀。

稽核內容：

- 完整矩陣筆數與 primary-key uniqueness
- baseline/comparison seed pairing
- paired mean difference 與 Student-t 95% CI
- paired Cohen dz
- two-sided exact sign-flip permutation test
- family-level Holm multiple-testing correction
- Python/OS/package 精確版本
- 核心 script、raw CSV 與 summary CSV 的 SHA-256
- actual EZKL 與 multi-round threat matrix policy simulation 的主張範圍

執行：

```powershell
python experimental_rigor_audit\analyze_rigor.py
python -m unittest experimental_rigor_audit.test_rigor_audit -v
```

本稽核的重點不是追求事後顯著性，而是說明 n=3/n=5 能支持哪些描述性與可行性結論，以及哪些強主張必須避免。
