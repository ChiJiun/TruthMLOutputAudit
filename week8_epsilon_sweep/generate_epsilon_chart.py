"""
Week 8 - Generate epsilon vs accuracy chart.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
CSV_PATH = RESULTS_DIR / "epsilon_sweep_results.csv"
os.chdir(BASE_DIR)


def load_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(
                {
                    "epsilon": float(row["epsilon"]),
                    "final_accuracy": float(row["final_accuracy"]),
                    "best_accuracy": float(row["best_accuracy"]),
                }
            )
    return rows


def main() -> int:
    if not CSV_PATH.exists():
        print(f"Epsilon sweep results not found: {CSV_PATH}")
        return 1

    rows = load_rows(CSV_PATH)
    epsilons = [row["epsilon"] for row in rows]
    accuracies = [row["best_accuracy"] for row in rows]

    plt.figure(figsize=(8, 5))
    plt.plot(epsilons, accuracies, marker="o", linewidth=2, color="#ff7f0e")
    for epsilon, accuracy in zip(epsilons, accuracies):
        plt.text(epsilon, accuracy + 0.0025, f"{accuracy:.3f}", ha="center", fontsize=9)

    plt.title("Week 8 S1 Baseline: Epsilon vs Accuracy")
    plt.xlabel("Epsilon")
    plt.ylabel("Best Accuracy")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.subplots_adjust(left=0.14, right=0.96, top=0.90, bottom=0.14)
    plt.savefig(RESULTS_DIR / "epsilon_vs_accuracy.png", dpi=200)
    plt.close()

    print(f"Chart saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
