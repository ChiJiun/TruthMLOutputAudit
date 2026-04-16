"""
Week 8 - Epsilon sweep for the DP-FedAvg baseline.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from week7_dp_updater.dp_fedavg_core import run_dp_fedavg_experiment


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def epsilon_to_noise_multiplier(epsilon: float) -> float:
    """
    Simplified baseline mapping:
    smaller epsilon -> stronger noise
    larger epsilon -> weaker noise
    """
    base = 0.08
    return round(base / epsilon, 4)


def write_results(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "epsilon",
        "noise_multiplier",
        "final_accuracy",
        "best_accuracy",
        "mean_round_time_sec",
        "rounds",
        "clip_norm",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    best_row = max(rows, key=lambda row: row["best_accuracy"])
    lines = [
        "# Week 8 Epsilon Sweep Summary",
        "",
        f"- Best epsilon by accuracy: {best_row['epsilon']} -> {best_row['best_accuracy']:.6f}",
        "",
        "Note:",
        "- This sweep uses a simplified epsilon-to-noise mapping for baseline comparison.",
        "- It is useful for relative comparison, but not yet a formal DP accountant result.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    epsilons = [0.5, 1.0, 2.0]
    results: list[dict[str, object]] = []

    print("=" * 60)
    print("Week 8 - Epsilon Sweep")
    print("=" * 60)

    for epsilon in epsilons:
        noise_multiplier = epsilon_to_noise_multiplier(epsilon)
        print(f"Running epsilon={epsilon}, noise_multiplier={noise_multiplier}")

        _, summary, _ = run_dp_fedavg_experiment(
            rounds=5,
            local_epochs=1,
            batch_size=128,
            lr=0.01,
            seed=42,
            clip_norm=1.0,
            noise_multiplier=noise_multiplier,
        )

        results.append(
            {
                "epsilon": epsilon,
                "noise_multiplier": noise_multiplier,
                "final_accuracy": summary["final_accuracy"],
                "best_accuracy": summary["best_accuracy"],
                "mean_round_time_sec": summary["mean_round_time_sec"],
                "rounds": summary["rounds"],
                "clip_norm": summary["clip_norm"],
            }
        )

    write_results(results, RESULTS_DIR / "epsilon_sweep_results.csv")
    write_summary(results, RESULTS_DIR / "summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
