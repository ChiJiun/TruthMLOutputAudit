"""non-IID client scaling - Paired CoverType experiments across client counts and non-IID partitions."""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import TensorDataset


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from covertype_large_dataset_scaling.run_covertype_scaling import (
    MulticlassLinearModel,
    PeakRSSMonitor,
    clip_update,
    evaluate,
    seeded_noise,
    set_seed,
    state_l2_norm,
    stratified_client_indices,
    stratified_subsample,
    train_local,
    weighted_average,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = BASE_DIR / "results"
MIB = 1024 * 1024


def dirichlet_client_indices(
    labels: np.ndarray,
    clients: int,
    alpha: float,
    seed: int,
    min_client_size: int = 64,
    max_attempts: int = 200,
) -> list[np.ndarray]:
    if alpha <= 0:
        raise ValueError("Dirichlet alpha must be positive")
    if len(labels) < clients * min_client_size:
        raise ValueError("Not enough samples for the requested minimum client size")
    for attempt in range(max_attempts):
        rng = np.random.default_rng(seed + attempt * 1_000_003)
        groups: list[list[int]] = [[] for _ in range(clients)]
        for class_label in np.unique(labels):
            class_indices = np.where(labels == class_label)[0]
            rng.shuffle(class_indices)
            proportions = rng.dirichlet(np.full(clients, alpha, dtype=np.float64))
            counts = rng.multinomial(len(class_indices), proportions)
            cursor = 0
            for client_id, count in enumerate(counts):
                groups[client_id].extend(int(index) for index in class_indices[cursor:cursor + count])
                cursor += int(count)
        if min(len(group) for group in groups) >= min_client_size:
            output = []
            for group in groups:
                rng.shuffle(group)
                output.append(np.asarray(group, dtype=np.int64))
            return output
    raise RuntimeError(
        f"Unable to draw Dirichlet partition with min_client_size={min_client_size} "
        f"after {max_attempts} attempts"
    )


def partition_diagnostics(
    labels: np.ndarray, groups: list[np.ndarray], num_classes: int
) -> dict[str, float | int]:
    global_counts = np.bincount(labels, minlength=num_classes).astype(np.float64)
    global_distribution = global_counts / global_counts.sum()
    sizes = np.asarray([len(group) for group in groups], dtype=np.float64)
    entropies: list[float] = []
    total_variations: list[float] = []
    for group in groups:
        counts = np.bincount(labels[group], minlength=num_classes).astype(np.float64)
        distribution = counts / counts.sum()
        positive = distribution[distribution > 0]
        entropy = -float(np.sum(positive * np.log(positive))) / math.log(num_classes)
        entropies.append(entropy)
        total_variations.append(0.5 * float(np.sum(np.abs(distribution - global_distribution))))
    return {
        "client_size_min": int(sizes.min()),
        "client_size_max": int(sizes.max()),
        "client_size_mean": round(float(sizes.mean()), 3),
        "client_size_cv": round(float(sizes.std() / sizes.mean()), 6),
        "label_entropy_mean": round(float(np.mean(entropies)), 6),
        "label_tv_mean": round(float(np.mean(total_variations)), 6),
        "label_tv_max": round(float(np.max(total_variations)), 6),
    }


def prepare_data(args: argparse.Namespace) -> tuple[list[TensorDataset], torch.Tensor, torch.Tensor, dict[str, Any]]:
    raw_x, raw_y = fetch_covtype(return_X_y=True)
    x = np.asarray(raw_x, dtype=np.float32)
    y = np.asarray(raw_y, dtype=np.int64) - 1
    del raw_x, raw_y
    all_indices = np.arange(len(y), dtype=np.int64)
    train_pool, test_indices = train_test_split(
        all_indices,
        test_size=args.test_fraction,
        random_state=args.seed,
        stratify=y,
    )
    train_indices = stratified_subsample(train_pool, y, args.train_size, args.seed)
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x[train_indices]).astype(np.float32, copy=False)
    x_test = scaler.transform(x[test_indices]).astype(np.float32, copy=False)
    y_train = y[train_indices]
    y_test = y[test_indices]
    if args.partition == "iid":
        groups = stratified_client_indices(y_train, args.clients, args.seed)
        alpha: float | None = None
    else:
        alpha = float(args.partition.split("_", 1)[1])
        groups = dirichlet_client_indices(
            y_train,
            clients=args.clients,
            alpha=alpha,
            seed=args.seed,
            min_client_size=args.min_client_size,
        )
    diagnostics = partition_diagnostics(y_train, groups, num_classes=7)
    datasets = [
        TensorDataset(
            torch.from_numpy(np.ascontiguousarray(x_train[group])),
            torch.from_numpy(np.ascontiguousarray(y_train[group])),
        )
        for group in groups
    ]
    metadata = {
        "total_samples": int(len(y)),
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "input_dim": int(x_train.shape[1]),
        "num_classes": 7,
        "parameter_count": 385,
        "partition": args.partition,
        "dirichlet_alpha": alpha,
        **diagnostics,
    }
    return (
        datasets,
        torch.from_numpy(np.ascontiguousarray(x_test)),
        torch.from_numpy(np.ascontiguousarray(y_test)),
        metadata,
    )


