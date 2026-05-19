"""
Tune DP parameters for the banknote dataset, which is sensitive to the default DP setting.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from run_multi_dataset_repeats import run_experiment


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "mode",
        "rounds",
        "clip_norm",
        "noise_multiplier",
        "fl_final_mean",
        "dp_final_mean",
        "final_accuracy_gap",
        "dp_retention_ratio",
        "dp_effect_preserved",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    best = max(rows, key=lambda row: float(row["dp_retention_ratio"]))
    lines = [
        "# Banknote DP Parameter Sweep Summary",
        "",
        "Goal:",
        "- Check whether the weak default DP result on banknote-authentication is caused by untuned DP parameters.",
        "",
        "Best setting by DP/FL retention:",
        f"- rounds: {best['rounds']}",
        f"- clip_norm: {best['clip_norm']}",
        f"- noise_multiplier: {best['noise_multiplier']}",
        f"- FL final mean: {best['fl_final_mean']:.6f}",
        f"- DP final mean: {best['dp_final_mean']:.6f}",
        f"- DP/FL retention: {best['dp_retention_ratio']:.6f}",
        f"- effective: {best['dp_effect_preserved']}",
        "",
        "Interpretation:",
        "- If lower noise or more rounds restores the retention ratio, the earlier failure is a parameter sensitivity issue rather than a hard dataset failure.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    seeds = [42, 52, 62]
    settings = [
        {"rounds": 5, "clip_norm": 1.0, "noise_multiplier": 0.08},
        {"rounds": 5, "clip_norm": 1.0, "noise_multiplier": 0.04},
        {"rounds": 5, "clip_norm": 1.0, "noise_multiplier": 0.02},
        {"rounds": 10, "clip_norm": 1.0, "noise_multiplier": 0.08},
        {"rounds": 10, "clip_norm": 1.0, "noise_multiplier": 0.04},
        {"rounds": 10, "clip_norm": 2.0, "noise_multiplier": 0.04},
    ]
    rows: list[dict[str, object]] = []

    for setting in settings:
        fl_values: list[float] = []
        dp_values: list[float] = []
        for seed in seeds:
            fl_row = run_experiment(
                dataset_name="banknote_authentication",
                mode="fl",
                seed=seed,
                rounds=int(setting["rounds"]),
                local_epochs=1,
                batch_size=64,
                lr=0.01,
                clients=3,
                clip_norm=float(setting["clip_norm"]),
                noise_multiplier=float(setting["noise_multiplier"]),
            )
            dp_row = run_experiment(
                dataset_name="banknote_authentication",
                mode="dp",
                seed=seed,
                rounds=int(setting["rounds"]),
                local_epochs=1,
                batch_size=64,
                lr=0.01,
                clients=3,
                clip_norm=float(setting["clip_norm"]),
                noise_multiplier=float(setting["noise_multiplier"]),
            )
            fl_values.append(float(fl_row["final_accuracy"]))
            dp_values.append(float(dp_row["final_accuracy"]))

        fl_mean = float(np.mean(fl_values))
        dp_mean = float(np.mean(dp_values))
        retention = dp_mean / max(1e-9, fl_mean)
        rows.append(
            {
                "dataset": "banknote_authentication",
                "mode": "dp_sweep",
                "rounds": int(setting["rounds"]),
                "clip_norm": float(setting["clip_norm"]),
                "noise_multiplier": float(setting["noise_multiplier"]),
                "fl_final_mean": round(fl_mean, 6),
                "dp_final_mean": round(dp_mean, 6),
                "final_accuracy_gap": round(fl_mean - dp_mean, 6),
                "dp_retention_ratio": round(retention, 6),
                "dp_effect_preserved": retention >= 0.9,
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "banknote_dp_sweep.csv")
    write_summary(rows, RESULTS_DIR / "banknote_dp_sweep_summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
