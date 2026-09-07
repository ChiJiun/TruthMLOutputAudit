# VDP-FL 專題實驗執行、成效、問題與結論報告

日期：2026-08-06

## 報告摘要

本專題研究零知識機器學習（ZKML）、差分隱私（DP）與聯邦學習（FL）的整合，核心問題是：聯邦學習客戶端所宣稱執行的裁剪與加噪，能否轉換成可由零知識證明審計的條件，並讓驗證結果實際控制伺服器聚合。

實驗從最小 EZKL prove/verify、FedAvg 與 DP updater baseline 開始，逐步完成量化約束、actual EZKL proof、proof-gated aggregation、16 個資料集重複實驗、581,012 筆 Forest CoverType 大型資料、K=3/10 與 non-IID client partition、多輪攻擊矩陣、正式 privacy accounting、統計與可重現性稽核，以及 context-bound hidden-randomness 參考協定。

整體結果支持以下較精確的結論：**DP update 的 clipping bound、context-bound hidden randomness、Poseidon PRG、離散噪聲 sampler 與 additive relation，已可被整合為 actual Halo2 可審計條件，而且 proof/check 結果可以控制 FL aggregation。** discrete-noise accounting 已對固定 `d=4, k=16, 10 rounds` profile 建立 replacement client-level accountant，得到 `epsilon <= 28.840669` at `delta=1e-5`；實際 Poseidon 版本是在 PRF assumption 下的 computational DP。此保證不能外推到全部高維 FL experiments，proof 也仍未驗證完整 local training。

> 投稿強化的 the publication-strengthening modules 方法、結果與主張邊界，請以 `docs/publication_strengthening_report.md` 為最新依據；本文件前半保留 the preceding experiment modules 的歷程證據。

## 一、研究架構與比較基準

實驗將系統分成三個層級：

| 層級 | 內容 | 用途 |
|---|---|---|
| S0 | FedAvg，不含 clipping、noise 與 proof | 聯邦學習效能基準 |
| S1 | FedAvg 加入 clipping 與 seeded noise，不含 proof gate | 觀察 DP update 對 utility 的影響 |
| S2 | S1 update 加上 EZKL proof、clipping/relation checks，只聚合通過者 | 驗證可審計更新能否控制聚合 |

比較實驗盡可能採 paired design：相同 seed、train/test split、client partition、模型初始化及訓練 shuffle，只改變 FL、clipping-only 或 DP-update 模式。主要指標包括 accuracy、DP/FL retention、honest/tampered acceptance、proving/verification time、proof size、peak RSS、payload、privacy budget、攻擊接受率與聚合後效用。

## 二、實驗做了什麼

### 2.1 建立 ZKML、FL 與 DP 基準

the foundational ZKML and model modules 建立 PyTorch → ONNX → EZKL settings/compile/setup → prove/verify 的最小流程，並測試量化 scale。Adult Income 實驗中，`scale=8` 的 quantized accuracy 為 0.841540，proving time 約 0.1391 秒，顯示小型模型可完成 actual proof，量化參數也會同時影響模型效能與證明成本。

the federated-learning baseline modules 建立 K=3 的 FedAvg baseline。初始 accuracy 為 0.694851，第 2 輪最高為 0.845122，第 5 輪為 0.842051，平均每輪 1.0171 秒，確認聯邦學習本身可穩定收斂。

the DP baseline and privacy-utility modules 加入 clipping 與 seeded noise。S1 最終 accuracy 為 0.838776，仍接近 S0 的 0.842051；早期 epsilon sweep 用於比較趨勢，但當時尚未具備正式 accountant，後續由 Gaussian privacy accounting 重新校正其隱私意義。

### 2.2 把 DP update 轉成可驗證約束

the clipping and noise-verification modules 分別驗證 clipping 與 noise relation。兩項實驗各有 3/3 honest cases 通過、6/6 tampered cases 被拒絕，證明 DP update 可以拆成可測試的合法與非法條件。

quantized-constraint analysis 將條件轉為 fixed-point integer constraint 時發現嚴重 rounding 問題：honest clipping 只有 5/9 精確成立，honest noise relation 為 0/9 精確成立。這表示直接把浮點等式搬進 ZK circuit 會誤拒合法更新。

the canonical-witness and constraint-profile modules 因此改用 canonical quantized witness：先分別量化 `q_clipped` 與 `q_noise`，再明確定義 `q_noisy = q_clipped + q_noise`。結果為 9/9 honest relation 成立、9/9 tampered relation 被拒絕。裁剪邊界另由 slack sweep 找到 `(4200, 73300) ppm` 的可行區間，固定採用 `4201 ppm` 後，推薦 profile 達成 9/9 honest accepted 與 18/18 tampered rejected。

