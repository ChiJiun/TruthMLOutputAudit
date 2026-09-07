"""production-oriented scaling: paired FL scaling and actual EZKL proof-dimension benchmarks."""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import platform
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import psutil
import torch
import torch.nn as nn
import torch.optim as optim
from scipy import stats
from torch.utils.data import DataLoader, TensorDataset


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from multiclass_vdp_zk.run_wine_vdp_zk_cost import run_ezkl_case
from covertype_large_dataset_scaling.run_covertype_scaling import (
    PeakRSSMonitor,
    clip_update,
    evaluate,
    set_seed,
    state_l2_norm,
    weighted_average,
)
from noniid_client_scaling.run_noniid_client_scaling import prepare_data


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
MIB = 1024 * 1024


class CoverTypeModel(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        if hidden_dim == 0:
            self.network = nn.Linear(54, 7)
        else:
            self.network = nn.Sequential(nn.Linear(54, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 7))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


PROFILES = [
    {"name": "linear_k10_r3", "hidden_dim": 0, "clients": 10, "rounds": 3},
    {"name": "linear_k25_r10", "hidden_dim": 0, "clients": 25, "rounds": 10},
    {"name": "linear_k50_r20", "hidden_dim": 0, "clients": 50, "rounds": 20},
    {"name": "mlp16_k25_r10", "hidden_dim": 16, "clients": 25, "rounds": 10},
]


def parameter_count(hidden_dim: int) -> int:
    return sum(parameter.numel() for parameter in CoverTypeModel(hidden_dim).parameters())


def train_local(
    global_model: nn.Module,
    dataset: TensorDataset,
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
) -> dict[str, torch.Tensor]:
    model = copy.deepcopy(global_model).cpu().train()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=generator, num_workers=0)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    for _ in range(epochs):
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def centered_binomial_noise(
    reference: dict[str, torch.Tensor], *, seed: int, k: int, unit: float
) -> dict[str, torch.Tensor]:
    rng = np.random.default_rng(seed)
    output: dict[str, torch.Tensor] = {}
    for key, value in reference.items():
        positive = rng.binomial(k, 0.5, size=tuple(value.shape))
        negative = rng.binomial(k, 0.5, size=tuple(value.shape))
        noise = (positive - negative).astype(np.float32) * unit
        output[key] = torch.from_numpy(noise).to(dtype=value.dtype)
    return output


def run_fl_mode(
    args: argparse.Namespace,
    profile: dict[str, Any],
    seed: int,
    mode: str,
) -> dict[str, Any]:
    prep_args = argparse.Namespace(
        seed=seed,
        train_size=args.train_size,
        test_fraction=args.test_fraction,
        clients=profile["clients"],
        partition=args.partition,
        min_client_size=args.min_client_size,
    )
    prep_start = time.perf_counter()
    client_datasets, test_x, test_y, metadata = prepare_data(prep_args)
    if args.test_size > 0 and len(test_y) > args.test_size:
        rng = np.random.default_rng(seed + 991)
        chosen = np.sort(rng.choice(len(test_y), size=args.test_size, replace=False))
        test_x = test_x[chosen]
        test_y = test_y[chosen]
    preprocess_sec = time.perf_counter() - prep_start

    set_seed(seed)
    model = CoverTypeModel(int(profile["hidden_dim"])).cpu()
    initial_accuracy = evaluate(model, test_x, test_y, torch.device("cpu"))
    accuracies = [initial_accuracy]
    clipped_updates = 0
    training_start = time.perf_counter()
    with PeakRSSMonitor() as monitor:
        for round_id in range(1, int(profile["rounds"]) + 1):
            global_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            updates: list[dict[str, torch.Tensor]] = []
            weights: list[int] = []
            for client_id, dataset in enumerate(client_datasets):
                update_seed = seed + round_id * 100_003 + client_id * 997
                local_state = train_local(
                    model,
                    dataset,
                    epochs=args.local_epochs,
                    batch_size=args.batch_size,
                    lr=args.lr,
                    seed=update_seed,
                )
                update = {key: local_state[key] - global_state[key] for key in global_state}
                if mode == "vdp_cbd":
                    if state_l2_norm(update) > args.clip_norm:
                        clipped_updates += 1
                    update = clip_update(update, args.clip_norm)
                    noise = centered_binomial_noise(
                        update,
                        seed=update_seed,
                        k=args.binomial_k,
                        unit=args.noise_unit,
                    )
                    update = {key: update[key] + noise[key] for key in update}
                updates.append(update)
                weights.append(len(dataset))
            averaged = weighted_average(updates, weights)
            model.load_state_dict({key: global_state[key] + averaged[key] for key in global_state})
            accuracies.append(evaluate(model, test_x, test_y, torch.device("cpu")))
    training_sec = time.perf_counter() - training_start
    return {
        "profile": profile["name"],
        "seed": seed,
        "mode": mode,
        "model": "linear" if profile["hidden_dim"] == 0 else f"mlp_{profile['hidden_dim']}",
        "parameter_count": parameter_count(int(profile["hidden_dim"])),
        "clients": int(profile["clients"]),
        "rounds": int(profile["rounds"]),
        "client_updates": int(profile["clients"] * profile["rounds"]),
        "train_size": int(metadata["train_size"]),
        "test_size": int(len(test_y)),
        "partition": args.partition,
        "label_tv_mean": metadata["label_tv_mean"],
        "initial_accuracy": round(initial_accuracy, 6),
        "final_accuracy": round(accuracies[-1], 6),
        "best_accuracy": round(max(accuracies), 6),
        "round_accuracies": [round(value, 6) for value in accuracies],
        "clipped_updates": clipped_updates,
        "preprocess_sec": round(preprocess_sec, 6),
        "training_sec": round(training_sec, 6),
        "peak_rss_mib": round(monitor.peak / MIB, 3),
    }


