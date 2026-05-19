# Week 19 Breast Cancer Repeatability Summary

Dataset:
- Wisconsin Breast Cancer Diagnostic dataset from `sklearn.datasets.load_breast_cancer`
- binary tabular classification, 30 features, 569 samples

Configuration:
- seeds: [42, 52, 62, 72, 82]
- clients: 3
- rounds: 5
- clip_norm: 1.0
- noise_multiplier: 0.08

Results:
- FL final accuracy mean/std: 0.933333 / 0.030183
- DP final accuracy mean/std: 0.917544 / 0.045950
- FL best accuracy mean: 0.933333
- DP best accuracy mean: 0.921052

Interpretation:
- A second tabular binary dataset helps check whether the FL/DP trend observed on Adult Income is dataset-specific.
- If DP remains close to the FL baseline across multiple random seeds, that supports the stability of the current prototype beyond one dataset.