"""Gaussian privacy accounting - Client-level RDP accounting and privacy-utility frontier."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from multiclass_repeatability.run_multiclass_dataset_repeats import (
    DATASETS,
    run_experiment,
)
from gaussian_privacy_accounting.privacy_accountant import (
    effective_noise_multiplier,
    gaussian_rdp_epsilon,
    public_deterministic_seed_epsilon,
    required_raw_noise_multiplier,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_accounting_rows(
    *,
    round_counts: list[int],
    noise_multipliers: list[float],
    delta: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rounds in round_counts:
        for raw_noise in noise_multipliers:
            rows.append(
                {
                    "scenario": "current_public_deterministic_seed",
                    "adjacency": "not_applicable",
                    "rounds": rounds,
                    "raw_noise_multiplier": raw_noise,
                    "effective_noise_multiplier": 0.0,
                    "delta": delta,
                    "epsilon": "inf",
                    "best_alpha": "n/a",
                    "formal_dp_valid": False,
                    "reason": "public seed makes noise reconstructible and removable by the verifier",
                }
            )
            for adjacency in ("add_remove", "replace_one"):
                epsilon, alpha = gaussian_rdp_epsilon(
                    raw_noise_multiplier=raw_noise,
                    steps=rounds,
                    delta=delta,
                    adjacency=adjacency,
                )
                rows.append(
                    {
                        "scenario": "ideal_secret_independent_gaussian",
                        "adjacency": adjacency,
                        "rounds": rounds,
                        "raw_noise_multiplier": raw_noise,
                        "effective_noise_multiplier": round(
                            effective_noise_multiplier(raw_noise, adjacency), 9
                        ),
                        "delta": delta,
                        "epsilon": round(epsilon, 6),
                        "best_alpha": round(alpha, 6),
                        "formal_dp_valid": True,
                        "reason": "conditional bound: seed/noise must remain secret and Gaussian",
                    }
                )
    return rows


def build_target_rows(
    *,
    round_counts: list[int],
    target_epsilons: list[float],
    delta: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rounds in round_counts:
        for target_epsilon in target_epsilons:
            for adjacency in ("add_remove", "replace_one"):
                raw_noise = required_raw_noise_multiplier(
                    target_epsilon=target_epsilon,
                    steps=rounds,
                    delta=delta,
                    adjacency=adjacency,
                )
                check_epsilon, alpha = gaussian_rdp_epsilon(
                    raw_noise_multiplier=raw_noise,
                    steps=rounds,
                    delta=delta,
                    adjacency=adjacency,
                )
                rows.append(
                    {
                        "rounds": rounds,
                        "target_epsilon": target_epsilon,
                        "delta": delta,
                        "adjacency": adjacency,
                        "required_raw_noise_multiplier": round(raw_noise, 9),
                        "check_epsilon": round(check_epsilon, 9),
                        "best_alpha": round(alpha, 6),
                    }
                )
    return rows


def build_profiles(args: argparse.Namespace) -> list[dict[str, Any]]:
    profiles = [
        {
            "profile": "current_utility_setting",
            "target_epsilon": None,
            "noise_multiplier": args.baseline_noise_multiplier,
        }
    ]
    for target_epsilon in sorted(args.frontier_epsilons, reverse=True):
        profiles.append(
            {
                "profile": f"conditional_target_eps_{target_epsilon:g}",
                "target_epsilon": target_epsilon,
                "noise_multiplier": required_raw_noise_multiplier(
                    target_epsilon=target_epsilon,
                    steps=args.rounds,
                    delta=args.delta,
                    adjacency="replace_one",
                ),
            }
        )
    return profiles


def run_utility_experiments(
    args: argparse.Namespace,
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in args.datasets:
        if dataset not in DATASETS:
            raise ValueError(f"unknown multiclass dataset: {dataset}")
        for seed in args.seeds:
            print(f"Running dataset={dataset}, seed={seed}, profile=fl_baseline", flush=True)
            fl_row = run_experiment(
                dataset_name=dataset,
                mode="fl",
                seed=seed,
                rounds=args.rounds,
                local_epochs=args.local_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                clients=args.clients,
                clip_norm=args.clip_norm,
                noise_multiplier=args.baseline_noise_multiplier,
            )
            rows.append(
                {
                    **fl_row,
                    "profile": "fl_baseline",
                    "noise_multiplier": 0.0,
                    "conditional_replace_epsilon": "inf",
                    "current_public_seed_epsilon": "inf",
                }
            )
            for profile in profiles:
                noise_multiplier = float(profile["noise_multiplier"])
                epsilon, _ = gaussian_rdp_epsilon(
                    raw_noise_multiplier=noise_multiplier,
                    steps=args.rounds,
                    delta=args.delta,
                    adjacency="replace_one",
                )
                print(
                    f"Running dataset={dataset}, seed={seed}, profile={profile['profile']}, "
                    f"noise_multiplier={noise_multiplier:.6f}",
                    flush=True,
                )
                dp_row = run_experiment(
                    dataset_name=dataset,
                    mode="dp",
                    seed=seed,
                    rounds=args.rounds,
                    local_epochs=args.local_epochs,
                    batch_size=args.batch_size,
                    lr=args.lr,
                    clients=args.clients,
                    clip_norm=args.clip_norm,
                    noise_multiplier=noise_multiplier,
                )
                rows.append(
                    {
                        **dp_row,
                        "profile": profile["profile"],
                        "noise_multiplier": round(noise_multiplier, 9),
                        "conditional_replace_epsilon": round(epsilon, 6),
                        "current_public_seed_epsilon": "inf",
                    }
                )
    return rows


def summarize_utility(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        fl_rows = [row for row in dataset_rows if row["profile"] == "fl_baseline"]
        fl_accuracies = np.array([float(row["final_accuracy"]) for row in fl_rows])
        fl_mean = float(np.mean(fl_accuracies))
        profiles = sorted(
            {str(row["profile"]) for row in dataset_rows if row["profile"] != "fl_baseline"},
            key=lambda profile: float(
                next(row["noise_multiplier"] for row in dataset_rows if row["profile"] == profile)
            ),
        )
        for profile in profiles:
            profile_rows = [row for row in dataset_rows if row["profile"] == profile]
            accuracies = np.array([float(row["final_accuracy"]) for row in profile_rows])
            summaries.append(
                {
                    "dataset": dataset,
                    "profile": profile,
                    "runs": len(profile_rows),
                    "rounds": int(profile_rows[0]["rounds"]),
                    "noise_multiplier": float(profile_rows[0]["noise_multiplier"]),
                    "conditional_replace_epsilon": float(
                        profile_rows[0]["conditional_replace_epsilon"]
                    ),
                    "current_public_seed_epsilon": "inf",
                    "fl_final_mean": round(fl_mean, 6),
                    "fl_final_std": round(float(np.std(fl_accuracies)), 6),
                    "dp_final_mean": round(float(np.mean(accuracies)), 6),
                    "dp_final_std": round(float(np.std(accuracies)), 6),
                    "dp_fl_retention": round(float(np.mean(accuracies)) / max(fl_mean, 1e-12), 6),
                }
            )
    return summaries


def write_chart(
    summaries: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for dataset in sorted({str(row["dataset"]) for row in summaries}):
        rows = sorted(
            [row for row in summaries if row["dataset"] == dataset],
            key=lambda row: float(row["conditional_replace_epsilon"]),
        )
        axes[0].plot(
            [row["conditional_replace_epsilon"] for row in rows],
            [row["dp_fl_retention"] for row in rows],
            marker="o",
            label=dataset,
        )
        axes[1].plot(
            [row["noise_multiplier"] for row in rows],
            [row["dp_final_mean"] for row in rows],
            marker="o",
            label=dataset,
        )
    axes[0].set_xscale("log")
    axes[0].axhline(0.9, color="black", linestyle="--", linewidth=1, label="0.9 threshold")
    axes[0].set_title("Conditional privacy-utility frontier")
    axes[0].set_xlabel("Replace-one epsilon (secret Gaussian assumption)")
    axes[0].set_ylabel("DP / FL final accuracy retention")
    axes[0].legend()

    axes[1].set_xscale("log")
    axes[1].set_title("Utility versus raw noise")
    axes[1].set_xlabel("Raw noise multiplier")
    axes[1].set_ylabel("DP final accuracy")
    axes[1].legend()

    replace_targets = [row for row in target_rows if row["adjacency"] == "replace_one"]
    for rounds in sorted({int(row["rounds"]) for row in replace_targets}):
        rows = sorted(
            [row for row in replace_targets if int(row["rounds"]) == rounds],
            key=lambda row: float(row["target_epsilon"]),
        )
        axes[2].plot(
            [row["target_epsilon"] for row in rows],
            [row["required_raw_noise_multiplier"] for row in rows],
            marker="o",
            label=f"{rounds} rounds",
        )
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_title("Noise required for target epsilon")
    axes[2].set_xlabel("Target epsilon (replace-one)")
    axes[2].set_ylabel("Required raw noise multiplier")
    axes[2].legend()

    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Gaussian privacy accounting: client-level RDP accounting and utility", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary(
    summaries: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    args: argparse.Namespace,
    output_path: Path,
) -> None:
    current_epsilon, _ = gaussian_rdp_epsilon(
        raw_noise_multiplier=args.baseline_noise_multiplier,
        steps=args.rounds,
        delta=args.delta,
        adjacency="replace_one",
    )
    lines = [
        "# Gaussian privacy accounting 正式 privacy accounting 與 utility frontier",
        "",
        "## 核心結論",
        "",
        "1. **目前 public deterministic seed 原型不具可宣稱的 Gaussian DP 保證。** "
        "noise seed 是 public input，verifier 可重建並扣除 noise，因此從 verifier/server view 應記為 epsilon = infinity。",
        "2. 下列有限 epsilon 僅是條件式反事實：noise 必須由 verifier 不知道的秘密、獨立 Gaussian randomness 產生。",
        "3. 目前 clipping 是整個 client update 的 L2 clipping，因此 accountant 是 client-level，而不是 record-level DP-SGD accountant。",
        "",
        "## Accounting 假設",
        "",
        f"- delta：{args.delta}",
        f"- rounds / sequential releases：{args.rounds}",
        "- client participation：q=1，沒有 subsampling amplification",
        "- replace-one sensitivity：2C；raw noise standard deviation：noise_multiplier * C",
        "- 轉換：Gaussian RDP 的 classic conservative (epsilon, delta) conversion",
        f"- 現行 noise_multiplier={args.baseline_noise_multiplier} 在秘密 Gaussian 假設下仍只有 epsilon={current_epsilon:.3f}；public-seed 現況則為 infinity。",
        "",
        "## Privacy-utility 結果",
        "",
        "| Dataset | Profile | Noise multiplier | 條件式 replace-one epsilon | FL final | DP final | Retention |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    profile_order = {profile["profile"]: index for index, profile in enumerate(profiles)}
    for row in sorted(
        summaries,
        key=lambda row: (str(row["dataset"]), profile_order[str(row["profile"])]),
    ):
        lines.append(
            f"| {row['dataset']} | {row['profile']} | {row['noise_multiplier']:.6f} | "
            f"{row['conditional_replace_epsilon']:.3f} | {row['fl_final_mean']:.6f} | "
            f"{row['dp_final_mean']:.6f} | {row['dp_fl_retention']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## 結案報告應採用的主張",
            "",
            "- 已完成：FL、DP-update prototype、quantized VDP constraints、actual EZKL proof、tampered rejection、proof-gated aggregation 與成本 benchmark。",
            "- 條件式完成：若使用秘密且獨立的 Gaussian noise，可用本實驗 RDP accountant 報告 client-level epsilon。",
            "- 尚未完成：目前 public-seed artifact 的正式 DP；seed-to-noise PRG/distribution 尚未在電路內驗證。",
            "- 正確定位：本研究是『可審計 DP 更新的 ZKML 原型』，不是已完成嚴格 DP 保證的大規模部署系統。",
            "",
            "## 後續密碼學修正方向",
            "",
            "需要讓 seed 對 verifier 保密，並在電路內驗證 secret seed -> PRG -> Gaussian/discrete-Gaussian noise；可再搭配 public commitment、VRF/commit-reveal randomness 或 distributed noise generation。只把 seed 從 JSON 移除但不驗證 noise generation，仍不足以形成 verifiable DP。",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run formal client-level privacy accounting experiment")
    parser.add_argument("--datasets", nargs="+", choices=sorted(DATASETS), default=["iris", "wine", "digits"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--accounting-rounds", nargs="+", type=int, default=[5, 10, 15])
    parser.add_argument("--frontier-epsilons", nargs="+", type=float, default=[128.0, 32.0, 8.0])
    parser.add_argument("--target-epsilons", nargs="+", type=float, default=[1.0, 2.0, 4.0, 8.0, 32.0, 128.0])
    parser.add_argument("--delta", type=float, default=1e-5)
    parser.add_argument("--baseline-noise-multiplier", type=float, default=0.08)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--skip-training", action="store_true")
    args = parser.parse_args()

    profiles = build_profiles(args)
    accounting_noise = sorted(
        {
            args.baseline_noise_multiplier,
            0.5,
            1.0,
            2.0,
            4.0,
            *(float(profile["noise_multiplier"]) for profile in profiles),
        }
    )
    accounting_rows = build_accounting_rows(
        round_counts=args.accounting_rounds,
        noise_multipliers=accounting_noise,
        delta=args.delta,
    )
    target_rows = build_target_rows(
        round_counts=args.accounting_rounds,
        target_epsilons=args.target_epsilons,
        delta=args.delta,
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(accounting_rows, RESULTS_DIR / "privacy_accounting_scenarios.csv")
    write_csv(target_rows, RESULTS_DIR / "target_noise_requirements.csv")

    if args.skip_training:
        print("Accounting tables generated; utility training skipped.")
        return 0

    utility_rows = run_utility_experiments(args, profiles)
    utility_summaries = summarize_utility(utility_rows)
    write_csv(utility_rows, RESULTS_DIR / "privacy_utility_runs.csv")
    write_csv(utility_summaries, RESULTS_DIR / "privacy_utility_summary.csv")
    write_chart(utility_summaries, target_rows, RESULTS_DIR / "privacy_utility_frontier.png")
    write_summary(utility_summaries, profiles, args, RESULTS_DIR / "summary.md")
    config = {
        **vars(args),
        "profiles": profiles,
        "current_public_seed_epsilon": "inf",
        "accounting_scope": "client-level direct per-client release; q=1",
        "conditional_assumption": "secret independent Gaussian noise unknown to verifier",
    }
    (RESULTS_DIR / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Completed {len(utility_rows)} utility runs")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