the artifact and EZKL integration modules 將約束匯出成固定 JSON artifact、public/private inputs 與 backend bundle，再映射為 EZKL check model。Actual proof 中，honest profile 同時通過 proof、clip 與 relation；tampered profile 雖可對其算術輸出產生有效 proof，但 relation check 失敗，因而被 gate 拒絕。

### 2.3 讓驗證結果實際控制聯邦聚合

the proof-gated aggregation modules 建立 proof-gated aggregation。三個 clients 中，兩個合法更新被接受，一個 tampered client 被拒絕。被接受的 aggregate 回寫 global model 後，下一輪 accuracy 為 0.839697；未過濾的 aggregation 為 0.836831。這個單次差距不能視為一般性優勢，但證明 proof/check 已不只是離線檢查，而能改變實際 round outcome。

### 2.4 擴展資料集與量測 ZK 成本

the repeatability evaluations 先把 utility 實驗由 Adult Income 擴展到 11 個額外二元表格資料集與 Iris、Wine、Digits；加上 CoverType large-data scaling 的 Forest CoverType，整體共涵蓋 16 個資料集。11 個新增二元資料集中，9 個在預設參數下維持 90% 以上 DP/FL retention；Banknote 與 Blood Transfusion 未達門檻，參數 sweep 後才恢復。Iris、Wine、Digits 三個多類別資料集的 retention 分別為 1.000000、1.009524、0.984586。

ZK 成本實驗對 15、42、650 維完整更新各使用 3 seeds，honest runs 為 9/9 通過：

| Dataset | 更新維度 | Prove mean | Verify mean | Peak RSS | S2 payload | Circuit rows |
|---|---:|---:|---:|---:|---:|---:|
| Iris | 15 | 0.100 s | 0.033 s | 410.0 MiB | 12,519 B | 138 |
| Wine | 42 | 0.154 s | 0.041 s | 412.5 MiB | 12,331 B | 379 |
| Digits | 650 | 0.586 s | 0.034 s | 426.0 MiB | 15,198 B | 5,851 |

維度由 15 增至 650 時，proving time 約增為 5.86 倍，proving key 約增為 28.4 倍。這顯示 constraint-only 線性模型仍可執行，但審查人所指出的 ZKML scaling 風險確實存在。

### 2.5 大型資料、client 數量與 non-IID 實驗

CoverType large-data scaling 使用 Forest CoverType，共 581,012 筆、54 特徵、7 類別，固定 20% test split，比較 10,000、100,000 與完整 464,809 筆 training split。三種資料量、3 seeds、FL/clipping-only/DP-update 共完成 27 組 paired runs。

| Training samples | FL final | Clip-only final | DP final | DP/FL retention | Train time F/C/D | Peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.627299 | 0.627299 | 0.569942 | 0.908566 | 12.8/12.6/12.8 s | 599–607 MiB |
| 100,000 | 0.712285 | 0.701078 | 0.667886 | 0.937666 | 20.8/20.4/20.0 s | 598–627 MiB |
| 464,809 | 0.719890 | 0.700633 | 0.636799 | 0.884579 | 51.1/50.7/52.0 s | 715–716 MiB |

完整資料的總 accuracy gap 為 0.083091，其中 clipping-only gap 為 0.019257，noise 帶來的額外 gap 為 0.063834。這表示大型資料可以執行，但目前固定 noise profile 在完整分割上未維持 90% retention。

CoverType 線性模型的完整 update 為 385 維。Actual EZKL honest case 的 prove/verify 為 0.306/0.040 秒、proof 12,293 bytes、peak RSS 約 430 MiB；tampered update 被 relation gate 拒絕。這支持「大型資料所產生的完整線性 update 可接入 S2」，但 proof 並未包含 464,809 筆 local training trace。

non-IID client scaling 進一步使用 100,000 筆 training subset、5 seeds，比較 K=3/10 與 IID、Dirichlet alpha=0.5/0.1，共完成 90 mode runs。六個條件的 DP/FL retention 介於 0.762431 至 0.962019；最低值出現在 K=3、alpha=0.1。架構在 non-IID partition 下仍可執行，但固定 clipping/noise 參數並不具跨 partition 的 utility 穩健性。

### 2.6 Privacy accounting、威脅矩陣與協定補強

