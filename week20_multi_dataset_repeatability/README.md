# Week 20 Multi-Dataset Repeatability

This experiment repeats the same FL/DP baseline comparison across multiple tabular binary classification datasets.

Datasets:

- Wisconsin Breast Cancer Diagnostic (`sklearn`)
- Pima Indians Diabetes (`OpenML` data id 37)
- German Credit (`OpenML` data id 31)
- Banknote Authentication (`OpenML` data id 1462)
- Spambase (`OpenML` data id 44)
- Tic-Tac-Toe (`OpenML` data id 50)
- Titanic (`OpenML` data id 40945)
- ILPD (`OpenML` data id 1480)
- PC4 (`OpenML` data id 1049)
- Blood Transfusion Service Center (`OpenML` data id 1464)
- KC2 (`OpenML` data id 1063)

## Run

```powershell
python week20_multi_dataset_repeatability\run_multi_dataset_repeats.py
```

Run the banknote-specific DP parameter sweep:

```powershell
python week20_multi_dataset_repeatability\run_banknote_dp_sweep.py
```

## Outputs

- `results/multi_dataset_runs.csv`
- `results/multi_dataset_summary.csv`
- `results/summary.md`
- `results/config.json`
- `results/banknote_dp_sweep.csv`
- `results/banknote_dp_sweep_summary.md`
