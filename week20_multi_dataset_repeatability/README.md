# Week 20 Multi-Dataset Repeatability

This experiment repeats the same FL/DP baseline comparison across multiple tabular binary classification datasets.

Datasets:

- Wisconsin Breast Cancer Diagnostic (`sklearn`)
- Pima Indians Diabetes (`OpenML` data id 37)
- German Credit (`OpenML` data id 31)
- Banknote Authentication (`OpenML` data id 1462)

## Run

```powershell
python week20_multi_dataset_repeatability\run_multi_dataset_repeats.py
```

## Outputs

- `results/multi_dataset_runs.csv`
- `results/multi_dataset_summary.csv`
- `results/summary.md`
- `results/config.json`
