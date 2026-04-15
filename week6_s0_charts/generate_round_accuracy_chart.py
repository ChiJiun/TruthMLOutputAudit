"""
Week 6 - Generate Round vs Accuracy chart for the S0 FedAvg baseline.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
WEEK5_CSV = ROOT_DIR / "week5_fedavg_simulator" / "results" / "round_metrics.csv"
OUTPUT_DIR = BASE_DIR / "results"

os.chdir(BASE_DIR)


def load_rows(csv_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(
                {
                    "round": int(row["round"]),
                    "test_accuracy": float(row["test_accuracy"]),
                    "round_time_sec": float(row["round_time_sec"]),
                }
            )
    return rows


def save_accuracy_chart(rows: list[dict[str, float]], output_path: Path) -> None:
    rounds = [row["round"] for row in rows]
    accuracies = [row["test_accuracy"] for row in rows]

    plt.figure(figsize=(8, 5))
    plt.plot(rounds, accuracies, marker="o", linewidth=2, color="#2ca02c")

    for round_idx, accuracy in zip(rounds, accuracies):
        plt.text(round_idx, accuracy + 0.004, f"{accuracy:.3f}", ha="center", fontsize=9)

    plt.title("Week 6 S0 Baseline: Round vs Accuracy")
    plt.xlabel("Round")
    plt.ylabel("Test Accuracy")
    plt.xticks(rounds)
    plt.ylim(min(accuracies) - 0.02, max(accuracies) + 0.03)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_summary(rows: list[dict[str, float]], output_path: Path) -> None:
    final_row = rows[-1]
    best_row = max(rows, key=lambda row: row["test_accuracy"])
    mean_round_time = sum(row["round_time_sec"] for row in rows[1:]) / max(1, len(rows) - 1)

    lines = [
        "# Week 6 S0 Summary",
        "",
        f"- Initial accuracy: round 0 -> {rows[0]['test_accuracy']:.6f}",
        f"- Final accuracy: round {final_row['round']} -> {final_row['test_accuracy']:.6f}",
        f"- Best accuracy: round {best_row['round']} -> {best_row['test_accuracy']:.6f}",
        f"- Mean round time: {mean_round_time:.4f} sec",
        "",
        "Generated files:",
        "- `round_vs_accuracy.png`",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not WEEK5_CSV.exists():
        print(f"Week 5 results not found: {WEEK5_CSV}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows(WEEK5_CSV)
    save_accuracy_chart(rows, OUTPUT_DIR / "round_vs_accuracy.png")
    save_summary(rows, OUTPUT_DIR / "summary.md")

    print(f"Charts saved to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
