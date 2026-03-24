"""
Week 4 - Generate baseline charts from Week 3 scale sweep results.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
WEEK3_RESULTS_CSV = ROOT_DIR / "week3_scale_sweep" / "results" / "scale_sweep_results.csv"
OUTPUT_DIR = BASE_DIR / "results"

os.chdir(BASE_DIR)


def parse_optional_float(value: str) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def load_results(csv_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(
                {
                    "scale": int(row["scale"]),
                    "quantized_accuracy": float(row["quantized_accuracy"]),
                    "proving_time_sec": parse_optional_float(row.get("proving_time_sec", "")),
                    "verify_time_sec": parse_optional_float(row.get("verify_time_sec", "")),
                    "proof_size_kb": parse_optional_float(row.get("proof_size_kb", "")),
                    "ezkl_status": row.get("ezkl_status", ""),
                }
            )
    return rows


def save_accuracy_chart(rows: list[dict[str, object]], output_path: Path) -> None:
    scales = [row["scale"] for row in rows]
    accuracies = [row["quantized_accuracy"] for row in rows]

    plt.figure(figsize=(8, 5))
    plt.plot(scales, accuracies, marker="o", linewidth=2, color="#1f77b4")

    for scale, accuracy in zip(scales, accuracies):
        plt.text(scale, accuracy + 0.0006, f"{accuracy:.4f}", ha="center", fontsize=9)

    plt.title("Week 4 Baseline: Scale vs Accuracy")
    plt.xlabel("Scale")
    plt.ylabel("Quantized Accuracy")
    plt.ylim(min(accuracies) - 0.002, max(accuracies) + 0.003)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_proving_time_chart(rows: list[dict[str, object]], output_path: Path) -> None:
    available_rows = [row for row in rows if row["proving_time_sec"] is not None]

    plt.figure(figsize=(8, 5))

    if available_rows:
        scales = [row["scale"] for row in available_rows]
        proving_times = [row["proving_time_sec"] for row in available_rows]
        plt.plot(scales, proving_times, marker="o", linewidth=2, color="#d62728")

        for scale, proving_time in zip(scales, proving_times):
            plt.text(scale, proving_time, f"{proving_time:.3f}s", ha="center", va="bottom", fontsize=9)

        plt.title("Week 4 Baseline: Scale vs Proving Time")
        plt.xlabel("Scale")
        plt.ylabel("Proving Time (sec)")
        plt.grid(True, linestyle="--", alpha=0.4)
    else:
        plt.text(
            0.5,
            0.55,
            "No proving time data available yet",
            ha="center",
            va="center",
            fontsize=16,
            transform=plt.gca().transAxes,
        )
        plt.text(
            0.5,
            0.42,
            "Run Week 3 scale sweep in an ezkl-enabled environment",
            ha="center",
            va="center",
            fontsize=11,
            transform=plt.gca().transAxes,
        )
        plt.title("Week 4 Baseline: Scale vs Proving Time")
        plt.axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_summary_markdown(rows: list[dict[str, object]], output_path: Path) -> None:
    best_accuracy_row = max(rows, key=lambda row: row["quantized_accuracy"])
    available_proving_rows = [row for row in rows if row["proving_time_sec"] is not None]

    lines = [
        "# Week 4 Baseline Chart Summary",
        "",
        f"- Best quantized accuracy: scale {best_accuracy_row['scale']} -> {best_accuracy_row['quantized_accuracy']:.6f}",
    ]

    if available_proving_rows:
        fastest_row = min(available_proving_rows, key=lambda row: row["proving_time_sec"])
        lines.append(
            f"- Fastest proving time: scale {fastest_row['scale']} -> {fastest_row['proving_time_sec']:.4f} sec"
        )
    else:
        lines.append("- Proving time: pending, because current CSV does not contain EZKL timing results")

    lines.extend(
        [
            "",
            "Generated files:",
            "- `scale_vs_accuracy.png`",
            "- `scale_vs_proving_time.png`",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not WEEK3_RESULTS_CSV.exists():
        print(f"Week 3 results not found: {WEEK3_RESULTS_CSV}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_results(WEEK3_RESULTS_CSV)

    save_accuracy_chart(rows, OUTPUT_DIR / "scale_vs_accuracy.png")
    save_proving_time_chart(rows, OUTPUT_DIR / "scale_vs_proving_time.png")
    save_summary_markdown(rows, OUTPUT_DIR / "summary.md")

    print(f"Charts saved to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