Gaussian privacy accounting 補上 client-level Gaussian RDP accountant，並發現現行 deterministic noise seed 被列為 public input。Verifier 可重建 `q_noise` 並從 `q_noisy` 還原 `q_clipped`，所以 verifier view 的 privacy budget 應記為 `epsilon = infinity`。

即使假設改成 verifier 不知道的獨立 Gaussian noise，現行 `noise_multiplier=0.08` 在 10 rounds、replace-one、`delta=1e-5` 下的條件式 epsilon 仍為 3504.357。當目標 epsilon 收緊至 128、32、8 時，所需 noise 使 Iris、Wine、Digits 的 retention 全部明顯下降；因此高 utility 與有意義 privacy budget 之間存在實質衝突。

multi-round threat matrix 在 CoverType、K=10、Dirichlet alpha=0.1、3 rounds、20% attackers 下，完成 48 條 trajectories 與 1,440 次 policy decisions：

| 攻擊 | Current gate 惡意接受率 | Strengthened gate 接受率 | 解讀 |
|---|---:|---:|---|
| Relation tamper | 0% | 0% | 現有 relation check 有效 |
| Clip bypass | 0% | 0% | 現有 clipping check 有效 |
| Replay | 100% | 0% | 必須加入 client/round/model binding 與 replay protection |
| Zero noise | 100% | 0% | 必須驗證 noise generation policy |
| Bounded sign flip | 100% | 100% | Update-level gate 無法證明更新來自正確 local training |

這 1,440 次是重用 actual-EZKL contract 的 policy simulation，不是 1,440 份 actual proofs。拒絕惡意 clients 也會減少可聚合資料，部分 strengthened trajectories 的 clean retention 僅 0.585848，顯示安全與 availability/utility 之間存在代價。

context-bound randomness protocol 把 replay、context swap、zero-noise 與 adaptive retry 的修正整理為可執行參考協定：client 先承諾 update，再取得單次 server challenge；hidden seed 綁定 client、round、model、nonce、update commitment 與 challenge；失敗嘗試仍消耗 challenge。Honest、replay、round/model/challenge swap、zero-noise、secret swap、clip bypass、noisy tamper 與 challenge reissue 共 10/10 cases 符合預期。此結果是 host-side reference semantics，尚不是 actual ZK circuit。

## 三、實驗帶來的主要效果

1. **確認核心架構可以實際執行。** 從 FL 訓練、DP update、artifact、actual proof、驗證決策到 aggregation outcome 已形成完整原型鏈。
2. **解決量化後 honest update 被誤拒的問題。** Canonical witness 與 4201 ppm fixed slack 讓 honest/tampered cases 在目前測試集上穩定分離。
3. **證明 gate 對聲明範圍內的篡改有效。** Relation tamper 與 clip bypass 在多輪 current gate 下的惡意接受率皆為 0%。
4. **補足資料與規模證據。** 實驗涵蓋 16 個資料集、581,012 筆大型資料、最多 10 clients、IID 與兩種 Dirichlet non-IID partition。
5. **把 ZKML 成本轉成可量化結果。** Proving time、verification time、proof size、circuit rows、proving key、RSS 與 payload 均有實測資料，不再只使用「成本可接受」的抽象描述。
6. **找出不能成立的過度主張。** Public seed 沒有有限 epsilon，bounded sign flip 不能被目前 gate 阻擋，深度模型與完整 local-training circuit 也尚未驗證。
7. **提高結果的可重現性。** experimental-rigor audit 確認 27/27、90/90、48/48 與 1,440/1,440 核心矩陣完整、主鍵無重複，並保留環境版本及 SHA-256 manifest；最新 the privacy, threat, rigor, and randomness modules regression tests 亦為 31/31 通過。

## 四、過程中遇到的問題、處理方式與剩餘限制

