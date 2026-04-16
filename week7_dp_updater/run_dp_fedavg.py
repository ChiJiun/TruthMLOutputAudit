"""
Week 7 - DP updater baseline with clipping + Gaussian noise.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch

from dp_fedavg_core import run_dp_fedavg_experiment, write_csv


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
MODELS_DIR = BASE_DIR / "models"
os.chdir(BASE_DIR)


def write_summary(summary: dict[str, object], output_path: Path) -> None:
    lines = [
        "# Week 7 DP-FedAvg Summary",
        "",
        f"- Initial accuracy: {summary['initial_accuracy']:.6f}",
        f"- Final accuracy: {summary['final_accuracy']:.6f}",
        f"- Best accuracy: {summary['best_accuracy']:.6f}",
        f"- Mean round time: {summary['mean_round_time_sec']:.4f} sec",
        "",
        "Configuration:",
        f"- clients: {summary['clients']}",
        f"- rounds: {summary['rounds']}",
        f"- local_epochs: {summary['local_epochs']}",
        f"- clip_norm: {summary['clip_norm']}",
        f"- noise_multiplier: {summary['noise_multiplier']}",
        "",
        "Note:",
        "- This Week 7 baseline uses a simplified Gaussian-noise mapping for DP experimentation.",
        "- It is useful for trend comparison, but not yet a formal privacy accountant implementation.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 7 DP-FedAvg baseline")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 7 - DP FedAvg Baseline")
    print("=" * 60)
    print(
        f"Rounds={args.rounds}, LocalEpochs={args.local_epochs}, "
        f"ClipNorm={args.clip_norm}, NoiseMultiplier={args.noise_multiplier}"
    )

    rows, summary, global_model = run_dp_fedavg_experiment(
        rounds=args.rounds,
        local_epochs=args.local_epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(rows, RESULTS_DIR / "round_metrics_dp.csv")
    write_summary(summary, RESULTS_DIR / "summary.md")
    torch.save(global_model.state_dict(), MODELS_DIR / "dp_fedavg_global_model.pt")

    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
