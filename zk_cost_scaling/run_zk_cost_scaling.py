"""ZK cost scaling - Repeated EZKL cost, memory, and communication scaling benchmark."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from multiclass_vdp_zk.run_wine_vdp_zk_cost import (
    build_multiclass_artifact,
    run_ezkl_case,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
# Reuse multiclass VDP/ZK evaluation's ignored artifact area so large proving keys never become source files.
DEFAULT_ARTIFACTS_DIR = (
    ROOT_DIR / "multiclass_vdp_zk" / "results" / "ezkl_cases" / "dimension_scaling"
)
MIB = 1024 * 1024


def mean(rows: list[dict[str, Any]], field: str) -> float:
    return statistics.fmean(float(row[field]) for row in rows)


def sample_std(rows: list[dict[str, Any]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return statistics.stdev(values) if len(values) > 1 else 0.0


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    preferred = [
        "dataset",
        "seed",
        "case_name",
        "vector_dim",
        "verified",
        "clip_ok",
        "relation_ok",
        "accepted",
        "pipeline_sec",
        "prove_sec",
        "verify_sec",
        "pipeline_peak_rss_bytes",
        "pipeline_peak_rss_delta_bytes",
        "prove_peak_rss_delta_bytes",
        "verify_peak_rss_delta_bytes",
        "proof_size_bytes",
        "update_payload_bytes",
        "audit_metadata_bytes",
        "s2_payload_bytes",
        "communication_overhead_bytes",
        "communication_overhead_ratio",
        "logrows",
        "num_rows",
        "total_assignments",
        "pk_size_bytes",
        "vk_size_bytes",
        "srs_size_bytes",
    ]
    all_fields = {key for row in rows for key in row}
    fieldnames = [field for field in preferred if field in all_fields]
    fieldnames.extend(sorted(all_fields - set(fieldnames)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for dataset in sorted({str(row["dataset"]) for row in raw_rows}):
        rows = [row for row in raw_rows if row["dataset"] == dataset]
        summary = {
            "dataset": dataset,
            "runs": len(rows),
            "vector_dim": int(rows[0]["vector_dim"]),
            "accepted_runs": sum(bool(row["accepted"]) for row in rows),
            "prove_sec_mean": round(mean(rows, "prove_sec"), 6),
            "prove_sec_std": round(sample_std(rows, "prove_sec"), 6),
            "verify_sec_mean": round(mean(rows, "verify_sec"), 6),
            "verify_sec_std": round(sample_std(rows, "verify_sec"), 6),
            "pipeline_sec_mean": round(mean(rows, "pipeline_sec"), 6),
            "pipeline_sec_std": round(sample_std(rows, "pipeline_sec"), 6),
            "pipeline_peak_rss_mib_mean": round(mean(rows, "pipeline_peak_rss_bytes") / MIB, 3),
            "pipeline_peak_rss_mib_std": round(sample_std(rows, "pipeline_peak_rss_bytes") / MIB, 3),
            "pipeline_peak_rss_delta_mib_mean": round(
                mean(rows, "pipeline_peak_rss_delta_bytes") / MIB, 3
            ),
            "prove_peak_rss_delta_mib_mean": round(
                mean(rows, "prove_peak_rss_delta_bytes") / MIB, 3
            ),
            "proof_size_bytes_mean": round(mean(rows, "proof_size_bytes"), 3),
            "update_payload_bytes_mean": round(mean(rows, "update_payload_bytes"), 3),
            "s2_payload_bytes_mean": round(mean(rows, "s2_payload_bytes"), 3),
            "communication_overhead_bytes_mean": round(
                mean(rows, "communication_overhead_bytes"), 3
            ),
            "communication_overhead_ratio_mean": round(
                mean(rows, "communication_overhead_ratio"), 6
            ),
            "circuit_rows_mean": round(mean(rows, "num_rows"), 3),
            "total_assignments_mean": round(mean(rows, "total_assignments"), 3),
            "pk_size_bytes_mean": round(mean(rows, "pk_size_bytes"), 3),
            "srs_size_bytes_mean": round(mean(rows, "srs_size_bytes"), 3),
        }
        summaries.append(summary)

    summaries.sort(key=lambda row: int(row["vector_dim"]))
    baseline = summaries[0]
    for row in summaries:
        row["prove_time_vs_smallest"] = round(
            float(row["prove_sec_mean"]) / float(baseline["prove_sec_mean"]), 3
        )
        row["peak_rss_vs_smallest"] = round(
            float(row["pipeline_peak_rss_mib_mean"])
            / float(baseline["pipeline_peak_rss_mib_mean"]),
            3,
        )
        row["s2_payload_vs_smallest"] = round(
            float(row["s2_payload_bytes_mean"]) / float(baseline["s2_payload_bytes_mean"]),
            3,
        )
    return summaries


def write_chart(rows: list[dict[str, Any]], output_path: Path) -> None:
    labels = [f"{row['dataset']}\n(d={row['vector_dim']})" for row in rows]
    positions = list(range(len(rows)))

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    axes[0].errorbar(
        positions,
        [row["prove_sec_mean"] for row in rows],
        yerr=[row["prove_sec_std"] for row in rows],
        marker="o",
        capsize=4,
        color="#1565C0",
    )
    axes[0].set_title("EZKL proving time")
    axes[0].set_ylabel("Seconds (mean +/- SD)")

    axes[1].errorbar(
        positions,
        [row["pipeline_peak_rss_mib_mean"] for row in rows],
        yerr=[row["pipeline_peak_rss_mib_std"] for row in rows],
        marker="o",
        capsize=4,
        color="#D84315",
    )
    axes[1].set_title("Pipeline peak RSS")
    axes[1].set_ylabel("MiB (mean +/- SD)")

    width = 0.35
    axes[2].bar(
        [position - width / 2 for position in positions],
        [row["update_payload_bytes_mean"] / 1024 for row in rows],
        width,
        label="S1 update",
        color="#43A047",
    )
    axes[2].bar(
        [position + width / 2 for position in positions],
        [row["s2_payload_bytes_mean"] / 1024 for row in rows],
        width,
        label="S2 update + audit",
        color="#7E57C2",
    )
    axes[2].set_title("Estimated communication payload")
    axes[2].set_ylabel("KiB per client update")
    axes[2].legend()

    for axis in axes:
        axis.set_xticks(positions, labels)
        axis.grid(axis="y", alpha=0.25)
    fig.suptitle("VDP/ZK cost scaling across multiclass update dimensions", fontsize=14)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary(rows: list[dict[str, Any]], output_path: Path, seeds: list[int]) -> None:
    smallest = rows[0]
    largest = rows[-1]
    proof_sizes = [float(row["proof_size_bytes_mean"]) for row in rows]
    lines = [
        "# ZK cost scaling ZK 成本、記憶體與通訊 scaling 摘要",
        "",
        "本實驗補齊計劃書原訂但先前尚未系統量測的 peak memory 與 communication overhead，",
        "並以獨立 Python process 重跑每個 dataset/seed，避免前一次 EZKL 配置保留的記憶體干擾 RSS 比較。",
        "",
        "## 設定",
        "",
        f"- 重跑 seeds：{', '.join(str(seed) for seed in seeds)}",
        "- 案例：honest profile（所有 run 均須通過 proof、clipping 與 additive relation）",
        "- Peak memory：5 ms polling 的 process RSS 峰值；同時保留相對 pipeline baseline 的增量",
        "- S1 payload：compact JSON 的 `client_id + q_noisy`",
        "- S2 payload：S1 payload + `proof.json` + compact JSON audit policy metadata",
        "- 通訊量不含 TCP/TLS/HTTP framing，因此是可重現的 application-layer wire-size 估計",
        "",
        "## 結果",
        "",
        "| Dataset | 維度 | 通過 | Prove 秒 mean±SD | Verify 秒 mean±SD | Peak RSS MiB mean±SD | S1 bytes | S2 bytes | S2 額外倍率 | Circuit rows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['dataset']} | {row['vector_dim']} | {row['accepted_runs']}/{row['runs']} | "
            f"{row['prove_sec_mean']:.6f}±{row['prove_sec_std']:.6f} | "
            f"{row['verify_sec_mean']:.6f}±{row['verify_sec_std']:.6f} | "
            f"{row['pipeline_peak_rss_mib_mean']:.3f}±{row['pipeline_peak_rss_mib_std']:.3f} | "
            f"{row['update_payload_bytes_mean']:.0f} | {row['s2_payload_bytes_mean']:.0f} | "
            f"{row['communication_overhead_ratio_mean']:.3f}x | {row['circuit_rows_mean']:.0f} |"
        )
    lines.extend(
        [
            "",
            "## 解讀",
            "",
            f"- 更新維度由 {smallest['vector_dim']} 增至 {largest['vector_dim']} 時，平均 proving time 為最小模型的 {largest['prove_time_vs_smallest']:.3f} 倍。",
            f"- 同一範圍內，pipeline peak RSS 為最小模型的 {largest['peak_rss_vs_smallest']:.3f} 倍，S2 application payload 為 {largest['s2_payload_vs_smallest']:.3f} 倍。",
            f"- Proof JSON 大小介於 {min(proof_sizes):.0f} 到 {max(proof_sizes):.0f} bytes；成本成長主要應搭配 circuit rows、proving key、RSS 與 proving time 一起解讀。",
            "- S2 額外倍率在小更新向量上較高，因固定大小的 proof 與 metadata 佔比更大；向量變大後，原始更新 payload 的占比上升。",
            "- 本實驗只比較三個線性多類別模型，不能據此宣稱對深度模型呈線性 scaling。",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_worker(args: argparse.Namespace) -> int:
    artifact = build_multiclass_artifact(
        dataset_name=args.dataset,
        case_name="honest_profile",
        client_id=args.client_id,
        seed=args.seed,
        scale=args.scale,
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
        local_epochs=args.local_epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        clients=args.clients,
        slack_ppm=args.slack_ppm,
    )
    summary = run_ezkl_case(artifact, Path(args.worker_case_dir))
    summary["seed"] = args.seed
    Path(args.worker_summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["accepted"] else 2


def run_isolated_case(args: argparse.Namespace, dataset: str, seed: int) -> dict[str, Any]:
    case_dir = Path(args.artifacts_dir) / dataset / "honest_profile"
    worker_summary = Path(args.artifacts_dir) / dataset / "worker_summary.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--dataset",
        dataset,
        "--seed",
        str(seed),
        "--worker-case-dir",
        str(case_dir),
        "--worker-summary",
        str(worker_summary),
        "--client-id",
        str(args.client_id),
        "--clients",
        str(args.clients),
        "--local-epochs",
        str(args.local_epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(args.lr),
        "--scale",
        str(args.scale),
        "--clip-norm",
        str(args.clip_norm),
        "--noise-multiplier",
        str(args.noise_multiplier),
        "--slack-ppm",
        str(args.slack_ppm),
    ]
    print(f"Running isolated EZKL case: dataset={dataset}, seed={seed}", flush=True)
    subprocess.run(command, check=True, cwd=ROOT_DIR)
    return json.loads(worker_summary.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated VDP/ZK scaling benchmark")
    parser.add_argument("--datasets", nargs="+", choices=["iris", "wine", "digits"], default=["iris", "wine", "digits"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--client-id", type=int, default=0)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--scale", type=int, default=10000)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--slack-ppm", type=int, default=4201)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dataset", choices=["iris", "wine", "digits"], help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-case-dir", help=argparse.SUPPRESS)
    parser.add_argument("--worker-summary", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.worker:
        return run_worker(args)

    raw_rows = [
        run_isolated_case(args, dataset, seed)
        for dataset in args.datasets
        for seed in args.seeds
    ]
    summary_rows = summarize(raw_rows)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(raw_rows, RESULTS_DIR / "zk_cost_scaling_runs.csv")
    write_csv(summary_rows, RESULTS_DIR / "zk_cost_scaling_summary.csv")
    write_chart(summary_rows, RESULTS_DIR / "zk_cost_scaling.png")
    write_summary(summary_rows, RESULTS_DIR / "summary.md", args.seeds)
    config = {
        **{key: value for key, value in vars(args).items() if key not in {"worker_case_dir", "worker_summary"}},
        "artifacts_dir": str(args.artifacts_dir),
        "memory_definition": "5 ms polling of process RSS; worker process isolated per dataset/seed",
        "communication_definition": "compact JSON update + proof.json + compact JSON audit policy metadata",
    }
    (RESULTS_DIR / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    failed = [row for row in raw_rows if not row["accepted"]]
    print(f"Completed {len(raw_rows)} runs; accepted={len(raw_rows) - len(failed)}; failed={len(failed)}")
    print(f"Results saved to: {RESULTS_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