| 問題 | 實驗證據 | 已採取的處理 | 尚未解決的部分 |
|---|---|---|---|
| 浮點條件無法直接轉成整數電路 | quantized-constraint analysis honest relation 0/9 精確成立 | Canonical quantized witness 與 fixed slack | 需在更多模型／尺度下驗證 slack 是否仍合適 |
| ZKML 成本隨維度快速成長 | 15→650 維時 proving time 5.86 倍、key 約 28.4 倍 | 量測 rows、RSS、key、payload 並限制主張範圍 | 深度模型與完整 training circuit 成本仍未知 |
| Public seed 與正式 DP 衝突 | Verifier 可扣除 noise，epsilon 為 infinity | 完成 privacy audit，提出 hidden seed 與 commit-before-challenge contract | Secret PRG/sampler 尚未進入 actual circuit，沒有 sampler-specific DP theorem |
| 小資料／K=3/IID 證據不足 | 原計畫資料與 clients 規模有限 | 加入 CoverType、K=10、Dirichlet non-IID 與 90 runs | 尚非 production-scale federation，最多 10 clients |
| Non-IID utility 明顯下降 | Retention 最低 0.762431 | 如實保留負面結果並加入 clipping-only control | 需自適應 clipping/noise 或更穩健的 FL 方法 |
| Replay 與 zero-noise 可通過原 gate | Current gate 接受率皆為 100% | Strengthened policy 與 context-bound randomness protocol context-bound protocol | 尚未 circuit 化或完成密碼學安全證明 |
| 合法界限內的 poisoning 可通過 | Bounded sign flip 接受率 100%，retention 0.179797 | 明確限制 update-audit 的安全主張 | 需 local-training provenance proof 或 robust aggregation |
| 拒絕攻擊者也損害可用性 | 部分 strengthened trajectory retention 0.585848 | 同時報告 acceptance 與 utility | 仍需設計容錯、client availability 與安全間的權衡 |
| 統計檢定力不足 | n=3 的最小 exact p=0.25，n=5 為 0.0625；Holm 顯著比較為 0 | 報告 paired effect、CI、exact test 與 Holm correction | 若要做母體推論或正式論文，需增加 seeds／獨立重跑 |
| EZKL 工具鏈與量化風險 | CoverType calibration 出現大型 lookup input 警告 | 保存警告並驗證 honest/tampered 皆能完成 compile/prove/verify | 需不同 backend、參數與硬體的穩定性測試 |

## 五、證據強度與可使用的主張

experimental-rigor audit 共分析 33 組 paired accuracy effects，執行 Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation test 與 family-level Holm correction。所有 Holm-adjusted p 均未低於 0.05，主要原因是只有 3–5 seeds。因此，本研究可以使用「支持」、「顯示」、「在本實驗範圍內可行」等工程與範圍性表述，但不應使用「統計顯著」、「證明所有聯邦學習情境」或「完成正式可驗證 DP」等措辭。

可合理主張：

> 聯邦學習中的 clipping bound 與 additive noise relation，可以透過 canonical quantized witness 與 fixed-slack policy 轉換成 ZKML 可審計條件；actual EZKL proof/check 能拒絕聲明範圍內的非法更新，且驗證結果能控制 aggregation。此架構已在多個線性分類資料集、大型 CoverType、K=10 non-IID 與多輪 policy simulation 中取得可重現的可行性證據。

不可主張：

> 系統已具有有限 epsilon 的正式可驗證差分隱私、已證明完整 local training 正確、能阻止所有 poisoning、可直接擴展至深度模型或 production-scale federation。

## 六、最終結論

本專題已完成一條可用於結案的完整實驗鏈，而且不再只是把既有 DP 與 ZK 工具簡單串接。研究實際處理了浮點到整數約束的 rounding 問題，提出並驗證 canonical quantized witness 與 fixed-slack policy，讓 proof/check 能控制聯邦聚合；同時以跨資料、大型資料、non-IID、多輪攻擊、成本量測及可重現性稽核補強架構可行性的證據。

最重要的正面結果是：**constraint-only DP-update audit 與 proof-gated aggregation 架構在本研究範圍內成立。** 最重要的負面結果是：**auditability 不等於 formal DP，也不等於完整 poisoning defense。** Public deterministic seed 使現行 verifier-view epsilon 為 infinity；即使驗證 clipping 與 additive relation，合法界限內的惡意更新仍可能通過。

the publication-strengthening modules 已完成上述五項強化：actual Halo2 randomness/sampler circuit、exact finite-epsilon accountant、10-seed/CI/backend reproducibility、1,991 維與 K=50/R=20 scaling，以及 10-seed robust aggregation。最重要的新證據包括 10/10 Halo2 proofs、9/9 高維 EZKL proofs、40 條 scaling trajectories、60 條 poisoning trajectories與 3,000 次 gate decisions。

因此，本研究足以用「具 context-bound verifiable randomness 與有限-profile client-level accountant 的 ZKML 聯邦學習 DP-update 審計原型」完成結案，也比前版更接近 systems/security 投稿。仍不可宣稱 full production VDP-FL：四維 epsilon 不適用於高維模型，1,000-proof workload 尚為外推，robust aggregation只緩解特定 20% bounded attack，且 local optimizer/provenance 仍未進 circuit。完整最新結論見 `docs/publication_strengthening_report.md`。
