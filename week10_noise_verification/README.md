# Week 10 - Noise Verification Prototype

Week 10 的目標是把 `seed -> noise -> noisy update` 的驗證邏輯做成可重跑的原型，作為後續可驗證差分隱私流程的第二個核心模組。

## 本週任務

- 以 Week 9 的 clipped update 為基礎
- 用固定 seed 生成可重現的 Gaussian-like noise
- 產生 noisy update `Δw_tilde = Δw_clipped + noise`
- 驗證 noise 是否真的由指定 seed 生成
- 驗證 noisy update 是否真的等於 clipped update 加上 noise
- 建立 honest / tampered case

## 執行方式

從專案根目錄：

```bash
python week10_noise_verification/run_noise_verification.py
```

或先進入資料夾：

```bash
cd week10_noise_verification
python run_noise_verification.py
```

## 輸出

- `results/noise_verification_cases.csv`
- `results/summary.md`

## 重要說明

- 這一週做的是 `pre-ZK verification prototype`
- 為了讓 noise 可驗證，這裡採用 `seed-based deterministic noise` 設計
- Week 7 baseline 現在也已改成同樣的 seed-based noise 方向，但目前仍不是正式 DP accountant 或正式 ZK proof