def make_constraint_artifact(model_name: str, vector_dim: int, seed: int) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    q_clipped = [0] * vector_dim
    for index, value in enumerate(rng.choice([-1, 1], size=4, replace=True)):
        q_clipped[index] = int(value)
    q_noise = rng.integers(-2, 3, size=vector_dim).astype(int).tolist()
    q_noisy = [left + right for left, right in zip(q_clipped, q_noise)]
    return {
        "meta": {
            "dataset": "covertype_synthetic_update",
            "task": "constraint-dimension benchmark",
            "client_id": 0,
            "case_name": f"{model_name}_seed_{seed}",
            "seed": seed,
            "scale": 1,
            "vector_dim": vector_dim,
            "input_dim": 54,
            "num_classes": 7,
            "clip_norm": 2.0,
            "noise_multiplier": 0.0,
            "noise_seed": seed,
            "slack_ppm": 0,
            "local_loss": 0.0,
        },
        "public_inputs": {"clip_rhs_bound_sq": 4, "slack_abs": 0, "scale": 1, "noise_seed": seed},
        "witness": {"q_clipped": q_clipped, "q_noise": q_noise, "q_noisy": q_noisy},
        "checks": {
            "clip_lhs_sum_sq": 4,
            "clip_bound_excess": 0,
            "relation_linf_gap": 0,
            "relation_sum_sq": 0,
            "clip_ok": True,
            "relation_ok": True,
        },
    }


def run_proof_benchmarks(seeds: list[int]) -> list[dict[str, Any]]:
    models = [("linear", 385), ("mlp_16", 999), ("mlp_32", 1991)]
    rows: list[dict[str, Any]] = []
    for model_name, dimension in models:
        for seed in seeds:
            print(f"actual EZKL proof model={model_name}, dim={dimension}, seed={seed}", flush=True)
            artifact = make_constraint_artifact(model_name, dimension, seed)
            with tempfile.TemporaryDirectory(prefix="truthml_ezkl_") as temporary:
                summary = run_ezkl_case(artifact, Path(temporary) / "case")
            rows.append({"backend": "ezkl_kzg", "model": model_name, "seed": seed, "actual_proof": True, **summary})
    return rows


def ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(stats.t.ppf(0.975, len(values) - 1) * np.std(values, ddof=1) / math.sqrt(len(values)))


def summarize_fl(rows: list[dict[str, Any]], proof_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proof_by_model: dict[str, list[dict[str, Any]]] = {}
    for row in proof_rows:
        proof_by_model.setdefault(str(row["model"]), []).append(row)
    output: list[dict[str, Any]] = []
    for profile, mode in sorted({(str(row["profile"]), str(row["mode"])) for row in rows}):
        group = [row for row in rows if row["profile"] == profile and row["mode"] == mode]
        first = group[0]
        model_key = str(first["model"])
        proof_group = proof_by_model[model_key]
        prove_mean = float(np.mean([float(row["prove_sec"]) for row in proof_group]))
        proof_size_mean = float(np.mean([float(row["proof_size_bytes"]) for row in proof_group]))
        updates = int(first["client_updates"])
        final_values = [float(row["final_accuracy"]) for row in group]
        training_values = [float(row["training_sec"]) for row in group]
        output.append({
            "profile": profile,
            "mode": mode,
            "model": model_key,
            "seeds": len(group),
            "parameter_count": int(first["parameter_count"]),
            "clients": int(first["clients"]),
            "rounds": int(first["rounds"]),
            "client_updates": updates,
            "final_accuracy_mean": round(float(np.mean(final_values)), 6),
            "final_accuracy_ci95": round(ci95(final_values), 6),
            "training_sec_mean": round(float(np.mean(training_values)), 6),
            "training_sec_ci95": round(ci95(training_values), 6),
            "single_actual_prove_sec_mean": round(prove_mean, 6),
            "estimated_serial_all_update_prove_hours": round(prove_mean * updates / 3600.0, 6),
            "estimated_all_update_proof_mib": round(proof_size_mean * updates / MIB, 6),
            "estimate_not_executed_end_to_end": True,
        })
    return output


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value)
            writer.writerow(serialized)


