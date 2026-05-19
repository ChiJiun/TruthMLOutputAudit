# Week 20 Multi-Dataset Repeatability Summary

Goal:
- Repeat the same FL/DP baseline experiment on multiple similar tabular binary classification datasets.
- Check whether DP remains close to the FL baseline across datasets and random seeds.

Datasets:
- banknote_authentication: samples=1372, encoded_features=4
- blood_transfusion: samples=748, encoded_features=4
- breast_cancer_wisconsin: samples=569, encoded_features=30
- german_credit: samples=1000, encoded_features=61
- ilpd: samples=583, encoded_features=11
- kc2: samples=522, encoded_features=21
- pc4: samples=1458, encoded_features=37
- pima_diabetes: samples=768, encoded_features=8
- spambase: samples=4601, encoded_features=57
- tic_tac_toe: samples=958, encoded_features=27
- titanic: samples=1309, encoded_features=2357

Configuration:
- seeds: [42, 52, 62]
- clients: 3
- rounds: 5
- clip_norm: 1.0
- noise_multiplier: 0.08

Results:
| Dataset | FL final mean | DP final mean | Gap | DP/FL retention | Effective? |
|---|---:|---:|---:|---:|---|
| banknote_authentication | 0.573333 | 0.467879 | 0.105455 | 0.816067 | False |
| blood_transfusion | 0.615556 | 0.535555 | 0.080000 | 0.870036 | False |
| breast_cancer_wisconsin | 0.912281 | 0.891813 | 0.020468 | 0.977564 | True |
| german_credit | 0.711667 | 0.710000 | 0.001667 | 0.997658 | True |
| ilpd | 0.609687 | 0.601140 | 0.008547 | 0.985981 | True |
| kc2 | 0.793651 | 0.784127 | 0.009524 | 0.988000 | True |
| pc4 | 0.820776 | 0.794521 | 0.026256 | 0.968011 | True |
| pima_diabetes | 0.731602 | 0.714286 | 0.017316 | 0.976332 | True |
| spambase | 0.913138 | 0.907347 | 0.005791 | 0.993658 | True |
| tic_tac_toe | 0.656250 | 0.645833 | 0.010417 | 0.984126 | True |
| titanic | 0.821883 | 0.790076 | 0.031807 | 0.961300 | True |

Interpretation:
- DP stayed within 90% of the FL final-accuracy baseline on 9/11 datasets.
- This supports that the current DP update prototype is not only tuned to Adult Income, although performance varies by dataset.
- The next useful step is to repeat the proof-gated VDP/ZK check on selected non-Adult datasets rather than only comparing FL and DP baselines.