"""CoverType large-data scaling - Large-dataset FL/DP scaling on Forest CoverType."""
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psutil
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = BASE_DIR / "results"
MIB = 1024 * 1024


class MulticlassLinearModel(nn.Module):
    def __init__(self, input_dim: int, num_classes: int) -> None:
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)


class PeakRSSMonitor:
    def __init__(self, interval_sec: float = 0.02) -> None:
        self.process = psutil.Process()
        self.interval_sec = interval_sec
        self.baseline = self.process.memory_info().rss
        self.peak = self.baseline
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(self.interval_sec):
            try:
                self.peak = max(self.peak, self.process.memory_info().rss)
            except (psutil.Error, OSError):
                return

    def __enter__(self) -> "PeakRSSMonitor":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        try:
            self.peak = max(self.peak, self.process.memory_info().rss)
        except (psutil.Error, OSError):
            pass
        self._stop.set()
        self._thread.join(timeout=1.0)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def stratified_subsample(indices: np.ndarray, labels: np.ndarray, size: int, seed: int) -> np.ndarray:
    if size >= len(indices):
        return indices.copy()
    selected, _ = train_test_split(
        indices,
        train_size=size,
        random_state=seed,
        stratify=labels[indices],
    )
    return np.asarray(selected, dtype=np.int64)