def run_mode(
    args: argparse.Namespace,
    mode: str,
    client_datasets: list[TensorDataset],
    test_x: torch.Tensor,
    test_y: torch.Tensor,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    set_seed(args.seed)
    device = torch.device("cpu")
    model = MulticlassLinearModel(54, 7).to(device)
    initial_accuracy = evaluate(model, test_x, test_y, device)
    accuracies = [initial_accuracy]
    clipped_updates = 0
    training_start = time.perf_counter()
    for round_idx in range(1, args.rounds + 1):
        global_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        updates: list[dict[str, torch.Tensor]] = []
        weights: list[int] = []
        for client_id, dataset in enumerate(client_datasets):
            local_state, _ = train_local(
                model,
                dataset,
                input_dim=54,
                num_classes=7,
                device=device,
                epochs=args.local_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                shuffle_seed=args.seed + round_idx * 10_000 + client_id * 100,
            )
            update = {key: local_state[key] - global_state[key] for key in global_state}
            if mode in ("clip", "dp"):
                if state_l2_norm(update) > args.clip_norm:
                    clipped_updates += 1
                update = clip_update(update, args.clip_norm)
            if mode == "dp":
                noise = seeded_noise(
                    update,
                    seed=args.seed + round_idx * 10_000 + client_id * 100,
                    clip_norm=args.clip_norm,
                    noise_multiplier=args.noise_multiplier,
                )
                update = {key: update[key] + noise[key] for key in update}
            updates.append(update)
            weights.append(len(dataset))
        averaged = weighted_average(updates, weights)
        model.load_state_dict({key: global_state[key] + averaged[key] for key in global_state})
        accuracies.append(evaluate(model, test_x, test_y, device))
    training_sec = time.perf_counter() - training_start
    return {
        "dataset": "covertype",
        "seed": args.seed,
        "clients": args.clients,
        "mode": mode,
        "rounds": args.rounds,
        "local_epochs": args.local_epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "clip_norm": args.clip_norm,
        "noise_multiplier": args.noise_multiplier,
        **metadata,
        "initial_accuracy": round(initial_accuracy, 6),
        "final_accuracy": round(accuracies[-1], 6),
        "best_accuracy": round(max(accuracies), 6),
        "round_accuracies": [round(value, 6) for value in accuracies],
        "clipped_client_updates": clipped_updates,
        "training_sec": round(training_sec, 6),
        "training_samples_per_sec": round(
            int(metadata["train_size"]) * args.rounds * args.local_epochs / max(training_sec, 1e-9),
            3,
        ),
    }


def run_worker(args: argparse.Namespace) -> int:
    if args.torch_threads > 0:
        torch.set_num_threads(args.torch_threads)
    wall_start = time.perf_counter()
    with PeakRSSMonitor() as monitor:
        prep_start = time.perf_counter()
        client_datasets, test_x, test_y, metadata = prepare_data(args)
        preprocess_sec = time.perf_counter() - prep_start
        rows = [
            run_mode(args, mode, client_datasets, test_x, test_y, metadata)
            for mode in args.modes
        ]
    for row in rows:
        row["preprocess_sec"] = round(preprocess_sec, 6)
        row["worker_wall_sec"] = round(time.perf_counter() - wall_start, 6)
        row["worker_peak_rss_mib"] = round(monitor.peak / MIB, 3)
    output = Path(args.worker_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(
        f"worker complete: clients={args.clients}, partition={args.partition}, seed={args.seed}, "
        f"finals={[row['final_accuracy'] for row in rows]}, peak={rows[0]['worker_peak_rss_mib']} MiB"
    )
    return 0


def mean(rows: list[dict[str, Any]], field: str) -> float:
    return float(np.mean([float(row[field]) for row in rows]))


def std(rows: list[dict[str, Any]], field: str) -> float:
    return float(np.std([float(row[field]) for row in rows], ddof=1)) if len(rows) > 1 else 0.0


def ci95(rows: list[dict[str, Any]], field: str) -> float:
    critical = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776}.get(len(rows), 1.96)
    return critical * std(rows, field) / math.sqrt(len(rows)) if len(rows) > 1 else 0.0


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    keys = sorted({(int(row["clients"]), str(row["partition"])) for row in rows})
    for clients, partition in keys:
        group = [row for row in rows if int(row["clients"]) == clients and row["partition"] == partition]
        modes = {mode: [row for row in group if row["mode"] == mode] for mode in ("fl", "clip", "dp")}
        fl_mean = mean(modes["fl"], "final_accuracy")
        clip_mean = mean(modes["clip"], "final_accuracy")
        dp_mean = mean(modes["dp"], "final_accuracy")
        output.append(
            {
                "clients": clients,
                "partition": partition,
                "dirichlet_alpha": group[0]["dirichlet_alpha"],
                "seeds": len(modes["fl"]),
                "train_size": int(group[0]["train_size"]),
                "client_size_min_mean": round(mean(group, "client_size_min"), 3),
                "client_size_max_mean": round(mean(group, "client_size_max"), 3),
                "client_size_cv_mean": round(mean(group, "client_size_cv"), 6),
                "label_entropy_mean": round(mean(group, "label_entropy_mean"), 6),
                "label_tv_mean": round(mean(group, "label_tv_mean"), 6),
                "fl_final_mean": round(fl_mean, 6),
                "fl_final_std": round(std(modes["fl"], "final_accuracy"), 6),
                "fl_final_ci95": round(ci95(modes["fl"], "final_accuracy"), 6),
                "clip_final_mean": round(clip_mean, 6),
                "clip_final_std": round(std(modes["clip"], "final_accuracy"), 6),
                "clip_final_ci95": round(ci95(modes["clip"], "final_accuracy"), 6),
                "dp_final_mean": round(dp_mean, 6),
                "dp_final_std": round(std(modes["dp"], "final_accuracy"), 6),
                "dp_final_ci95": round(ci95(modes["dp"], "final_accuracy"), 6),
                "clip_fl_retention": round(clip_mean / max(fl_mean, 1e-9), 6),
                "dp_fl_retention": round(dp_mean / max(fl_mean, 1e-9), 6),
                "fl_training_sec_mean": round(mean(modes["fl"], "training_sec"), 3),
                "clip_training_sec_mean": round(mean(modes["clip"], "training_sec"), 3),
                "dp_training_sec_mean": round(mean(modes["dp"], "training_sec"), 3),
                "worker_peak_rss_mib_mean": round(mean(group, "worker_peak_rss_mib"), 3),
                "completed": len(group) == 3 * len(modes["fl"]),
            }
        )
    return output


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            if isinstance(serialized.get("round_accuracies"), list):
                serialized["round_accuracies"] = json.dumps(serialized["round_accuracies"])
            writer.writerow(serialized)


def write_chart(rows: list[dict[str, Any]], path: Path) -> None:
    labels = [f"K={row['clients']}\n{row['partition']}" for row in rows]
    positions = np.arange(len(rows))
    width = 0.25
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for offset, mode, label, color in [
        (-width, "fl", "FL", "#1565C0"),
        (0, "clip", "Clipping only", "#EF6C00"),
        (width, "dp", "DP-update", "#2E7D32"),
    ]:
        axes[0, 0].bar(
            positions + offset,
            [row[f"{mode}_final_mean"] for row in rows],
            width,
            yerr=[row[f"{mode}_final_ci95"] for row in rows],
            capsize=3,
            label=label,
            color=color,
        )
    axes[0, 0].set_title("Final accuracy with 95% CI")
    axes[0, 0].set_ylabel("Accuracy")
    axes[0, 0].legend()

    axes[0, 1].plot(positions, [row["clip_fl_retention"] for row in rows], marker="o", label="Clip / FL")
    axes[0, 1].plot(positions, [row["dp_fl_retention"] for row in rows], marker="o", label="DP / FL")
    axes[0, 1].axhline(0.9, linestyle="--", color="#C62828", label="90% threshold")
    axes[0, 1].set_title("Utility retention")
    axes[0, 1].set_ylabel("Retention")
    axes[0, 1].legend()

    axes[1, 0].bar(positions - width / 2, [row["label_tv_mean"] for row in rows], width, label="Mean label TV")
    axes[1, 0].bar(positions + width / 2, [1 - row["label_entropy_mean"] for row in rows], width, label="1 - normalized entropy")
    axes[1, 0].set_title("Measured client heterogeneity")
    axes[1, 0].set_ylabel("Higher = more heterogeneous")
    axes[1, 0].legend()

    axes[1, 1].plot(positions, [row["fl_training_sec_mean"] for row in rows], marker="o", label="FL")
    axes[1, 1].plot(positions, [row["clip_training_sec_mean"] for row in rows], marker="o", label="Clip")
    axes[1, 1].plot(positions, [row["dp_training_sec_mean"] for row in rows], marker="o", label="DP")
    axes[1, 1].set_title("Training time")
    axes[1, 1].set_ylabel("Seconds")
    axes[1, 1].legend()

    for axis in axes.flat:
        axis.set_xticks(positions, labels)
        axis.grid(axis="y", alpha=0.25)
    fig.suptitle("CoverType non-IID and client-count scaling", fontsize=14)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(rows: list[dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    lines = [
        "# non-IID client scaling CoverType Non-IID 與 Client Scaling 摘要",
        "",
        "## 預先固定的設計",
        "",
        f"- Training samples={args.train_size}；seeds={args.seeds}。",
        f"- Clients={args.client_counts}；partitions={args.partitions}。",
        f"- Rounds={args.rounds}；local epochs={args.local_epochs}；batch size={args.batch_size}。",
        "- 每個 condition/seed 共用資料、初始化與 shuffle，依序執行 FL、clipping-only、DP-update。",
        "- 95% CI 使用 seed-level Student-t interval；這是小樣本描述性區間。",
        "- Label TV 越大、normalized entropy 越低，代表 client label distribution 越異質。",
        "",
        "## 結果",
        "",
        "| K | Partition | Label TV | FL mean±CI | Clip mean±CI | DP mean±CI | Clip/FL | DP/FL | Train sec F/C/D |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['clients']} | {row['partition']} | {row['label_tv_mean']:.3f} | "
            f"{row['fl_final_mean']:.6f}±{row['fl_final_ci95']:.6f} | "
            f"{row['clip_final_mean']:.6f}±{row['clip_final_ci95']:.6f} | "
            f"{row['dp_final_mean']:.6f}±{row['dp_final_ci95']:.6f} | "
            f"{row['clip_fl_retention']:.6f} | {row['dp_fl_retention']:.6f} | "
            f"{row['fl_training_sec_mean']:.1f}/{row['clip_training_sec_mean']:.1f}/{row['dp_training_sec_mean']:.1f} |"
        )
    worst = min(rows, key=lambda row: float(row["dp_fl_retention"]))
    lines.extend(
        [
            "",
            "## 假設判定",
            "",
            f"- 全部 {len(rows)} 個 condition 均完成：{all(bool(row['completed']) for row in rows)}。",
            f"- 最低 DP/FL retention 出現在 K={worst['clients']}、{worst['partition']}：{worst['dp_fl_retention']:.6f}。",
            "- 本實驗檢查執行可行性與 utility robustness；public seed 的 epsilon infinity 限制不變。",
            "- 若 non-IID condition 低於 90%，應如實解讀為固定 clipping/noise profile 不具跨 partition 穩健性，而不是隱藏該結果。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_parent(args: argparse.Namespace) -> int:
    results_dir = Path(args.results_dir)
    workers_dir = results_dir / "worker_rows"
    workers_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for clients in args.client_counts:
        for partition in args.partitions:
            for seed in args.seeds:
                worker_output = workers_dir / f"k{clients}_{partition}_seed{seed}.json"
                if args.resume and worker_output.exists():
                    print(f"Reusing {worker_output.name}")
                else:
                    command = [
                        sys.executable, str(Path(__file__).resolve()), "--worker",
                        "--worker-output", str(worker_output),
                        "--clients", str(clients), "--partition", partition,
                        "--seed", str(seed), "--train-size", str(args.train_size),
                        "--rounds", str(args.rounds), "--local-epochs", str(args.local_epochs),
                        "--batch-size", str(args.batch_size), "--lr", str(args.lr),
                        "--clip-norm", str(args.clip_norm), "--noise-multiplier", str(args.noise_multiplier),
                        "--test-fraction", str(args.test_fraction),
                        "--min-client-size", str(args.min_client_size),
                        "--torch-threads", str(args.torch_threads),
                        "--modes", *args.modes,
                    ]
                    print(f"Running K={clients}, partition={partition}, seed={seed}", flush=True)
                    subprocess.run(command, check=True, cwd=ROOT_DIR)
                rows.extend(json.loads(worker_output.read_text(encoding="utf-8")))
    rows.sort(key=lambda row: (int(row["clients"]), str(row["partition"]), int(row["seed"]), str(row["mode"])))
    summary = summarize(rows)
    write_csv(rows, results_dir / "noniid_client_runs.csv")
    write_csv(summary, results_dir / "noniid_client_summary.csv")
    write_chart(summary, results_dir / "noniid_client_scaling.png")
    write_summary_md(summary, results_dir / "summary.md", args)
    config = vars(args).copy()
    config.pop("worker_output", None)
    config.pop("worker", None)
    (results_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Completed {len(rows)} mode runs across {len(summary)} conditions")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CoverType non-IID and client scaling")
    parser.add_argument("--train-size", type=int, default=100000)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62, 72, 82])
    parser.add_argument("--client-counts", nargs="+", type=int, default=[3, 10])
    parser.add_argument("--partitions", nargs="+", choices=["iid", "dirichlet_0.5", "dirichlet_0.1"], default=["iid", "dirichlet_0.5", "dirichlet_0.1"])
    parser.add_argument("--modes", nargs="+", choices=["fl", "clip", "dp"], default=["fl", "clip", "dp"])
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--min-client-size", type=int, default=64)
    parser.add_argument("--torch-threads", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    parser.add_argument("--clients", type=int, default=3, help=argparse.SUPPRESS)
    parser.add_argument("--partition", default="iid", help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=42, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        if not args.worker_output:
            raise ValueError("--worker-output is required")
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