def write_summary(rows: list[dict[str, Any]], proof_rows: list[dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    lines = [
        "# production-oriented scaling Production-oriented Scaling Summary",
        "",
        f"- CoverType train/test={args.train_size}/{args.test_size}, non-IID {args.partition}, seeds={args.seeds}.",
        "- FL trajectories are actual CPU training. `vdp_cbd` uses clipping plus centered-binomial systems-stress noise.",
        "- EZKL rows are actual proofs of the full update-vector clipping/relation constraint dimensions.",
        "- Full local training is not inside EZKL; all-update proof totals below are explicit extrapolations, not executed end-to-end runs.",
        "",
        "| Profile | Mode | Params | K x R | Accuracy mean ± CI95 | Training sec mean ± CI95 | Estimated serial proof h | Estimated proofs MiB |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['profile']} | {row['mode']} | {row['parameter_count']} | {row['clients']} x {row['rounds']} | "
            f"{row['final_accuracy_mean']:.4f} ± {row['final_accuracy_ci95']:.4f} | "
            f"{row['training_sec_mean']:.2f} ± {row['training_sec_ci95']:.2f} | "
            f"{row['estimated_serial_all_update_prove_hours']:.3f} | {row['estimated_all_update_proof_mib']:.2f} |"
        )
    lines.extend([
        "",
        "## Actual EZKL single-proof measurements",
        "",
        "| Model | Dimension | Seeds | Prove sec mean ± CI95 | Verify sec mean ± CI95 | Proof bytes mean | Peak RSS MiB mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for model in ("linear", "mlp_16", "mlp_32"):
        group = [row for row in proof_rows if row["model"] == model]
        prove = [float(row["prove_sec"]) for row in group]
        verify = [float(row["verify_sec"]) for row in group]
        lines.append(
            f"| {model} | {group[0]['vector_dim']} | {len(group)} | {np.mean(prove):.3f} ± {ci95(prove):.3f} | "
            f"{np.mean(verify):.3f} ± {ci95(verify):.3f} | "
            f"{np.mean([float(row['proof_size_bytes']) for row in group]):.0f} | "
            f"{np.mean([float(row['pipeline_peak_rss_bytes']) for row in group]) / MIB:.1f} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62, 72, 82])
    parser.add_argument("--proof-seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--train-size", type=int, default=50_000)
    parser.add_argument("--test-size", type=int, default=20_000)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--partition", default="dirichlet_0.5")
    parser.add_argument("--min-client-size", type=int, default=32)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--binomial-k", type=int, default=16)
    parser.add_argument("--noise-unit", type=float, default=0.01)
    parser.add_argument("--torch-threads", type=int, default=4)
    args = parser.parse_args()
    torch.set_num_threads(args.torch_threads)

    proof_rows = run_proof_benchmarks(args.proof_seeds)
    fl_rows: list[dict[str, Any]] = []
    for profile in PROFILES:
        for seed in args.seeds:
            for mode in ("clean", "vdp_cbd"):
                print(f"FL profile={profile['name']}, seed={seed}, mode={mode}", flush=True)
                fl_rows.append(run_fl_mode(args, profile, seed, mode))
    summary = summarize_fl(fl_rows, proof_rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(proof_rows, RESULTS_DIR / "actual_ezkl_proof_scaling.csv")
    write_csv(fl_rows, RESULTS_DIR / "fl_trajectories.csv")
    write_csv(summary, RESULTS_DIR / "scaling_summary.csv")
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    (RESULTS_DIR / "hardware_manifest.json").write_text(json.dumps({
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ezkl": __import__("ezkl").__version__,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "memory_bytes": psutil.virtual_memory().total,
    }, indent=2), encoding="utf-8")
    write_summary(summary, proof_rows, RESULTS_DIR / "summary.md", args)
    print(f"completed {len(proof_rows)} actual proofs and {len(fl_rows)} FL trajectories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