def stratified_client_indices(labels: np.ndarray, clients: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    groups: list[list[int]] = [[] for _ in range(clients)]
    for class_label in np.unique(labels):
        class_indices = np.where(labels == class_label)[0]
        rng.shuffle(class_indices)
        for offset, index in enumerate(class_indices):
            groups[offset % clients].append(int(index))
    output: list[np.ndarray] = []
    for group in groups:
        rng.shuffle(group)
        output.append(np.asarray(group, dtype=np.int64))
    return output


def state_l2_norm(state: dict[str, torch.Tensor]) -> float:
    return float(sum(torch.sum(value.float() ** 2).item() for value in state.values()) ** 0.5)


def clip_update(update: dict[str, torch.Tensor], clip_norm: float) -> dict[str, torch.Tensor]:
    norm = state_l2_norm(update)
    if norm == 0.0 or norm <= clip_norm:
        return {key: value.clone() for key, value in update.items()}
    factor = clip_norm / norm
    return {key: value * factor for key, value in update.items()}


def seeded_noise(
    reference: dict[str, torch.Tensor], *, seed: int, clip_norm: float, noise_multiplier: float
) -> dict[str, torch.Tensor]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    std = clip_norm * noise_multiplier
    return {
        key: torch.randn(value.shape, generator=generator, dtype=value.dtype) * std
        for key, value in reference.items()
    }


def weighted_average(
    states: list[dict[str, torch.Tensor]], weights: list[int]
) -> dict[str, torch.Tensor]:
    total = float(sum(weights))
    return {
        key: sum(state[key] * (weight / total) for state, weight in zip(states, weights))
        for key in states[0]
    }


def evaluate(model: nn.Module, test_x: torch.Tensor, test_y: torch.Tensor, device: torch.device) -> float:
    model.eval()
    correct = 0
    total = 0
    loader = DataLoader(TensorDataset(test_x, test_y), batch_size=8192, shuffle=False)
    with torch.no_grad():
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            predictions = torch.argmax(model(batch_x), dim=1)
            correct += int((predictions == batch_y).sum().item())
            total += int(batch_y.numel())
    return correct / max(1, total)


def train_local(
    global_model: nn.Module,
    dataset: TensorDataset,
    *,
    input_dim: int,
    num_classes: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
    lr: float,
    shuffle_seed: int,
) -> tuple[dict[str, torch.Tensor], float]:
    local_model = MulticlassLinearModel(input_dim, num_classes).to(device)
    local_model.load_state_dict(global_model.state_dict())
    local_model.train()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(shuffle_seed)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
    )
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(local_model.parameters(), lr=lr)
    total_loss = 0.0
    batches = 0
    for _ in range(epochs):
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            loss = criterion(local_model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
            batches += 1
    state = {key: value.detach().cpu().clone() for key, value in local_model.state_dict().items()}
    return state, total_loss / max(1, batches)


def run_worker(args: argparse.Namespace) -> int:
    set_seed(args.seed)
    if args.torch_threads > 0:
        torch.set_num_threads(args.torch_threads)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    wall_start = time.perf_counter()

    with PeakRSSMonitor() as monitor:
        load_start = time.perf_counter()
        raw_x, raw_y = fetch_covtype(return_X_y=True)
        x = np.asarray(raw_x, dtype=np.float32)
        y = np.asarray(raw_y, dtype=np.int64) - 1
        del raw_x, raw_y
        dataset_load_sec = time.perf_counter() - load_start

        preprocess_start = time.perf_counter()
        all_indices = np.arange(len(y), dtype=np.int64)
        train_pool, test_indices = train_test_split(
            all_indices,
            test_size=args.test_fraction,
            random_state=args.seed,
            stratify=y,
        )
        requested_train_size = len(train_pool) if args.train_size <= 0 else args.train_size
        train_indices = stratified_subsample(train_pool, y, requested_train_size, args.seed)

        scaler = StandardScaler()
        x_train = scaler.fit_transform(x[train_indices]).astype(np.float32, copy=False)
        x_test = scaler.transform(x[test_indices]).astype(np.float32, copy=False)
        y_train = y[train_indices]
        y_test = y[test_indices]
        client_indices = stratified_client_indices(y_train, args.clients, args.seed)
        client_datasets = [
            TensorDataset(
                torch.from_numpy(np.ascontiguousarray(x_train[idx])),
                torch.from_numpy(np.ascontiguousarray(y_train[idx])),
            )
            for idx in client_indices
        ]
        test_x = torch.from_numpy(np.ascontiguousarray(x_test))
        test_y = torch.from_numpy(np.ascontiguousarray(y_test))
        preprocess_sec = time.perf_counter() - preprocess_start

        input_dim = int(x_train.shape[1])
        num_classes = int(len(np.unique(y)))
        model = MulticlassLinearModel(input_dim, num_classes).to(device)
        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        initial_accuracy = evaluate(model, test_x, test_y, device)
        round_accuracies = [initial_accuracy]
        round_losses: list[float] = []
        clipped_clients = 0

        training_start = time.perf_counter()
        for round_idx in range(1, args.rounds + 1):
            global_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            updates: list[dict[str, torch.Tensor]] = []
            weights: list[int] = []
            losses: list[float] = []
            for client_id, dataset in enumerate(client_datasets):
                local_state, loss = train_local(
                    model,
                    dataset,
                    input_dim=input_dim,
                    num_classes=num_classes,
                    device=device,
                    epochs=args.local_epochs,
                    batch_size=args.batch_size,
                    lr=args.lr,
                    shuffle_seed=args.seed + round_idx * 10_000 + client_id * 100,
                )
                update = {key: local_state[key] - global_state[key] for key in global_state}
                if args.mode in ("clip", "dp"):
                    if state_l2_norm(update) > args.clip_norm:
                        clipped_clients += 1
                    clipped = clip_update(update, args.clip_norm)
                    update = clipped
                    if args.mode == "dp":
                        noise = seeded_noise(
                            clipped,
                            seed=args.seed + round_idx * 10_000 + client_id * 100,
                            clip_norm=args.clip_norm,
                            noise_multiplier=args.noise_multiplier,
                        )
                        update = {key: clipped[key] + noise[key] for key in clipped}
                updates.append(update)
                weights.append(len(dataset))
                losses.append(loss)
            averaged = weighted_average(updates, weights)
            model.load_state_dict({key: global_state[key] + averaged[key] for key in global_state})
            round_accuracies.append(evaluate(model, test_x, test_y, device))
            round_losses.append(float(np.mean(losses)))
        training_sec = time.perf_counter() - training_start

    sample_exposures = len(y_train) * args.rounds * args.local_epochs
    row: dict[str, Any] = {
        "dataset": "covertype",
        "mode": args.mode,
        "seed": args.seed,
        "total_samples": int(len(y)),
        "train_pool_size": int(len(train_pool)),
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "input_dim": input_dim,
        "num_classes": num_classes,
        "parameter_count": int(parameter_count),
        "clients": args.clients,
        "rounds": args.rounds,
        "local_epochs": args.local_epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "clip_norm": args.clip_norm,
        "noise_multiplier": args.noise_multiplier,
        "initial_accuracy": round(initial_accuracy, 6),
        "final_accuracy": round(round_accuracies[-1], 6),
        "best_accuracy": round(max(round_accuracies), 6),
        "mean_round_loss": round(float(np.mean(round_losses)), 6),
        "clipped_client_updates": clipped_clients,
        "round_accuracies": [round(value, 6) for value in round_accuracies],
        "dataset_load_sec": round(dataset_load_sec, 6),
        "preprocess_sec": round(preprocess_sec, 6),
        "training_sec": round(training_sec, 6),
        "wall_sec": round(time.perf_counter() - wall_start, 6),
        "sample_exposures": int(sample_exposures),
        "training_samples_per_sec": round(sample_exposures / max(training_sec, 1e-9), 3),
        "baseline_rss_mib": round(monitor.baseline / MIB, 3),
        "peak_rss_mib": round(monitor.peak / MIB, 3),
        "peak_rss_delta_mib": round((monitor.peak - monitor.baseline) / MIB, 3),
        "device": str(device),
        "partition": "stratified_iid",
    }
    output = Path(args.worker_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(row, indent=2), encoding="utf-8")
    print(
        f"worker complete: train={len(y_train)}, seed={args.seed}, mode={args.mode}, "
        f"final={row['final_accuracy']}, wall={row['wall_sec']}s, peak={row['peak_rss_mib']} MiB"
    )
    return 0


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    preferred = [
        "dataset", "mode", "seed", "total_samples", "train_pool_size", "train_size",
        "test_size", "input_dim", "num_classes", "parameter_count", "clients", "rounds",
        "local_epochs", "batch_size", "lr", "clip_norm", "noise_multiplier",
        "initial_accuracy", "final_accuracy", "best_accuracy", "mean_round_loss",
        "clipped_client_updates", "dataset_load_sec", "preprocess_sec", "training_sec",
        "wall_sec", "sample_exposures", "training_samples_per_sec", "baseline_rss_mib",
        "peak_rss_mib", "peak_rss_delta_mib", "device", "partition", "round_accuracies",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=preferred)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["round_accuracies"] = json.dumps(row["round_accuracies"])
            writer.writerow(serialized)


def mean(values: list[float]) -> float:
    return float(np.mean(values))


def std(values: list[float]) -> float:
    return float(np.std(values))


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for train_size in sorted({int(row["train_size"]) for row in rows}):
        subset = [row for row in rows if int(row["train_size"]) == train_size]
        fl = [row for row in subset if row["mode"] == "fl"]
        clip = [row for row in subset if row["mode"] == "clip"]
        dp = [row for row in subset if row["mode"] == "dp"]
        fl_final = [float(row["final_accuracy"]) for row in fl]
        clip_final = [float(row["final_accuracy"]) for row in clip]
        dp_final = [float(row["final_accuracy"]) for row in dp]

        def optional_mean(mode_rows: list[dict[str, Any]], field: str) -> float:
            if not mode_rows:
                return float("nan")
            return mean([float(row[field]) for row in mode_rows])

        summaries.append(
            {
                "dataset": "covertype",
                "train_size": train_size,
                "test_size": int(subset[0]["test_size"]),
                "runs_per_mode": len(fl),
                "input_dim": int(subset[0]["input_dim"]),
                "num_classes": int(subset[0]["num_classes"]),
                "parameter_count": int(subset[0]["parameter_count"]),
                "fl_final_mean": round(mean(fl_final), 6),
                "fl_final_std": round(std(fl_final), 6),
                "clip_final_mean": round(mean(clip_final), 6) if clip_final else float("nan"),
                "clip_final_std": round(std(clip_final), 6) if clip_final else float("nan"),
                "dp_final_mean": round(mean(dp_final), 6),
                "dp_final_std": round(std(dp_final), 6),
                "accuracy_gap": round(mean(fl_final) - mean(dp_final), 6),
                "clip_fl_retention": round(mean(clip_final) / max(mean(fl_final), 1e-9), 6)
                if clip_final else float("nan"),
                "dp_fl_retention": round(mean(dp_final) / max(mean(fl_final), 1e-9), 6),
                "fl_training_sec_mean": round(mean([float(row["training_sec"]) for row in fl]), 3),
                "clip_training_sec_mean": round(optional_mean(clip, "training_sec"), 3),
                "dp_training_sec_mean": round(mean([float(row["training_sec"]) for row in dp]), 3),
                "fl_wall_sec_mean": round(mean([float(row["wall_sec"]) for row in fl]), 3),
                "clip_wall_sec_mean": round(optional_mean(clip, "wall_sec"), 3),
                "dp_wall_sec_mean": round(mean([float(row["wall_sec"]) for row in dp]), 3),
                "fl_peak_rss_mib_mean": round(mean([float(row["peak_rss_mib"]) for row in fl]), 3),
                "clip_peak_rss_mib_mean": round(optional_mean(clip, "peak_rss_mib"), 3),
                "dp_peak_rss_mib_mean": round(mean([float(row["peak_rss_mib"]) for row in dp]), 3),
                "fl_samples_per_sec_mean": round(mean([float(row["training_samples_per_sec"]) for row in fl]), 3),
                "clip_samples_per_sec_mean": round(optional_mean(clip, "training_samples_per_sec"), 3),
                "dp_samples_per_sec_mean": round(mean([float(row["training_samples_per_sec"]) for row in dp]), 3),
            }
        )
    return summaries


def write_summary_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_chart(rows: list[dict[str, Any]], path: Path) -> None:
    sizes = [int(row["train_size"]) for row in rows]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes[0, 0].errorbar(sizes, [row["fl_final_mean"] for row in rows],
                        yerr=[row["fl_final_std"] for row in rows], marker="o", capsize=4, label="FL")
    axes[0, 0].errorbar(sizes, [row["clip_final_mean"] for row in rows],
                        yerr=[row["clip_final_std"] for row in rows], marker="o", capsize=4, label="Clipping only")
    axes[0, 0].errorbar(sizes, [row["dp_final_mean"] for row in rows],
                        yerr=[row["dp_final_std"] for row in rows], marker="o", capsize=4, label="DP-update")
    axes[0, 0].set_ylabel("Final accuracy")
    axes[0, 0].set_title("Utility vs training-set size")
    axes[0, 0].legend()

    axes[0, 1].plot(sizes, [row["clip_fl_retention"] for row in rows], marker="o", label="Clipping / FL")
    axes[0, 1].plot(sizes, [row["dp_fl_retention"] for row in rows], marker="o", color="#7E57C2", label="DP / FL")
    axes[0, 1].axhline(0.9, color="#C62828", linestyle="--", label="90% threshold")
    axes[0, 1].set_ylabel("DP / FL final-accuracy retention")
    axes[0, 1].set_title("Utility retention")
    axes[0, 1].legend()

    axes[1, 0].plot(sizes, [row["fl_training_sec_mean"] for row in rows], marker="o", label="FL")
    axes[1, 0].plot(sizes, [row["clip_training_sec_mean"] for row in rows], marker="o", label="Clipping only")
    axes[1, 0].plot(sizes, [row["dp_training_sec_mean"] for row in rows], marker="o", label="DP-update")
    axes[1, 0].set_ylabel("Training seconds (mean)")
    axes[1, 0].set_title("Training cost")
    axes[1, 0].legend()

    axes[1, 1].plot(sizes, [row["fl_peak_rss_mib_mean"] for row in rows], marker="o", label="FL")
    axes[1, 1].plot(sizes, [row["clip_peak_rss_mib_mean"] for row in rows], marker="o", label="Clipping only")
    axes[1, 1].plot(sizes, [row["dp_peak_rss_mib_mean"] for row in rows], marker="o", label="DP-update")
    axes[1, 1].set_ylabel("Peak process RSS (MiB)")
    axes[1, 1].set_title("Memory cost")
    axes[1, 1].legend()

    for axis in axes.flat:
        axis.set_xscale("log")
        axis.set_xlabel("Training samples (log scale)")
        axis.grid(alpha=0.25)
    fig.suptitle("Forest CoverType large-dataset FL/DP scaling", fontsize=14)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(rows: list[dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    largest = rows[-1]
    smallest = rows[0]
    time_ratio = float(largest["fl_training_sec_mean"]) / max(float(smallest["fl_training_sec_mean"]), 1e-9)
    total_gap = float(largest["fl_final_mean"]) - float(largest["dp_final_mean"])
    clipping_gap = float(largest["fl_final_mean"]) - float(largest["clip_final_mean"])
    noise_gap = float(largest["clip_final_mean"]) - float(largest["dp_final_mean"])
    lines = [
        "# CoverType large-data scaling Forest CoverType 大型資料集 scaling 摘要",
        "",
        "## 資料與設定",
        "",
        "- Forest CoverType：581,012 筆、54 特徵、7 類別。",
        f"- 固定 20% test split；訓練子集大小：{', '.join(str(row['train_size']) for row in rows)}。",
        f"- Seeds：{args.seeds}；clients={args.clients}；rounds={args.rounds}；local epochs={args.local_epochs}。",
        f"- clip_norm={args.clip_norm}；noise_multiplier={args.noise_multiplier}。",
        "- 同一 train size/seed 的 FL、clipping-only 與 DP-update 共用 split、子集、client partition、初始化與 batch shuffle。",
        "- Client partition 為 stratified IID，用來隔離資料量效應；不是 non-IID robustness 測試。",
        "- Peak RSS 由獨立 worker process 以 20 ms polling 量測。",
        "",
        "## 結果",
        "",
        "| Train samples | FL final | Clip-only final | DP final | Clip/FL | DP/FL | FL/Clip/DP train sec | Peak RSS range |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['train_size']} | {row['fl_final_mean']:.6f}±{row['fl_final_std']:.6f} | "
            f"{row['clip_final_mean']:.6f}±{row['clip_final_std']:.6f} | "
            f"{row['dp_final_mean']:.6f}±{row['dp_final_std']:.6f} | "
            f"{row['clip_fl_retention']:.6f} | {row['dp_fl_retention']:.6f} | "
            f"{row['fl_training_sec_mean']:.1f}/{row['clip_training_sec_mean']:.1f}/{row['dp_training_sec_mean']:.1f} | "
            f"{min(row['fl_peak_rss_mib_mean'], row['clip_peak_rss_mib_mean'], row['dp_peak_rss_mib_mean']):.1f}--"
            f"{max(row['fl_peak_rss_mib_mean'], row['clip_peak_rss_mib_mean'], row['dp_peak_rss_mib_mean']):.1f} MiB |"
        )
    lines.extend(
        [
            "",
            "## 解讀",
            "",
            f"- 訓練樣本由 {smallest['train_size']} 增至 {largest['train_size']} 時，FL 平均訓練時間成長為 {time_ratio:.2f} 倍。",
            f"- 最大訓練分割的 FL/DP final accuracy 分別為 {largest['fl_final_mean']:.6f} / {largest['dp_final_mean']:.6f}，retention={largest['dp_fl_retention']:.6f}。",
            f"- 最大分割的 clipping-only final accuracy 為 {largest['clip_final_mean']:.6f}；這個 control 用來區分 clipping 與 noise 的效應。",
            f"- 最大分割的總 accuracy gap 為 {total_gap:.6f}：clipping-only gap={clipping_gap:.6f}，加入 noise 後的額外 gap={noise_gap:.6f}。這是 control-based 差距分解，不宣稱一般性的因果比例。",
            f"- 線性 7 類模型共有 {largest['parameter_count']} 個參數，因此 constraint-only VDP 的完整更新向量為 385 維；樣本數本身不會直接增加該 proof 的輸入維度。",
            "- 本結果補強樣本規模可行性，但仍不代表深度模型、大量 clients 或 non-IID federation 的可行性。",
            "- DP-update 的有限 epsilon 限制與 Gaussian privacy accounting 相同：public deterministic seed 現況仍為 epsilon infinity。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_parent(args: argparse.Namespace) -> int:
    results_dir = Path(args.results_dir)
    workers_dir = results_dir / "worker_rows"
    workers_dir.mkdir(parents=True, exist_ok=True)
    requested_sizes = [int(value) for value in args.train_sizes]
    rows: list[dict[str, Any]] = []
    for train_size in requested_sizes:
        for seed in args.seeds:
            for mode in args.modes:
                size_label = "full" if train_size <= 0 else str(train_size)
                worker_output = workers_dir / f"train_{size_label}_seed_{seed}_{mode}.json"
                if args.resume and worker_output.exists():
                    print(f"Reusing {worker_output.name}")
                else:
                    command = [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--worker-output", str(worker_output),
                        "--train-size", str(train_size),
                        "--seed", str(seed),
                        "--mode", mode,
                        "--rounds", str(args.rounds),
                        "--local-epochs", str(args.local_epochs),
                        "--batch-size", str(args.batch_size),
                        "--lr", str(args.lr),
                        "--clients", str(args.clients),
                        "--test-fraction", str(args.test_fraction),
                        "--clip-norm", str(args.clip_norm),
                        "--noise-multiplier", str(args.noise_multiplier),
                        "--torch-threads", str(args.torch_threads),
                    ]
                    if args.cpu:
                        command.append("--cpu")
                    print(f"Running train_size={size_label}, seed={seed}, mode={mode}", flush=True)
                    subprocess.run(command, check=True)
                rows.append(json.loads(worker_output.read_text(encoding="utf-8")))

    rows.sort(key=lambda row: (int(row["train_size"]), int(row["seed"]), str(row["mode"])))
    summaries = summarize(rows)
    write_csv(rows, results_dir / "covertype_scaling_runs.csv")
    write_summary_csv(summaries, results_dir / "covertype_scaling_summary.csv")
    write_chart(summaries, results_dir / "covertype_scaling.png")
    write_summary_md(summaries, results_dir / "summary.md", args)
    config = vars(args).copy()
    config.pop("worker", None)
    config.pop("worker_output", None)
    (results_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Results saved to {results_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scale paired FL/DP experiments on Forest CoverType")
    parser.add_argument("--train-sizes", nargs="+", default=["10000", "100000", "-1"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--modes", nargs="+", choices=["fl", "clip", "dp"], default=["fl", "dp"])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--torch-threads", type=int, default=0)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    parser.add_argument("--train-size", type=int, default=-1, help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=42, help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=["fl", "clip", "dp"], default="fl", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        if not args.worker_output:
            raise ValueError("--worker-output is required in worker mode")
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
