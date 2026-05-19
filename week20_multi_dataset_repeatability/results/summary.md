# Week 20 Multi-Dataset Repeatability Summary

Goal:
- Repeat the same FL/DP baseline experiment on multiple similar tabular binary classification datasets.
- Check whether DP remains close to the FL baseline across datasets and random seeds.

Datasets:
- banknote_authentication: samples=1372, encoded_features=4
- breast_cancer_wisconsin: samples=569, encoded_features=30
- german_credit: samples=1000, encoded_features=61
- pima_diabetes: samples=768, encoded_features=8

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
| breast_cancer_wisconsin | 0.912281 | 0.891813 | 0.020468 | 0.977564 | True |
| german_credit | 0.711667 | 0.710000 | 0.001667 | 0.997658 | True |
| pima_diabetes | 0.731602 | 0.714286 | 0.017316 | 0.976332 | True |

Interpretation:
- DP stayed within 90% of the FL final-accuracy baseline on 3/4 datasets.
- This supports that the current DP update prototype is not only tuned to Adult Income, although performance varies by dataset.
- The next useful step is to repeat the proof-gated VDP/ZK check on selected non-Adult datasets rather than only comparing FL and DP baselines.