# 文件索引

這裡以用途而不是時間順序整理文件。若不同文件的文字衝突，以「威脅模型 → 主張—證據對照 → 投稿強化報告 → 個別實驗原始結果」的順序判定。

## 目前有效的入口

1. [`research/threat-model.md`](research/threat-model.md)：誰驗證、保護誰、信任什麼，以及未證明什麼。
2. [`research/claim-evidence-map.md`](research/claim-evidence-map.md)：每個可用主張對應到腳本、結果檔與限制。
3. [`publication/strengthening-report.md`](publication/strengthening-report.md)：最新整合結果與投稿邊界。
4. [`../experiments/actual_multiround_halo2/README.md`](../experiments/actual_multiround_halo2/README.md)：逐更新 actual Halo2 的重現方式。

## NSTC 結案

- [`nstc/report-draft.md`](nstc/report-draft.md)：長版既有草稿；含歷史階段文字，送件前應依主張—證據表收斂。
- [`nstc/experiment-summary.md`](nstc/experiment-summary.md)：實驗成果摘要。
- [`nstc/submission-checklist.md`](nstc/submission-checklist.md)：圖表、限制與送件檢查。

建議最終報告只保留一份正文；上述摘要與 checklist 作為寫作材料，不再各自擴寫成另一份「最終版」。

## 投稿與研究規格

- [`publication/roadmap.md`](publication/roadmap.md)：workshop／arXiv 到 full paper 的 gate。
- [`publication/manuscript-source.txt`](publication/manuscript-source.txt)：舊版 LaTeX 來源，尚未同步全部 Halo2 結果。
- [`research/system-architecture.md`](research/system-architecture.md)：架構說明。
- [`research/constraint-profile.md`](research/constraint-profile.md)：量化 constraint profile。
- [`research/hypothesis-evidence-matrix.md`](research/hypothesis-evidence-matrix.md)：研究假說判定。

## 歷史文件

`archive/` 保存研究計畫、進度報告、早期新增實驗整理與審查回應。它們用於追溯，不是目前主張的權威來源。

## 本機交付物

簡報、海報、PDF 與個人寫作筆記放在被 Git 忽略的 `docs/local/`。正式要發布的版本應在確認個資、授權與最終內容後，另行放入 release，而不是直接提交所有二進位檔。
